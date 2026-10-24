"""Animación cinemática: se escribe qpos directamente (sin física) y se llama mj_forward."""

import math

import mujoco
import numpy as np

import marcha_x2
from club import BASE_D1, NODOS, POS_X2, TRAMO_BLOQUEABLE, ZONAS

# Poses del X2 (calibradas con capturas). En su puesto el X2 mira hacia -x, así que su brazo
# derecho queda del lado +y, donde está el mapa.
POSE_NEUTRA = {
    "right_shoulder_roll_joint": -0.1, "left_shoulder_roll_joint": 0.1,
    "right_elbow_joint": -0.3, "left_elbow_joint": -0.3,
}
POSE_SALUDO = {"right_shoulder_roll_joint": -1.3, "right_shoulder_yaw_joint": -1.5,
               "right_elbow_joint": -1.5}
POSE_SENALAR = {"right_shoulder_roll_joint": -1.45, "right_shoulder_pitch_joint": -0.35,
                "right_elbow_joint": -0.05, "head_yaw_joint": -0.34}
# El X2 Ultra no tiene cabeceo de cabeza: para mirar a la persona inclina un poco la cintura
POSE_ESCANEAR = {"waist_pitch_joint": 0.12}

# Límites del X2 Ultra (manual de AimDK, 1.7.3). El modelo v1.3.0 trae la junta head_pitch, pero
# en el Ultra solo se mueve el giro de la cabeza (±20°); el cabeceo es de la versión nueva.
LIMITES_ULTRA = {"head_yaw_joint": (-0.349, 0.349), "head_pitch_joint": (0.0, 0.0)}

ALTO_X2 = 0.68          # pelvis del X2 de pie
YAW_PUESTO = math.pi    # en su puesto mira hacia la entrada

# Patas del D1 (muslo, pierna) para calcular el alto del cuerpo: de pie y agachado.
PATAS_D1_REAL = dict(muslo=0.20, pierna=0.21, pie=0.025, de_pie=(0.8, -1.6), agachado=(1.25, -2.5))
PATAS_D1_PRIM = dict(muslo=0.20, pierna=0.20, pie=0.0, de_pie=(0.6, -1.2), agachado=(1.1, -2.2))


def _quat_yaw(yaw: float) -> np.ndarray:
    return np.array([math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)])


def _angulo(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


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
        self._rango_x2 = {}   # ninguna pose ni gesto pasa los límites de las juntas del Ultra
        for j in range(model.njnt):
            nombre = model.joint(j).name
            if nombre.startswith("x2_") and model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE:
                self._qx2[nombre[3:]] = model.jnt_qposadr[j]
                self._rango_x2[nombre[3:]] = LIMITES_ULTRA.get(nombre[3:], tuple(model.jnt_range[j]))
        self.x2_actual = {k: 0.0 for k in self._qx2}
        self.x2_objetivo = dict(POSE_NEUTRA)
        self.x2_extra = {}  # oscilaciones (saludar, negar) que se suman a la pose
        # El X2 camina: posición, orientación y fase de la marcha.
        self.x2_xy = np.array(POS_X2, dtype=float)
        self.x2_yaw = self.x2_yaw_objetivo = YAW_PUESTO
        self.x2_andando = False
        self.x2_rampa = 0.0          # 0 quieto, 1 andando a paso normal
        self.x2_fase = 0.0
        self.x2_alto = ALTO_X2
        self.x2_buscando = False     # mueve la cabeza buscando a quién recibir

        self.d1_xy = np.array(BASE_D1, dtype=float)
        self.d1_yaw = math.pi / 2
        self.d1_fase = 0.0
        self.d1_andando = False
        self.d1_real = any(model.joint(j).name == "d1_dd_abduccion" for j in range(model.njnt))
        self.d1_agachado = 0.0       # 0 de pie, 1 agachado (para recibir o entregar la carga)
        self.d1_agachar = 0.0
        self.d1_carga = None         # "maleta" | "caja" | None
        self._carga = {c: model.geom(f"d1_{c}").id for c in ("maleta", "caja")}

        self.personas = [{"xy": np.array([-30.0, i]), "yaw": 0.0, "fase": 0.0, "andando": False}
                         for i in range(n_personas)]
        self._mapa_geoms = {z: model.geom(f"mapa_{z}").id for z in ZONAS}
        self._mapa_rgba = {z: model.geom_rgba[g].copy() for z, g in self._mapa_geoms.items()}
        self._servicio = [g for g in range(model.ngeom)
                          if (model.geom(g).name or "").endswith("_servicio")]
        self._servicio_rgba = model.geom_rgba[self._servicio[0]].copy() if self._servicio else None
        self.zona_resaltada = None
        self.geocerca = False    # resalta el pasillo de servicio (externo acompañado)
        self.bloqueado = False   # pasillo central cerrado (tecla B)
        self.t = 0.0

    # --- escritura en qpos --------------------------------------------------------------------
    def _base(self, junta: str, xy, z: float, yaw: float) -> None:
        a = self.m.joint(junta).qposadr[0]
        self.d.qpos[a:a + 3] = [xy[0], xy[1], z]
        self.d.qpos[a + 3:a + 7] = _quat_yaw(yaw)

    def _aplicar_x2(self, dt: float) -> None:
        objetivo_rampa = 1.0 if self.x2_andando else 0.0
        self.x2_rampa += (objetivo_rampa - self.x2_rampa) * min(1.0, dt * 3)
        self.x2_yaw += _angulo(self.x2_yaw_objetivo - self.x2_yaw) * min(1.0, dt * 4)
        alfa = 1 - math.exp(-dt * 6)
        for nombre in self._qx2:
            objetivo = self.x2_objetivo.get(nombre, 0.0)
            self.x2_actual[nombre] += (objetivo - self.x2_actual[nombre]) * alfa
        sway, giro = 0.0, 0.0
        if self.x2_rampa > 0.02:
            self.x2_fase = (self.x2_fase + dt / marcha_x2.PERIODO) % 1.0
            juntas, sway, z, giro = marcha_x2.pose_marcha(self.x2_fase, self.x2_rampa)
            for nombre, valor in juntas.items():
                # La marcha manda sobre la pose; al detenerse, la pose vuelve sola.
                previo = self.x2_actual[nombre]
                self.x2_actual[nombre] = previo + (valor - previo) * min(1.0, self.x2_rampa * 4)
            self.x2_alto = z
        else:
            self.x2_alto += (ALTO_X2 - self.x2_alto) * alfa
        if self.x2_buscando:
            self.x2_extra = {"head_yaw_joint": 0.34 * math.sin(self.t * 1.1)}
        for nombre, adr in self._qx2.items():
            bajo, alto = self._rango_x2[nombre]
            valor = self.x2_actual[nombre] + self.x2_extra.get(nombre, 0.0)
            self.d.qpos[adr] = min(max(valor, bajo), alto)
        c, s = math.cos(self.x2_yaw), math.sin(self.x2_yaw)
        xy = self.x2_xy + np.array([-s, c]) * sway
        self._base("x2_floating_base_joint", xy, self.x2_alto, self.x2_yaw + giro)

    def _aplicar_d1(self, dt: float) -> None:
        # Trote con pares diagonales en contrafase; para recibir o entregar algo se agacha.
        if self.d1_andando:
            self.d1_fase += dt * 2 * math.pi * 2.2
        self.d1_agachado += (self.d1_agachar - self.d1_agachado) * min(1.0, dt * 3)
        p = PATAS_D1_REAL if self.d1_real else PATAS_D1_PRIM
        k = self.d1_agachado
        cadera = p["de_pie"][0] + (p["agachado"][0] - p["de_pie"][0]) * k
        rodilla = p["de_pie"][1] + (p["agachado"][1] - p["de_pie"][1]) * k
        base = (p["muslo"] * math.cos(cadera) + p["pierna"] * math.cos(cadera + rodilla)
                + p["pie"])
        for pata, desfase in [("dd", 0), ("ti", 0), ("di", math.pi), ("td", math.pi)]:
            s = math.sin(self.d1_fase + desfase) if self.d1_andando else 0.0
            self.d.qpos[self.m.joint(f"d1_{pata}_cadera").qposadr[0]] = cadera + 0.35 * s
            self.d.qpos[self.m.joint(f"d1_{pata}_rodilla").qposadr[0]] = rodilla - 0.4 * max(s, 0)
        alto = base + (0.01 * abs(math.sin(self.d1_fase)) if self.d1_andando else 0)
        self._base("d1_base", self.d1_xy, alto, self.d1_yaw)
        for carga, g in self._carga.items():
            self.m.geom_rgba[g][3] = 1.0 if self.d1_carga == carga else 0.0

    def aplicar(self, dt: float) -> None:
        self.t += dt
        self._aplicar_x2(dt)
        self._aplicar_d1(dt)

        for i, p in enumerate(self.personas):
            if p["andando"]:
                p["fase"] += dt * 2 * math.pi * 1.8
            z = 0.02 * abs(math.sin(p["fase"])) if p["andando"] else 0.0
            self._base(f"persona_{i}_base", p["xy"], z, p["yaw"])

        (xa, ya), (xb, yb) = NODOS[TRAMO_BLOQUEABLE[0]], NODOS[TRAMO_BLOQUEABLE[1]]
        medio = ((xa + xb) / 2, (ya + yb) / 2)
        # Abierto: la barrera se guarda lejos (bajo el piso se seguiría viendo su etiqueta).
        self._base("barrera_base", medio if self.bloqueado else (-60.0, -60.0),
                   0.0 if self.bloqueado else -5.0, math.atan2(yb - ya, xb - xa))

        # Zona resaltada en el mapa: parpadea. Geocerca: el pasillo de servicio pulsa.
        for z, g in self._mapa_geoms.items():
            rgba = self._mapa_rgba[z].copy()
            if z == self.zona_resaltada and int(self.t * 4) % 2 == 0:
                rgba[:3] = 1.0
            self.m.geom_rgba[g] = rgba
        for g in self._servicio:
            rgba = self._servicio_rgba.copy()
            if self.geocerca:
                brillo = 0.5 + 0.5 * math.sin(self.t * 5)
                rgba[:3] = rgba[:3] * (1 - brillo) + np.array([1.0, 0.35, 0.1]) * brillo
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

    def x2_caminar(self, puntos):
        """El X2 camina por la ruta (arranca y frena suave) mirando hacia donde va."""
        ruta = Ruta([tuple(self.x2_xy)] + list(puntos))
        s = 0.0
        self.x2_andando = True
        try:
            while s < ruta.largo:
                s += marcha_x2.VELOCIDAD * max(self.x2_rampa, 0.15) * self._dt
                self.x2_xy, yaw = ruta.en(s)
                self.x2_yaw_objetivo = yaw
                yield
        finally:
            self.x2_andando = False

    def x2_girar(self, yaw: float, segundos: float = 0.8):
        self.x2_yaw_objetivo = yaw
        yield from self.esperar(segundos)

    def d1_agacharse(self, agachado: bool, segundos: float = 1.0):
        self.d1_agachar = 1.0 if agachado else 0.0
        yield from self.esperar(segundos)

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
