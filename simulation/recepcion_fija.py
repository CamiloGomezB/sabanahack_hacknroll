"""Recepción fija con el X2: el robot no se mueve. Mira, reconoce y habla.

La cámara del portátil hace de cámara del X2 (reconocimiento facial real, SFace). Cuando alguien se
pone frente a ella:

- si es miembro o personal y su cara está registrada, el X2 lo saluda por su nombre, le da la
  bienvenida y le cuenta lo suyo del día (su reserva, su primera tarea);
- si no lo reconoce, le pide el QR y lo lee con la misma cámara; con un pase de invitado o de
  externo avisa a su anfitrión o responsable (la app móvil) y espera su respuesta;
- si no puede dejarlo seguir (QR vencido, membresía vencida, fuera de horario, cara dudosa), lo
  explica y lo manda al mostrador de recepción.

Nunca promete moverse ni acompañar: quien acompaña es recepción.

Con --ollama, Ollama (en el portátil) reescribe con un tono más cálido solo la bienvenida y la
respuesta del anfitrión. Los datos (nombre, hora y lugar de la reserva, tarea, punto de encuentro,
empresa, anfitrión) tienen que quedar idénticos o se usa el texto fijo. Los mensajes de QR y de
recepción no se reescriben: tienen que ser claros.

    python recepcion_fija.py                     # decide la copia local; voz por el portátil
    python recepcion_fija.py --supabase          # decide la base real (eventos, avisos a la app)
    python recepcion_fija.py --supabase --voz audio   # voz por el parlante del X2 (conectar_voz.ps1)
    python recepcion_fija.py --supabase --voz audio --ollama   # tono más cálido (qwen2.5:3b)

Teclas en la ventana de la cámara: Q no tengo QR · N el anfitrión no responde (solo sin --supabase)
· R volver a saludar a la misma persona · Esc salir.
"""

import argparse
import sys
import time
import unicodedata
from datetime import datetime

import agente as voz
import datos_falsos
import flujos
from base_real import BaseReal, ErrorBase
from camaras import QR_DEMO, CamaraWebcam
from caras import MODELO
from club import ESPACIOS_APP, ZONAS, nombre_destino
from dataset import distancia
from recepcion import CATEGORIAS, MOTIVOS, contexto_llegada, reconocer, registrar_llegada
from voz_x2 import LETRAS_POR_SEGUNDO, PUERTO_VOZ, ErrorVoz, Voz

BUSCAR_CARA = 2.5     # s para conseguir una foto en la que la cara se reconozca
ESPERA_QR = 12.0      # s por intento de lectura del QR (son dos intentos)
ESPERA_AVISO = 60.0   # s que se espera la respuesta del anfitrión en la app (con --supabase)
ESPERA_AVISO_SIM = 4.0  # sin --supabase la app es simulada: acepta sola a los 4 s (N: no responde)
MISMA_PERSONA = 0.60  # distancia de huella: por debajo es la misma persona que se acaba de atender
SIN_CARA = 2.0        # s sin ver una cara para dar por terminada la atención
NUEVO_SALUDO = 30.0   # s después de los cuales se vuelve a saludar aunque sea la misma persona
ESPERA_OLLAMA = 3.5   # s: qwen2.5:3b tarda ~2,5 s; después hay que generar el audio
CALENTAR_OLLAMA = 40.0  # s que se espera al arrancar a que el modelo suba a la GPU

MOSTRADOR = "Acércate al mostrador de recepción, por favor; allí te ayudan."
PEDIR_QR = ("No encuentro tu registro. Si traes invitación, pase u orden de trabajo, "
            "muéstrame el código QR frente a la cámara, por favor.")
SIN_QR = "No pude leer ningún código. " + MOSTRADOR
LEYENDO = "Un momento, estoy verificando tu código."
CARAS = dict(espera="parpadeo", atento="parpadeo", bienvenida="feliz", vip="encantado",
             problema="aburrido")


def _saludo(ahora: datetime) -> str:
    return ("Buenos días" if ahora.hour < 12 else "Buenas tardes" if ahora.hour < 19
            else "Buenas noches")


def _lugar(clave: str | None) -> str | None:
    if not clave:
        return None
    if clave in ESPACIOS_APP or clave in ZONAS:
        return nombre_destino(clave)
    return clave.replace("_", " ")


def _hora(h) -> str:
    return h.strftime("%H:%M") if h else ""


def _sin_tildes(texto: str) -> str:
    """cv2.putText no dibuja tildes."""
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c)).encode("ascii", "ignore").decode()


def _con_datos(texto: str, trato, datos: list) -> tuple[str, list[str]]:
    """El texto (de tú o de usted) y los datos que Ollama no puede cambiar ni quitar."""
    texto = voz.ajustar(texto, trato)
    return texto, [d for d in dict.fromkeys(datos) if d and d in texto]


def bienvenida(r, ctx: dict, ahora: datetime) -> tuple[str, list[str]]:
    """Lo que dice el X2 a quien puede seguir, y sus datos. Sin promesas de moverse: está fijo."""
    trato = voz.leer_trato(ctx.get("trato"))
    nombre = trato.nombre or r.nombre
    texto = f"¡{_saludo(ahora)}, {nombre}! Te damos la bienvenida a N Club."
    datos = [nombre]
    if r.categoria in ("vip", "regular"):
        reserva = next(iter(ctx.get("reservas") or []), None)
        if reserva:
            lugar = reserva.get("nombre") or _lugar(reserva.get("espacio"))
            texto += f" Tu reserva en {lugar} es a las {_hora(reserva['inicio'])}."
            datos += [lugar, _hora(reserva["inicio"])]
        elif r.categoria == "vip":
            texto += " Qué gusto tenerte de vuelta."
        if r.requiere_tour:
            texto += " Es tu primera visita: en recepción te muestran el club."
    elif r.categoria == "personal":
        tarea = next(iter(ctx.get("tareas") or []), None)
        if tarea:
            texto += (f" Tu primera tarea es {tarea['titulo']}"
                      + (f", a las {_hora(tarea['hora'])}" if tarea.get("hora") else "") + ".")
            datos += [tarea["titulo"], _hora(tarea.get("hora"))]
        novedad = next(iter(ctx.get("novedades") or []), None)
        if novedad and not trato.breve:
            texto += f" Novedad: {novedad['titulo']}."
            datos.append(novedad["titulo"])
    elif r.categoria in ("invitado", "externo"):
        visita = ctx.get("visita") or {}
        lugar = _lugar(visita.get("punto_encuentro") or r.destino)
        quien = visita.get("responsable") or r.responsable
        if r.categoria == "externo":
            motivo = visita.get("motivo") or "tu orden de trabajo"
            texto += f" Vienes de {r.empresa or 'tu empresa'} para: {motivo}."
            datos += [r.empresa, motivo]
        if quien:
            texto += f" Ya le avisé a {quien} que llegaste."
        if lugar:
            texto += f" Punto de encuentro: {lugar}."
        datos += [quien, lugar]
    return _con_datos(texto, trato, datos)


def respuesta_aviso(r, estado: str | None, ctx: dict) -> tuple[str, list[str]]:
    """Lo que dice el X2 cuando el anfitrión (o el responsable) responde, o no responde."""
    quien = (ctx.get("visita") or {}).get("responsable") or r.responsable or "tu anfitrión"
    if estado == "aceptado":
        if r.categoria == "externo":
            texto = f"{quien} confirmó tu ingreso. Recepción te acompaña hasta el área de trabajo."
        else:
            texto = f"{quien} confirmó que ya viene por ti. Puedes esperar aquí, en el lobby."
    elif estado == "sin_respuesta":
        texto = f"{quien} todavía no responde. " + MOSTRADOR
    else:
        texto = "Recepción ya sabe que llegaste. Puedes esperar aquí, en el lobby."
    return _con_datos(texto, voz.leer_trato(ctx.get("trato")), [quien, "Recepción", "lobby"])


def no_sigue(r) -> str:
    """Lo que dice el X2 a quien no puede seguir solo. Explica sin acusar y manda a recepción."""
    if r.resultado == "pendiente_revision":
        if r.motivo in voz.PROBLEMA_QR:
            return f"{voz.PROBLEMA_QR[r.motivo]} {MOSTRADOR}"
        return "Necesito que recepción confirme tu identidad. " + MOSTRADOR
    if r.motivo in voz.PROBLEMA_QR:
        return f"{voz.PROBLEMA_QR[r.motivo]} {MOSTRADOR}"
    if r.motivo == "fuera_de_horario":
        return f"Tu horario es {r.horario}; ahora no puedo registrar tu ingreso. {MOSTRADOR}"
    if r.motivo == "acreditacion_vencida":
        vence = f" el {r.vinculo_hasta:%d/%m}" if r.vinculo_hasta else ""
        return f"Te reconozco, pero tu membresía venció{vence}. En recepción te ayudan a renovarla."
    if r.motivo == "no_identificado":
        return "No pude identificarte; eso no significa que no seas miembro. " + MOSTRADOR
    return f"No puedo registrar tu ingreso: {MOTIVOS.get(r.motivo, r.motivo)}. {MOSTRADOR}"


class RecepcionFija:
    def __init__(self, camara: CamaraWebcam, voz_x2: Voz, base: BaseReal | None,
                 agente: voz.Agente | None = None):
        self.cam, self.voz, self.base = camara, voz_x2, base
        self.agente = agente or voz.Agente()
        ahora = datetime.now()
        # Copia local: las personas reales del equipo, como en Supabase. Con --supabase sirve solo
        # para la vista en vivo y para elegir la mejor foto; decide la base.
        self.datos = dict(personas={}, visitas={}, credenciales=[], fotografias=[], eventos=[])
        self.registradas = datos_falsos.agregar_caras_reales(self.datos, ahora)
        datos_falsos.agregar_qr_reales(self.datos, ahora)
        datos_falsos.agenda(self.datos, ahora)
        camara.identificar = self._quien
        self.salir = False
        self.sin_respuesta = False        # tecla N
        self.ultima = None                # (huella, hora) de la última persona atendida
        self.cara_vista = time.monotonic()

    # --- registro en consola y en la ventana --------------------------------------------------
    def nota(self, texto: str) -> None:
        print(f"[{datetime.now():%H:%M:%S}] {texto}", flush=True)

    def mostrar(self, texto: str) -> None:
        self.cam.mensaje = _sin_tildes(texto)

    def decir(self, texto: str, cara: str | None = None) -> None:
        """El X2 dice la frase (y cambia la cara) y espera a que termine, sin congelar la cámara."""
        if cara:
            self.voz.cara(CARAS[cara])
        self.nota(f"X2: {texto}")
        try:
            dura = self.voz.decir(texto)
        except ErrorVoz as e:
            self.nota(f"(sin voz: {e})")
            dura = len(texto) / LETRAS_POR_SEGUNDO
        self.mirar(dura + 0.3)

    def pedir_redaccion(self, r, texto: str, datos: list[str], ctx: dict, animo):
        """Pide a Ollama (en otro hilo) la versión cálida. Devuelve (plan, pedido o None)."""
        trato = voz.leer_trato(ctx.get("trato"))
        plan = voz.Plan(texto, None, None, trato=trato, llamar=trato.nombre or r.nombre,
                        oferta=flujos.Oferta(claves=datos))
        return plan, self.agente.redactar(plan, r, animo, con_decision=False)

    def decir_redactado(self, r, plan, pedido, cara: str, espera: float = ESPERA_OLLAMA) -> None:
        """Espera la versión de Ollama sin congelar la cámara. Solo se usa si conserva todos los
        datos (aceptar revisa los nombres y las claves); si no llega o no sirve, el texto fijo."""
        if pedido is not None:
            self.mirar(espera, pedido.done)
            if pedido.done() and pedido.exception() is None:
                plan = self.agente.aceptar(plan, pedido.result(), r)
            else:
                pedido.cancel()
            self.nota(f"(texto: {plan.fuente})")
        self.decir(plan.texto, cara)

    # --- cámara -------------------------------------------------------------------------------
    def tecla(self, k: int) -> None:
        if k == 27:
            self.salir = True
        elif k in (ord("q"), ord("Q")) and self.cam.buscar_qr:
            self.cam.buscar_qr = False         # no tiene QR: termina el intento
        elif k in (ord("n"), ord("N")):
            self.sin_respuesta = True
        elif k in (ord("r"), ord("R")):
            self.ultima = None

    def mirar(self, segundos: float, hasta=lambda: False) -> bool:
        """Sigue mostrando la cámara `segundos` o hasta que se cumpla la condición."""
        fin = time.monotonic() + segundos
        while time.monotonic() < fin and not self.salir:
            self.tecla(self.cam.actualizar())
            if hasta():
                return True
        return False

    def _quien(self, captura) -> tuple[str, bool]:
        """Vista en vivo: a quién se parece la cara. No registra ninguna llegada."""
        rec = reconocer(self.datos, captura.embedding, True, "real", MODELO)
        if rec["candidato"] is None:
            return "Desconocido", False
        p = self.datos["personas"][rec["candidato"]]
        texto = f"{p['nombre_demo']} - {p['vinculo']} ({rec['distancia']:.2f})"
        if rec["cara"] != "reconocida":
            texto = "Dudoso: " + texto
        return _sin_tildes(texto), rec["cara"] == "reconocida"

    def _es_la_misma(self, captura) -> bool:
        if self.ultima is None or captura.embedding is None:
            return False
        huella, cuando = self.ultima
        return (time.monotonic() - cuando < NUEVO_SALUDO
                and distancia(huella, captura.embedding) < MISMA_PERSONA)

    def esperar_persona(self):
        """Espera a que alguien nuevo se ponga frente a la cámara (o muestre un QR directamente).
        Devuelve la captura (o None si solo mostró el QR)."""
        self.voz.cara(CARAS["espera"], repetir=True)
        self.mostrar("Esperando visitantes... (Esc: salir)")
        self.cam.qr, self.cam.pase, self.cam.buscar_qr = None, None, True
        while not self.salir:
            self.tecla(self.cam.actualizar())
            if self.cam.qr:
                return None
            if self.cam.n % CamaraWebcam.CADA:
                continue
            c = self.cam()
            if not c.valida:
                if time.monotonic() - self.cara_vista > SIN_CARA:
                    self.ultima = None          # se fue: la próxima cara es otra atención
                continue
            self.cara_vista = time.monotonic()
            if not self._es_la_misma(c):
                return c
        return None

    def mejor_foto(self, primera):
        """Unos instantes más para tener una foto en la que la cara se reconozca."""
        mejor, fin = primera, time.monotonic() + BUSCAR_CARA
        while time.monotonic() < fin and not self.salir and not self.cam.qr:
            if reconocer(self.datos, mejor.embedding, True, "real", MODELO)["cara"] == "reconocida":
                return mejor, True
            self.tecla(self.cam.actualizar())
            c = self.cam()
            if c.valida:
                mejor = c
        return mejor, reconocer(self.datos, mejor.embedding, True, "real", MODELO)["cara"] == "reconocida"

    def pedir_qr(self) -> str | None:
        """Pide el QR y lo lee con la misma cámara; dos intentos. None si no tiene o no se lee."""
        for texto in (PEDIR_QR, voz.REINTENTO_QR):
            self.cam.qr, self.cam.pase, self.cam.buscar_qr = None, None, True
            self.decir(texto, "atento")
            self.mostrar("Muestra tu QR a la camara (Q: no tengo QR)")
            self.mirar(ESPERA_QR, lambda: self.cam.qr or not self.cam.buscar_qr)
            qr, sin_qr = self.cam.qr, not self.cam.buscar_qr and not self.cam.qr
            self.cam.buscar_qr = False
            if qr or sin_qr or self.salir:
                return qr
        return None

    # --- decisión -----------------------------------------------------------------------------
    def registrar(self, captura, token: str | None):
        embedding = captura.embedding if captura else None
        valida = captura.valida if captura else True
        if self.base is not None:
            try:
                r = self.base.registrar_llegada(self.datos, embedding, token, valida, "real", MODELO)
                self.nota(f"Supabase: registrar_llegada → {r.resultado} (evento {r.evento_id[:8]})")
                return r
            except ErrorBase as e:
                # Como el robot: sin la base no decide; queda para recepción.
                self.nota(f"Supabase no responde: {e}")
                return registrar_llegada(self.datos, embedding, token, datetime.now(), valida,
                                         servicio=False, modo="real", modelo=MODELO)
        return registrar_llegada(self.datos, embedding, token, datetime.now(), valida,
                                 modo="real", modelo=MODELO)

    def contexto(self, r) -> dict:
        ctx = contexto_llegada(self.datos, r.persona_id, r.visita_id, datetime.now())
        if self.base is not None and getattr(r, "evento_id", None):
            try:
                ctx.update(self.base.contexto_llegada(r.persona_id, r.visita_id))
            except ErrorBase as e:
                self.nota(f"contexto_llegada sin respuesta: {e}")
        return ctx

    def esperar_aviso(self, r) -> str | None:
        """El aviso a la app del anfitrión lo creó registrar_llegada. Se espera su respuesta."""
        if self.base is None:
            aviso = next((a for a in reversed(self.datos.get("avisos", []))
                          if a["visita_id"] == r.visita_id), None)
            if aviso is None:
                return None
            self.sin_respuesta = False
            self.mostrar(f"[SIMULADO] app de {r.responsable}: aviso enviado (N: no responde)")
            self.mirar(ESPERA_AVISO_SIM, lambda: self.sin_respuesta)
            aviso["estado"] = "sin_respuesta" if self.sin_respuesta else "aceptado"
            return aviso["estado"]
        try:
            aviso = self.base.aviso_de(r.visita_id)
        except ErrorBase as e:
            self.nota(f"no se pudo leer el aviso: {e}")
            return None
        if aviso is None:
            return None
        inicio = time.monotonic()
        while aviso["estado"] not in ("aceptado", "sin_respuesta") and not self.salir:
            self.mostrar(f"App de {r.responsable}: {aviso['estado'].replace('_', ' ')} "
                         f"({int(ESPERA_AVISO - (time.monotonic() - inicio))} s)")
            if time.monotonic() - inicio >= ESPERA_AVISO:
                try:
                    self.base.aviso_sin_respuesta(aviso["id"])   # recepción lo ve en el panel web
                except ErrorBase as e:
                    self.nota(f"no se pudo marcar el aviso: {e}")
                aviso["estado"] = "sin_respuesta"
                break
            self.mirar(1.0)
            try:
                aviso = self.base.aviso_de(r.visita_id) or aviso
            except ErrorBase:
                pass
        self.nota(f"aviso a {r.responsable}: {aviso['estado']}")
        return aviso["estado"]

    def orientacion(self, r, destino: str | None) -> None:
        """Cierra el evento en la base: el X2 dio la indicación (no acompaña: está fijo)."""
        if self.base is not None and getattr(r, "evento_id", None):
            try:
                self.base.registrar_orientacion(r.evento_id, "indicacion", destino, None)
            except ErrorBase as e:
                self.nota(f"registrar_orientacion sin respuesta: {e}")

    # --- una atención completa ----------------------------------------------------------------
    def atender(self, captura) -> None:
        token = self.cam.qr
        if captura is not None and not token:
            captura, reconocida = self.mejor_foto(captura)
            self.nota("cara " + ("reconocida" if reconocida else "no reconocida"))
            if not reconocida and not self.cam.qr:
                token = self.pedir_qr()
                if not token:
                    self.decir(SIN_QR, "problema")
                    return
        token = token or self.cam.qr
        if token and token.startswith(QR_DEMO):
            self.decir(f"{voz.QR_DE_DEMOSTRACION} {MOSTRADOR}", "problema")
            return
        if token:
            pase = self.cam.pase
            self.nota("QR leído" + (f": pase de {pase.get('nombre')} ({pase.get('tipo')})"
                                    if pase else ""))
            self.mostrar("Verificando el QR...")
            self.voz.decir(LEYENDO)

        r = self.registrar(captura, token)
        if not r.habilitado:
            self.mostrar(MOTIVOS.get(r.motivo, r.resultado))
            self.decir(no_sigue(r), "problema")
            return
        self.mostrar(f"{r.nombre}: {CATEGORIAS[r.categoria]}")
        ctx = self.contexto(r)
        animo = captura.animo if captura else None
        plan, pedido = self.pedir_redaccion(r, *bienvenida(r, ctx, datetime.now()), ctx, animo)
        self.decir_redactado(r, plan, pedido, "vip" if r.categoria == "vip" else "bienvenida")
        if r.categoria in ("invitado", "externo"):
            # La respuesta "ya viene" se redacta mientras se espera al anfitrión: sale sin demora.
            aceptado = self.pedir_redaccion(r, *respuesta_aviso(r, "aceptado", ctx), ctx, animo)
            estado = self.esperar_aviso(r)
            if estado == "aceptado":
                self.decir_redactado(r, *aceptado, "bienvenida", espera=0.5)
            else:
                if aceptado[1] is not None:
                    aceptado[1].cancel()
                self.decir(respuesta_aviso(r, estado, ctx)[0], "problema")
        self.orientacion(r, r.destino)

    def correr(self) -> None:
        while not self.salir:
            captura = self.esperar_persona()
            if self.salir:
                break
            self.atender(captura)
            if captura is not None and captura.embedding is not None:
                self.ultima = (captura.embedding, time.monotonic())
            self.cara_vista = time.monotonic()
            self.mirar(1.5)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Recepción fija del X2: reconoce, saluda y pide el QR. "
                                             "El robot no se mueve.")
    ap.add_argument("--supabase", action="store_true",
                    help="decide la base real (eventos, avisos a la app móvil, panel web)")
    ap.add_argument("--voz", choices=("auto", "audio", "x2", "pc"), default="auto",
                    help="audio: español del portátil por el parlante del X2; x2: voz propia del "
                         "robot; pc: parlantes del portátil; auto: audio si el robot responde")
    ap.add_argument("--host", default="127.0.0.1", help="puente de voz (el túnel de conectar_voz.ps1)")
    ap.add_argument("--puerto", type=int, default=PUERTO_VOZ)
    ap.add_argument("--volumen", type=int, help="volumen del X2, 10-100")
    ap.add_argument("--camara", type=int, default=0, help="índice de la cámara del portátil")
    ap.add_argument("--ollama", nargs="?", const=voz.OLLAMA_MODELO, default=None, metavar="MODELO",
                    help=f"tono más cálido en la bienvenida con Ollama local (por defecto "
                         f"{voz.OLLAMA_MODELO}); los datos se conservan o se usa el texto fijo")
    args = ap.parse_args()

    base = None
    if args.supabase:
        base = BaseReal()
        if not base.disponible():
            print("Supabase no responde: decide la copia local hasta que vuelva a arrancar.")
            base = None
    try:
        hablar = Voz(args.voz, args.host, args.puerto, args.volumen)
    except ErrorVoz as e:
        raise SystemExit(str(e))
    print(f"Voz: {hablar.nota}")
    print("Decide: " + ("Supabase (base real)" if base else "copia local (personas del equipo)"))
    print("Preparando las frases fijas…", flush=True)
    hablar.preparar([PEDIR_QR, voz.REINTENTO_QR, SIN_QR, LEYENDO,
                     f"{voz.QR_DE_DEMOSTRACION} {MOSTRADOR}"])

    agente = voz.Agente(args.ollama)
    if agente.modelo:
        print(f"Cargando {agente.modelo} en Ollama (hasta {CALENTAR_OLLAMA:.0f} s)…", flush=True)
        fin = time.monotonic() + CALENTAR_OLLAMA
        while not agente.listo and time.monotonic() < fin and "no respondió" not in agente.estado:
            time.sleep(0.5)
    print(f"Textos: {agente.estado}")

    camara = CamaraWebcam(args.camara)
    recepcion = RecepcionFija(camara, hablar, base, agente)
    print(f"Personas del equipo: {', '.join(p['nombre_demo'] for p in recepcion.registradas) or 'ninguna'}")
    print("Teclas" + __doc__.split("Teclas")[1].rstrip())
    try:
        recepcion.correr()
    except KeyboardInterrupt:
        pass
    finally:
        hablar.cerrar()
        camara.cerrar()


if __name__ == "__main__":
    main()
