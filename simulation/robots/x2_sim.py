"""X2 Ultra dentro de la simulación. Implementa robots.interfaz.X2 sobre el mundo de MuJoCo.

La cámara es intercambiable: una foto del dataset de prueba (reconocimiento simulado) o la cámara
del computador con el modelo facial real (ver camaras.py).
"""

from collections.abc import Callable

import numpy as np

from animacion import POSE_ESCANEAR, YAW_PUESTO, Mundo
from caras import Captura
from club import PATRULLA_X2, POS_X2


class X2Simulado:
    def __init__(self, mundo: Mundo, al_hablar: Callable[[str], None]):
        self.mundo = mundo
        self.al_hablar = al_hablar
        self.camara: Callable[[], Captura] | None = None

    def capturar(self) -> Captura:
        if self.camara is None:
            raise RuntimeError("El X2 no tiene cámara conectada.")
        return self.camara()

    def decir(self, texto: str) -> None:
        self.al_hablar(texto)

    def mirar_visitante(self, segundos: float):
        yield from self.mundo.pose_x2(POSE_ESCANEAR, segundos)

    def saludar(self, segundos: float):
        yield from self.mundo.saludar(segundos)

    def negar(self, segundos: float):
        yield from self.mundo.negar(segundos)

    def senalar_mapa(self, zona: str, segundos: float):
        yield from self.mundo.senalar_mapa(zona, segundos)

    def esperar(self, segundos: float):
        yield from self.mundo.esperar(segundos)

    def ir_a(self, puntos):
        yield from self.mundo.x2_caminar(puntos)

    def volver_al_puesto(self):
        """Camina a su puesto junto al mapa y se gira hacia la entrada."""
        self.detener()
        if np.linalg.norm(self.mundo.x2_xy - np.array(POS_X2)) > 0.05:
            yield from self.mundo.x2_caminar([POS_X2])
        yield from self.mundo.x2_girar(YAW_PUESTO, 0.8)

    def patrullar(self):
        """Mientras no llega nadie, recorre el lobby buscando a quién recibir (no termina)."""
        try:
            while True:
                for punto in PATRULLA_X2:
                    self.mundo.x2_buscando = True
                    yield from self.mundo.x2_caminar([punto])
                    yield from self.mundo.esperar(1.5)
        finally:
            self.detener()

    def detener(self) -> None:
        self.mundo.x2_andando = False
        self.mundo.x2_buscando = False
        self.mundo.x2_extra = {}
