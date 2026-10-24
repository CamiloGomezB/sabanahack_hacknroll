"""Arma el modelo de MuJoCo: club, X2 Ultra (modelo oficial de AgiBot), D1 y las personas."""

import math
import os
import unicodedata
from pathlib import Path

import mujoco
from dotenv import load_dotenv

from club import (BASE_D1, ENTRADA, NODOS, POS_MAPA, POS_RECEPCION, POS_X2, SOLO_PERSONAL,
                  TRAMOS, ZONAS)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Los archivos del X2 son de AgiBot y no van en el repo público: se leen desde la carpeta de la
# hackathon (o desde X2_MODELO en el .env).
X2_MODELO_DEFECTO = (Path.home() / "Desktop/Hackaton/Agibot X2-X2ultra-20261022T223240Z-1-001"
                     / "Agibot X2-X2ultra/X2_URDF/X2_URDF-v1.4.0/X2-Ultra.xml")

COLOR_CATEGORIA = {
    "vip": (0.95, 0.75, 0.15, 1),
    "regular": (0.20, 0.45, 0.90, 1),
    "personal": (0.20, 0.70, 0.35, 1),
    "invitado": (0.65, 0.35, 0.85, 1),
    "externo": (0.95, 0.50, 0.15, 1),
    None: (0.55, 0.55, 0.55, 1),
}

ESCALA_MAPA = 0.06  # metros del tablero por metro del club

_SIMBOLOS = {"¡": "", "¿": "", "…": "...", "→": "->", "–": "-", "—": "-", "·": "-", "×": "x"}


def ascii(texto: str) -> str:
    """La fuente de MuJoCo solo tiene ASCII: quita tildes y cambia los símbolos."""
    for k, v in _SIMBOLOS.items():
        texto = texto.replace(k, v)
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).encode("ascii", "ignore").decode()


def _agregar_club(spec: mujoco.MjSpec) -> None:
    mundo = spec.worldbody
    spec.add_texture(name="piso", type=mujoco.mjtTexture.mjTEXTURE_2D,
                     builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER, rgb1=[0.92, 0.92, 0.90],
                     rgb2=[0.86, 0.86, 0.84], width=512, height=512)
    spec.add_material(name="piso", textures=["", "piso"], texrepeat=[20, 20], reflectance=0.05)
    mundo.add_geom(name="piso", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[30, 30, 0.1],
                   pos=[4, 0, 0], material="piso")

    for z in ZONAS.values():
        mundo.add_geom(name=f"zona_{z.clave}", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[z.tamano[0] / 2, z.tamano[1] / 2, 0.005],
                       pos=[z.centro[0], z.centro[1], 0.005], rgba=[*z.color, 1],
                       contype=0, conaffinity=0)
        mundo.add_site(name=ascii(z.nombre), pos=[z.centro[0], z.centro[1] - z.tamano[1] / 2 + 0.3, 0.3],
                       size=[0.05, 0, 0], rgba=[0, 0, 0, 0.01])

    # Pasillos (el de servicio, solo para personal y externos, en naranja).
    for a, b, permitido in TRAMOS:
        (xa, ya), (xb, yb) = NODOS[a], NODOS[b]
        yaw = math.atan2(yb - ya, xb - xa)
        color = [0.93, 0.72, 0.45, 1] if permitido == SOLO_PERSONAL else [0.80, 0.80, 0.77, 1]
        mundo.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[math.dist((xa, ya), (xb, yb)) / 2 + 0.3, 0.3, 0.002],
                       pos=[(xa + xb) / 2, (ya + yb) / 2, 0.002],
                       quat=[math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)], rgba=color,
                       contype=0, conaffinity=0)
    mundo.add_site(name="Pasillo de servicio", pos=[10.8, -3.0, 0.3], size=[0.05, 0, 0],
                   rgba=[0, 0, 0, 0.01])

    # Muros bajos del perímetro, con la puerta en la entrada.
    muro = dict(type=mujoco.mjtGeom.mjGEOM_BOX, rgba=[0.75, 0.73, 0.70, 1], contype=0,
                conaffinity=0)
    for nombre, pos, size in [
        ("muro_n", [4, 9, 0.5], [14.5, 0.1, 0.5]),
        ("muro_s", [4, -9, 0.5], [14.5, 0.1, 0.5]),
        ("muro_e", [18.5, 0, 0.5], [0.1, 9, 0.5]),
        ("muro_o1", [-10, 5.2, 0.5], [0.1, 3.8, 0.5]),
        ("muro_o2", [-10, -5.2, 0.5], [0.1, 3.8, 0.5]),
    ]:
        mundo.add_geom(name=nombre, pos=pos, size=size, **muro)
    mundo.add_site(name="Entrada", pos=[ENTRADA[0], ENTRADA[1], 2.2], size=[0.05, 0, 0],
                   rgba=[0, 0, 0, 0.01])

    # Mostrador de recepción y tablero con el mapa del club.
    mundo.add_geom(name="mostrador", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.3, 0.9, 0.5],
                   pos=[POS_X2[0] + 0.6, POS_X2[1], 0.5], rgba=[0.45, 0.32, 0.22, 1],
                   contype=0, conaffinity=0)
    mapa = mundo.add_body(name="mapa", pos=[POS_MAPA[0], POS_MAPA[1], 1.3])
    ancho = 28 * ESCALA_MAPA / 2  # el club va de x=-10 a x=18
    alto = 18 * ESCALA_MAPA / 2   # y de -9 a 9
    mapa.add_geom(name="tablero", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.02, ancho + 0.05,
                  alto + 0.05], rgba=[0.15, 0.15, 0.18, 1], contype=0, conaffinity=0)
    mapa.add_geom(name="pata_mapa", type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.03, 0.65],
                  pos=[0, 0, -0.65], rgba=[0.2, 0.2, 0.2, 1], contype=0, conaffinity=0)
    for z in ZONAS.values():
        # El tablero mira hacia la entrada (-x): el eje x del club queda sobre el eje -y del
        # tablero para que el visitante lo lea de izquierda a derecha.
        cy = -(z.centro[0] - 4) * ESCALA_MAPA
        cz = z.centro[1] * ESCALA_MAPA
        mapa.add_geom(name=f"mapa_{z.clave}", type=mujoco.mjtGeom.mjGEOM_BOX,
                      size=[0.005, z.tamano[0] / 2 * ESCALA_MAPA * 0.9,
                            z.tamano[1] / 2 * ESCALA_MAPA * 0.9],
                      pos=[-0.025, cy, cz], rgba=[*z.color, 1], contype=0, conaffinity=0)
    mapa.add_site(name="Mapa", pos=[0, 0, alto + 0.15], size=[0.02, 0, 0],
                  rgba=[0, 0, 0, 0.01])

    # Recepción humana: mostrador y operador.
    mundo.add_geom(name="mostrador_recepcion", type=mujoco.mjtGeom.mjGEOM_BOX,
                   size=[0.8, 0.3, 0.5], pos=[POS_RECEPCION[0], POS_RECEPCION[1], 0.5],
                   rgba=[0.30, 0.35, 0.45, 1], contype=0, conaffinity=0)
    operador = mundo.add_body(name="operador", pos=[POS_RECEPCION[0], POS_RECEPCION[1] + 0.6, 0])
    _figura(operador, [0.15, 0.25, 0.45, 1])
    operador.add_site(name="Recepcion (humano)", pos=[0, 0, 2.0], size=[0.02, 0, 0],
                      rgba=[0, 0, 0, 0.01])

    # Barrera para cerrar un pasillo (se esconde bajo el piso cuando está abierto).
    barrera = mundo.add_body(name="barrera", pos=[0, 0, -5])
    barrera.add_freejoint(name="barrera_base")
    for lado in (-0.6, 0.6):
        barrera.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.05, 0.5], pos=[0, lado, 0.5],
                         rgba=[0.2, 0.2, 0.2, 1], contype=0, conaffinity=0)
    for k, z in enumerate((0.75, 0.45)):
        barrera.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.04, 0.6, 0.08], pos=[0, 0, z],
                         rgba=[0.9, 0.15, 0.1, 1] if k == 0 else [0.95, 0.95, 0.95, 1],
                         contype=0, conaffinity=0)
    barrera.add_site(name="Pasillo cerrado", pos=[0, 0, 1.4], size=[0.02, 0, 0],
                     rgba=[0, 0, 0, 0.01])

    mundo.add_light(name="sol", pos=[4, 0, 12], dir=[0, 0, -1], diffuse=[0.6, 0.6, 0.6],
                    type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL)


def _agregar_x2(spec: mujoco.MjSpec, ruta: Path) -> None:
    x2 = mujoco.MjSpec.from_file(str(ruta))
    for site in list(x2.sites):
        x2.delete(site)
    for light in list(x2.lights):
        x2.delete(light)
    marco = spec.worldbody.add_frame(pos=[POS_X2[0], POS_X2[1], 0], quat=[0, 0, 0, 1])
    marco.attach_body(x2.body("pelvis"), "x2_", "")
    spec.worldbody.add_site(name="X2 Ultra (simulado)", pos=[POS_X2[0], POS_X2[1], 2.0],
                            size=[0.02, 0, 0], rgba=[0, 0, 0, 0.01])


# Modelo 3D del D1 Ultra (URDF de AgiBot con sus 17 piezas STL). Sin licencia declarada: vive en
# models/d1/, que no se sube al repositorio. Si no está, el D1 se arma con primitivas.
D1_URDF = Path(__file__).resolve().parent / "models" / "d1" / "urdf" / "ultra.urdf"
PATAS_D1 = {"dd": "FR", "di": "FL", "td": "RR", "ti": "RL"}   # delantera/trasera, derecha/izquierda


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
    d1.add_frame().attach_body(d1_spec.body("base_link"), "d1_", "")


ALTO_D1_REAL = 0.31   # m del piso al cuerpo, de pie


def _agregar_d1(spec: mujoco.MjSpec) -> None:
    """D1 Edu armado con primitivas y sus medidas reales: 635 × 360 × 420 mm de pie."""
    if D1_URDF.exists():
        _agregar_d1_real(spec)
        return
    gris = [0.25, 0.27, 0.30, 1]
    negro = [0.08, 0.08, 0.09, 1]
    sin_choque = dict(contype=0, conaffinity=0)
    d1 = spec.worldbody.add_body(name="d1", pos=[BASE_D1[0], BASE_D1[1], 0.33])
    d1.add_freejoint(name="d1_base")
    d1.add_geom(name="d1_torso", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.24, 0.10, 0.06],
                rgba=gris, mass=10, **sin_choque)
    d1.add_geom(name="d1_cabeza", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.05, 0.08, 0.045],
                pos=[0.27, 0, 0.03], rgba=negro, **sin_choque)
    d1.add_geom(name="d1_ojos", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.005, 0.06, 0.012],
                pos=[0.32, 0, 0.04], rgba=[0.2, 0.8, 1.0, 1], **sin_choque)
    d1.add_site(name="D1 (simulado)", pos=[0, 0, 0.35], size=[0.02, 0, 0], rgba=[0, 0, 0, 0.01])
    for nombre, x, y in [("dd", 0.19, -0.13), ("di", 0.19, 0.13), ("td", -0.19, -0.13),
                         ("ti", -0.19, 0.13)]:
        cadera = d1.add_body(name=f"d1_{nombre}_cadera", pos=[x, y, 0])
        cadera.add_joint(name=f"d1_{nombre}_cadera", axis=[0, 1, 0])
        cadera.add_geom(type=mujoco.mjtGeom.mjGEOM_CYLINDER, size=[0.045, 0.03],
                        quat=[0.7071, 0.7071, 0, 0], rgba=negro, **sin_choque)
        cadera.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, 0, 0, 0, 0, -0.2],
                        size=[0.028, 0, 0], rgba=gris, **sin_choque)
        rodilla = cadera.add_body(name=f"d1_{nombre}_rodilla", pos=[0, 0, -0.2])
        rodilla.add_joint(name=f"d1_{nombre}_rodilla", axis=[0, 1, 0])
        rodilla.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, 0, 0, 0, 0, -0.2],
                         size=[0.02, 0, 0], rgba=negro, **sin_choque)
        rodilla.add_geom(type=mujoco.mjtGeom.mjGEOM_SPHERE, size=[0.025, 0, 0],
                         pos=[0, 0, -0.2], rgba=negro, **sin_choque)


def _figura(cuerpo, color) -> None:
    """Persona hecha con cápsulas: piernas, torso del color dado y cabeza."""
    sin_choque = dict(contype=0, conaffinity=0)
    for lado in (-0.09, 0.09):
        cuerpo.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, lado, 0.05, 0, lado, 0.85],
                        size=[0.06, 0, 0], rgba=[0.2, 0.2, 0.25, 1], **sin_choque)
    cuerpo.add_geom(type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, 0, 0.95, 0, 0, 1.4],
                    size=[0.17, 0, 0], rgba=color, **sin_choque)
    cuerpo.add_geom(type=mujoco.mjtGeom.mjGEOM_SPHERE, size=[0.11, 0, 0], pos=[0, 0, 1.68],
                    rgba=[0.87, 0.72, 0.60, 1], **sin_choque)


def _agregar_personas(spec: mujoco.MjSpec, personas: list[tuple[str, str | None]]) -> None:
    """Una figura por persona de la fila. El color indica su categoría real."""
    for i, (etiqueta, categoria) in enumerate(personas):
        p = spec.worldbody.add_body(name=f"persona_{i}", pos=[ENTRADA[0] - 2 - i, 0, 0])
        p.add_freejoint(name=f"persona_{i}_base")
        _figura(p, list(COLOR_CATEGORIA[categoria]))
        p.add_site(name=ascii(etiqueta), pos=[0, 0, 1.95], size=[0.02, 0, 0], rgba=[0, 0, 0, 0.01])


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
    _agregar_club(spec)
    _agregar_x2(spec, ruta_x2)
    _agregar_d1(spec)
    _agregar_personas(spec, personas)
    return spec.compile()
