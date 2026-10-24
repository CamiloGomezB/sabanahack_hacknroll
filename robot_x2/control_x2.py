#!/usr/bin/env python3
"""Control a distancia del X2 Ultra desde el portátil (no necesita ROS).

Habla con `puente_x2.py`, que corre en el robot. Primero se abre el túnel SSH (ver README) y luego:

    python control_x2.py              # consola de órdenes
    python control_x2.py avanzar 1    # una sola orden y espera a que termine

Órdenes en la consola:
    avanzar 1        avanza 1 m (negativo = atrás, máx. 0.5 m)   ·   avanzar 1 0.4 = a 0.4 m/s
    girar 90         gira 90° a la izquierda (negativo = derecha)
    estado           posición, modo del robot y orden en curso
    teclado          mando con W/A/S/D, Q/E de lado, Espacio = parar, Esc = salir
    navegar MAPA X Y va a (X, Y) del mapa con la navegación del robot
    d | detener      se detiene (también Ctrl+C)
    salir
"""

import json
import socket
import sys
import threading
import time


class ErrorX2(RuntimeError):
    pass


class ClienteX2:
    """Órdenes al puente del X2: cada una es una línea JSON y su respuesta."""

    def __init__(self, host="127.0.0.1", puerto=8765, timeout=3.0):
        self._sock = socket.create_connection((host, puerto), timeout=timeout)
        self._archivo = self._sock.makefile("rwb")
        self._lock = threading.Lock()
        self._id = 0

    def orden(self, nombre, **datos):
        with self._lock:
            self._id += 1
            mensaje = {"id": self._id, "orden": nombre, **datos}
            self._archivo.write((json.dumps(mensaje) + "\n").encode("utf-8"))
            self._archivo.flush()
            linea = self._archivo.readline()
        if not linea:
            raise ErrorX2("el puente cerró la conexión")
        respuesta = json.loads(linea)
        if not respuesta.get("ok"):
            raise ErrorX2(respuesta.get("error", "error desconocido"))
        return respuesta

    def estado(self):
        return self.orden("estado")

    def detener(self):
        return self.orden("detener")

    def velocidad(self, adelante=0.0, lateral=0.0, giro=0.0):
        return self.orden("velocidad", adelante=adelante, lateral=lateral, giro=giro)

    def avanzar(self, metros, velocidad=0.3, esperar=True):
        self.orden("avanzar", metros=metros, velocidad=velocidad)
        return self.esperar() if esperar else None

    def girar(self, grados, velocidad=0.3, esperar=True):
        self.orden("girar", grados=grados, velocidad=velocidad)
        return self.esperar() if esperar else None

    def navegar(self, map_id, x, y, yaw_grados=0.0, radio=0.5, velocidad=0.4):
        return self.orden("navegar", map_id=map_id, x=x, y=y, yaw_grados=yaw_grados,
                          radio=radio, velocidad=velocidad)

    def en_curso(self):
        return self.estado()["accion"] in ("avanzar", "girar")

    def esperar(self, cada=0.1):
        """Espera a que termine la orden de avanzar o girar; Ctrl+C la detiene."""
        try:
            while True:
                e = self.estado()
                if e["accion"] not in ("avanzar", "girar"):
                    return e
                time.sleep(cada)
        except KeyboardInterrupt:
            self.detener()
            raise

    def cerrar(self):
        try:
            self.detener()
        except (ErrorX2, OSError):
            pass
        self._archivo.close()
        self._sock.close()


def mostrar(e):
    obstaculo = "libre" if e["obstaculo_m"] is None else f"{e['obstaculo_m']:.2f} m"
    print(f"  {e['mensaje']}  ·  x={e['x']:+.2f} m  y={e['y']:+.2f} m  giro={e['yaw_grados']:+.0f}°"
          f"  ({e['posicion']})")
    print(f"  modo {e['modo']} · {e['postura']} · sistema {e['sistema']} · batería {e['bateria']} %"
          f" · delante {obstaculo}" + ("" if e["lidar"] else " (SIN LiDAR)")
          + f" · mando: {e['fuente_activa'] or '-'}")
    if not e["puede_caminar"]:
        print(f"  NO PUEDE CAMINAR: {e['motivo']}")


# Mando con teclado: cada tecla sube o baja una velocidad, como el ejemplo 6.1.12 de AimDK
PASO_ADELANTE, PASO_LATERAL, PASO_GIRO = 0.1, 0.1, 0.1


def _lector_teclas():
    """Devuelve una función que lee una tecla sin bloquear (o None)."""
    try:
        import msvcrt

        def leer():
            if msvcrt.kbhit():
                return msvcrt.getwch()
            return None

        return leer, lambda: None
    except ImportError:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        viejo = termios.tcgetattr(fd)
        tty.setcbreak(fd)

        def leer():
            if select.select([sys.stdin], [], [], 0)[0]:
                return sys.stdin.read(1)
            return None

        return leer, lambda: termios.tcsetattr(fd, termios.TCSADRAIN, viejo)


def teclado(x2):
    print("  W/S adelante/atrás · A/D girar · Q/E de lado · Espacio parar · Esc salir")
    leer, restaurar = _lector_teclas()
    adelante = lateral = giro = 0.0
    try:
        while True:
            tecla = leer()
            if tecla:
                tecla = tecla.lower()
                if tecla == "\x1b":
                    break
                if tecla == " ":
                    adelante = lateral = giro = 0.0
                elif tecla == "w":
                    adelante = max(0.2, adelante + PASO_ADELANTE) if adelante >= 0 else adelante + PASO_ADELANTE
                elif tecla == "s":
                    adelante = min(-0.2, adelante - PASO_ADELANTE) if adelante <= 0 else adelante - PASO_ADELANTE
                elif tecla == "a":
                    giro += PASO_GIRO
                elif tecla == "d":
                    giro -= PASO_GIRO
                elif tecla == "q":
                    lateral = max(0.5, lateral + PASO_LATERAL) if lateral >= 0 else lateral + PASO_LATERAL
                elif tecla == "e":
                    lateral = min(-0.5, lateral - PASO_LATERAL) if lateral <= 0 else lateral - PASO_LATERAL
                adelante, lateral, giro = (round(v, 2) for v in (adelante, lateral, giro))
                print(f"\r  adelante {adelante:+.1f} m/s  lateral {lateral:+.1f} m/s  giro {giro:+.1f} rad/s   ",
                      end="", flush=True)
            try:
                if (adelante, lateral, giro) == (0.0, 0.0, 0.0):
                    x2.detener()
                else:
                    x2.velocidad(adelante, lateral, giro)  # se renueva 10 veces por segundo
            except ErrorX2 as err:
                print(f"\n  {err}")
                adelante = lateral = giro = 0.0
            time.sleep(0.1)
    finally:
        restaurar()
        x2.detener()
        print()


def ejecutar(x2, partes):
    nombre, args = partes[0].lower(), [float(a) for a in partes[1:]]
    if nombre == "avanzar":
        mostrar(x2.avanzar(*args))
    elif nombre == "girar":
        mostrar(x2.girar(*args))
    elif nombre == "estado":
        mostrar(x2.estado())
    elif nombre in ("d", "detener", "parar"):
        x2.detener()
        mostrar(x2.estado())
    elif nombre == "teclado":
        teclado(x2)
    elif nombre == "navegar":
        x2.navegar(int(partes[1]), args[1], args[2])
        mostrar(x2.estado())
    else:
        print("  Órdenes: avanzar M, girar G, estado, teclado, navegar MAPA X Y, detener, salir")


def main():
    import argparse

    p = argparse.ArgumentParser(description="Control a distancia del X2 Ultra")
    p.add_argument("--host", default="127.0.0.1", help="127.0.0.1 con el túnel SSH abierto")
    p.add_argument("--puerto", type=int, default=8765)
    p.add_argument("orden", nargs="*", help="una sola orden, p. ej.: avanzar 1")
    a = p.parse_args()
    try:
        x2 = ClienteX2(a.host, a.puerto)
    except OSError as e:
        raise SystemExit(f"No se pudo conectar con el puente en {a.host}:{a.puerto} ({e}). "
                         "¿Está corriendo puente_x2.py y abierto el túnel SSH?")
    try:
        if a.orden:
            ejecutar(x2, a.orden)
            return
        mostrar(x2.estado())
        while True:
            try:
                linea = input("x2> ").strip()
            except EOFError:
                break
            if not linea:
                continue
            if linea.lower() in ("salir", "exit", "q"):
                break
            try:
                ejecutar(x2, linea.split())
            except (ErrorX2, ValueError, IndexError, TypeError) as e:
                print(f"  No: {e}")
            except KeyboardInterrupt:
                print("\n  Detenido.")
    except KeyboardInterrupt:
        pass
    finally:
        x2.cerrar()


if __name__ == "__main__":
    main()
