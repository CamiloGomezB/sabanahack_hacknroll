"""Tres tomas para el video de presentación, en el mismo pasillo de madera de video_x2.py.

    python videos_presentacion.py d1        # D1 de frente guiando a una persona que lo sigue;
                                            #   la cámara retrocede a su paso
    python videos_presentacion.py saludo    # detrás del X2, a su izquierda: llega una persona y
                                            #   el X2 la saluda con la mano izquierda
    python videos_presentacion.py dos       # detrás del X2, centrada y alta: llegan dos personas
                                            #   y el X2 levanta los brazos para recibirlas
    python videos_presentacion.py pasa      # cámara fija a la derecha: el D1 viene por el
                                            #   pasillo y pasa de largo
    python videos_presentacion.py saludo --cuadros 0 3 6   # solo esos segundos como PNG, para revisar

Como video_x2.py, es animación cinemática (se escribe qpos y se llama mj_forward), no física.
"""

import argparse
import math
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np

from escena import _agregar_d1
from marcha_x2 import pose_marcha
from video_x2 import agregar_x2, pasillo

AQUI = Path(__file__).resolve().parent
SIN_CHOQUE = dict(contype=0, conaffinity=0)
CAPSULA = mujoco.mjtGeom.mjGEOM_CAPSULE


def suave(t: float, inicio: float, dur: float) -> float:
    """0 antes de `inicio`, 1 después de `inicio + dur`, con arranque y frenada suaves."""
    s = min(1.0, max(0.0, (t - inicio) / dur))
    return s * s * (3 - 2 * s)


def quat_yaw(yaw: float) -> list[float]:
    return [math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)]


def base(m: mujoco.MjModel, d: mujoco.MjData, junta: str, xyz, yaw: float) -> None:
    a = m.joint(junta).qposadr[0]
    d.qpos[a:a + 3] = xyz
    d.qpos[a + 3:a + 7] = quat_yaw(yaw)


def q(m: mujoco.MjModel, d: mujoco.MjData, junta: str, valor: float) -> None:
    d.qpos[m.joint(junta).qposadr[0]] = valor


# --- Personas articuladas (piernas y brazos con bisagra) -------------------------------------

ALTO_CADERA, MUSLO_P, CANILLA_P = 0.92, 0.46, 0.44
ROPA = [([0.13, 0.27, 0.45, 1], [0.18, 0.18, 0.22, 1], [0.82, 0.66, 0.54, 1]),
        ([0.62, 0.20, 0.22, 1], [0.25, 0.22, 0.20, 1], [0.60, 0.45, 0.35, 1]),
        ([0.85, 0.78, 0.62, 1], [0.15, 0.20, 0.30, 1], [0.90, 0.75, 0.62, 1])]


def agregar_persona(spec: mujoco.MjSpec, i: int, ropa) -> None:
    camisa, pantalon, piel = ropa
    p = spec.worldbody.add_body(name=f"p{i}", pos=[0, 0, 0])
    p.add_freejoint(name=f"p{i}_base")
    p.add_geom(type=CAPSULA, fromto=[0, 0, 0.98, 0, 0, 1.36], size=[0.16, 0, 0], rgba=camisa,
               **SIN_CHOQUE)
    p.add_geom(type=CAPSULA, fromto=[0, 0, 1.5, 0, 0, 1.56], size=[0.05, 0, 0], rgba=piel,
               **SIN_CHOQUE)
    p.add_geom(type=mujoco.mjtGeom.mjGEOM_ELLIPSOID, size=[0.10, 0.09, 0.12], pos=[0.01, 0, 1.67],
               rgba=piel, **SIN_CHOQUE)
    p.add_geom(type=mujoco.mjtGeom.mjGEOM_ELLIPSOID, size=[0.105, 0.095, 0.07],
               pos=[-0.01, 0, 1.73], rgba=[0.12, 0.08, 0.06, 1], **SIN_CHOQUE)
    for lado, y in (("i", 0.095), ("d", -0.095)):
        muslo = p.add_body(name=f"p{i}_muslo_{lado}", pos=[0, y, ALTO_CADERA])
        muslo.add_joint(name=f"p{i}_cadera_{lado}", axis=[0, 1, 0])
        muslo.add_geom(type=CAPSULA, fromto=[0, 0, 0, 0, 0, -MUSLO_P], size=[0.065, 0, 0],
                       rgba=pantalon, **SIN_CHOQUE)
        canilla = muslo.add_body(name=f"p{i}_canilla_{lado}", pos=[0, 0, -MUSLO_P])
        canilla.add_joint(name=f"p{i}_rodilla_{lado}", axis=[0, 1, 0])
        canilla.add_geom(type=CAPSULA, fromto=[0, 0, 0, 0, 0, -CANILLA_P + 0.04],
                         size=[0.052, 0, 0], rgba=pantalon, **SIN_CHOQUE)
        canilla.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.11, 0.045, 0.03],
                         pos=[0.05, 0, -CANILLA_P + 0.03], rgba=[0.1, 0.1, 0.1, 1], **SIN_CHOQUE)
        brazo = p.add_body(name=f"p{i}_brazo_{lado}", pos=[0, 2.15 * y, 1.4])
        brazo.add_joint(name=f"p{i}_hombro_{lado}", axis=[0, 1, 0])
        brazo.add_geom(type=CAPSULA, fromto=[0, 0, 0, 0, 0, -0.52], size=[0.045, 0, 0],
                       rgba=camisa, **SIN_CHOQUE)
        brazo.add_geom(type=mujoco.mjtGeom.mjGEOM_SPHERE, size=[0.045, 0, 0], pos=[0, 0, -0.57],
                       rgba=piel, **SIN_CHOQUE)


class Persona:
    """Camina en línea recta de `desde` a `hasta` (x, y) y se detiene, con frenada suave."""
    FRECUENCIA = 0.85  # ciclos (dos pasos) por segundo

    def __init__(self, i: int, desde, hasta, salida: float, velocidad: float = 1.05):
        self.i = i
        self.desde, self.hasta = np.array(desde, float), np.array(hasta, float)
        self.salida, self.v = salida, velocidad
        self.largo = float(np.linalg.norm(self.hasta - self.desde))
        self.dir = (self.hasta - self.desde) / self.largo
        self.yaw = math.atan2(self.dir[1], self.dir[0])
        self.recorrido, self.fase = 0.0, 0.0

    def aplicar(self, m, d, t: float, dt: float) -> None:
        falta = self.largo - self.recorrido
        andar = suave(t, self.salida, 0.6) * min(1.0, falta / 0.8)
        self.recorrido = min(self.largo, self.recorrido + self.v * max(andar, 0.15 * (falta > 0.01)) * dt)
        self.fase += dt * 2 * math.pi * self.FRECUENCIA * max(andar, 0.3 if falta > 0.01 else 0)
        self.pose(m, d, self.desde + self.dir * self.recorrido, andar)

    def pose(self, m, d, xy, andar: float) -> None:
        amplitud = 0.38 * andar
        n = self.i
        for lado, desfase in (("i", 0.0), ("d", math.pi)):
            s = math.sin(self.fase + desfase)
            balanceo = math.cos(self.fase + desfase)
            # Cadera positiva lleva la pierna hacia atrás (eje +y del cuerpo).
            q(m, d, f"p{n}_cadera_{lado}", -amplitud * s)
            q(m, d, f"p{n}_rodilla_{lado}", amplitud * 1.6 * max(0.0, balanceo))
            q(m, d, f"p{n}_hombro_{lado}", amplitud * 0.8 * s)
        rebote = 0.015 * abs(math.sin(self.fase)) * andar
        base(m, d, f"p{n}_base", [xy[0], xy[1], rebote], self.yaw)


# --- X2 parado con gestos de brazos -----------------------------------------------------------

def x2_parado(m, d, xy, yaw: float, brazos: dict[str, float], waist: dict[str, float] | None = None):
    juntas, _, z, _ = pose_marcha(0.0, 0.0)
    juntas.update(waist or {})
    juntas.update(brazos)
    base(m, d, "x2_floating_base_joint", [xy[0], xy[1], z], yaw)
    for junta, valor in juntas.items():
        q(m, d, f"x2_{junta}", valor)


REPOSO = {"left_shoulder_pitch_joint": 0.0, "left_shoulder_roll_joint": 0.12,
          "left_shoulder_yaw_joint": 0.0, "left_elbow_joint": -0.45,
          "right_shoulder_pitch_joint": 0.0, "right_shoulder_roll_joint": -0.12,
          "right_shoulder_yaw_joint": 0.0, "right_elbow_joint": -0.45}
# Espejo de POSE_SALUDO (animacion.py), que es del brazo derecho.
SALUDO_IZQ = {"left_shoulder_roll_joint": 1.3, "left_shoulder_yaw_joint": 1.5,
              "left_elbow_joint": -1.5}
# Brazos adelante y un poco abiertos, como para recibir una caja: un gesto de bienvenida.
RECIBIR = {"left_shoulder_pitch_joint": -0.7, "right_shoulder_pitch_joint": -0.7,
           "left_shoulder_roll_joint": 0.22, "right_shoulder_roll_joint": -0.22,
           "left_elbow_joint": -0.95, "right_elbow_joint": -0.95,
           "left_shoulder_yaw_joint": 0.0, "right_shoulder_yaw_joint": 0.0}


def mezclar(a: dict, b: dict, k: float) -> dict:
    return {j: a.get(j, 0.0) + (b.get(j, a.get(j, 0.0)) - a.get(j, 0.0)) * k
            for j in set(a) | set(b)}


# --- Las tres tomas ---------------------------------------------------------------------------

class TroteD1:
    """Trote del D1 por pares diagonales con los pies apoyados quietos en el piso (cinemática
    inversa de cada pata), para cualquier posición y rumbo."""
    FRECUENCIA = 2.0
    MUSLO, PIERNA, PIE = 0.20, 0.21, 0.025

    def __init__(self, m: mujoco.MjModel, d: mujoco.MjData):
        self.m, self.d = m, d
        real = any(m.joint(j).name == "d1_dd_abduccion" for j in range(m.njnt))
        if not real:
            self.MUSLO, self.PIERNA, self.PIE = 0.20, 0.20, 0.0
        cadera, rodilla = (0.8, -1.6) if real else (0.6, -1.2)
        self.alto = (self.MUSLO * math.cos(cadera) + self.PIERNA * math.cos(cadera + rodilla)
                     + self.PIE)
        self.fase = 0.0

    def ik(self, dx: float, dz: float) -> tuple[float, float]:
        """Cadera y rodilla para poner el pie en (dx, dz) desde la cadera. Cadera positiva lleva
        la pata hacia atrás; la rodilla dobla en negativo, como en animacion.py."""
        l1, l2 = self.MUSLO, self.PIERNA
        r = min(math.hypot(dx, dz), l1 + l2 - 1e-4)
        rodilla = -math.acos(max(-1.0, min(1.0, (r * r - l1 * l1 - l2 * l2) / (2 * l1 * l2))))
        beta = math.atan2(l2 * math.sin(rodilla), l1 + l2 * math.cos(rodilla))
        return math.atan2(-dx, -dz) - beta, rodilla

    def aplicar(self, xy, yaw: float, v: float, rampa: float, dt: float) -> None:
        self.fase = (self.fase + dt * self.FRECUENCIA) % 1.0
        zancada = v / self.FRECUENCIA / 2   # lo que avanza el cuerpo mientras el pie está apoyado
        for pata, desfase in (("dd", 0.0), ("ti", 0.0), ("di", 0.5), ("td", 0.5)):
            f = (self.fase + desfase) % 1.0
            if f < 0.5:   # apoyo: el pie se queda en el piso y el cuerpo avanza
                dx, alto = zancada / 2 - zancada * (f / 0.5), 0.0
            else:         # vuelo: la pata vuelve adelante por el aire
                s = (f - 0.5) / 0.5
                dx = -zancada / 2 + zancada * s * s * (3 - 2 * s)
                alto = 0.055 * math.sin(math.pi * s) * rampa
            cadera, rodilla = self.ik(dx, -(self.alto - self.PIE - alto))
            q(self.m, self.d, f"d1_{pata}_cadera", cadera)
            q(self.m, self.d, f"d1_{pata}_rodilla", rodilla)
        rebote = 0.006 * math.cos(4 * math.pi * self.fase) * rampa
        base(self.m, self.d, "d1_base", [xy[0], xy[1], self.alto + rebote], yaw)


class TomaD1:
    nombre, salida = "d1_de_frente", "d1_de_frente.mp4"
    VELOCIDAD = 0.8
    DETRAS = 1.45   # distancia de la persona que sigue al D1

    def __init__(self):
        spec = pasillo("d1_video")
        _agregar_d1(spec)
        agregar_persona(spec, 0, ROPA[0])
        self.m = spec.compile()
        self.d = mujoco.MjData(self.m)
        self.trote = TroteD1(self.m, self.d)
        self.x = 0.0
        self.mirada = None
        self.persona = Persona(0, (0, 0), (1, 0), salida=0)

    def cuadro(self, t: float, dt: float, cam: mujoco.MjvCamera) -> None:
        rampa = suave(t, 0.6, 1.4)
        v = self.VELOCIDAD * rampa
        self.x += v * dt
        self.trote.aplicar((self.x, 0.0), 0.0, v, rampa, dt)

        # La persona va detrás, al mismo paso: el D1 la está guiando. Arranca un poco después.
        andar = suave(t, 0.9, 1.4)
        self.persona.fase += dt * 2 * math.pi * (self.VELOCIDAD / 1.25) * andar
        self.persona.pose(self.m, self.d, (self.x - self.DETRAS - 0.25 * (1 - andar), -0.05), andar)
        mujoco.mj_forward(self.m, self.d)

        # De frente al D1: la cámara mira hacia -x y retrocede a su paso, con un poco de retraso.
        # Abierta para que entren el D1 y la persona que lo sigue.
        centro = np.array([self.x - 0.75, 0.0, 0.62])
        self.mirada = centro if self.mirada is None else self.mirada + (centro - self.mirada) * 0.12
        cam.azimuth, cam.elevation, cam.distance = 180, -11, 3.3
        cam.lookat[:] = self.mirada + [0, 0, 0.004 * math.sin(t * 2.3)]


class TomaSaludo:
    nombre, salida = "x2_saluda", "x2_saluda.mp4"
    X2 = (0.0, 0.0)

    def __init__(self):
        spec = pasillo("x2_saludo")
        agregar_x2(spec)
        agregar_persona(spec, 0, ROPA[0])
        self.m = spec.compile()
        self.d = mujoco.MjData(self.m)
        self.persona = Persona(0, (8.5, -0.15), (1.35, -0.1), salida=0.4)

    def cuadro(self, t: float, dt: float, cam: mujoco.MjvCamera) -> None:
        self.persona.aplicar(self.m, self.d, t, dt)
        subir = suave(t, 5.6, 0.7) * (1 - suave(t, 9.6, 0.8))
        brazos = mezclar(REPOSO, SALUDO_IZQ, subir)
        brazos["left_shoulder_yaw_joint"] += 0.35 * math.sin((t - 5.6) * 9) * suave(t, 6.1, 0.3) \
            * (1 - suave(t, 9.2, 0.4))
        x2_parado(self.m, self.d, self.X2, 0.0, brazos)
        mujoco.mj_forward(self.m, self.d)

        # Fija, detrás del X2 y corrida hacia su izquierda (+y, porque mira hacia +x).
        cam.azimuth, cam.elevation, cam.distance = -17, -8, 4.3
        cam.lookat[:] = [1.0, 0.05, 0.95]


class TomaDos:
    nombre, salida = "x2_recibe_dos", "x2_recibe_dos.mp4"
    X2 = (0.0, 0.0)

    def __init__(self):
        spec = pasillo("x2_dos")
        agregar_x2(spec)
        agregar_persona(spec, 0, ROPA[1])
        agregar_persona(spec, 1, ROPA[2])
        self.m = spec.compile()
        self.d = mujoco.MjData(self.m)
        self.personas = [Persona(0, (8.8, 0.42), (1.45, 0.42), salida=0.3),
                         Persona(1, (8.8, -0.42), (1.45, -0.42), salida=0.3, velocidad=1.02)]

    def cuadro(self, t: float, dt: float, cam: mujoco.MjvCamera) -> None:
        for p in self.personas:
            p.aplicar(self.m, self.d, t, dt)
        subir = suave(t, 5.4, 1.1) * (1 - suave(t, 10.2, 1.0))
        brazos = mezclar(REPOSO, RECIBIR, subir)
        x2_parado(self.m, self.d, self.X2, 0.0, brazos,
                  waist={"waist_pitch_joint": 0.06 * subir})
        mujoco.mj_forward(self.m, self.d)

        # Fija, detrás del X2, centrada y desde arriba.
        cam.azimuth, cam.elevation, cam.distance = 0, -16, 4.4
        cam.lookat[:] = [1.5, 0.0, 1.0]


class TomaPasa:
    """Solo el D1, con la cámara fija a su altura y a la derecha de su camino: viene por el
    pasillo, pasa al lado de la cámara y sale de cuadro."""
    nombre, salida = "d1_pasa", "d1_pasa.mp4"
    DESDE, Y_D1, VELOCIDAD = 8.6, -0.85, 1.0

    def __init__(self):
        spec = pasillo("d1_pasa")
        _agregar_d1(spec)
        self.m = spec.compile()
        self.d = mujoco.MjData(self.m)
        self.trote = TroteD1(self.m, self.d)
        self.x = self.DESDE

    def cuadro(self, t: float, dt: float, cam: mujoco.MjvCamera) -> None:
        rampa = suave(t, 0.3, 1.0)
        v = self.VELOCIDAD * rampa
        self.x -= v * dt
        self.trote.aplicar((self.x, self.Y_D1), math.pi, v, rampa, dt)
        mujoco.mj_forward(self.m, self.d)

        # Fija, a ras de piso (a la altura del D1) y a la derecha de su camino, cerca, para que
        # se vea grande al pasar. Queda en (-0.8, -1.55, 0.31) mirando hacia el fondo del pasillo.
        cam.azimuth, cam.elevation, cam.distance = 12, -0.5, 3.9
        cam.lookat[:] = [3.0, -0.75, 0.28]


TOMAS = {"d1": TomaD1, "saludo": TomaSaludo, "dos": TomaDos, "pasa": TomaPasa}


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("toma", choices=TOMAS)
    args.add_argument("--segundos", type=float, default=12.0)
    args.add_argument("--fps", type=int, default=40)
    args.add_argument("--salida", type=Path)
    args.add_argument("--cuadros", type=float, nargs="*",
                      help="en vez del video, guarda PNG de estos segundos (para revisar)")
    a = args.parse_args()

    toma = TOMAS[a.toma]()
    salida = a.salida or AQUI / "videos" / toma.salida
    render = mujoco.Renderer(toma.m, 1080, 1920)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    opciones = mujoco.MjvOption()
    dt = 1 / a.fps
    cuadros = int(a.segundos * a.fps)
    salida.parent.mkdir(parents=True, exist_ok=True)

    if a.cuadros is not None:
        pedidos = {int(round(s * a.fps)) for s in a.cuadros}
        for n in range(max(pedidos) + 1):
            toma.cuadro(n * dt, dt, cam)
            if n in pedidos:
                render.update_scene(toma.d, cam, opciones)
                png = salida.with_name(f"{salida.stem}_{n / a.fps:05.2f}s.png")
                imageio.imwrite(png, render.render())
                print(png)
        return

    with imageio.get_writer(salida, fps=a.fps, codec="libx264", quality=9,
                            macro_block_size=8) as video:
        for n in range(cuadros):
            toma.cuadro(n * dt, dt, cam)
            render.update_scene(toma.d, cam, opciones)
            video.append_data(render.render())
            if n % a.fps == 0:
                print(f"{n / a.fps:4.0f} s / {a.segundos:.0f} s")
    print(f"Listo: {salida} ({cuadros} cuadros a {a.fps} fps)")


if __name__ == "__main__":
    main()
