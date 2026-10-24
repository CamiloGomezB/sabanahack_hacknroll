"""Prueba las protecciones del puente con el robot simulado."""
import subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from control_x2 import ClienteX2, ErrorX2

PY = sys.executable
PUENTE = str(Path(__file__).resolve().parent / "puente_x2.py")
PUERTO = 8797
NORMAL = {"modo": "STAND_DEFAULT", "accion_estado": 0, "fsm": 2, "postura": 1, "modo_velocidad": 1,
          "sistema": "Business", "sistema_estado": 1, "bateria": 80, "cargando": False, "marcha_s": 0,
          "alertas": [], "otra_fuente": None,
          "pared_x": None, "callado": []}
fallos = 0


def ok(cond, texto):
    global fallos
    print(("  OK   " if cond else "  FALLA") + " " + texto)
    fallos += not cond


p = subprocess.Popen([PY, PUENTE, "--simulado", "--puerto", str(PUERTO)], stdout=subprocess.DEVNULL)
for _ in range(50):
    try:
        x2 = ClienteX2(puerto=PUERTO); break
    except OSError:
        time.sleep(0.1)


def sim(**c):
    x2.orden("simular", cambios={**NORMAL, **c})


def rechaza(f, palabra):
    try:
        f(); return False
    except ErrorX2 as e:
        return palabra in str(e)


try:
    print("Antes de moverse (rechaza la orden):")
    casos = [
        ({"modo": "PASSIVE_DEFAULT"}, "modo PASSIVE_DEFAULT"),
        ({"accion_estado": 200}, "cambiando de modo"),
        ({"fsm": 4}, "SAFE"),
        ({"postura": 6}, "CAYENDO"),
        ({"postura": 4}, "sentado"),
        ({"modo_velocidad": 0}, "NONE"),
        ({"sistema": "EStop"}, "EStop"),
        ({"sistema_estado": 2}, "cambiando de modo"),
        ({"alertas": [52]}, "robot_sig 52"),
        ({"alertas": [19]}, "robot_sig 19"),
        ({"bateria": 28}, "batería en 28"),
        ({"cargando": True}, "cargando"),
        ({"marcha_s": 600}, "descanso"),
        ({"callado": ["movimiento"]}, "control de movimiento"),
        ({"callado": ["sistema"]}, "estado del sistema"),
        ({"callado": ["bateria"]}, "batería"),
        ({"callado": ["lidar"]}, "LiDAR"),
        ({"pared_x": 0.5}, "obstáculo"),
        ({"otra_fuente": "linkswarm"}, "Linkswarm"),
    ]
    for cambio, palabra in casos:
        sim(**cambio)
        ok(rechaza(lambda: x2.avanzar(1), palabra), f"{cambio} -> '{palabra}'")
    sim(alertas=[209])
    ok(x2.estado()["puede_caminar"], "alerta de cámara tapada (209) no bloquea")
    sim(callado=["lidar"])
    try:
        x2.girar(10); ok(True, "sin LiDAR sí puede girar en el sitio")
    except ErrorX2 as e:
        ok(False, f"sin LiDAR sí puede girar en el sitio ({e})")
    sim()
    ok(rechaza(lambda: x2.avanzar(-1), "atrás"), "retroceder más de 0.5 m se rechaza")
    ok(rechaza(lambda: x2.avanzar(6), "máximo"), "más de 5 m se rechaza")

    print("Durante el movimiento (se detiene):")
    durante = [
        ({"postura": 6}, "CAYENDO"),
        ({"fsm": 4}, "SAFE"),
        ({"alertas": [42]}, "robot_sig 42"),
        ({"sistema": "EStop"}, "EStop"),
        ({"callado": ["movimiento"]}, "control de movimiento"),
        ({"callado": ["lidar"]}, "LiDAR"),
        ({"otra_fuente": "rc"}, "rc tomó el mando"),
        ({"bateria": 10}, "batería"),
    ]
    for cambio, palabra in durante:
        sim()
        x2.avanzar(3, esperar=False); time.sleep(0.4)
        sim(**cambio); time.sleep(0.8)
        e = x2.estado()
        ok(e["accion"] == "quieto" and palabra in e["mensaje"], f"{cambio} -> {e['mensaje']}")
    # obstáculo que aparece delante mientras avanza
    sim()
    x0 = x2.estado()["x"]
    sim(pared_x=x0 + 1.2)
    x2.avanzar(3, esperar=False)
    e = x2.esperar()
    ok("obstáculo" in e["mensaje"] and e["x"] < x0 + 1.2 - 0.5, f"pared a 1.2 m: se detuvo en {e['x'] - x0:.2f} m ({e['mensaje']})")
    ok(rechaza(lambda: x2.avanzar(1), "obstáculo"), "con la pared delante no avanza")
    x2.avanzar(-0.3); ok(True, "pero sí puede retroceder")
    # mando manual: se acota a los límites
    sim()
    x2.velocidad(2.0, 0, 3.0); time.sleep(0.1)
    ok(True, "mando manual a 2 m/s se acota (ver límites)")
    x2.detener()
    # navegación: se cancela si falla algo
    sim()
    x2.navegar(1, 2.0, 1.0); time.sleep(0.3)
    ok(x2.estado()["accion"] == "navegando", "navegación en curso")
    sim(postura=6); time.sleep(0.3)
    e = x2.estado(); ok(e["accion"] == "quieto" and "navegación detenida" in e["mensaje"], f"caída durante la navegación -> {e['mensaje']}")
    sim(); x2.navegar(1, 2.0, 1.0); time.sleep(2.5)
    e = x2.estado(); ok(e["accion"] == "quieto" and "llegó" in e["mensaje"], f"navegación terminada -> {e['mensaje']}")
finally:
    x2.cerrar(); p.terminate(); p.wait()
print(f"\n{'TODO OK' if not fallos else f'{fallos} FALLAS'}")
