"""X2 Ultra real. Implementa los movimientos de robots.interfaz.X2 sobre el puente de AimDK.

Habla con `robot_x2/puente_x2.py` (en el robot) mediante `robot_x2/control_x2.py`: solo pide
"gira tantos grados" y "avanza tantos metros"; la caminata y el equilibrio son del robot.

Las coordenadas del club se pasan a las del robot suponiendo que arranca en su puesto (POS_X2)
mirando hacia la entrada. Sin mapa del lugar la posición es la estimada por el puente, así que los
recorridos largos acumulan error: para algo autónomo de verdad falta mapear el lobby y usar
`navegar` (la navegación propia del robot).

Cámara, voz y gestos todavía no van al robot: `capturar` usa la cámara que se le asigne (la del
portátil, como en la simulación), `decir` imprime y los gestos solo esperan su duración.
"""

import math
import sys
import time
from collections.abc import Callable
from pathlib import Path

from caras import Captura
from club import PATRULLA_X2, POS_X2

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "robot_x2"))
from control_x2 import ClienteX2  # noqa: E402

YAW_PUESTO = math.pi  # en su puesto mira hacia la entrada (-x), igual que en la simulación
VELOCIDAD = 0.3  # m/s
CONSULTA = 0.1  # s entre consultas del estado (además sirve de latido para el puente)


def _angulo(a):
    return math.atan2(math.sin(a), math.cos(a))


class X2Aimdk:
    def __init__(self, cliente: ClienteX2, al_hablar: Callable[[str], None] = print):
        self.x2 = cliente
        self.al_hablar = al_hablar
        self.camara: Callable[[], Captura] | None = None
        e = cliente.estado()
        # Referencia: la pose del robot al conectar corresponde a POS_X2 mirando a la entrada
        self._origen = (e["x"], e["y"], math.radians(e["yaw_grados"]))

    # Pose del robot en coordenadas del club
    def pose(self):
        e = self.x2.estado()
        x0, y0, yaw0 = self._origen
        dx, dy = e["x"] - x0, e["y"] - y0
        giro = YAW_PUESTO - yaw0
        c, s = math.cos(giro), math.sin(giro)
        return (POS_X2[0] + c * dx - s * dy, POS_X2[1] + s * dx + c * dy,
                _angulo(YAW_PUESTO + math.radians(e["yaw_grados"]) - yaw0))

    def capturar(self) -> Captura:
        if self.camara is None:
            raise RuntimeError("El X2 no tiene cámara conectada.")
        return self.camara()

    def decir(self, texto: str) -> None:
        self.al_hablar(texto)

    def esperar(self, segundos: float):
        fin = time.monotonic() + segundos
        while time.monotonic() < fin:
            time.sleep(CONSULTA)
            yield

    mirar_visitante = saludar = negar = esperar

    def senalar_mapa(self, zona: str, segundos: float):
        yield from self.esperar(segundos)

    def _hasta_terminar(self):
        while self.x2.en_curso():
            time.sleep(CONSULTA)
            yield

    def _girar_a(self, yaw):
        delta = math.degrees(_angulo(yaw - self.pose()[2]))
        if abs(delta) > 3:
            self.x2.girar(delta, esperar=False)
            yield from self._hasta_terminar()

    def ir_a(self, puntos):
        try:
            for px, py in puntos:
                x, y, _ = self.pose()
                distancia = math.hypot(px - x, py - y)
                if distancia < 0.05:
                    continue
                yield from self._girar_a(math.atan2(py - y, px - x))
                self.x2.avanzar(distancia, VELOCIDAD, esperar=False)
                yield from self._hasta_terminar()
        finally:
            self.detener()

    def volver_al_puesto(self):
        yield from self.ir_a([POS_X2])
        yield from self._girar_a(YAW_PUESTO)

    def patrullar(self):
        try:
            while True:
                for punto in PATRULLA_X2:
                    yield from self.ir_a([punto])
                    yield from self.esperar(1.5)
        finally:
            self.detener()

    def detener(self) -> None:
        self.x2.detener()
