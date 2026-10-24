"""Plano del club (inventado para la demo). Coordenadas en metros; el eje x apunta hacia adentro.

Cada zona es una habitación con muros y una puerta en el lado de su entrada (sin techo, para verla
desde arriba). Los pasillos forman un grafo: las rutas se calculan con Dijkstra solo por tramos autorizados para
la categoría de la visita y que no estén bloqueados.
"""

import heapq
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Zona:
    clave: str
    nombre: str
    centro: tuple[float, float]
    tamano: tuple[float, float]  # ancho en x, ancho en y
    color: tuple[float, float, float]
    entrada: tuple[float, float]


ZONAS: dict[str, Zona] = {
    z.clave: z
    for z in [
        Zona("lobby", "Lobby", (-6.0, 0.0), (8.0, 6.0), (0.85, 0.82, 0.76), (-2.0, -2.4)),
        Zona("sala_vip", "Sala VIP", (2.0, 6.0), (5.0, 4.0), (0.85, 0.68, 0.20), (2.0, 4.5)),
        Zona("piscina", "Piscina", (9.0, 6.0), (6.0, 4.0), (0.25, 0.60, 0.85), (9.0, 4.5)),
        Zona("canchas", "Canchas", (15.5, 6.0), (5.0, 4.0), (0.35, 0.70, 0.35), (15.5, 4.5)),
        Zona("restaurante", "Restaurante", (15.5, 0.0), (5.0, 4.0), (0.85, 0.45, 0.30), (13.5, 0.0)),
        Zona("gimnasio", "Gimnasio", (9.0, -6.0), (6.0, 4.0), (0.55, 0.40, 0.75), (9.0, -4.5)),
        Zona("oficinas", "Oficinas del personal", (2.0, -6.0), (5.0, 4.0), (0.45, 0.55, 0.60),
             (2.0, -4.5)),
        Zona("mantenimiento", "Mantenimiento", (15.5, -6.0), (5.0, 4.0), (0.55, 0.50, 0.45),
             (15.5, -4.5)),
    ]
}

# Espacios de la app móvil (repo app_registro_nclub, src/constants/spaces.ts): es la clave que guarda
# visitas.destino cuando un miembro invita o registra a un externo desde la app. Allá también son
# provisionales, así que cada uno se ubica en la zona de la maqueta que más se le parece.
ESPACIOS_APP: dict[str, tuple[str, str]] = {   # clave de la app: (nombre en la app, zona aquí)
    "salon-social": ("Salón social", "restaurante"),
    "terraza": ("Terraza", "piscina"),
    "sala-lectura": ("Sala de lectura", "gimnasio"),
    "salon-privado": ("Salón privado VIP", "sala_vip"),
    "comedor-reservado": ("Comedor reservado", "restaurante"),
    "sala-juntas": ("Sala de juntas VIP", "sala_vip"),
    "zona-servicio": ("Zona de servicio", "mantenimiento"),
}


def zona_de_destino(destino: str | None) -> str | None:
    """Zona de la maqueta para un destino guardado por la simulación o por la app móvil."""
    if destino in ZONAS:
        return destino
    return ESPACIOS_APP[destino][1] if destino in ESPACIOS_APP else None


def nombre_destino(destino: str) -> str:
    """Nombre que ve la persona: el de la app si el destino viene de ella."""
    return ESPACIOS_APP[destino][0] if destino in ESPACIOS_APP else ZONAS[destino].nombre


# Lugares fijos del lobby.
ENTRADA = (-10.0, 0.0)
POS_X2 = (-4.0, 0.0)          # el X2 mira hacia la entrada (-x)
POS_VISITANTE = (-5.2, 0.0)   # donde se para la persona frente al X2
POS_MAPA = (-4.3, 1.4)        # tablero con el mapa, a la derecha del X2
BASE_D1 = (-4.2, -1.8)        # donde espera el D1
POS_RECEPCION = (-7.0, 2.2)   # mostrador de recepción (humano)
POS_ANTE_RECEPCION = (-7.0, 1.3)
SALIDA_VISITANTE = (-5.2, -2.4)  # primer paso desde el X2 hacia la salida del lobby
POS_ESPERA = (-7.6, -1.9)     # sala de espera del lobby (sofás)
FUERA = (ENTRADA[0] - 1.5, 0.0)  # afuera, frente a la puerta: ahí espera quien va a entrar

# Puntos que el X2 recorre mientras no hay nadie llegando, buscando a quién recibir.
PATRULLA_X2 = [(-5.6, 1.1), (-7.6, 0.5), (-7.2, -1.1), (-5.2, -1.2)]

ALTO_MURO = 2.4
ANCHO_PUERTA = 1.6

# Recorrido de bienvenida para un miembro regular nuevo.
RECORRIDO_TOUR = ["piscina", "canchas", "restaurante", "gimnasio"]

# --- Grafo de pasillos --------------------------------------------------------------------------
NODOS: dict[str, tuple[float, float]] = {
    "salida": ZONAS["lobby"].entrada,
    "c0": (-2.0, 0.0), "c1": (2.0, 0.0), "c2": (9.0, 0.0), "c3": (12.6, 0.0),
    "n0": (-2.0, 3.0), "n1": (2.0, 3.0), "n2": (9.0, 3.0), "n3": (12.6, 3.0),
    "s0": (-2.0, -3.0), "s1": (2.0, -3.0), "s2": (9.0, -3.0), "s3": (12.6, -3.0),
    "n4": (15.5, 3.0), "s4": (15.5, -3.0),   # frente a las puertas de Canchas y Mantenimiento
    **{f"z_{z.clave}": z.entrada for z in ZONAS.values() if z.clave != "lobby"},
}

SOLO_PERSONAL = frozenset({"personal", "externo"})  # pasillo de servicio

# (a, b, categorías autorizadas o None = todas)
TRAMOS: list[tuple[str, str, frozenset | None]] = [
    ("salida", "c0", None), ("salida", "s0", None),
    ("c0", "c1", None), ("c1", "c2", None), ("c2", "c3", None),
    ("n0", "n1", None), ("n1", "n2", None), ("n2", "n3", None),
    ("s0", "s1", None), ("s1", "s2", None), ("s2", "s3", SOLO_PERSONAL),
    ("c0", "n0", None), ("c1", "n1", None), ("c2", "n2", None), ("c3", "n3", None),
    ("c0", "s0", None), ("c1", "s1", None), ("c2", "s2", None), ("c3", "s3", SOLO_PERSONAL),
    ("n3", "n4", None), ("s3", "s4", SOLO_PERSONAL),
    ("n1", "z_sala_vip", None), ("n2", "z_piscina", None), ("n4", "z_canchas", None),
    ("c3", "z_restaurante", None), ("s2", "z_gimnasio", None),
    ("s1", "z_oficinas", SOLO_PERSONAL), ("s4", "z_mantenimiento", SOLO_PERSONAL),
]

# Tramo que se puede cerrar en la demo (tecla B): pasillo central entre la Sala VIP y la Piscina.
TRAMO_BLOQUEABLE = ("c1", "c2")


def _clave(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def ruta(origen: str, destino: str, categoria: str | None,
         bloqueados: set[tuple[str, str]]) -> list[str] | None:
    """Camino más corto entre dos nodos usando solo tramos autorizados y abiertos."""
    vecinos: dict[str, list[tuple[str, float]]] = {n: [] for n in NODOS}
    for a, b, permitido in TRAMOS:
        if _clave(a, b) in bloqueados:
            continue
        if permitido is not None and categoria not in permitido:
            continue
        largo = math.dist(NODOS[a], NODOS[b])
        vecinos[a].append((b, largo))
        vecinos[b].append((a, largo))
    distancia = {origen: 0.0}
    previo: dict[str, str] = {}
    cola = [(0.0, origen)]
    while cola:
        d, n = heapq.heappop(cola)
        if n == destino:
            camino = [n]
            while n in previo:
                n = previo[n]
                camino.append(n)
            return camino[::-1]
        if d > distancia.get(n, math.inf):
            continue
        for m, largo in vecinos[n]:
            if d + largo < distancia.get(m, math.inf):
                distancia[m] = d + largo
                previo[m] = n
                heapq.heappush(cola, (d + largo, m))
    return None


def puntos(nodos: list[str]) -> list[tuple[float, float]]:
    return [NODOS[n] for n in nodos]


def nodo_de_zona(zona: str) -> str:
    return "salida" if zona == "lobby" else f"z_{zona}"


def usa_tramo(nodos: list[str], tramo: tuple[str, str]) -> bool:
    return any(_clave(a, b) == _clave(*tramo) for a, b in zip(nodos, nodos[1:]))


def puerta(zona: Zona) -> tuple[str, float]:
    """Muro de la zona donde va la puerta (n, s, e, o: el más cercano a su entrada) y la
    coordenada del centro de la puerta a lo largo de ese muro."""
    (cx, cy), (ax, ay), (ex, ey) = zona.centro, zona.tamano, zona.entrada
    distancias = {"s": ey - (cy - ay / 2), "n": (cy + ay / 2) - ey,
                  "o": ex - (cx - ax / 2), "e": (cx + ax / 2) - ex}
    lado = min(distancias, key=distancias.get)
    return lado, ex if lado in ("n", "s") else ey


def punto_llegada(zona: str) -> tuple[float, float]:
    """Dónde se para la persona al llegar: un poco adentro de la puerta, hacia el centro."""
    z = ZONAS[zona]
    (cx, cy), (ex, ey) = z.centro, z.entrada
    d = math.dist(z.centro, z.entrada)
    t = min(1.0, 0.7 / d) if d else 0.0
    return (ex + (cx - ex) * t, ey + (cy - ey) * t)
