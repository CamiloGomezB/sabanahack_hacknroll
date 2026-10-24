"""X2 Ultra dentro de la simulación. Implementa robots.interfaz.X2 sobre el mundo de MuJoCo.

La cámara es intercambiable: una foto del dataset de prueba (reconocimiento simulado) o la cámara
del computador con el modelo facial real (ver camaras.py).
"""

from collections.abc import Callable

from animacion import POSE_ESCANEAR, Mundo
from caras import Captura


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
