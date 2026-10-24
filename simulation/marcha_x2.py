"""Caminata del X2 Ultra por cinemática inversa (los pies no resbalan). No es un controlador real:
sirve para animar al X2 en la simulación (patrullar el lobby, volver a su puesto) y en el video.
"""

import math

# Medidas de la pierna del X2 Ultra (de x2_ultra.xml v1.3.0).
MUSLO = 0.13685 + 0.1831     # cadera -> rodilla
CANILLA = 0.282              # rodilla -> tobillo
TOBILLO_SUELO = 0.078        # alto del tobillo con el pie apoyado
TOBILLO_ATRAS = 0.021        # el tobillo queda 2 cm detrás de la cadera con la pierna recta
CADERA_Y = 0.07135 + 0.0657  # separación lateral de cada cadera

ALTURA_PELVIS = 0.66         # rodillas un poco dobladas, como camina un humanoide
PERIODO = 0.9                # segundos por ciclo (dos pasos)
PASO = 0.28                  # metros por paso
LEVANTE = 0.07               # alto máximo del pie en el aire
VELOCIDAD = PASO / (PERIODO / 2)


def ik_pierna(dx: float, dz: float) -> tuple[float, float, float]:
    """Cadera, rodilla y tobillo (pitch) para llevar el tobillo a (dx, dz) desde la cadera,
    con el pie paralelo al piso. Pitch positivo lleva la pierna hacia atrás."""
    r = min(math.hypot(dx, dz), MUSLO + CANILLA - 1e-4)
    rodilla = math.pi - math.acos((MUSLO ** 2 + CANILLA ** 2 - r ** 2) / (2 * MUSLO * CANILLA))
    alfa = math.acos((MUSLO ** 2 + r ** 2 - CANILLA ** 2) / (2 * MUSLO * r))
    cadera = -(math.atan2(dx, -dz) + alfa)
    return cadera, rodilla, -(cadera + rodilla)


def pose_marcha(fase: float, rampa: float) -> tuple[dict[str, float], float, float, float]:
    """Articulaciones del X2 en la fase (0-1) del ciclo, con la zancada escalada por `rampa`
    (0 quieto, 1 andando). Devuelve (juntas, balanceo lateral, alto de la pelvis, giro)."""
    paso = PASO * rampa
    y_sway = 0.025 * math.sin(2 * math.pi * fase) * rampa
    z = ALTURA_PELVIS + 0.012 * math.cos(4 * math.pi * fase) * rampa
    giro = 0.03 * math.sin(2 * math.pi * fase) * rampa  # leve giro de cadera
    q = {}
    for lado, desfase in (("left", 0.0), ("right", 0.5)):
        f = (fase + desfase) % 1.0
        if f < 0.5:   # apoyo: el pie queda quieto en el piso mientras el cuerpo avanza
            s = f / 0.5
            dx = paso / 2 - paso * s
            alto = 0.0
        else:         # balanceo: el pie pasa adelante por el aire
            s = (f - 0.5) / 0.5
            suave = s * s * (3 - 2 * s)
            dx = -paso / 2 + paso * suave
            alto = LEVANTE * math.sin(math.pi * s) * rampa
        dz = -(z - TOBILLO_SUELO - alto)
        cadera, rodilla, tobillo = ik_pierna(dx + TOBILLO_ATRAS, dz)
        q[f"{lado}_hip_pitch_joint"] = cadera
        q[f"{lado}_knee_joint"] = rodilla
        q[f"{lado}_ankle_pitch_joint"] = tobillo
        # Compensa el balanceo lateral para que los pies sigan en su carril.
        q[f"{lado}_hip_roll_joint"] = -y_sway / (z - TOBILLO_SUELO)
        q[f"{lado}_ankle_roll_joint"] = y_sway / (z - TOBILLO_SUELO)
        q[f"{lado}_hip_yaw_joint"] = -giro
        # Brazos en contrafase con la pierna del mismo lado.
        brazo = 0.35 * math.sin(2 * math.pi * (f - 0.25)) * rampa
        signo = 1 if lado == "left" else -1
        q[f"{lado}_shoulder_pitch_joint"] = -brazo
        q[f"{lado}_shoulder_roll_joint"] = signo * 0.12
        q[f"{lado}_elbow_joint"] = -0.45 - 0.15 * max(0.0, -brazo)
    q["waist_yaw_joint"] = giro * 0.8
    q["waist_pitch_joint"] = 0.07 * rampa  # torso levemente hacia adelante
    return q, y_sway, z, giro
