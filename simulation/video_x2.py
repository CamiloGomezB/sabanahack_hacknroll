"""Video del X2 Ultra caminando, grabado desde la espalda, sobre piso de madera laminada.

Es material para el video de presentación, no para las pruebas: la caminata es una animación por
cinemática inversa (los pies no resbalan), no un controlador real.

    python video_x2.py                        # 12 s a 40 fps en videos/x2_caminando.mp4
    python video_x2.py --segundos 20 --salida videos/otro.mp4
"""

import argparse
import math
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np
from PIL import Image

from escena import X2_MODELO_DEFECTO
from marcha_x2 import PERIODO, VELOCIDAD, pose_marcha

AQUI = Path(__file__).resolve().parent
TEXTURA_MADERA = AQUI / "texturas" / "madera_laminada.png"


def generar_madera(ruta: Path, lado: int = 2048, tablas: int = 12, semilla: int = 7) -> None:
    """Textura de madera laminada: tablas de roble con veta, tonos variados y juntas desfasadas.
    La imagen representa 2.4 × 2.4 m: 12 tablas de 20 cm de ancho y 1.2 m de largo."""
    rng = np.random.default_rng(semilla)
    v, u = np.mgrid[0:lado, 0:lado].astype(np.float32) / lado  # u: largo de la tabla
    fila = np.floor(v * tablas).astype(int)
    desfase = rng.uniform(0, 1, tablas)[fila]
    columna = np.floor(u * 2 + desfase).astype(int)
    id_tabla = fila * 3 + columna
    tono = rng.uniform(-0.09, 0.09, tablas * 3 + 3)[id_tabla]
    base = np.array([0.74, 0.55, 0.36], dtype=np.float32)

    # Veta: líneas a lo largo de la tabla, deformadas con ondas lentas.
    fase = rng.uniform(0, 100, tablas * 3 + 3)[id_tabla]
    ondas = (np.sin(u * 9 + fase) * 0.004 + np.sin(u * 23 + fase * 1.7) * 0.0015)
    veta = np.sin((v + ondas) * lado * 0.9 + fase) * 0.5 + 0.5
    veta = veta ** 3 * 0.10 + np.sin((v + ondas * 3) * lado * 0.13 + fase) * 0.025
    ruido = rng.normal(0, 0.012, (lado, lado)).astype(np.float32)
    brillo = 1 + tono - veta + ruido

    # Juntas oscuras entre tablas (a lo largo y en las cabeceras).
    borde_v = np.abs(v * tablas - np.round(v * tablas)) * lado / tablas
    borde_u = np.abs((u * 2 + desfase) - np.round(u * 2 + desfase)) * lado / 2
    junta = (borde_v < 1.5) | (borde_u < 1.5)
    brillo = np.where(junta, 0.55, brillo)

    rgb = np.clip(base[None, None, :] * brillo[..., None], 0, 1)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(ruta)


def construir() -> mujoco.MjModel:
    if not TEXTURA_MADERA.exists():
        generar_madera(TEXTURA_MADERA)
    spec = mujoco.MjSpec()
    spec.modelname = "x2_video"
    spec.option.timestep = 0.001
    spec.option.gravity = [0, 0, 0]
    spec.visual.global_.offwidth = 1920
    spec.visual.global_.offheight = 1080
    spec.visual.quality.shadowsize = 8192
    spec.visual.quality.offsamples = 8
    spec.visual.headlight.ambient = [0.25, 0.25, 0.25]
    spec.visual.headlight.diffuse = [0.35, 0.35, 0.35]
    spec.visual.map.znear = 0.01
    spec.visual.map.zfar = 80

    spec.add_texture(name="cielo", type=mujoco.mjtTexture.mjTEXTURE_SKYBOX,
                     builtin=mujoco.mjtBuiltin.mjBUILTIN_GRADIENT, rgb1=[0.95, 0.95, 0.97],
                     rgb2=[0.75, 0.77, 0.80], width=512, height=512)
    spec.add_texture(name="madera", type=mujoco.mjtTexture.mjTEXTURE_2D,
                     file=str(TEXTURA_MADERA))
    spec.add_material(name="madera", textures=["", "madera"], texuniform=True,
                      texrepeat=[1 / 2.4, 1 / 2.4], reflectance=0.05, shininess=0.4,
                      specular=0.35)
    spec.add_material(name="pared", rgba=[0.93, 0.92, 0.89, 1], specular=0.1)
    spec.add_material(name="zocalo", rgba=[0.97, 0.97, 0.97, 1])

    mundo = spec.worldbody
    mundo.add_geom(name="piso", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[40, 4, 0.1],
                   pos=[15, 0, 0], material="madera")
    # Pasillo: paredes, zócalo y columnas para que se note el avance.
    sin_choque = dict(contype=0, conaffinity=0)
    for lado in (-1, 1):
        mundo.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX, size=[40, 0.05, 1.6],
                       pos=[15, lado * 3.0, 1.6], material="pared", **sin_choque)
        mundo.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX, size=[40, 0.012, 0.05],
                       pos=[15, lado * 2.94, 0.05], material="zocalo", **sin_choque)
        for x in np.arange(-6, 50, 4.0):
            mundo.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.18, 0.12, 1.6],
                           pos=[x, lado * 2.88, 1.6], material="pared", **sin_choque)
    mundo.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.05, 3, 1.6], pos=[55, 0, 1.6],
                   material="pared", **sin_choque)
    for x in np.arange(-4, 52, 6.0):
        mundo.add_light(pos=[x, 0, 3.0], dir=[0, 0, -1], diffuse=[0.35, 0.34, 0.32],
                        specular=[0.1, 0.1, 0.1], cutoff=70, exponent=2,
                        castshadow=False)
    mundo.add_light(name="sol", pos=[0, 0, 6], dir=[0.25, 0.15, -1], diffuse=[0.55, 0.53, 0.5],
                    type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL, castshadow=True)

    x2 = mujoco.MjSpec.from_file(str(X2_MODELO_DEFECTO))
    for site in list(x2.sites):
        x2.delete(site)
    for light in list(x2.lights):
        x2.delete(light)
    mundo.add_frame().attach_body(x2.body("pelvis"), "x2_", "")
    return spec.compile()


class Caminata:
    def __init__(self, model: mujoco.MjModel, data: mujoco.MjData):
        self.m, self.d = model, data
        self.x = 0.0

    def q(self, junta: str, valor: float) -> None:
        self.d.qpos[self.m.joint(f"x2_{junta}").qposadr[0]] = valor

    def aplicar(self, t: float, dt: float) -> np.ndarray:
        # Arranca quieto y acelera en el primer segundo y medio.
        rampa = min(1.0, max(0.0, (t - 0.5) / 1.5))
        rampa = rampa * rampa * (3 - 2 * rampa)
        v = VELOCIDAD * rampa
        self.x += v * dt
        fase = (t / PERIODO) % 1.0

        juntas, y_sway, z, giro = pose_marcha(fase, rampa)
        a = self.m.joint("x2_floating_base_joint").qposadr[0]
        self.d.qpos[a:a + 3] = [self.x, y_sway, z]
        self.d.qpos[a + 3:a + 7] = [math.cos(giro / 2), 0, 0, math.sin(giro / 2)]
        for junta, valor in juntas.items():
            self.q(junta, valor)
        mujoco.mj_forward(self.m, self.d)
        return np.array([self.x, y_sway * 0.3, 0.0])


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("--segundos", type=float, default=12.0)
    args.add_argument("--fps", type=int, default=40)
    args.add_argument("--salida", type=Path, default=AQUI / "videos" / "x2_caminando.mp4")
    args.add_argument("--distancia", type=float, default=2.6, help="cámara detrás del X2 (m)")
    a = args.parse_args()

    model = construir()
    data = mujoco.MjData(model)
    caminata = Caminata(model, data)
    render = mujoco.Renderer(model, 1080, 1920)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.azimuth = 0          # mira hacia +x, la dirección en que camina
    cam.elevation = -14
    cam.distance = a.distancia
    opciones = mujoco.MjvOption()

    a.salida.parent.mkdir(parents=True, exist_ok=True)
    dt = 1 / a.fps
    cuadros = int(a.segundos * a.fps)
    mirada = None
    with imageio.get_writer(a.salida, fps=a.fps, codec="libx264", quality=9,
                            macro_block_size=8) as video:
        for n in range(cuadros):
            centro = caminata.aplicar(n * dt, dt) + [0, 0, 0.95]
            # Cámara de mano: sigue al robot con un poco de retraso y un vaivén suave.
            mirada = centro if mirada is None else mirada + (centro - mirada) * 0.15
            cam.lookat[:] = mirada + [0, 0, 0.01 * math.sin(n * dt * 2.1)]
            render.update_scene(data, cam, opciones)
            video.append_data(render.render())
            if n % a.fps == 0:
                print(f"{n / a.fps:4.0f} s / {a.segundos:.0f} s")
    print(f"Listo: {a.salida} ({cuadros} cuadros a {a.fps} fps)")


if __name__ == "__main__":
    main()
