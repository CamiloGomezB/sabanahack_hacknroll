"""Arma el modelo de MuJoCo: club, X2 Ultra (modelo oficial de AgiBot), D1 y las personas.

El club tiene habitaciones con muros de 2.4 m y una puerta por zona, sin techo para verlo desde
arriba, con su mobiliario. Cada persona lleva una cámara a la altura de los ojos (vista_<i>) para
ver la llegada desde su perspectiva.
"""

import math
import os
import unicodedata
from pathlib import Path

import mujoco
from dotenv import load_dotenv

from club import (ALTO_MURO, ANCHO_PUERTA, BASE_D1, ENTRADA, NODOS, POS_ESPERA, POS_MAPA,
                  POS_RECEPCION, POS_X2, SOLO_PERSONAL, TRAMOS, ZONAS, puerta)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Los archivos del X2 son de AgiBot y no van en el repo público: se leen desde la carpeta de la
# hackathon (o desde X2_MODELO en el .env).
X2_MODELO_DEFECTO = (Path.home() / "Desktop/Hackaton/Agibot X2-X2ultra-20261022T223240Z-1-001"
                     / "Agibot X2-X2ultra/X2_URDF/X2_URDF-v1.4.0/X2-Ultra.xml")
TEXTURA_MADERA = Path(__file__).resolve().parent / "texturas" / "madera_laminada.png"

COLOR_CATEGORIA = {
    "vip": (0.95, 0.75, 0.15, 1),
    "regular": (0.20, 0.45, 0.90, 1),
    "personal": (0.20, 0.70, 0.35, 1),
    "invitado": (0.65, 0.35, 0.85, 1),
    "externo": (0.95, 0.50, 0.15, 1),
    None: (0.55, 0.55, 0.55, 1),
}

ESCALA_MAPA = 0.06  # metros del tablero por metro del club
ALTO_OJOS = 1.62    # cámara de cada persona
INCLINACION_VISTA = math.radians(12)   # mira un poco hacia abajo

_SIMBOLOS = {"¡": "", "¿": "", "…": "...", "→": "->", "–": "-", "—": "-", "·": "-", "×": "x"}
SIN_CHOQUE = dict(contype=0, conaffinity=0)
CAJA, CILINDRO, ESFERA = mujoco.mjtGeom.mjGEOM_BOX, mujoco.mjtGeom.mjGEOM_CYLINDER, \
    mujoco.mjtGeom.mjGEOM_SPHERE


def ascii(texto: str) -> str:
    """La fuente de MuJoCo solo tiene ASCII: quita tildes y cambia los símbolos."""
    for k, v in _SIMBOLOS.items():
        texto = texto.replace(k, v)
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).encode("ascii", "ignore").decode()


def _caja(cuerpo, pos, size, rgba, yaw=0.0, **extra):
    return cuerpo.add_geom(type=CAJA, pos=pos, size=size, rgba=rgba,
                           quat=[math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)], **SIN_CHOQUE, **extra)


def _cilindro(cuerpo, pos, radio, medio_alto, rgba, **extra):
    return cuerpo.add_geom(type=CILINDRO, pos=pos, size=[radio, medio_alto, 0], rgba=rgba,
                           **SIN_CHOQUE, **extra)


# --- Muros -------------------------------------------------------------------------------------
PARED = [0.93, 0.91, 0.87, 1]
GROSOR = 0.08   # medio grosor del muro


def _muro(mundo, a: tuple[float, float], b: tuple[float, float], huecos=(), alto=ALTO_MURO,
          rgba=PARED) -> None:
    """Muro recto de a a b (horizontal o vertical) con huecos [(centro, ancho)] para las puertas."""
    horizontal = a[1] == b[1]
    ini, fin = (a[0], b[0]) if horizontal else (a[1], b[1])
    ini, fin = min(ini, fin), max(ini, fin)
    tramos, cursor = [], ini
    for centro, ancho in sorted(huecos):
        tramos.append((cursor, centro - ancho / 2))
        cursor = centro + ancho / 2
    tramos.append((cursor, fin))
    for t0, t1 in tramos:
        if t1 - t0 < 0.05:
            continue
        medio, largo = (t0 + t1) / 2, (t1 - t0) / 2 + GROSOR
        pos = [medio, a[1], alto / 2] if horizontal else [a[0], medio, alto / 2]
        size = [largo, GROSOR, alto / 2] if horizontal else [GROSOR, largo, alto / 2]
        _caja(mundo, pos, size, rgba)
        # Remate oscuro arriba para que los muros se lean desde la vista de arriba.
        tope = [pos[0], pos[1], alto + 0.01]
        _caja(mundo, tope, [size[0], size[1], 0.01], [0.55, 0.52, 0.48, 1])


def _habitacion(mundo, zona) -> None:
    (cx, cy), (ax, ay) = zona.centro, zona.tamano
    x0, x1, y0, y1 = cx - ax / 2, cx + ax / 2, cy - ay / 2, cy + ay / 2
    lado, centro = puerta(zona)
    hueco = [(centro, ANCHO_PUERTA)]
    _muro(mundo, (x0, y0), (x1, y0), hueco if lado == "s" else ())
    _muro(mundo, (x0, y1), (x1, y1), hueco if lado == "n" else ())
    _muro(mundo, (x0, y0), (x0, y1), hueco if lado == "o" else ())
    _muro(mundo, (x1, y0), (x1, y1), hueco if lado == "e" else ())
    # Marco de la puerta.
    for d in (-1, 1):
        p = centro + d * (ANCHO_PUERTA / 2 + 0.04)
        pos = [p, y0 if lado == "s" else y1, ALTO_MURO / 2] if lado in ("n", "s") else \
            [x0 if lado == "o" else x1, p, ALTO_MURO / 2]
        _caja(mundo, pos, [0.06, 0.06, ALTO_MURO / 2 + 0.02], [0.45, 0.33, 0.22, 1])


# --- Pisos y mobiliario ----------------------------------------------------------------------
MADERA = "madera"


def _materiales(spec: mujoco.MjSpec) -> None:
    spec.add_texture(name="exterior", type=mujoco.mjtTexture.mjTEXTURE_2D,
                     builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER, rgb1=[0.78, 0.78, 0.75],
                     rgb2=[0.74, 0.74, 0.71], width=512, height=512)
    spec.add_material(name="exterior", textures=["", "exterior"], texrepeat=[30, 30])
    spec.add_texture(name="baldosa", type=mujoco.mjtTexture.mjTEXTURE_2D,
                     builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER, rgb1=[0.90, 0.89, 0.86],
                     rgb2=[0.85, 0.84, 0.81], width=256, height=256)
    spec.add_material(name="baldosa", textures=["", "baldosa"], texuniform=True,
                      texrepeat=[1.2, 1.2])
    if TEXTURA_MADERA.exists():
        spec.add_texture(name="madera", type=mujoco.mjtTexture.mjTEXTURE_2D,
                         file=str(TEXTURA_MADERA))
        spec.add_material(name=MADERA, textures=["", "madera"], texuniform=True,
                          texrepeat=[1 / 2.4, 1 / 2.4], reflectance=0.04)
    else:
        spec.add_material(name=MADERA, rgba=[0.70, 0.52, 0.34, 1])


PISO_ZONA = {   # material o color del piso de cada habitación
    "lobby": MADERA, "sala_vip": MADERA, "restaurante": MADERA, "oficinas": MADERA,
    "piscina": [0.86, 0.80, 0.68, 1], "canchas": [0.30, 0.55, 0.36, 1],
    "gimnasio": [0.22, 0.22, 0.25, 1], "mantenimiento": [0.62, 0.62, 0.60, 1],
}


def _planta(mundo, x, y):
    _cilindro(mundo, [x, y, 0.2], 0.18, 0.2, [0.55, 0.42, 0.30, 1])
    mundo.add_geom(type=ESFERA, pos=[x, y, 0.7], size=[0.32, 0, 0], rgba=[0.22, 0.50, 0.25, 1],
                   **SIN_CHOQUE)


def _sofa(mundo, x, y, largo, yaw, rgba):
    """Sofá de `largo` m; el respaldo queda detrás según yaw (0 = mira hacia +y)."""
    c, s = math.cos(yaw), math.sin(yaw)
    _caja(mundo, [x, y, 0.22], [largo / 2, 0.35, 0.22], rgba, yaw)
    _caja(mundo, [x + 0.3 * s, y - 0.3 * c, 0.5], [largo / 2, 0.08, 0.35], rgba, yaw)


def _mesa(mundo, x, y, radio=0.4, alto=0.75, sillas=4):
    _cilindro(mundo, [x, y, alto], radio, 0.02, [0.95, 0.94, 0.92, 1])
    _cilindro(mundo, [x, y, alto / 2], 0.05, alto / 2, [0.3, 0.3, 0.3, 1])
    for k in range(sillas):
        a = 2 * math.pi * k / sillas
        _caja(mundo, [x + (radio + 0.25) * math.cos(a), y + (radio + 0.25) * math.sin(a), 0.23],
              [0.18, 0.18, 0.23], [0.45, 0.30, 0.20, 1], a)


def _mobiliario(mundo) -> None:
    oscuro, blanco = [0.2, 0.2, 0.22, 1], [0.97, 0.97, 0.97, 1]
    # Lobby: tapete frente al X2, sala de espera con sofás, plantas y el logo en la entrada.
    _caja(mundo, [-6.6, 0, 0.014], [1.6, 1.1, 0.004], [0.50, 0.16, 0.18, 1])
    ex, ey = POS_ESPERA
    _sofa(mundo, ex - 1.0, ey - 0.65, 1.8, 0, [0.30, 0.34, 0.45, 1])
    _sofa(mundo, ex - 1.95, ey - 0.1, 1.0, -math.pi / 2, [0.30, 0.34, 0.45, 1])
    _cilindro(mundo, [ex - 1.0, ey + 0.35, 0.2], 0.35, 0.2, [0.45, 0.33, 0.22, 1])
    for x, y in [(-9.5, 2.5), (-2.6, 2.5), (-5.6, 2.6)]:
        _planta(mundo, x, y)
    _caja(mundo, [ENTRADA[0] - 0.1, 2.0, 2.0], [0.02, 0.5, 0.18], [0.85, 0.68, 0.20, 1])
    _caja(mundo, [ENTRADA[0] - 0.1, -2.0, 2.0], [0.02, 0.5, 0.18], [0.85, 0.68, 0.20, 1])

    # Sala VIP: sofás, mesa de centro, sillones y barra.
    _sofa(mundo, 2.0, 7.35, 2.2, math.pi, [0.55, 0.10, 0.15, 1])
    _cilindro(mundo, [2.0, 6.6, 0.2], 0.45, 0.2, [0.15, 0.12, 0.10, 1])
    for x in (0.4, 3.2):
        _caja(mundo, [x, 6.4, 0.25], [0.4, 0.4, 0.25], [0.55, 0.10, 0.15, 1])
    _caja(mundo, [4.15, 6.2, 0.55], [0.25, 1.2, 0.55], [0.85, 0.68, 0.20, 1])

    # Piscina: agua, borde y asoleadoras.
    _caja(mundo, [9.0, 6.9, 0.02], [2.8, 0.95, 0.02], [0.95, 0.95, 0.95, 1])
    _caja(mundo, [9.0, 6.9, 0.03], [2.6, 0.8, 0.02], [0.15, 0.55, 0.85, 0.85])
    for x in (6.6, 7.5, 10.5, 11.4):
        _caja(mundo, [x, 5.1, 0.15], [0.3, 0.75, 0.12], [0.95, 0.95, 0.95, 1])
    _cilindro(mundo, [10.95, 5.1, 1.0], 0.03, 1.0, oscuro)
    _cilindro(mundo, [10.95, 5.1, 2.0], 0.65, 0.03, [0.90, 0.35, 0.30, 1])

    # Canchas: superficie, líneas y red.
    _caja(mundo, [15.5, 6.75, 0.014], [2.2, 1.05, 0.004], [0.20, 0.42, 0.62, 1])
    for y in (5.7, 7.8):
        _caja(mundo, [15.5, y, 0.02], [2.2, 0.025, 0.003], blanco)
    for x in (13.3, 17.7):
        _caja(mundo, [x, 6.75, 0.02], [0.025, 1.05, 0.003], blanco)
    _caja(mundo, [15.5, 6.75, 0.5], [0.02, 1.1, 0.5], [0.95, 0.95, 0.95, 0.6])

    # Restaurante: mesas con sillas y barra.
    for x, y in [(15.6, 1.1), (15.6, -1.1), (17.0, 1.1), (17.0, -1.1)]:
        _mesa(mundo, x, y, 0.3)
    _caja(mundo, [17.75, 0, 0.55], [0.2, 0.9, 0.55], [0.45, 0.33, 0.22, 1])

    # Gimnasio: caminadoras, banco, colchonetas y rack de pesas.
    for x in (6.9, 8.1, 9.9, 11.1):
        _caja(mundo, [x, -7.0, 0.12], [0.35, 0.7, 0.12], oscuro)
        _caja(mundo, [x, -7.75, 0.75], [0.35, 0.05, 0.5], [0.35, 0.35, 0.38, 1])
    _caja(mundo, [7.0, -5.6, 0.25], [0.6, 0.18, 0.25], [0.6, 0.1, 0.1, 1])
    _caja(mundo, [11.4, -5.6, 0.45], [0.2, 0.9, 0.45], [0.35, 0.35, 0.38, 1])
    for y in (-6.4, -5.6):
        _caja(mundo, [10.4, y, 0.01], [0.4, 0.3, 0.01], [0.25, 0.45, 0.70, 1])

    # Oficinas: escritorios, sillas, monitores y archivador.
    for x in (0.6, 3.4):
        _caja(mundo, [x, -6.9, 0.37], [0.75, 0.4, 0.02], [0.95, 0.95, 0.95, 1])
        _caja(mundo, [x, -6.9, 0.18], [0.7, 0.35, 0.18], [0.75, 0.75, 0.75, 1])
        _caja(mundo, [x, -7.15, 0.6], [0.3, 0.02, 0.18], oscuro)
        _caja(mundo, [x, -6.2, 0.25], [0.22, 0.22, 0.25], [0.15, 0.25, 0.45, 1])
    _caja(mundo, [4.2, -4.8, 0.6], [0.2, 0.4, 0.6], [0.6, 0.6, 0.62, 1])

    # Patio entre las habitaciones: jardineras con bancas, lejos de los pasillos.
    for x, y in [(5.5, 1.6), (5.5, -1.6), (10.8, 1.6), (10.8, -1.6), (-0.2, 1.6), (-0.2, -1.6)]:
        _planta(mundo, x, y)
        _caja(mundo, [x + 0.75, y, 0.22], [0.35, 0.18, 0.22], [0.55, 0.40, 0.25, 1])

    # Mantenimiento: estanterías, banco de trabajo y tanque.
    for x in (14.2, 16.8):
        _caja(mundo, [x, -7.65, 1.0], [0.9, 0.25, 1.0], [0.45, 0.47, 0.50, 1])
    _caja(mundo, [17.55, -5.7, 0.45], [0.35, 0.9, 0.45], [0.55, 0.40, 0.25, 1])
    _cilindro(mundo, [13.6, -5.6, 0.6], 0.38, 0.6, [0.75, 0.75, 0.78, 1])


def _agregar_club(spec: mujoco.MjSpec) -> None:
    mundo = spec.worldbody
    _materiales(spec)
    mundo.add_geom(name="piso", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[34, 34, 0.1],
                   pos=[4, 0, 0], material="exterior")
    # Interior del club (patio de pasillos) en baldosa.
    _caja(mundo, [4.25, 0, 0.001], [14.25, 9, 0.001], [1, 1, 1, 1], material="baldosa")

    for z in ZONAS.values():
        piso = PISO_ZONA[z.clave]
        extra = dict(material=piso) if isinstance(piso, str) else dict(rgba=piso)
        mundo.add_geom(name=f"zona_{z.clave}", type=CAJA,
                       size=[z.tamano[0] / 2, z.tamano[1] / 2, 0.005],
                       pos=[z.centro[0], z.centro[1], 0.005], **SIN_CHOQUE,
                       **({"rgba": [1, 1, 1, 1]} if isinstance(piso, str) else {}), **extra)
        if z.clave != "lobby":
            _habitacion(mundo, z)
        mundo.add_site(name=ascii(z.nombre), pos=[z.centro[0], z.centro[1], ALTO_MURO + 0.4],
                       size=[0.05, 0, 0], rgba=[0, 0, 0, 0.01])

    # Lobby: puerta principal al oeste y salida al pasillo por el este (y de -3 a 1.2).
    lobby = ZONAS["lobby"]
    x0 = lobby.centro[0] - lobby.tamano[0] / 2
    x1 = lobby.centro[0] + lobby.tamano[0] / 2
    _muro(mundo, (x0, 3.0), (x1, 3.0))
    _muro(mundo, (x0, -3.0), (x1, -3.0))
    _muro(mundo, (x1, 1.2), (x1, 3.0))

    # Pasillos (el de servicio, solo para personal y externos, en naranja: es la geocerca).
    for k, (a, b, permitido) in enumerate(TRAMOS):
        (xa, ya), (xb, yb) = NODOS[a], NODOS[b]
        yaw = math.atan2(yb - ya, xb - xa)
        servicio = permitido == SOLO_PERSONAL
        mundo.add_geom(name=f"pasillo_{k}{'_servicio' if servicio else ''}", type=CAJA,
                       size=[math.dist((xa, ya), (xb, yb)) / 2 + 0.3, 0.3, 0.003],
                       pos=[(xa + xb) / 2, (ya + yb) / 2, 0.004],
                       quat=[math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)],
                       rgba=[0.93, 0.72, 0.45, 1] if servicio else [0.80, 0.80, 0.77, 1],
                       **SIN_CHOQUE)
    mundo.add_site(name="Pasillo de servicio", pos=[10.8, -3.0, 0.3], size=[0.05, 0, 0],
                   rgba=[0, 0, 0, 0.01])

    # Muros del perímetro, con la puerta principal en la entrada.
    _muro(mundo, (-10.0, 9.0), (18.5, 9.0))
    _muro(mundo, (-10.0, -9.0), (18.5, -9.0))
    _muro(mundo, (18.5, -9.0), (18.5, 9.0))
    _muro(mundo, (-10.0, -9.0), (-10.0, 9.0), huecos=[(0.0, 2.8)])
    mundo.add_site(name="Entrada", pos=[ENTRADA[0], ENTRADA[1], ALTO_MURO + 0.3],
                   size=[0.05, 0, 0], rgba=[0, 0, 0, 0.01])

    _mobiliario(mundo)

    # Mostrador del X2 y tablero con el mapa del club.
    mundo.add_geom(name="mostrador", type=CAJA, size=[0.3, 0.9, 0.5],
                   pos=[POS_X2[0] + 0.6, POS_X2[1], 0.5], rgba=[0.45, 0.32, 0.22, 1],
                   **SIN_CHOQUE)
    mapa = mundo.add_body(name="mapa", pos=[POS_MAPA[0], POS_MAPA[1], 1.3])
    ancho = 28 * ESCALA_MAPA / 2  # el club va de x=-10 a x=18
    alto = 18 * ESCALA_MAPA / 2   # y de -9 a 9
    mapa.add_geom(name="tablero", type=CAJA, size=[0.02, ancho + 0.05, alto + 0.05],
                  rgba=[0.15, 0.15, 0.18, 1], **SIN_CHOQUE)
    mapa.add_geom(name="pata_mapa", type=CILINDRO, size=[0.03, 0.65, 0], pos=[0, 0, -0.65],
                  rgba=[0.2, 0.2, 0.2, 1], **SIN_CHOQUE)
    for z in ZONAS.values():
        # El tablero mira hacia la entrada (-x): el eje x del club queda sobre el eje -y del
        # tablero para que el visitante lo lea de izquierda a derecha.
        cy = -(z.centro[0] - 4) * ESCALA_MAPA
        cz = z.centro[1] * ESCALA_MAPA
        mapa.add_geom(name=f"mapa_{z.clave}", type=CAJA,
                      size=[0.005, z.tamano[0] / 2 * ESCALA_MAPA * 0.9,
                            z.tamano[1] / 2 * ESCALA_MAPA * 0.9],
                      pos=[-0.025, cy, cz], rgba=[*z.color, 1], **SIN_CHOQUE)
    mapa.add_site(name="Mapa", pos=[0, 0, alto + 0.15], size=[0.02, 0, 0],
                  rgba=[0, 0, 0, 0.01])

    # Recepción humana (el punto físico de atención): mostrador y operador.
    mundo.add_geom(name="mostrador_recepcion", type=CAJA, size=[0.8, 0.3, 0.5],
                   pos=[POS_RECEPCION[0], POS_RECEPCION[1], 0.5], rgba=[0.30, 0.35, 0.45, 1],
                   **SIN_CHOQUE)
    operador = mundo.add_body(name="operador", pos=[POS_RECEPCION[0], POS_RECEPCION[1] + 0.5, 0],
                              quat=[0.7071, 0, 0, -0.7071])
    _figura(operador, [0.15, 0.25, 0.45, 1])
    operador.add_site(name="Recepcion (humano)", pos=[0, 0, 2.0], size=[0.02, 0, 0],
                      rgba=[0, 0, 0, 0.01])

    # Barrera para cerrar un pasillo (se esconde bajo el piso cuando está abierto).
    barrera = mundo.add_body(name="barrera", pos=[0, 0, -5])
    barrera.add_freejoint(name="barrera_base")
    for lado in (-0.6, 0.6):
        barrera.add_geom(type=CILINDRO, size=[0.05, 0.5, 0], pos=[0, lado, 0.5],
                         rgba=[0.2, 0.2, 0.2, 1], **SIN_CHOQUE)
    for k, z in enumerate((0.75, 0.45)):
        barrera.add_geom(type=CAJA, size=[0.04, 0.6, 0.08], pos=[0, 0, z],
                         rgba=[0.9, 0.15, 0.1, 1] if k == 0 else [0.95, 0.95, 0.95, 1],
                         **SIN_CHOQUE)
    barrera.add_site(name="Pasillo cerrado", pos=[0, 0, 1.4], size=[0.02, 0, 0],
                     rgba=[0, 0, 0, 0.01])

    mundo.add_light(name="sol", pos=[4, -6, 14], dir=[0.15, 0.35, -1], diffuse=[0.55, 0.55, 0.52],
                    specular=[0.1, 0.1, 0.1], type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
                    castshadow=True)
    for z in ZONAS.values():   # luz cálida en cada habitación
        mundo.add_light(pos=[z.centro[0], z.centro[1], 3.2], dir=[0, 0, -1],
                        diffuse=[0.20, 0.19, 0.17], specular=[0, 0, 0], cutoff=75, exponent=3,
                        castshadow=False)


def _agregar_x2(spec: mujoco.MjSpec, ruta: Path) -> None:
    x2 = mujoco.MjSpec.from_file(str(ruta))
    for site in list(x2.sites):
        x2.delete(site)
    for light in list(x2.lights):
        x2.delete(light)
    marco = spec.worldbody.add_frame(pos=[POS_X2[0], POS_X2[1], 0], quat=[0, 0, 0, 1])
    pelvis = marco.attach_body(x2.body("pelvis"), "x2_", "")
    pelvis.add_site(name="X2 Ultra (simulado)", pos=[0, 0, 1.35], size=[0.02, 0, 0],
                    rgba=[0, 0, 0, 0.01])


# Modelo 3D del D1 Ultra (URDF de AgiBot con sus 17 piezas STL). Sin licencia declarada: vive en
# models/d1/, que no se sube al repositorio. Si no está, el D1 se arma con primitivas.
D1_URDF = Path(__file__).resolve().parent / "models" / "d1" / "urdf" / "ultra.urdf"
PATAS_D1 = {"dd": "FR", "di": "FL", "td": "RR", "ti": "RL"}   # delantera/trasera, derecha/izquierda


def _carga_d1(d1) -> None:
    """Lo que el D1 puede llevar en el lomo: la maleta de un VIP o la caja de herramientas de un
    externo. Empiezan invisibles; la animación las muestra."""
    d1.add_geom(name="d1_maleta", type=CAJA, size=[0.17, 0.11, 0.08], pos=[-0.02, 0, 0.15],
                rgba=[0.40, 0.25, 0.15, 0], **SIN_CHOQUE)
    d1.add_geom(name="d1_caja", type=CAJA, size=[0.15, 0.09, 0.06], pos=[-0.02, 0, 0.13],
                rgba=[0.80, 0.12, 0.10, 0], **SIN_CHOQUE)


def _agregar_d1_real(spec: mujoco.MjSpec) -> None:
    """D1 con su modelo real. Las articulaciones se renombran como las del D1 de primitivas
    (d1_<pata>_cadera / _rodilla, más _abduccion) para que la animación sirva para los dos."""
    d1_spec = mujoco.MjSpec.from_file(str(D1_URDF))
    carpeta = D1_URDF.parent
    for malla in d1_spec.meshes:      # rutas absolutas: al unirlo al club cambia la carpeta base
        malla.file = str((carpeta / malla.file).resolve())
    nombres = {f"{lado}_{junta}_JOINT": f"{pata}_{nuevo}" for pata, lado in PATAS_D1.items()
               for junta, nuevo in (("ABAD", "abduccion"), ("HIP", "cadera"), ("KNEE", "rodilla"))}
    for j in d1_spec.joints:
        j.name = nombres.get(j.name, j.name)
        j.limited = mujoco.mjtLimited.mjLIMITED_FALSE   # se anima por cinemática
    for g in d1_spec.geoms:
        g.contype = g.conaffinity = 0
        pieza = g.meshname.upper()
        g.rgba = ([0.08, 0.08, 0.09, 1] if "KNEE" in pieza or "FOOT" in pieza
                  else [0.78, 0.80, 0.83, 1] if "BASE" in pieza else [0.25, 0.27, 0.30, 1])
    d1 = spec.worldbody.add_body(name="d1", pos=[BASE_D1[0], BASE_D1[1], ALTO_D1_REAL])
    d1.add_freejoint(name="d1_base")
    d1.add_site(name="D1 Ultra (simulado)", pos=[0, 0, 0.35], size=[0.02, 0, 0],
                rgba=[0, 0, 0, 0.01])
    _carga_d1(d1)
    d1.add_frame().attach_body(d1_spec.body("base_link"), "d1_", "")


ALTO_D1_REAL = 0.31   # m del piso al cuerpo, de pie


def _agregar_d1(spec: mujoco.MjSpec) -> None:
    """D1 Edu armado con primitivas y sus medidas reales: 635 × 360 × 420 mm de pie."""
    if D1_URDF.exists():
        _agregar_d1_real(spec)
        return
    gris = [0.25, 0.27, 0.30, 1]
    negro = [0.08, 0.08, 0.09, 1]
    d1 = spec.worldbody.add_body(name="d1", pos=[BASE_D1[0], BASE_D1[1], 0.33])
    d1.add_freejoint(name="d1_base")
    d1.add_geom(name="d1_torso", type=CAJA, size=[0.24, 0.10, 0.06], rgba=gris, mass=10,
                **SIN_CHOQUE)
    d1.add_geom(name="d1_cabeza", type=CAJA, size=[0.05, 0.08, 0.045], pos=[0.27, 0, 0.03],
                rgba=negro, **SIN_CHOQUE)
    d1.add_geom(name="d1_ojos", type=CAJA, size=[0.005, 0.06, 0.012], pos=[0.32, 0, 0.04],
                rgba=[0.2, 0.8, 1.0, 1], **SIN_CHOQUE)
    d1.add_site(name="D1 (simulado)", pos=[0, 0, 0.35], size=[0.02, 0, 0], rgba=[0, 0, 0, 0.01])
    _carga_d1(d1)
    for nombre, x, y in [("dd", 0.19, -0.13), ("di", 0.19, 0.13), ("td", -0.19, -0.13),
                         ("ti", -0.19, 0.13)]:
        cadera = d1.add_body(name=f"d1_{nombre}_cadera", pos=[x, y, 0])
        cadera.add_joint(name=f"d1_{nombre}_cadera", axis=[0, 1, 0])
        cadera.add_geom(type=CILINDRO, size=[0.045, 0.03, 0], quat=[0.7071, 0.7071, 0, 0],
                        rgba=negro, **SIN_CHOQUE)
        cadera.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, 0, 0, 0, 0, -0.2],
                        size=[0.028, 0, 0], rgba=gris, **SIN_CHOQUE)
        rodilla = cadera.add_body(name=f"d1_{nombre}_rodilla", pos=[0, 0, -0.2])
        rodilla.add_joint(name=f"d1_{nombre}_rodilla", axis=[0, 1, 0])
        rodilla.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, 0, 0, 0, 0, -0.2],
                         size=[0.02, 0, 0], rgba=negro, **SIN_CHOQUE)
        rodilla.add_geom(type=ESFERA, size=[0.025, 0, 0], pos=[0, 0, -0.2], rgba=negro,
                         **SIN_CHOQUE)


def _figura(cuerpo, color) -> None:
    """Persona hecha con cápsulas: piernas, torso del color dado, brazos y cabeza."""
    for lado in (-0.09, 0.09):
        cuerpo.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, lado, 0.05, 0, lado, 0.85],
                        size=[0.06, 0, 0], rgba=[0.2, 0.2, 0.25, 1], **SIN_CHOQUE)
    cuerpo.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, 0, 0.95, 0, 0, 1.4],
                    size=[0.17, 0, 0], rgba=color, **SIN_CHOQUE)
    for lado in (-0.24, 0.24):
        cuerpo.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, lado, 1.42, 0, lado, 0.9],
                        size=[0.045, 0, 0], rgba=color, **SIN_CHOQUE)
    cuerpo.add_geom(type=ESFERA, size=[0.11, 0, 0], pos=[0, 0, 1.68],
                    rgba=[0.87, 0.72, 0.60, 1], **SIN_CHOQUE)


def _agregar_personas(spec: mujoco.MjSpec, personas: list[tuple[str, str | None]]) -> None:
    """Una figura por persona de la fila. El color indica su categoría real. La cámara vista_<i>
    está a la altura de sus ojos, mirando hacia adelante y un poco hacia abajo."""
    s, c = math.sin(INCLINACION_VISTA), math.cos(INCLINACION_VISTA)
    for i, (etiqueta, categoria) in enumerate(personas):
        p = spec.worldbody.add_body(name=f"persona_{i}", pos=[ENTRADA[0] - 2 - i, 0, 0])
        p.add_freejoint(name=f"persona_{i}_base")
        _figura(p, list(COLOR_CATEGORIA[categoria]))
        p.add_site(name=ascii(etiqueta), pos=[0, 0, 1.95], size=[0.02, 0, 0], rgba=[0, 0, 0, 0.01])
        p.add_camera(name=f"vista_{i}", pos=[0.13, 0, ALTO_OJOS], xyaxes=[0, -1, 0, s, 0, c],
                     fovy=65)


def construir(personas: list[tuple[str, str | None]]) -> mujoco.MjModel:
    ruta_x2 = Path(os.environ.get("X2_MODELO") or X2_MODELO_DEFECTO)
    if not ruta_x2.exists():
        raise FileNotFoundError(f"No encuentro el modelo del X2 en {ruta_x2}. "
                                "Pon la ruta de X2-Ultra.xml en X2_MODELO dentro del .env.")
    spec = mujoco.MjSpec()
    spec.modelname = "nclub"
    spec.option.timestep = 0.001     # igual al del X2, para que no avise al unirlos
    spec.option.gravity = [0, 0, 0]  # todo se anima por cinemática; no hay control de caminata
    spec.visual.global_.offwidth = 1600
    spec.visual.global_.offheight = 900
    spec.visual.quality.shadowsize = 4096
    spec.visual.headlight.ambient = [0.32, 0.32, 0.32]
    spec.visual.headlight.diffuse = [0.30, 0.30, 0.30]
    spec.visual.map.znear = 0.005
    spec.add_texture(name="cielo", type=mujoco.mjtTexture.mjTEXTURE_SKYBOX,
                     builtin=mujoco.mjtBuiltin.mjBUILTIN_GRADIENT, rgb1=[0.62, 0.78, 0.95],
                     rgb2=[0.95, 0.96, 0.98], width=512, height=512)
    _agregar_club(spec)
    _agregar_x2(spec, ruta_x2)
    _agregar_d1(spec)
    _agregar_personas(spec, personas)
    return spec.compile()
