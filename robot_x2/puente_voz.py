#!/usr/bin/env python3
"""Puente de voz y caras del AgiBot X2 Ultra, para la recepción fija (el robot no se mueve).

Corre en la unidad de desarrollo del robot (PC2, 10.0.1.41), igual que puente_x2.py, pero no toca
nada del movimiento: no registra fuente de entrada, no publica velocidades ni navegación y no
importa esos mensajes. El robot queda en la postura que le dejó el operador con su control remoto.

Solo usa funciones de AimDK que ya trae el robot (manual de AimDK, 5.2 y ejemplos 6.1.20 a 6.1.26):
- `/aimdk_5Fmsgs/srv/PlayTts`: la voz del robot. Prioridad INTERACTION_L6, la de las respuestas
  al usuario: no tapa las alertas de seguridad del robot (caída, temperatura), que van más alto.
- `/aima/hal/audio/playback` (AudioPlayback) con `/aimdk_5Fmsgs/srv/RequestAudioFocus` y
  `AbandonAudioFocus`: reproduce en el parlante del robot un audio que manda el portátil (PCM
  16 kHz mono S16LE). Es el respaldo en español: el manual solo promete chino e inglés para PlayTts.
- `/aimdk_5Fmsgs/srv/PlayEmoji`: la expresión de la pantalla de la cara.
- `/aimdk_5Fmsgs/srv/SetVolume`: el volumen (0-100).

Protocolo: una línea JSON por orden sobre TCP (puerto 8766, solo en 127.0.0.1; desde el portátil se
llega con el túnel SSH de conectar_voz.ps1). Órdenes: estado, decir, audio, callar, cara, volumen.

    python3 puente_voz.py              # en el robot, con ROS 2 y AimDK
    python3 puente_voz.py --simulado   # en cualquier computador, sin robot
"""

import argparse
import base64
import json
import os
import signal
import socketserver
import threading
import time

PUERTO = 8766
DOMINIO = "anfitrion_recepcion"   # quién llama a PlayTts (lo pide AimDK)
PRIORIDAD_TTS = 6                 # INTERACTION_L6: por debajo de las alertas del robot (7, 8, 10)
PRIORIDAD_AUDIO = 6               # foco de audio (1-10): igual que la voz de interacción
PRIORIDAD_CARA = 10
MUESTREO = 16000                  # Hz, mono, S16LE: lo que piden los ejemplos de audio
TROZO_S = 0.1                     # s de audio por mensaje; se publican a ritmo real
MAX_AUDIO_S = 30                  # s: un audio más largo se rechaza
MAX_TEXTO = 300                   # caracteres por frase

# Expresiones de la cara que usa la recepción (ids del ejemplo 6.1.26 de AimDK).
CARAS = {"parpadeo": 1, "aburrido": 60, "error": 70, "dormido": 80, "feliz": 90, "enojado": 190,
         "encantado": 200}
MODO_UNA_VEZ, MODO_REPETIR = 1, 2


def _esperar(futuro, segundos=0.25):
    limite = time.time() + segundos
    while not futuro.done() and time.time() < limite:
        time.sleep(0.01)
    return futuro.done()


class VozAimdk:
    """La voz, el parlante y la cara del X2 real (un solo nodo de ROS, como pide el manual)."""

    def __init__(self):
        import rclpy
        from rclpy.executors import MultiThreadedExecutor
        from rclpy.node import Node
        from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
        import aimdk_msgs.msg as am
        import aimdk_msgs.srv as asrv

        faltan = [n for n in ("PlayTts", "PlayEmoji", "RequestAudioFocus", "AbandonAudioFocus",
                              "SetVolume") if not hasattr(asrv, n)]
        faltan += [n for n in ("AudioPlayback", "AudioInfo", "AudioData", "FocusRequester",
                               "FocusResponse", "TtsPriorityLevel") if not hasattr(am, n)]
        if faltan:
            raise SystemExit("Faltan mensajes de AimDK: " + ", ".join(faltan))
        self._rclpy, self._am, self._srv = rclpy, am, asrv
        rclpy.init()
        self.nodo = Node("anfitrion_puente_voz")
        self._tts = self.nodo.create_client(asrv.PlayTts, "/aimdk_5Fmsgs/srv/PlayTts")
        self._emoji = self.nodo.create_client(asrv.PlayEmoji, "/aimdk_5Fmsgs/srv/PlayEmoji")
        self._foco = self.nodo.create_client(asrv.RequestAudioFocus, "/aimdk_5Fmsgs/srv/RequestAudioFocus")
        self._soltar = self.nodo.create_client(asrv.AbandonAudioFocus, "/aimdk_5Fmsgs/srv/AbandonAudioFocus")
        self._volumen = self.nodo.create_client(asrv.SetVolume, "/aimdk_5Fmsgs/srv/SetVolume")
        self._pub_audio = self.nodo.create_publisher(am.AudioPlayback, "/aima/hal/audio/playback", 10)
        self.nodo.create_subscription(
            am.FocusResponse, "/aima/hal/audio/focus_response", self._al_foco,
            QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                       history=HistoryPolicy.KEEP_LAST, durability=DurabilityPolicy.VOLATILE))
        self.paquete = f"anfitrion_voz{os.getpid()}"
        self._con_foco = False
        self._ejecutor = MultiThreadedExecutor()
        self._ejecutor.add_node(self.nodo)
        threading.Thread(target=self._ejecutor.spin, daemon=True).start()

    def log(self, texto):
        self.nodo.get_logger().info(texto)

    def _llamar(self, cliente, req, cabecera="header"):
        """Como los ejemplos de AimDK: hasta 8 intentos de 0,25 s (los servicios entre equipos de
        ROS a veces no responden al primero)."""
        if not cliente.wait_for_service(timeout_sec=2.0):
            raise RuntimeError(f"no aparece el servicio {cliente.srv_name}")
        futuro = None
        for _ in range(8):
            cab = getattr(req, cabecera, None)
            if cab is not None and hasattr(cab, "header"):
                cab.header.stamp = self.nodo.get_clock().now().to_msg()
            futuro = cliente.call_async(req)
            if _esperar(futuro):
                break
        if futuro is None or not futuro.done() or futuro.result() is None:
            raise RuntimeError(f"{cliente.srv_name} no respondió")
        return futuro.result()

    # --- voz del robot (PlayTts) ---------------------------------------------------------------
    def decir(self, texto, interrumpir=True):
        req = self._srv.PlayTts.Request()
        req.tts_req.text = texto
        req.tts_req.domain = DOMINIO
        req.tts_req.trace_id = f"r{int(time.time() * 1000)}"
        req.tts_req.is_interrupted = bool(interrumpir)
        req.tts_req.priority_weight = 0
        req.tts_req.priority_level.value = PRIORIDAD_TTS
        r = self._llamar(self._tts, req).tts_resp
        if not getattr(r, "is_success", False):
            # error_code llegó en la v1.1.0 de AimDK; el firmware anterior puede no traerlo.
            raise RuntimeError(f"PlayTts falló (código {getattr(r, 'error_code', '?')}: "
                               f"{getattr(r, 'error_message', 'sin detalle')})")

    # --- audio del portátil por el parlante (foco + AudioPlayback) ----------------------------
    def _al_foco(self, msg):
        if msg.pkg_name == self.paquete and not msg.focus_gain:
            self._con_foco = False       # otro programa (de más prioridad) tomó el parlante

    def _pedir_foco(self, soltar=False):
        tipo = self._srv.AbandonAudioFocus if soltar else self._srv.RequestAudioFocus
        req = tipo.Request()
        quien = self._am.FocusRequester()
        quien.pkg_name, quien.priority = self.paquete, PRIORIDAD_AUDIO
        req.focus_requester = quien
        r = self._llamar(self._soltar if soltar else self._foco, req, cabecera="request")
        estado = getattr(r, "reponse", None) or getattr(r, "response", None)   # "reponse" es del SDK
        ok = estado is not None and estado.status.value == 1
        self._con_foco = (not soltar) and ok and bool(r.focus_response.focus_gain)
        return self._con_foco

    def publicar_audio(self, trozo, turno):
        msg = self._am.AudioPlayback()
        msg.pkg_name = self.paquete
        msg.token_id = f"{self.paquete}_{turno}"   # token nuevo = se descarta lo que sonaba antes
        info = self._am.AudioInfo()
        info.channels, info.sample_rate = 1, MUESTREO
        datos = self._am.AudioData()
        datos.data = list(trozo)
        msg.info, msg.data = info, datos
        self._pub_audio.publish(msg)

    def tomar_parlante(self):
        return self._con_foco or self._pedir_foco()

    def soltar_parlante(self):
        if self._con_foco:
            try:
                self._pedir_foco(soltar=True)
            except RuntimeError as e:
                self.log(f"No se pudo soltar el parlante: {e}")
        self._con_foco = False

    def tiene_parlante(self):
        return self._con_foco

    # --- cara y volumen ------------------------------------------------------------------------
    def cara(self, emocion_id, modo):
        req = self._srv.PlayEmoji.Request()
        req.emotion_id, req.mode, req.priority = int(emocion_id), int(modo), PRIORIDAD_CARA
        if not getattr(self._llamar(self._emoji, req), "success", True):
            raise RuntimeError("PlayEmoji no pudo mostrar la expresión")

    def volumen(self, valor):
        req = self._srv.SetVolume.Request()
        req.audio_volume = int(valor)
        return int(self._llamar(self._volumen, req, cabecera="request").audio_volume)

    def cerrar(self):
        self.soltar_parlante()
        self._ejecutor.shutdown()
        self.nodo.destroy_node()
        if self._rclpy.ok():
            self._rclpy.shutdown()


class VozSimulada:
    """Sin robot: anota lo que haría el X2 (para probar el portátil sin el robot)."""

    def __init__(self):
        self._con_foco = False
        self.dicho, self.caras, self.audio_bytes = [], [], 0

    def log(self, texto):
        print(f"[voz simulada] {texto}", flush=True)

    def decir(self, texto, interrumpir=True):
        self.dicho.append(texto)
        self.log(f"PlayTts: {texto}")

    def tomar_parlante(self):
        self._con_foco = True
        return True

    def soltar_parlante(self):
        self._con_foco = False

    def tiene_parlante(self):
        return self._con_foco

    def publicar_audio(self, trozo, turno):
        self.audio_bytes += len(trozo)

    def cara(self, emocion_id, modo):
        self.caras.append(emocion_id)
        self.log(f"PlayEmoji: {emocion_id} (modo {modo})")

    def volumen(self, valor):
        self.log(f"SetVolume: {valor}")
        return int(valor)

    def cerrar(self):
        pass


class Parlante:
    """Reproduce en un hilo el audio que manda el portátil, a ritmo real, y suelta el parlante al
    terminar. Un audio nuevo o `callar` cortan el anterior."""

    def __init__(self, voz):
        self.voz = voz
        self._turno = 0
        self._lock = threading.Lock()
        self.sonando = False

    def reproducir(self, pcm):
        with self._lock:
            self._turno += 1
            turno = self._turno
        if not self.voz.tomar_parlante():
            raise RuntimeError("el robot no dio el parlante (otro audio con más prioridad)")
        threading.Thread(target=self._sonar, args=(pcm, turno), daemon=True).start()
        return len(pcm) / (2 * MUESTREO)

    def _sonar(self, pcm, turno):
        self.sonando = True
        paso = int(TROZO_S * MUESTREO) * 2
        inicio = time.monotonic()
        try:
            for k, i in enumerate(range(0, len(pcm), paso)):
                if turno != self._turno or not self.voz.tiene_parlante():
                    return
                self.voz.publicar_audio(pcm[i:i + paso], turno)
                # Ritmo real con un poco de adelanto, para que el robot no se quede sin datos.
                espera = inicio + (k + 1) * TROZO_S - 0.15 - time.monotonic()
                if espera > 0:
                    time.sleep(espera)
            time.sleep(0.3)
        finally:
            if turno == self._turno:
                self.sonando = False
                self.voz.soltar_parlante()

    def callar(self):
        with self._lock:
            self._turno += 1
        self.voz.soltar_parlante()
        self.sonando = False


# --- órdenes --------------------------------------------------------------------------------------
def _texto(orden):
    texto = str(orden["texto"]).strip()
    if not texto:
        raise ValueError("texto vacío")
    if len(texto) > MAX_TEXTO:
        raise ValueError(f"texto de más de {MAX_TEXTO} caracteres")
    return texto


def o_estado(s, orden):
    return {"robot": "simulado" if s.simulado else "X2", "sonando": s.parlante.sonando,
            "caras": sorted(CARAS)}


def o_decir(s, orden):
    s.parlante.callar()
    s.voz.decir(_texto(orden), orden.get("interrumpir", True))
    return {}


def o_audio(s, orden):
    if int(orden.get("muestreo", MUESTREO)) != MUESTREO or int(orden.get("canales", 1)) != 1:
        raise ValueError(f"el audio tiene que ser PCM {MUESTREO} Hz mono S16LE")
    pcm = base64.b64decode(orden["pcm"], validate=True)
    if len(pcm) % 2 or not pcm:
        raise ValueError("audio PCM vacío o mal formado")
    if len(pcm) > MAX_AUDIO_S * MUESTREO * 2:
        raise ValueError(f"audio de más de {MAX_AUDIO_S} s")
    return {"segundos": round(s.parlante.reproducir(pcm), 2)}


def o_callar(s, orden):
    s.parlante.callar()
    return {}


def o_cara(s, orden):
    emocion = orden["emocion"]
    if emocion not in CARAS:
        raise ValueError(f"expresión desconocida: {emocion} (hay: {', '.join(sorted(CARAS))})")
    s.voz.cara(CARAS[emocion], MODO_REPETIR if orden.get("repetir") else MODO_UNA_VEZ)
    return {}


def o_volumen(s, orden):
    valor = int(orden["valor"])
    if not 10 <= valor <= 100:
        raise ValueError("volumen entre 10 y 100")
    return {"volumen": s.voz.volumen(valor)}


ORDENES = {"estado": o_estado, "decir": o_decir, "audio": o_audio, "callar": o_callar,
           "cara": o_cara, "volumen": o_volumen}


class Manejador(socketserver.StreamRequestHandler):
    def handle(self):
        s = self.server
        s.voz.log(f"Conectado: {self.client_address[0]}")
        try:
            for linea in self.rfile:
                linea = linea.strip()
                if not linea:
                    continue
                orden = None
                try:
                    orden = json.loads(linea)
                    if orden.get("orden") not in ORDENES:
                        raise ValueError(f"orden desconocida: {orden.get('orden')}")
                    respuesta = {"ok": True, **(ORDENES[orden["orden"]](s, orden) or {})}
                except KeyError as e:
                    respuesta = {"ok": False, "error": f"falta {e}"}
                except (ValueError, TypeError, RuntimeError) as e:
                    respuesta = {"ok": False, "error": str(e)}
                except Exception as e:  # noqa: BLE001  un campo distinto en otro firmware: no se corta la conexión
                    respuesta = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
                if isinstance(orden, dict) and "id" in orden:
                    respuesta["id"] = orden["id"]
                self.wfile.write((json.dumps(respuesta, ensure_ascii=False) + "\n").encode("utf-8"))
        except (ConnectionError, OSError):
            pass
        finally:
            s.parlante.callar()
            s.voz.log(f"Desconectado: {self.client_address[0]}")


class Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--host", default="127.0.0.1", help="127.0.0.1 = solo por túnel SSH (recomendado)")
    p.add_argument("--puerto", type=int, default=PUERTO)
    p.add_argument("--simulado", action="store_true", help="sin robot, para probar")
    args = p.parse_args()

    voz = VozSimulada() if args.simulado else VozAimdk()
    servidor = Servidor((args.host, args.puerto), Manejador)
    servidor.voz, servidor.parlante, servidor.simulado = voz, Parlante(voz), args.simulado
    voz.log(f"Puente de voz del X2 escuchando en {args.host}:{args.puerto} (sin movimiento)")

    def _cerrar_por_senal(_num, _marco):
        raise KeyboardInterrupt
    for nombre in ("SIGHUP", "SIGTERM"):
        if hasattr(signal, nombre):
            signal.signal(getattr(signal, nombre), _cerrar_por_senal)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
        servidor.parlante.callar()
        voz.cerrar()


if __name__ == "__main__":
    main()
