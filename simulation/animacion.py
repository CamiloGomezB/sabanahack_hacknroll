"""Animación cinemática: se escribe qpos directamente (sin física) y se llama mj_forward."""

import math

import mujoco
import numpy as np

from club import BASE_D1, NODOS, POS_X2, TRAMO_BLOQUEABLE, ZONAS

# Poses del X2 (calibradas con capturas). El X2 mira hacia -x, así que su brazo derecho queda
# del lado +y, donde está el mapa.
POSE_NEUTRA = {
    "right_shoulder_roll_joint": -0.1, "left_shoulder_roll_joint": 0.1,
    "right_elbow_joint": -0.3, "left_elbow_joint": -0.3,
}
POSE_SALUDO = {"right_shoulder_roll_joint": -1.3, "right_shoulder_yaw_joint": -1.5,
               "right_elbow_joint": -1.5}
POSE_SENALAR = {"right_shoulder_roll_joint": -1.45, "right_shoulder_pitch_joint": -0.35,
                "right_elbow_joint": -0.05, "head_yaw_joint": -0.45}
POSE_ESCANEAR = {"head_pitch_joint": 0.15}


def _quat_yaw(yaw: float) -> np.ndarray:
    return np.array([math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)])


class Ruta:
    """Polilínea recorrida por longitud de arco."""

    def __init__(self, puntos):
        self.p = np.array(puntos, dtype=float)
        tramos = np.linalg.norm(np.diff(self.p, axis=0), axis=1)
        self.acum = np.concatenate([[0], np.cumsum(tramos)])
        self.largo = float(self.acum[-1])

    def en(self, s: float) -> tuple[np.ndarray, float]:
        s = min(max(s, 0.0), self.largo)
        i = min(int(np.searchsorted(self.acum, s, side="right")) - 1, len(self.p) - 2)
        tramo = self.p[i + 1] - self.p[i]
        n = np.linalg.norm(tramo)
        t = 0.0 if n == 0 else (s - self.acum[i]) / n
        return self.p[i] + t * tramo, math.atan2(tramo[1], tramo[0])


class Mundo:
    def __init__(self, model: mujoco.MjModel, data: mujoco.MjData, n_personas: int):
        self.m, self.d = model, data
        self._qx2 = {}
        for j in range(model.njnt):
            nombre = model.joint(j).name
            if nombre.startswith("x2_") and model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE:
                self._qx2[nombre[3:]] = model.jnt_qposadr[j]
        self.x2_actual = {k: 0.0 for k in self._qx2}
        self.x2_objetivo = dict(POSE_NEUTRA)
        self.x2_extra = {}  # oscilaciones (saludar, negar) que se suman a la pose

        self.d1_xy = np.array(BASE_D1, dtype=float)
        self.d1_yaw = math.pi / 2
        self.d1_fase = 0.0
        self.d1_andando = False
        self.d1_real = any(model.joint(j).name == "d1_dd_abduccion" for j in range(model.njnt))

        self.personas = [{"xy": np.array([-30.0, i]), "yaw": 0.0, "fase": 0.0, "andando": False}
                         for i in range(n_personas)]
        self._mapa_geoms = {z: model.geom(f"mapa_{z}").id for z in ZONAS}
        self._mapa_rgba = {z: model.geom_rgba[g].copy() for z, g in self._mapa_geoms.items()}
        self.zona_resaltada = None
        self.bloqueado = False   # pasillo central cerrado (tecla B)
        self.t = 0.0

    # --- escritura en qpos --------------------------------------------------------------------
    def _base(self, junta: str, xy, z: float, yaw: float) -> None:
        a = self.m.joint(junta).qposadr[0]
        self.d.qpos[a:a + 3] = [xy[0], xy[1], z]
        self.d.qpos[a + 3:a + 7] = _quat_yaw(yaw)

    def aplicar(self, dt: float) -> None:
        self.t += dt
        # X2: fijo en la recepción, articulaciones suavizadas hacia la pose objetivo.
        self._base("x2_floating_base_joint", POS_X2, 0.68, math.pi)
        alfa = 1 - math.exp(-dt * 6)
        for nombre, adr in self._qx2.items():
            objetivo = self.x2_objetivo.get(nombre, 0.0)
            self.x2_actual[nombre] += (objetivo - self.x2_actual[nombre]) * alfa
            self.d.qpos[adr] = self.x2_actual[nombre] + self.x2_extra.get(nombre, 0.0)

        # D1: trote con pares diagonales en contrafase. Pose de pie del modelo real (muslo 0.20 m,
        # pierna 0.21 m: cadera 0.8 y rodilla -1.6 dejan el cuerpo a 0.31 m) o del de primitivas.
        if self.d1_andando:
            self.d1_fase += dt * 2 * math.pi * 2.2
        cadera, rodilla, base = (0.8, -1.6, 0.31) if self.d1_real else (0.6, -1.2, 0.33)
        for pata, desfase in [("dd", 0), ("ti", 0), ("di", math.pi), ("td", math.pi)]:
            s = math.sin(self.d1_fase + desfase) if self.d1_andando else 0.0
            self.d.qpos[self.m.joint(f"d1_{pata}_cadera").qposadr[0]] = cadera + 0.35 * s
            self.d.qpos[self.m.joint(f"d1_{pata}_rodilla").qposadr[0]] = rodilla - 0.4 * max(s, 0)
        alto = base + (0.01 * abs(math.sin(self.d1_fase)) if self.d1_andando else 0)
        self._base("d1_base", self.d1_xy, alto, self.d1_yaw)

        for i, p in enumerate(self.personas):
            if p["andando"]:
                p["fase"] += dt * 2 * math.pi * 1.8
            z = 0.02 * abs(math.sin(p["fase"])) if p["andando"] else 0.0
            self._base(f"persona_{i}_base", p["xy"], z, p["yaw"])

        (xa, ya), (xb, yb) = NODOS[TRAMO_BLOQUEABLE[0]], NODOS[TRAMO_BLOQUEABLE[1]]
        medio = ((xa + xb) / 2, (ya + yb) / 2)
        self._base("barrera_base", medio, 0.0 if self.bloqueado else -5.0,
                   math.atan2(yb - ya, xb - xa))

        # Zona resaltada en el mapa: parpadea.
        for z, g in self._mapa_geoms.items():
            rgba = self._mapa_rgba[z].copy()
            if z == self.zona_resaltada and int(self.t * 4) % 2 == 0:
                rgba[:3] = 1.0
            self.m.geom_rgba[g] = rgba

        mujoco.mj_forward(self.m, self.d)

    # --- acciones (generadores que avanzan un paso por cuadro) ----------------------------------
    def esperar(self, segundos: float):
        fin = self.t + segundos
        while self.t < fin:
            yield

    def pose_x2(self, pose: dict, segundos: float):
        self.x2_objetivo = {**POSE_NEUTRA, **pose}
        yield from self.esperar(segundos)

    def saludar(self, segundos: float = 2.5):
        self.x2_objetivo = {**POSE_NEUTRA, **POSE_SALUDO}
        inicio = self.t
        while self.t - inicio < segundos:
            self.x2_extra = {"right_shoulder_yaw_joint": 0.35 * math.sin((self.t - inicio) * 9)}
            yield
        self.x2_extra = {}
        self.x2_objetivo = dict(POSE_NEUTRA)

    def negar(self, segundos: float = 2.0):
        inicio = self.t
        while self.t - inicio < segundos:
            self.x2_extra = {"head_yaw_joint": 0.35 * math.sin((self.t - inicio) * 8)}
            yield
        self.x2_extra = {}

    def senalar_mapa(self, zona: str, segundos: float = 3.0):
        self.zona_resaltada = zona
        yield from self.pose_x2(POSE_SENALAR, segundos)
        self.x2_objetivo = dict(POSE_NEUTRA)
        self.zona_resaltada = None

    def caminar(self, i: int, puntos, velocidad: float = 1.3):
        p = self.personas[i]
        ruta = Ruta([tuple(p["xy"])] + list(puntos))
        s = 0.0
        p["andando"] = True
        while s < ruta.largo:
            s += velocidad * self._dt
            p["xy"], p["yaw"] = ruta.en(s)
            yield
        p["andando"] = False

    DISTANCIA_GUIA = 1.2

    def punto_de_encuentro(self, i: int, puntos) -> np.ndarray:
        """Dónde se para el guía para empezar: un poco adelante de la persona en la ruta."""
        return Ruta([tuple(self.personas[i]["xy"])] + list(puntos)).en(self.DISTANCIA_GUIA)[0]

    def seguir(self, i: int, inicio_guia, puntos, avance, guiando):
        """La persona camina detrás del guía por su misma ruta, a DISTANCIA_GUIA metros.
        `avance()` son los metros que lleva el guía desde `inicio_guia`; `guiando()` si sigue."""
        p = self.personas[i]
        ruta = Ruta([tuple(p["xy"]), tuple(inicio_guia)] + list(puntos))
        ventaja = float(np.linalg.norm(np.array(inicio_guia) - p["xy"]))
        s = 0.0
        p["andando"] = True
        while True:
            objetivo = min(ventaja + avance() - self.DISTANCIA_GUIA, ruta.largo)
            s = max(s, min(objetivo, s + 1.6 * self._dt))
            p["xy"], p["yaw"] = ruta.en(s)
            if not guiando() and s >= objetivo - 1e-3:
                break
            yield
        p["andando"] = False

    _dt = 1 / 60  # lo ajusta el ciclo principal
