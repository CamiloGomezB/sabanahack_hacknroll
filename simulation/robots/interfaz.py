"""Órdenes que el coordinador (la recepción) le da a cada robot.

El X2 y el D1 son máquinas distintas, cada una con su SDK: el X2 usa AimDK sobre ROS 2 y el D1 el
SDK agibot_D1_Edu-Ultra. Por eso cada uno tiene su propio programa con esta misma interfaz:

- `x2_sim.py` / `d1_sim.py`: los robots dentro de la simulación de MuJoCo.
- `x2_aimdk.py`: el X2 Ultra real; por ahora sus movimientos (`ir_a`, `volver_al_puesto`,
  `patrullar`), a través del puente de `robot_x2/`. Más adelante, `d1_sdk.py` para el D1.

El coordinador no sabe cuál de los dos está usando. Las acciones que tardan (caminar, saludar)
devuelven un iterable que avanza hasta que la acción termina: en la simulación da un paso por
cuadro; en el robot real, el adaptador consulta el estado del SDK en cada paso.

Los robots no hablan con Supabase ni guardan claves: reciben solo la orden que necesitan.
"""

from collections.abc import Iterator
from typing import Protocol

from caras import Captura

Accion = Iterator[None]
Punto = tuple[float, float]


class X2(Protocol):
    """Recepcionista: cámara, voz, gestos y el mapa del lobby."""

    def capturar(self) -> Captura:
        """Toma la imagen de la persona que llega y devuelve su huella (o por qué no sirve)."""

    def decir(self, texto: str) -> None: ...

    def mirar_visitante(self, segundos: float) -> Accion: ...

    def saludar(self, segundos: float) -> Accion: ...

    def negar(self, segundos: float) -> Accion: ...

    def senalar_mapa(self, zona: str, segundos: float) -> Accion: ...

    def esperar(self, segundos: float) -> Accion: ...

    def ir_a(self, puntos: list[Punto]) -> Accion:
        """Camina por el lobby (el X2 Ultra camina; en el robot real, con AimDK)."""

    def volver_al_puesto(self) -> Accion:
        """Vuelve junto al mapa y se gira hacia la entrada para recibir a quien llega."""

    def patrullar(self) -> Accion:
        """Recorre el lobby buscando a quién recibir hasta que se cancele (no termina solo)."""

    def detener(self) -> None: ...


class D1(Protocol):
    """Guía cuadrúpedo: recorre rutas de puntos (x, y) en metros sobre el plano del club."""

    @property
    def posicion(self) -> Punto: ...

    @property
    def avance(self) -> float:
        """Metros recorridos en la ruta actual (la persona lo sigue a cierta distancia)."""

    def ir_a(self, puntos: list[Punto]) -> Accion: ...

    def guiar(self, puntos: list[Punto]) -> Accion:
        """Recorre la ruta a paso de guía; la persona camina detrás."""

    def agacharse(self, segundos: float) -> Accion:
        """Baja el cuerpo para recibir o entregar la carga."""

    def levantarse(self, segundos: float) -> Accion: ...

    def cargar(self, objeto: str | None) -> None:
        """Lleva "maleta" (VIP) o "caja" de herramientas (externo) en el lomo; None la entrega."""

    def descansar(self) -> None:
        """Se queda quieto en su base, mirando hacia el lobby."""
