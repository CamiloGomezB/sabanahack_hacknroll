#!/usr/bin/env python3
"""Puente de control a distancia del AgiBot X2 Ultra.

Corre en la unidad de desarrollo del robot (PC2, 10.0.1.41). Solo usa funciones que ya trae AimDK
y deja la caminata, el equilibrio y las protecciones al propio robot:

Órdenes al robot
- `/aima/mc/locomotion/velocity` (McLocomotionVelocity): se le pide una velocidad, como en el
  ejemplo 6.1.10; el control de movimiento del robot decide cómo caminar.
- `/aimdk_5Fmsgs/srv/SetMcInputSource`: registra nuestra fuente de entrada "sdk_anfitrion_remoto"
  con prioridad 30 (rango de desarrollo 20-39), por debajo de la app (60) y del control remoto (80):
  si alguien toma el control remoto, el robot le hace caso a él y no a nosotros.
- `/aima/te/pnc_task_request` (PncTaskRequest): navegación propia del robot (ejemplo 6.1.30).

Lo que se vigila antes y durante cada movimiento (si algo falla o deja de llegar, se detiene)
- `/aima/mc/common/state`: modo (STAND_DEFAULT / LOCOMOTION_DEFAULT), que no esté cambiando de modo,
  máquina de estados (STABLE / MOVING; SAFE = protección activa), postura (de pie; no caída),
  modo y límites de velocidad del robot, y quién tiene el mando.
- `/aima/sm/system_state`: modo del sistema (Business) y estado (listo). Así se respeta EStop, OTA,
  apagado por batería baja, etc.
- `/aima/hds/post_proc/signal`: alertas de diagnóstico que restringen el movimiento (parada de
  emergencia, protección por caída, sobretemperatura, ...).
- `/aima/hal/pmu/state`: batería y si está cargando (el manual prohíbe operarlo mientras carga).
- `/aima/hal/sensor/lidar_chest_front/lidar_pointcloud`: obstáculos al frente. La velocidad directa
  no esquiva nada, así que el puente frena si hay algo cerca delante.
- `/slam/lidar_odom`: posición (solo si el robot está relocalizado en un mapa).
- `/aima/pnc/pnc_task_response`: cómo va la navegación del robot (en curso, terminó, falló).

Si falta cualquiera de esos datos, el puente no mueve el robot (falla cerrado). Además: AimDK lo
detiene si pasan 200 ms sin velocidad; el mando manual dura 0,5 s; si el portátil pasa 1 s sin
enviar nada o se cae la conexión, se detiene; velocidades, distancias y tiempos están limitados.

Protocolo: una línea JSON por orden sobre TCP (puerto 8765, solo en 127.0.0.1; desde el portátil se
llega con un túnel SSH). Órdenes: estado, avanzar, girar, velocidad, detener, navegar,
cancelar_navegacion (y simular, solo con --simulado).

    python3 puente_x2.py              # en el robot, con ROS 2 y AimDK
    python3 puente_x2.py --simulado   # en cualquier computador, sin robot
"""

import argparse
import json
import math
import signal
import socketserver
import threading
import time

FRECUENCIA = 50.0  # Hz, la que recomienda AimDK para la velocidad
FUENTE = "sdk_anfitrion_remoto"  # prefijo sdk_, como pide AimDK para no chocar con rc, app_proxy, ...
PRIORIDAD_FUENTE = 30  # rango de desarrollo (20-39): la app (60) y el control remoto (80) mandan más
TIMEOUT_FUENTE_MS = 1000

LIMITES = {
    "adelante": 0.5,  # m/s (el modo de velocidad LOW del robot admite hasta +0.8)
    "atras": 0.25,  # m/s: atrás no hay LiDAR, así que despacio
    "lateral": 0.6,  # m/s (el arranque lateral pide ~0.5-0.7)
    "giro": 0.5,  # rad/s (los manuales piden evitar giros rápidos)
    "metros": 5.0,  # por orden de avanzar
    "metros_atras": 0.5,  # por orden de retroceder
    "grados": 360.0,  # por orden de girar
}
VELOCIDAD_MINIMA = 0.2  # m/s: por debajo, el X2 quieto no da el primer paso
GIRO_MINIMO = 0.15  # rad/s
DURACION_MANUAL = 0.5  # s que dura una orden de velocidad sin renovarse
ACELERACION = {"adelante": 0.5, "lateral": 0.5, "giro": 1.0}  # m/s², rad/s²: órdenes suaves y continuas
SIN_NOTICIAS = 1.0  # s sin mensajes del portátil con el robot en movimiento: se detiene
CEROS_AL_PARAR = 0.5  # s de velocidad cero que se publican al detenerse
TOLERANCIA_M = 0.03
TOLERANCIA_RAD = math.radians(2)
SALTO_ODOMETRIA = 0.3  # m entre dos lecturas seguidas: la localización saltó, se detiene
OTRA_FUENTE = 0.5  # s con otra fuente al mando mientras nos movemos: se detiene

# Lo que tiene que cumplir el robot para moverse (nombres y valores del manual de AimDK)
MODOS_PARA_CAMINAR = {"STAND_DEFAULT", "LOCOMOTION_DEFAULT"}
ACCION_CAMBIANDO = {200, 300}  # TRANSITION, UNINTERRUPTIBLE_TRANSITION
FSM_PERMITIDOS = {2: "STABLE", 3: "MOVING"}
FSM_NOMBRES = {0: "UNKNOWN", 1: "STARTING", 2: "STABLE", 3: "MOVING", 4: "SAFE (protección activa)",
               5: "SPECIAL", 6: "TEST"}
POSTURA_DE_PIE = 1
POSTURAS = {0: "desconocida", 1: "de pie", 2: "boca arriba", 3: "boca abajo", 4: "sentado",
            5: "agachado", 6: "CAYENDO"}
SISTEMA_MODO = "Business"
SISTEMA_LISTO = 1  # IN_READY
SISTEMA_ESTADOS = {0: "iniciando", 1: "listo", 2: "cambiando de modo", 3: "revirtiendo",
                   4: "degradado", 5: "degradado y cambiando"}
BATERIA_MINIMA = 30  # %: el robot avisa "carga pronto" bajo 30 %
CORRIENTE_CARGANDO = 0.3  # A: corriente positiva = cargando, y el manual prohíbe operarlo cargando
MARCHA_MAXIMA = 600.0  # s: el manual pide no caminar más de 10 min seguidos (se recalienta)
DESCANSO = 180.0  # s quieto que reinician la cuenta de marcha
# Señales de diagnóstico (robot_sig) que no tienen que ver con caminar: no bloquean
ALERTAS_SIN_EFECTO = {0, 161, 209, 210, 255}  # ninguna, batería mal mostrada, cámara/micrófono
ALERTA_VIGENTE = 1.0  # s: HDS repite la alerta a ~20 Hz mientras está activa

# Datos que tienen que estar llegando (segundos máximos desde el último mensaje)
VIGENCIA = {"movimiento": 0.5, "sistema": 3.0, "bateria": 5.0, "lidar": 0.5}
ODOM_VIGENTE = 0.5
NAV_NOMBRES = {0: "desconocido", 1: "en curso", 2: "falló", 3: "en pausa", 4: "llegó",
               22: "se agotó el tiempo de recuperación"}

# Freno por obstáculo con el LiDAR del pecho (frame lidar_chest_front: x adelante, y izquierda,
# z arriba). Confirmar en el robot con `estado` y una caja delante antes de caminar.
OBSTACULO_PARAR = 1.0  # m: la guía de AgiBot pide nada a menos de 1 m delante mientras camina
OBSTACULO_ZONA = {"x": (0.15, 2.5), "y": (-0.4, 0.4), "z": (-0.85, 0.5)}  # el suelo queda fuera


def _acotar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def _angulo(a):
    return math.atan2(math.sin(a), math.cos(a))


def obstaculo_al_frente(xyz):
    """Distancia (m) al punto más cercano dentro de la zona de delante, o None si está libre."""
    import numpy as np

    if xyz is None or len(xyz) == 0:
        return None
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    zona = OBSTACULO_ZONA
    dentro = ((x > zona["x"][0]) & (x < zona["x"][1]) & (y > zona["y"][0]) & (y < zona["y"][1])
              & (z > zona["z"][0]) & (z < zona["z"][1]) & np.isfinite(x))
    return float(x[dentro].min()) if dentro.any() else None


def revisar(salud, ahora):
    """Lista de motivos por los que el robot NO debe moverse ahora (vacía = puede)."""
    motivos = []
    edad = lambda k: ahora - salud["recibido"].get(k, -1e9)  # noqa: E731

    if edad("movimiento") > VIGENCIA["movimiento"]:
        motivos.append("no llega el estado del control de movimiento (/aima/mc/common/state)")
    else:
        if salud["modo"] not in MODOS_PARA_CAMINAR:
            motivos.append(f"modo {salud['modo'] or 'desconocido'}: ponlo de pie en equilibrio "
                           "(STAND_DEFAULT) con el control remoto")
        if salud["accion_estado"] in ACCION_CAMBIANDO:
            motivos.append("el robot está cambiando de modo")
        if salud["fsm"] not in FSM_PERMITIDOS:
            motivos.append(f"máquina de estados en {FSM_NOMBRES.get(salud['fsm'], salud['fsm'])}")
        if salud["postura"] != POSTURA_DE_PIE:
            motivos.append(f"postura: {POSTURAS.get(salud['postura'], salud['postura'])}")
        if salud["limites"] is None or salud["modo_velocidad"] == 0:
            motivos.append("el robot no admite velocidad ahora (modo de velocidad NONE)")
        if salud["fuente_activa"] == "linkswarm":
            motivos.append("Linkswarm tiene el control exclusivo del robot")
    if edad("sistema") > VIGENCIA["sistema"]:
        motivos.append("no llega el estado del sistema (/aima/sm/system_state)")
    elif salud["sistema"] != SISTEMA_MODO or salud["sistema_estado"] != SISTEMA_LISTO:
        estado = SISTEMA_ESTADOS.get(salud["sistema_estado"], salud["sistema_estado"])
        motivos.append(f"sistema en {salud['sistema']} ({estado}); debe estar en {SISTEMA_MODO} y listo")
    alertas = sorted(s for s, t in salud["alertas"].items()
                     if s not in ALERTAS_SIN_EFECTO and ahora - t < ALERTA_VIGENTE)
    if alertas:
        motivos.append("alerta de diagnóstico activa (robot_sig " + ", ".join(map(str, alertas)) + ")")
    if edad("bateria") > VIGENCIA["bateria"]:
        motivos.append("no llega el estado de la batería (/aima/hal/pmu/state)")
    else:
        if salud["bateria"] is not None and salud["bateria"] < BATERIA_MINIMA:
            motivos.append(f"batería en {salud['bateria']} % (mínimo {BATERIA_MINIMA} %)")
        if salud["cargando"]:
            motivos.append("el robot está cargando: no se opera mientras carga")
    return motivos


def lidar_listo(salud, ahora):
    return ahora - salud["recibido"].get("lidar", -1e9) <= VIGENCIA["lidar"]


class Pose:
    """Posición en el plano (m, m, rad) e integración de la velocidad pedida."""

    def __init__(self):
        self.x = self.y = self.yaw = 0.0

    def integrar(self, adelante, lateral, giro, dt):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        self.x += (adelante * c - lateral * s) * dt
        self.y += (adelante * s + lateral * c) * dt
        self.yaw = _angulo(self.yaw + giro * dt)


def _salud_vacia():
    return {"recibido": {}, "modo": None, "accion_estado": None, "fsm": None, "postura": None,
            "modo_velocidad": None, "limites": None, "fuente_activa": None, "sistema": None,
            "sistema_estado": None, "alertas": {}, "bateria": None, "cargando": False, "obstaculo": None}


# ---------------------------------------------------------------------------------------------
# Conexión con el robot


class RobotAimdk:
    """El X2 real a través de ROS 2 y AimDK (mismos mensajes y QoS que los ejemplos de AgiBot)."""

    def __init__(self):
        import rclpy
        from rclpy.callback_groups import ReentrantCallbackGroup
        from rclpy.executors import MultiThreadedExecutor
        from rclpy.node import Node
        from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import PointCloud2
        import aimdk_msgs.msg as am
        import aimdk_msgs.srv as asrv

        faltan = [n for n in ("McLocomotionVelocity", "MessageHeader", "McInputAction", "McCommonState",
                              "SmSystemState", "PostProcSigArray", "PmuState", "PncTaskRequest",
                              "PncTaskResponse") if not hasattr(am, n)]
        faltan += [n for n in ("SetMcInputSource",) if not hasattr(asrv, n)]
        if faltan:  # sin estos mensajes no se pueden vigilar las protecciones: no arranca
            raise SystemExit("Faltan mensajes de AimDK: " + ", ".join(faltan))
        self._rclpy = rclpy
        self._am = am
        rclpy.init()
        self.nodo = Node("anfitrion_puente_x2")
        self._pub_vel = self.nodo.create_publisher(am.McLocomotionVelocity, "/aima/mc/locomotion/velocity", 10)
        self._pub_nav = self.nodo.create_publisher(am.PncTaskRequest, "/aima/te/pnc_task_request", 10)
        self._cli_fuente = self.nodo.create_client(asrv.SetMcInputSource, "/aimdk_5Fmsgs/srv/SetMcInputSource")
        self._SetMcInputSource = asrv.SetMcInputSource

        def qos(confiable=False, persistente=False, profundidad=10):
            return QoSProfile(
                depth=profundidad,
                reliability=ReliabilityPolicy.RELIABLE if confiable else ReliabilityPolicy.BEST_EFFORT,
                durability=DurabilityPolicy.TRANSIENT_LOCAL if persistente else DurabilityPolicy.VOLATILE)

        grupo = ReentrantCallbackGroup()  # el LiDAR no debe retrasar el estado del robot

        def sub(tipo, tema, funcion, perfil):
            self.nodo.create_subscription(tipo, tema, funcion, perfil, callback_group=grupo)

        sub(am.McCommonState, "/aima/mc/common/state", self._al_movimiento, qos(persistente=True))
        sub(am.SmSystemState, "/aima/sm/system_state", self._al_sistema, qos(persistente=True))
        sub(am.PostProcSigArray, "/aima/hds/post_proc/signal", self._al_alerta, qos())
        sub(am.PmuState, "/aima/hal/pmu/state", self._al_bateria, qos(persistente=True))
        sub(PointCloud2, "/aima/hal/sensor/lidar_chest_front/lidar_pointcloud", self._al_lidar,
            qos(confiable=True, profundidad=1))
        sub(Odometry, "/slam/lidar_odom", self._al_odom, qos())
        sub(am.PncTaskResponse, "/aima/pnc/pnc_task_response", self._al_navegacion, qos(persistente=True))

        self._lock = threading.Lock()
        self._salud = _salud_vacia()
        self._odom = None  # (x, y, yaw, instante)
        self._nav = None  # (estado, instante) de nuestra última tarea de navegación
        self.id_navegacion = int(time.time() * 1000)

        self._ejecutor = MultiThreadedExecutor()
        self._ejecutor.add_node(self.nodo)
        threading.Thread(target=self._ejecutor.spin, daemon=True).start()

    def log(self, texto):
        self.nodo.get_logger().info(texto)

    # Fuente de entrada (como register_input_source del ejemplo 6.1.10)
    def _llamar_fuente(self, accion):
        req = self._SetMcInputSource.Request()
        req.action.value = accion
        req.input_source.name = FUENTE
        req.input_source.priority = PRIORIDAD_FUENTE
        req.input_source.timeout = TIMEOUT_FUENTE_MS
        futuro = None
        for _ in range(8):  # reintentos: los servicios entre equipos de ROS fallan a veces
            req.request.header.stamp = self.nodo.get_clock().now().to_msg()
            futuro = self._cli_fuente.call_async(req)
            limite = time.time() + 0.25
            while not futuro.done() and time.time() < limite:
                time.sleep(0.01)
            if futuro.done():
                break
        if futuro is None or not futuro.done():
            return False
        try:
            respuesta = futuro.result()
        except Exception as e:  # noqa: BLE001 - se informa y se sigue con la otra acción
            self.log(f"Error con la fuente de entrada: {e}")
            return False
        return respuesta is not None and respuesta.response.header.code == 0

    def registrar_fuente(self):
        acciones = self._am.McInputAction
        if not self._cli_fuente.wait_for_service(timeout_sec=8.0):
            self.log("No aparece el servicio SetMcInputSource")
            return False
        if self._llamar_fuente(acciones.INPUTACTION_ADD):
            self.log(f"Fuente de entrada registrada: {FUENTE} (prioridad {PRIORIDAD_FUENTE})")
            return True
        if self._llamar_fuente(acciones.INPUTACTION_ENABLE):  # ya existía
            self.log(f"Fuente de entrada habilitada: {FUENTE}")
            return True
        return False

    def soltar_fuente(self):
        """Al cerrar, deshabilita la fuente (DISABLE, 2002) para no dejarla registrada activa."""
        if self._llamar_fuente(2002):
            self.log("Fuente de entrada deshabilitada")

    # Lecturas
    def _marcar(self, clave):
        self._salud["recibido"][clave] = time.monotonic()

    def _al_movimiento(self, msg):
        rapidez = msg.speed_status
        with self._lock:
            s = self._salud
            s["modo"] = msg.action_info.action_desc or None
            s["accion_estado"] = msg.action_info.status.value
            s["fsm"] = int(getattr(msg.fsm_state.current_state, "value", msg.fsm_state.current_state))
            s["postura"] = msg.body_status.value
            s["modo_velocidad"] = rapidez.speed_mode.value
            s["limites"] = {
                "adelante": (rapidez.forward_bounds.min_value, rapidez.forward_bounds.max_value),
                "lateral": (rapidez.lateral_bounds.min_value, rapidez.lateral_bounds.max_value),
                "giro": (rapidez.angular_bounds.min_value, rapidez.angular_bounds.max_value),
            }
            s["fuente_activa"] = msg.input_source.name or None
            self._marcar("movimiento")

    def _al_sistema(self, msg):
        with self._lock:
            self._salud["sistema"] = msg.cur_state
            self._salud["sistema_estado"] = msg.cur_status.value
            self._marcar("sistema")

    def _al_alerta(self, msg):
        ahora = time.monotonic()
        with self._lock:
            for p in msg.post_proc_sig:
                sig = int(p.sig_set.robot_sig)
                if sig == 255:  # todas las alertas se resolvieron
                    self._salud["alertas"].clear()
                else:
                    self._salud["alertas"][sig] = ahora

    def _al_bateria(self, msg):
        with self._lock:
            self._salud["bateria"] = int(msg.battery_remaining_capacity_percentage)
            self._salud["cargando"] = float(msg.battery_current) > CORRIENTE_CARGANDO
            self._marcar("bateria")

    def _al_lidar(self, msg):
        import numpy as np
        from sensor_msgs_py import point_cloud2

        campos = ("x", "y", "z")
        if hasattr(point_cloud2, "read_points_numpy"):
            xyz = point_cloud2.read_points_numpy(msg, field_names=campos, skip_nans=True).astype(float)
        else:
            xyz = np.array(list(point_cloud2.read_points(msg, field_names=campos, skip_nans=True)), dtype=float)
        xyz = xyz.reshape(-1, 3) if xyz.size else None
        distancia = obstaculo_al_frente(xyz)
        with self._lock:
            self._salud["obstaculo"] = distancia
            self._marcar("lidar")

    def _al_odom(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        with self._lock:
            self._odom = (p.x, p.y, yaw, time.monotonic())

    def _al_navegacion(self, msg):
        if msg.task_id == self.id_navegacion:
            with self._lock:
                self._nav = (int(msg.task_status), time.monotonic())

    def estado_navegacion(self):
        with self._lock:
            return self._nav

    def salud(self):
        with self._lock:
            s = dict(self._salud)
            s["recibido"] = dict(s["recibido"])
            s["alertas"] = dict(s["alertas"])
            return s

    def odometria(self):
        """(x, y, yaw) del robot en el mapa, o None si no hay odometría reciente."""
        with self._lock:
            if self._odom and time.monotonic() - self._odom[3] < ODOM_VIGENTE:
                return self._odom[:3]
        return None

    def publicar(self, adelante, lateral, giro):
        msg = self._am.McLocomotionVelocity()
        msg.header = self._am.MessageHeader()
        msg.header.stamp = self.nodo.get_clock().now().to_msg()
        msg.source = FUENTE
        msg.forward_velocity = float(adelante)
        msg.lateral_velocity = float(lateral)
        msg.angular_velocity = float(giro)
        self._pub_vel.publish(msg)

    def navegar(self, map_id, x, y, yaw, radio, velocidad, iniciar=True):
        """Ejemplo 6.1.30: pide a la navegación del robot ir a (x, y) del mapa, o la detiene."""
        import numpy as np
        from geometry_msgs.msg import PoseStamped

        if iniciar:
            self.id_navegacion = int(time.time() * 1000)
            with self._lock:
                self._nav = None
        msg = self._am.PncTaskRequest()
        header = self._am.MessageHeader()
        ahora = self.nodo.get_clock().now().to_msg()
        header.stamp = ahora
        header.meas_stamp = ahora
        header.frame_id = "map"
        header.sequence = 0
        msg.header = header
        msg.task_type = 2
        msg.task_request = 1 if iniciar else 2  # START / STOP
        msg.pnc_mode = 0
        msg.max_forward_speed = float(velocidad)
        msg.task_id = self.id_navegacion
        msg.map_id = int(map_id)
        msg.target_pose_radius = float(radio) if iniciar else 0.0
        msg.reserve_info = np.zeros(64, dtype=np.uint8)
        destino = PoseStamped()
        destino.header.stamp = ahora
        destino.header.frame_id = "map"
        destino.pose.position.x = float(x)
        destino.pose.position.y = float(y)
        destino.pose.orientation.z = math.sin(yaw / 2)
        destino.pose.orientation.w = math.cos(yaw / 2)
        msg.target_pose = destino
        self._pub_nav.publish(msg)

    def cerrar(self):
        self.soltar_fuente()
        self._ejecutor.shutdown()
        self.nodo.destroy_node()
        if self._rclpy.ok():
            self._rclpy.shutdown()


class RobotSimulado:
    """Sin robot: responde como el X2 (estados, alertas, batería, obstáculos) para probar."""

    def __init__(self, retraso=0.3, con_odometria=True):
        self.con_odometria = con_odometria
        self.pose = Pose()
        self.estado = {"modo": "STAND_DEFAULT", "accion_estado": 0, "fsm": 2, "postura": 1,
                       "modo_velocidad": 1, "sistema": "Business", "sistema_estado": 1,
                       "bateria": 80, "cargando": False, "alertas": [], "fuente_activa": None, "otra_fuente": None,
                       "pared_x": None, "callado": []}
        self._vel = (0.0, 0.0, 0.0)
        self._ultima = 0.0
        self._retraso = retraso  # el robot real tarda en responder a la velocidad
        self._real = [0.0, 0.0, 0.0]
        self._t = time.monotonic()
        self._lock = threading.Lock()
        self.navegaciones = []

    def log(self, texto):
        print(f"[puente simulado] {texto}", flush=True)

    def registrar_fuente(self):
        return True

    def simular(self, cambios):
        """Cambia el estado del robot simulado (para probar las protecciones)."""
        with self._lock:
            for k, v in cambios.items():
                if k not in self.estado:
                    raise ValueError(f"no se puede simular {k}")
                self.estado[k] = v

    def salud(self):
        self._avanzar_tiempo()
        ahora = time.monotonic()
        with self._lock:
            e = dict(self.estado)
        s = _salud_vacia()
        for k in ("modo", "accion_estado", "fsm", "postura", "modo_velocidad", "sistema",
                  "sistema_estado", "bateria", "cargando"):
            s[k] = e[k]
        s["limites"] = {"adelante": (-1.0, 0.8), "lateral": (-1.0, 1.0), "giro": (-1.0, 1.0)}
        s["fuente_activa"] = e["otra_fuente"] or e["fuente_activa"]
        s["alertas"] = {int(a): ahora for a in e["alertas"]}
        s["recibido"] = {k: ahora for k in ("movimiento", "sistema", "bateria", "lidar")
                         if k not in e["callado"]}
        if e["pared_x"] is not None:  # pared perpendicular al eje x del mundo
            delante = (e["pared_x"] - self.pose.x) / max(math.cos(self.pose.yaw), 1e-6)
            s["obstaculo"] = delante if math.cos(self.pose.yaw) > 0.3 and 0 < delante < OBSTACULO_ZONA["x"][1] else None
        return s

    def odometria(self):
        self._avanzar_tiempo()
        return (self.pose.x, self.pose.y, self.pose.yaw) if self.con_odometria else None

    def publicar(self, adelante, lateral, giro):
        self._avanzar_tiempo()
        self._vel = (adelante, lateral, giro)
        self._ultima = time.monotonic()
        self.estado["fuente_activa"] = FUENTE

    def _avanzar_tiempo(self):
        with self._lock:
            ahora = time.monotonic()
            dt, self._t = ahora - self._t, ahora
            manda_otro = self.estado["otra_fuente"] is not None
            objetivo = self._vel if ahora - self._ultima < 0.2 and not manda_otro else (0.0, 0.0, 0.0)
            k = min(1.0, dt / self._retraso) if self._retraso else 1.0
            self._real = [r + (o - r) * k for r, o in zip(self._real, objetivo)]
            self.pose.integrar(*self._real, dt)

    def navegar(self, map_id, x, y, yaw, radio, velocidad, iniciar=True):
        self.navegaciones.append((map_id, x, y, yaw, iniciar))
        self._nav_inicio = time.monotonic() if iniciar else None

    def estado_navegacion(self):
        """Simula que la navegación llega a los 2 s."""
        inicio = getattr(self, "_nav_inicio", None)
        if inicio is None:
            return None
        return (4, time.monotonic()) if time.monotonic() - inicio > 2 else (1, time.monotonic())

    def cerrar(self):
        pass


# ---------------------------------------------------------------------------------------------
# Lógica del puente: órdenes, tareas y seguridad


class Controlador:
    def __init__(self, robot):
        self.robot = robot
        self._lock = threading.Lock()
        self._manual = (0.0, 0.0, 0.0)
        self._manual_hasta = 0.0
        self._tarea = None  # dict con la orden en curso
        self._ceros_hasta = 0.0
        self._estimada = Pose()
        self._pose_anterior = None
        self._otra_fuente_desde = None
        self._enviada = (0.0, 0.0, 0.0)  # última velocidad publicada (para suavizar)
        self._navegando = False
        self.marcha = 0.0  # s caminando en el tramo actual (se reinicia tras DESCANSO quieto)
        self._quieto = 0.0
        self.mensaje = "quieto"
        self.ultimo_contacto = time.monotonic()
        self._activo = True
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()

    # Posición: odometría si hay; si no, la estimación por velocidad pedida
    def _pose(self):
        odom = self.robot.odometria()
        if odom is not None:
            return odom, "odometria"
        return (self._estimada.x, self._estimada.y, self._estimada.yaw), "estimada"

    def _motivos(self, salud, vel=None):
        """Motivos para no moverse; con vel, también los que dependen de la dirección."""
        ahora = time.monotonic()
        motivos = revisar(salud, ahora)
        if self.marcha >= MARCHA_MAXIMA:
            falta = DESCANSO - self._quieto
            motivos.append(f"lleva {self.marcha / 60:.0f} min caminando: descanso de {max(falta, 0):.0f} s "
                           "para que no se recaliente")
        if vel is not None and vel[0] > 0:
            if not lidar_listo(salud, ahora):
                motivos.append("no llegan datos del LiDAR: no se avanza a ciegas")
            elif salud["obstaculo"] is not None and salud["obstaculo"] < OBSTACULO_PARAR:
                motivos.append(f"obstáculo a {salud['obstaculo']:.2f} m delante")
        return motivos

    def estado(self):
        (x, y, yaw), fuente = self._pose()
        salud = self.robot.salud()
        motivos = self._motivos(salud)
        ahora = time.monotonic()
        with self._lock:
            tarea = self._tarea
            accion = tarea["tipo"] if tarea else ("manual" if ahora < self._manual_hasta else
                                                  ("navegando" if self._navegando else "quieto"))
            return {
                "accion": accion,
                "progreso": round(tarea.get("progreso", 0.0), 3) if tarea else None,
                "mensaje": self.mensaje,
                "x": round(x, 3), "y": round(y, 3), "yaw_grados": round(math.degrees(yaw), 1),
                "posicion": fuente,
                "modo": salud["modo"],
                "postura": POSTURAS.get(salud["postura"], salud["postura"]),
                "sistema": salud["sistema"],
                "bateria": salud["bateria"],
                "obstaculo_m": None if salud["obstaculo"] is None else round(salud["obstaculo"], 2),
                "lidar": lidar_listo(salud, ahora),
                "fuente_activa": salud["fuente_activa"],
                "marcha_s": round(self.marcha),
                "puede_caminar": not motivos,
                "motivo": "; ".join(motivos),
            }

    def _comprobar(self, vel):
        motivos = self._motivos(self.robot.salud(), vel)
        if motivos:
            raise ValueError("; ".join(motivos))

    def _acotar_al_robot(self, adelante, lateral, giro, salud):
        """Respeta los límites del puente y los del modo de velocidad actual del robot."""
        lim = salud["limites"] or {"adelante": (0, 0), "lateral": (0, 0), "giro": (0, 0)}
        adelante = _acotar(adelante, max(-LIMITES["atras"], lim["adelante"][0]),
                           min(LIMITES["adelante"], lim["adelante"][1]))
        lateral = _acotar(lateral, max(-LIMITES["lateral"], lim["lateral"][0]),
                          min(LIMITES["lateral"], lim["lateral"][1]))
        giro = _acotar(giro, max(-LIMITES["giro"], lim["giro"][0]), min(LIMITES["giro"], lim["giro"][1]))
        return adelante, lateral, giro

    def avanzar(self, metros, velocidad=0.3):
        metros = float(metros)
        if metros > LIMITES["metros"]:
            raise ValueError(f"máximo {LIMITES['metros']} m por orden")
        if metros < -LIMITES["metros_atras"]:
            raise ValueError(f"hacia atrás, máximo {LIMITES['metros_atras']} m por orden (no hay LiDAR atrás)")
        tope = LIMITES["adelante"] if metros > 0 else LIMITES["atras"]
        v = max(VELOCIDAD_MINIMA, min(abs(float(velocidad)), tope))
        self._comprobar((math.copysign(v, metros), 0.0, 0.0))
        (x, y, _), _ = self._pose()
        with self._lock:
            self._tarea = {"tipo": "avanzar", "meta": metros, "v": v, "inicio": (x, y),
                           "t0": time.monotonic(), "limite": abs(metros) / v * 2 + 4, "progreso": 0.0}
            self.mensaje = f"avanzando {metros:+.2f} m a {v:.2f} m/s"

    def girar(self, grados, velocidad=0.3):
        grados = float(grados)
        if abs(grados) > LIMITES["grados"]:
            raise ValueError(f"máximo {LIMITES['grados']}° por orden")
        w = max(GIRO_MINIMO, min(abs(float(velocidad)), LIMITES["giro"]))
        self._comprobar((0.0, 0.0, w))
        (_, _, yaw), _ = self._pose()
        meta = math.radians(grados)
        with self._lock:
            self._tarea = {"tipo": "girar", "meta": meta, "w": w, "yaw_prev": yaw, "girado": 0.0,
                           "t0": time.monotonic(), "limite": abs(meta) / w * 2 + 4, "progreso": 0.0}
            self.mensaje = f"girando {grados:+.0f}°"

    def velocidad(self, adelante=0.0, lateral=0.0, giro=0.0):
        """Mando manual (teclado): dura DURACION_MANUAL si no se renueva."""
        vel = self._acotar_al_robot(float(adelante), float(lateral), float(giro), self.robot.salud())
        self._comprobar(vel)
        with self._lock:
            self._tarea = None
            self._manual = vel
            self._manual_hasta = time.monotonic() + DURACION_MANUAL
            self.mensaje = "mando manual"

    def detener(self, motivo="detenido"):
        with self._lock:
            hubo = self._tarea is not None or time.monotonic() < self._manual_hasta
            navegando, self._navegando = self._navegando, False
            self._tarea = None
            self._manual = (0.0, 0.0, 0.0)
            self._manual_hasta = 0.0
            self._ceros_hasta = time.monotonic() + CEROS_AL_PARAR
            self.mensaje = motivo
        if navegando:
            self.robot.navegar(0, 0, 0, 0, 0, 0.5, iniciar=False)
        if hubo or navegando:
            self.robot.log(f"Detener: {motivo}")

    def navegar(self, map_id, x, y, yaw_grados=0.0, radio=0.5, velocidad=0.4):
        """Navegación del robot: planea la ruta y esquiva obstáculos con su propia percepción."""
        self._comprobar((0.3, 0.0, 0.0))
        self.detener("pasa a la navegación del robot")
        self.robot.navegar(map_id, x, y, math.radians(float(yaw_grados)), radio,
                           min(float(velocidad), LIMITES["adelante"]))
        with self._lock:
            self._navegando = True
            self.mensaje = f"navegando a ({x}, {y}) en el mapa {map_id}"

    def cancelar_navegacion(self):
        with self._lock:
            self._navegando = True  # que detener() mande la parada aunque no supiéramos que navegaba
        self.detener("navegación cancelada")

    # Bucle a 50 Hz: decide la velocidad y la publica
    def _velocidad_tarea(self, tarea, pose):
        x, y, yaw = pose
        if time.monotonic() - tarea["t0"] > tarea["limite"]:
            return None, "se acabó el tiempo de la orden (¿obstáculo o robot sin avanzar?)"
        if tarea["tipo"] == "avanzar":
            x0, y0 = tarea["inicio"]
            hecho = math.hypot(x - x0, y - y0)
            falta = abs(tarea["meta"]) - hecho
            tarea["progreso"] = hecho
            if falta <= TOLERANCIA_M:
                return None, f"avanzó {hecho:.2f} m"
            v = min(tarea["v"], max(VELOCIDAD_MINIMA, falta * 1.5))  # frena al final
            return (math.copysign(v, tarea["meta"]), 0.0, 0.0), None
        # girar: se acumula lo girado para admitir vueltas de más de 180°
        tarea["girado"] += _angulo(yaw - tarea["yaw_prev"])
        tarea["yaw_prev"] = yaw
        falta = abs(tarea["meta"]) - abs(tarea["girado"])
        tarea["progreso"] = math.degrees(abs(tarea["girado"]))
        if falta <= TOLERANCIA_RAD:
            return None, f"giró {math.degrees(abs(tarea['girado'])):.0f}°"
        w = min(tarea["w"], max(GIRO_MINIMO, falta * 1.5))
        return (0.0, 0.0, math.copysign(w, tarea["meta"])), None

    def _suavizar(self, vel, dt):
        """Sube y baja la velocidad de a poco (las paradas por seguridad, en cambio, son inmediatas)."""
        return tuple(
            previa + _acotar(nueva - previa, -ACELERACION[eje] * dt, ACELERACION[eje] * dt)
            for nueva, previa, eje in zip(vel, self._enviada, ("adelante", "lateral", "giro")))

    def _parar(self, motivo, ahora):
        """Para dentro del bucle (con el lock tomado)."""
        self._tarea = None
        self._manual = (0.0, 0.0, 0.0)
        self._manual_hasta = 0.0
        self._ceros_hasta = ahora + CEROS_AL_PARAR
        self.mensaje = motivo
        self.robot.log(motivo)

    def _bucle(self):
        periodo = 1.0 / FRECUENCIA
        siguiente = time.monotonic()
        anterior = siguiente
        while self._activo:
            ahora = time.monotonic()
            dt, anterior = ahora - anterior, ahora
            pose, fuente_pose = self._pose()
            salud = self.robot.salud()
            parar_navegacion = False
            with self._lock:
                vel = None
                moviendo = self._tarea is not None or ahora < self._manual_hasta
                if moviendo and ahora - self.ultimo_contacto > SIN_NOTICIAS:
                    self._parar("detenido: sin noticias del portátil", ahora)
                    moviendo = False
                if self._tarea is not None:
                    vel, fin = self._velocidad_tarea(self._tarea, pose)
                    if vel is None:
                        self._tarea = None
                        self._ceros_hasta = ahora + CEROS_AL_PARAR
                        self.mensaje = fin
                        self.robot.log(fin)
                elif ahora < self._manual_hasta:
                    vel = self._manual
                elif self._manual != (0.0, 0.0, 0.0):
                    self._manual = (0.0, 0.0, 0.0)
                    self._ceros_hasta = ahora + CEROS_AL_PARAR
                    self.mensaje = "quieto (el mando manual no se renovó)"

                if vel is not None:
                    vel = self._acotar_al_robot(*vel, salud)
                    motivos = self._motivos(salud, vel)
                    # salto de la localización
                    if (fuente_pose == "odometria" and self._pose_anterior is not None
                            and math.dist(pose[:2], self._pose_anterior[:2]) > SALTO_ODOMETRIA):
                        motivos.append("la localización saltó")
                    # otra fuente (control remoto, app) tomó el mando
                    otra = salud["fuente_activa"] not in (None, "", FUENTE)
                    self._otra_fuente_desde = (self._otra_fuente_desde or ahora) if otra else None
                    if otra and ahora - self._otra_fuente_desde > OTRA_FUENTE:
                        motivos.append(f"{salud['fuente_activa']} tomó el mando")
                    if motivos:
                        self._parar("detenido: " + "; ".join(motivos), ahora)
                        vel = None
                    else:
                        vel = self._suavizar(vel, dt)
                elif self._navegando and revisar(salud, ahora):
                    self._navegando = False
                    parar_navegacion = True
                    self.mensaje = "navegación detenida: " + "; ".join(revisar(salud, ahora))
                    self.robot.log(self.mensaje)
                elif self._navegando:
                    nav = self.robot.estado_navegacion()
                    if nav is not None and nav[0] not in (0, 1):
                        self._navegando = False
                        self.mensaje = f"navegación: {NAV_NOMBRES.get(nav[0], nav[0])}"
                        self.robot.log(self.mensaje)
                self._pose_anterior = pose
                publicar = vel is not None or ahora < self._ceros_hasta
                vel = vel or (0.0, 0.0, 0.0)
            # Cuenta de marcha (velocidad distinta de cero o navegación del robot)
            if (publicar and vel != (0.0, 0.0, 0.0)) or self._navegando:
                self.marcha += dt
                self._quieto = 0.0
            else:
                self._quieto += dt
                if self._quieto >= DESCANSO:
                    self.marcha = 0.0
            if parar_navegacion:
                self.robot.navegar(0, 0, 0, 0, 0, 0.5, iniciar=False)
            if publicar:
                # Lo que no mide la odometría se estima con la velocidad pedida
                self._estimada.integrar(*vel, dt)
                self.robot.publicar(*vel)
            self._enviada = vel if publicar else (0.0, 0.0, 0.0)
            siguiente += periodo
            time.sleep(max(0.0, siguiente - time.monotonic()))

    def cerrar(self):
        self.detener("puente cerrado")
        time.sleep(CEROS_AL_PARAR + 0.1)
        self._activo = False


# ---------------------------------------------------------------------------------------------
# Servidor: una línea JSON por orden


ORDENES = {
    "estado": lambda c, a: c.estado(),
    "avanzar": lambda c, a: c.avanzar(a["metros"], a.get("velocidad", 0.3)),
    "girar": lambda c, a: c.girar(a["grados"], a.get("velocidad", 0.3)),
    "velocidad": lambda c, a: c.velocidad(a.get("adelante", 0.0), a.get("lateral", 0.0), a.get("giro", 0.0)),
    "detener": lambda c, a: c.detener(a.get("motivo", "detenido desde el portátil")),
    "navegar": lambda c, a: c.navegar(a["map_id"], a["x"], a["y"], a.get("yaw_grados", 0.0),
                                      a.get("radio", 0.5), a.get("velocidad", 0.4)),
    "cancelar_navegacion": lambda c, a: c.cancelar_navegacion(),
}


def _simular(control, orden):
    if not isinstance(control.robot, RobotSimulado):
        raise ValueError("simular solo existe con --simulado")
    cambios = dict(orden.get("cambios", {}))
    if "marcha_s" in cambios:  # tiempo ya caminado, para probar el límite de 10 min
        control.marcha = float(cambios.pop("marcha_s"))
    control.robot.simular(cambios)


class Manejador(socketserver.StreamRequestHandler):
    def handle(self):
        control = self.server.control
        ordenes = dict(ORDENES, simular=_simular) if self.server.simulado else ORDENES
        control.robot.log(f"Conectado: {self.client_address[0]}")
        try:
            for linea in self.rfile:
                linea = linea.strip()
                if not linea:
                    continue
                orden = None
                control.ultimo_contacto = time.monotonic()
                try:
                    orden = json.loads(linea)
                    if orden.get("orden") not in ordenes:
                        raise ValueError(f"orden desconocida: {orden.get('orden')}")
                    datos = ordenes[orden["orden"]](control, orden) or {}
                    respuesta = {"ok": True, **datos}
                except KeyError as e:
                    respuesta = {"ok": False, "error": f"falta {e}"}
                except (ValueError, TypeError, AttributeError) as e:
                    respuesta = {"ok": False, "error": str(e)}
                if isinstance(orden, dict) and "id" in orden:
                    respuesta["id"] = orden["id"]
                self.wfile.write((json.dumps(respuesta, ensure_ascii=False) + "\n").encode("utf-8"))
        except (ConnectionError, OSError):
            pass
        finally:
            control.detener("se perdió la conexión con el portátil")
            control.robot.log(f"Desconectado: {self.client_address[0]}")


class Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--host", default="127.0.0.1",
                   help="127.0.0.1 = solo por túnel SSH (recomendado); 0.0.0.0 = toda la red del robot")
    p.add_argument("--puerto", type=int, default=8765)
    p.add_argument("--simulado", action="store_true", help="sin robot, para probar")
    p.add_argument("--sin-odometria", action="store_true",
                   help="con --simulado: como el robot sin mapa (la distancia se estima)")
    args = p.parse_args()

    robot = RobotSimulado(con_odometria=not args.sin_odometria) if args.simulado else RobotAimdk()
    if not robot.registrar_fuente():
        robot.log("No se pudo registrar la fuente de entrada; el robot no aceptará velocidades")
        robot.cerrar()
        raise SystemExit(1)
    control = Controlador(robot)
    servidor = Servidor((args.host, args.puerto), Manejador)
    servidor.control = control
    servidor.simulado = args.simulado
    robot.log(f"Puente del X2 escuchando en {args.host}:{args.puerto}")

    # Si se cae la sesión SSH que lo arrancó (SIGHUP) o lo cierran (SIGTERM), se cierra igual que con
    # Ctrl+C: detiene el robot y deshabilita la fuente de entrada
    def _cerrar_por_senal(_num, _marco):
        raise KeyboardInterrupt
    for nombre in ("SIGHUP", "SIGTERM"):
        if hasattr(signal, nombre):
            signal.signal(getattr(signal, nombre), _cerrar_por_senal)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
        control.cerrar()
        robot.cerrar()


if __name__ == "__main__":
    main()
