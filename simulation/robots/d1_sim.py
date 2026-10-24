"""D1 dentro de la simulación. Implementa robots.interfaz.D1 sobre el mundo de MuJoCo."""

import math

from animacion import Mundo, Ruta

VELOCIDAD = 1.4        # m/s yendo solo
VELOCIDAD_GUIA = 1.1   # m/s con una persona detrás


class D1Simulado:
    def __init__(self, mundo: Mundo):
        self.mundo = mundo
        self._avance = 0.0

    @property
    def posicion(self) -> tuple[float, float]:
        return tuple(self.mundo.d1_xy)

    @property
    def avance(self) -> float:
        return self._avance

    def _recorrer(self, puntos, velocidad: float):
        ruta = Ruta([self.posicion] + list(puntos))
        self._avance = 0.0
        self.mundo.d1_andando = True
        while self._avance < ruta.largo:
            self._avance = min(self._avance + velocidad * self.mundo._dt, ruta.largo)
            self.mundo.d1_xy, self.mundo.d1_yaw = ruta.en(self._avance)
            yield
        self.mundo.d1_andando = False

    def ir_a(self, puntos):
        yield from self._recorrer(puntos, VELOCIDAD)

    def guiar(self, puntos):
        yield from self._recorrer(puntos, VELOCIDAD_GUIA)

    def agacharse(self, segundos: float = 1.2):
        yield from self.mundo.d1_agacharse(True, segundos)

    def levantarse(self, segundos: float = 1.0):
        yield from self.mundo.d1_agacharse(False, segundos)

    def cargar(self, objeto: str | None) -> None:
        """Pone (o quita, con None) la maleta o la caja de herramientas en el lomo."""
        self.mundo.d1_carga = objeto

    @property
    def carga(self) -> str | None:
        return self.mundo.d1_carga

    def descansar(self) -> None:
        self.mundo.d1_andando = False
        self.mundo.d1_yaw = math.pi / 2
