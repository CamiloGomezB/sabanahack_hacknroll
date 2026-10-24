"""Dataset facial de la demo y reconocimiento SIMULADO.

Cada persona que dio consentimiento tiene 3 fotos de registro y 2 de prueba distintas. Las de
registro son las únicas que se comparan; las de prueba representan llegadas al club.

Lo simulado es la cámara y el modelo que convierte una foto en huella (vector de 512 números): cada
foto trae una "receta" oculta que dice de qué rostro base sale y cuánta variación tiene (luz,
ángulo). La comparación que viene después sí es la real: distancia coseno contra las huellas de
registro, igual que en Supabase. El componente que reconoce recibe solo la huella; la persona
esperada de cada foto de prueba se guarda aparte para evaluar y nunca se le entrega.

Los números salen de md5, así que Python y Postgres generan exactamente las mismas huellas.
"""

import hashlib
from dataclasses import dataclass

import numpy as np

MODELO = "simulado-v1"
DIM = 512
CON_BIOMETRIA = ["valentina", "andres", "carlos", "diana", "tomas", "mateo", "lucia", "ricardo",
                 "julian"]


@dataclass(frozen=True)
class Foto:
    clave: str
    uso: str                          # registro | prueba
    persona: str | None               # registro: dueña; prueba: persona esperada (None: no registrada)
    receta: tuple[tuple[str, float], ...]  # SIMULACIÓN: rostro base y variación (oculto)
    valida: bool = True               # False: borrosa o sin cara detectable

    @property
    def ruta(self) -> str:
        return f"demo/{self.uso}/{self.clave}.jpg"


def _componentes(semilla: str) -> np.ndarray:
    return np.array([int(hashlib.md5(f"{semilla}:{i}".encode()).hexdigest()[:8], 16)
                     / 4294967295 * 2 - 1 for i in range(DIM)])


_cache: dict[str, np.ndarray] = {}


def _base(semilla: str) -> np.ndarray:
    if semilla not in _cache:
        _cache[semilla] = _componentes(semilla)
    return _cache[semilla]


def huella(foto: Foto) -> np.ndarray | None:
    """SIMULA cámara + modelo: la huella de la foto, o None si la captura no sirve."""
    if not foto.valida:
        return None
    return sum(peso * _base(semilla) for semilla, peso in foto.receta)


def distancia(a: np.ndarray, b: np.ndarray) -> float:
    """Distancia coseno, la misma del operador <=> de pgvector."""
    return float(1 - a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def _fotos() -> list[Foto]:
    fotos = []
    for p in CON_BIOMETRIA:
        fotos += [Foto(f"{p}_r{n}", "registro", p, ((p, 1.0), (f"{p}_r{n}", 0.4))) for n in (1, 2, 3)]
        fotos += [Foto(f"{p}_p{n}", "prueba", p, ((p, 1.0), (f"{p}_p{n}", 0.5))) for n in (1, 2)]
    fotos += [
        # Invitados y externos no registran su cara: al llegar, el reconocimiento no los conoce.
        *[Foto(f"{p}_p1", "prueba", p, ((p, 1.0), (f"{p}_p1", 0.5)))
          for p in ["sofia", "jorge", "pedro", "ana", "desconocido", "visitante"]],
        # Marta se parece mucho a Valentina: el reconocimiento se equivoca (falso positivo).
        Foto("marta_p1", "prueba", "marta", (("valentina", 1.0), ("marta", 0.5), ("marta_p1", 0.4))),
        # Mateo con corte de pelo nuevo y mala luz: queda entre umbrales.
        Foto("mateo_p3", "prueba", "mateo", (("mateo", 1.0), ("mateo_p3", 1.4))),
        # Lucía, de lado, se parece igual a ella y a Mateo: dos candidatos demasiado cercanos.
        Foto("lucia_p3", "prueba", "lucia", (("lucia", 1.0), ("mateo", 1.0), ("lucia_p3", 0.3))),
        # Julián pasó muy rápido: la foto salió movida.
        Foto("julian_p3", "prueba", "julian", (), valida=False),
    ]
    return fotos


FOTOS: dict[str, Foto] = {f.clave: f for f in _fotos()}
