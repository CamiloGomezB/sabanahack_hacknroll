"""Tomas para la presentación dentro del club de la simulación (mismo plano que main.py).

    python videos_club.py recepcion   # desde la esquina alta del lobby: llega una persona, el X2
                                      #   le habla moviendo las manos; recepcionista y D1 al fondo
    python videos_club.py entrega     # a la altura del D1: el D1 deja a la persona en la puerta
                                      #   de la Sala VIP, ella entra y el D1 gira y se va
    python videos_club.py entrega --cuadros 2 6 10   # solo PNG de esos segundos, para revisar

Animación cinemática (qpos + mj_forward), como videos_presentacion.py.
"""

import argparse
import math
import os
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np

from club import BASE_D1, ENTRADA, NODOS, POS_VISITANTE, POS_X2, ZONAS
from escena import X2_MODELO_DEFECTO, _agregar_club, _agregar_d1, _agregar_x2
from videos_presentacion import (REPOSO, ROPA, Persona, TroteD1, agregar_persona, mezclar,
                                 suave, x2_parado)

AQUI = Path(__file__).resolve().parent


def club(personas: int) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """El club de escena.construir(), pero con personas articuladas y calidad de video."""
    spec = mujoco.MjSpec()
    spec.modelname = "nclub_video"
    spec.option.timestep = 0.001
    spec.option.gravity = [0, 0, 0]
    spec.visual.global_.offwidth = 1920
    spec.visual.global_.offheight = 1080
    spec.visual.quality.shadowsize = 8192
    spec.visual.quality.offsamples = 8
    spec.visual.headlight.ambient = [0.32, 0.32, 0.32]
    spec.visual.headlight.diffuse = [0.30, 0.30, 0.30]
    spec.visual.map.znear = 0.005
    spec.add_texture(name="cielo", type=mujoco.mjtTexture.mjTEXTURE_SKYBOX,
                     builtin=mujoco.mjtBuiltin.mjBUILTIN_GRADIENT, rgb1=[0.62, 0.78, 0.95],
                     rgb2=[0.95, 0.96, 0.98], width=512, height=512)
    _agregar_club(spec)
    _agregar_x2(spec, Path(os.environ.get("X2_MODELO") or X2_MODELO_DEFECTO))
    _agregar_d1(spec)
    for i in range(personas):
        agregar_persona(spec, i, ROPA[i])
    m = spec.compile()
    return m, mujoco.MjData(m)


def mirar(cam: mujoco.MjvCamera, desde, hacia) -> None:
    """Pone la cámara libre en `desde` mirando a `hacia`."""
    d = np.array(hacia, float) - np.array(desde, float)
    cam.lookat[:] = hacia
    cam.distance = float(np.linalg.norm(d))
    cam.azimuth = math.degrees(math.atan2(d[1], d[0]))
    cam.elevation = math.degrees(math.asin(d[2] / cam.distance))


def _angulo(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


class Movil:
    """Recorre tramos rectos que arrancan a una hora dada. Si el siguiente tramo va en otra
    dirección, primero se detiene y gira en el lugar; frena suave al llegar a cada punto."""

    def __init__(self, xy, yaw: float, vmax: float, acel: float = 1.1, giro: float = 2.0):
        self.p, self.yaw, self.v = np.array(xy, float), yaw, 0.0
        self.vmax, self.acel, self.giro = vmax, acel, giro
        self.tramos: list[tuple[float, np.ndarray, float | None]] = []
        self.k = 0
        self.girando = False

    def ir(self, t0: float, xy, yaw_final: float | None = None) -> "Movil":
        self.tramos.append((t0, np.array(xy, float), yaw_final))
        return self

    def _girar_hacia(self, rumbo: float, dt: float) -> float:
        err = _angulo(rumbo - self.yaw)
        self.yaw += max(-self.giro * dt, min(self.giro * dt, err))
        return err

    def paso(self, t: float, dt: float) -> None:
        self.girando = False
        if self.k >= len(self.tramos) or t < self.tramos[self.k][0]:
            self.v = 0.0
            return
        _, destino, yaw_final = self.tramos[self.k]
        delta = destino - self.p
        dist = float(np.linalg.norm(delta))
        if dist < 0.004:
            self.v = 0.0
            if yaw_final is not None and abs(self._girar_hacia(yaw_final, dt)) > 0.02:
                self.girando = True
                return
            self.k += 1
            return
        rumbo = math.atan2(delta[1], delta[0])
        if self.v < 0.05 and abs(_angulo(rumbo - self.yaw)) > 0.3:
            self._girar_hacia(rumbo, dt)
            self.girando = True
            return
        self._girar_hacia(rumbo, dt)
        self.v = max(0.08, min(self.vmax, self.v + self.acel * dt, math.sqrt(2 * self.acel * dist)))
        self.p += delta / dist * min(self.v * dt, dist)

    @property
    def andar(self) -> float:
        return self.v / self.vmax


def animar_persona(persona: Persona, movil: Movil, m, d, dt: float) -> None:
    andar = max(movil.andar, 0.35 if movil.girando else 0.0)
    if andar > 0.01:
        persona.fase += dt * 2 * math.pi * (movil.vmax / 1.25 if not movil.girando else 0.9)
    persona.yaw = movil.yaw
    persona.pose(m, d, movil.p, andar)


def animar_d1(trote: TroteD1, movil: Movil) -> tuple:
    rampa = max(movil.andar, 0.6 if movil.girando else 0.0)
    return movil.p, movil.yaw, movil.v, rampa


# Brazos del X2 mientras habla: adelante y doblados, con movimientos de "explicar".
HABLAR = {"left_shoulder_pitch_joint": -0.55, "right_shoulder_pitch_joint": -0.55,
          "left_shoulder_roll_joint": 0.25, "right_shoulder_roll_joint": -0.25,
          "left_elbow_joint": -1.25, "right_elbow_joint": -1.25,
          "left_shoulder_yaw_joint": 0.0, "right_shoulder_yaw_joint": 0.0}


def gesto_hablar(t: float, k: float) -> dict[str, float]:
    brazos = mezclar(REPOSO, HABLAR, k)
    osc = {
        "left_shoulder_pitch_joint": 0.18 * math.sin(2.1 * t) + 0.07 * math.sin(5.3 * t),
        "right_shoulder_pitch_joint": 0.18 * math.sin(2.1 * t + 1.9) + 0.07 * math.sin(4.1 * t + 0.5),
        "left_elbow_joint": 0.25 * math.sin(3.0 * t + 0.4),
        "right_elbow_joint": 0.25 * math.sin(2.6 * t + 2.0),
        "left_shoulder_yaw_joint": 0.3 * math.sin(1.7 * t),
        "right_shoulder_yaw_joint": -0.3 * math.sin(1.7 * t + 0.8),
        "waist_yaw_joint": 0.05 * math.sin(0.9 * t),
        "head_yaw_joint": 0.07 * math.sin(1.3 * t + 0.3),
    }
    for junta, valor in osc.items():
        brazos[junta] = brazos.get(junta, 0.0) + valor * k
    for codo in ("left_elbow_joint", "right_elbow_joint"):
        brazos[codo] = min(brazos[codo], 0.0)
    return brazos


class TomaRecepcion:
    salida = "club_recepcion.mp4"

    def __init__(self):
        self.m, self.d = club(personas=1)
        self.persona = Persona(0, (0, 0), (1, 0), salida=0)
        self.movil = Movil((ENTRADA[0] + 0.4, 0.0), 0.0, vmax=1.0).ir(0.4, POS_VISITANTE)
        self.trote = TroteD1(self.m, self.d)

    def cuadro(self, t: float, dt: float, cam: mujoco.MjvCamera) -> None:
        self.movil.paso(t, dt)
        animar_persona(self.persona, self.movil, self.m, self.d, dt)
        # El X2 habla desde que la persona llega hasta casi el final.
        k = suave(t, 5.2, 0.8) * (1 - suave(t, 11.6, 0.8))
        x2_parado(self.m, self.d, POS_X2, math.pi, gesto_hablar(t, k),
                  waist={"waist_pitch_joint": 0.04 * k})
        self.trote.aplicar(BASE_D1, math.pi / 2, 0.0, 0.0, dt)
        mujoco.mj_forward(self.m, self.d)

        # Desde lo alto del muro sur del lobby: el X2 de frente (se le ven las manos), la persona,
        # la recepcionista a un lado y el D1 en su base.
        mirar(cam, (-7.8, -2.85, 3.3), (-5.3, 0.3, 0.75))


class TomaEntrega:
    salida = "club_entrega.mp4"
    PUERTA = ZONAS["sala_vip"].entrada          # (2.0, 4.5): puerta de la Sala VIP
    Y = NODOS["n1"][1]                          # pasillo norte, y = 3

    def __init__(self):
        self.m, self.d = club(personas=1)
        self.m.vis.global_.fovy = 56     # más abierta: cámara cerca del D1 sin cortar a la persona
        self.trote = TroteD1(self.m, self.d)
        x = self.PUERTA[0]
        self.d1 = (Movil((x - 3.3, self.Y), 0.0, vmax=0.9)
                   .ir(0.3, (x + 0.85, self.Y))
                   .ir(8.6, (x - 3.6, self.Y)))      # gira en el lugar y se va
        self.persona = Persona(0, (0, 0), (1, 0), salida=0)
        self.movil = (Movil((x - 4.6, self.Y), 0.0, vmax=0.9)
                      .ir(0.5, (x, self.Y))
                      .ir(0.5, (x, self.PUERTA[1] + 1.1))
                      .ir(0.5, (x + 1.6, self.PUERTA[1] + 1.4)))   # sigue hacia adentro

    def cuadro(self, t: float, dt: float, cam: mujoco.MjvCamera) -> None:
        self.d1.paso(t, dt)
        self.trote.aplicar(*animar_d1(self.trote, self.d1), dt)
        self.movil.paso(t, dt)
        animar_persona(self.persona, self.movil, self.m, self.d, dt)
        x2_parado(self.m, self.d, POS_X2, math.pi, REPOSO)
        mujoco.mj_forward(self.m, self.d)

        # A ras de piso (altura del D1), de frente a la puerta.
        x = self.PUERTA[0]
        mirar(cam, (x, 0.5, 0.33), (x, self.Y + 1.0, 0.5))


TOMAS = {"recepcion": TomaRecepcion, "entrega": TomaEntrega}


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("toma", choices=TOMAS)
    args.add_argument("--segundos", type=float, default=13.0)
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

    cuadros = int(a.segundos * a.fps)
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
