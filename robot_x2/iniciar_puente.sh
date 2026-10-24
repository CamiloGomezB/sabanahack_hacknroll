#!/usr/bin/env bash
# Arranca el puente del X2 Ultra en la unidad de desarrollo (PC2, 10.0.1.41). No instala nada en el
# sistema del robot: solo usa ROS 2 Humble y AimDK, que vienen de fábrica.
#
# Desde el firmware v1.2.0, AgiBot exige que los programas propios corran dentro del contenedor de
# desarrollo (manual de AimDK, 4.4 "Develop in a Container"; por defecto se llama aimdk-dev). Si lo
# lanzas en PC2, este script entra solo al contenedor y se vuelve a ejecutar allí. Por eso esta
# carpeta va dentro de ~/aimdk, la única que el contenedor comparte con PC2.
#
#   bash iniciar_puente.sh              # revisa y arranca el puente (Ctrl+C lo detiene)
#   bash iniciar_puente.sh --revisar    # solo revisa, sin arrancar nada
#   bash iniciar_puente.sh --voz        # recepción fija: solo voz y caras (puente_voz.py), sin movimiento
#   bash iniciar_puente.sh --voz --revisar
#
# Solo con firmware v1.1.0 (transición, aún permite correr fuera del contenedor):
#   ANFITRION_EN_HOST=1 bash iniciar_puente.sh
set -u
AQUI="$(cd "$(dirname "$0")" && pwd)"
cd "$AQUI"
CONTENEDOR="${CONTENEDOR:-aimdk-dev}"
# --voz (primer argumento): el puente de voz y caras, que no toca el movimiento
PROGRAMA=puente_x2.py
[ "${1:-}" = "--voz" ] && PROGRAMA=puente_voz.py

ok()    { echo "  OK    $*"; }
falla() { echo "  FALLA $*"; FALLAS=$((FALLAS + 1)); }
FALLAS=0

# 1. Que estemos en PC2 y no en la unidad de control de movimiento (PC1): AgiBot lo prohíbe
if ip -4 addr 2>/dev/null | grep -q "10\.0\.1\.40/"; then
  echo "  ALTO  Esta es la unidad de control de movimiento (PC1, 10.0.1.40). El puente va en PC2 (10.0.1.41)."
  exit 1
fi

# 2. Fuera del contenedor: entrar a él (con red, procesos e IPC del robot compartidos, según el manual)
if [ ! -f /run/.containerenv ] && [ ! -f /.dockerenv ]; then
  if [ "${ANFITRION_EN_HOST:-}" = "1" ]; then
    echo "  AVISO corriendo fuera del contenedor: solo vale con firmware v1.1.0"
  elif ! command -v podman >/dev/null 2>&1; then
    echo "  FALLA no está podman, así que no hay contenedor de desarrollo. Pregunta a soporte la versión"
    echo "        del firmware; solo con v1.1.0 se puede usar ANFITRION_EN_HOST=1 bash iniciar_puente.sh"
    exit 1
  elif podman ps --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
    case "$AQUI" in
      "$HOME"/aimdk/*) ;;
      *) echo "  FALLA esta carpeta ($AQUI) no está dentro de ~/aimdk: el contenedor no la ve."
         echo "        Cópiala con desplegar.ps1, que la deja en ~/aimdk/anfitrion_x2."
         exit 1 ;;
    esac
    echo "== Entrando al contenedor $CONTENEDOR"
    if [ -t 0 ]; then exec podman exec -it "$CONTENEDOR" bash "$AQUI/iniciar_puente.sh" "$@"
    else exec podman exec "$CONTENEDOR" bash "$AQUI/iniciar_puente.sh" "$@"; fi
  elif podman ps -a --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
    echo "  FALLA el contenedor $CONTENEDOR existe pero está apagado. Arráncalo:"
    echo "        podman start $CONTENEDOR      (o, si no arranca: bash $AQUI/contenedor/run.sh)"
    exit 1
  else
    echo "  FALLA no existe el contenedor $CONTENEDOR. Hay que crearlo una vez (manual de AimDK, 4.4),"
    echo "        con espejos internacionales y el run.sh corregido que van en este repo:"
    echo "        bash $AQUI/contenedor/crear_contenedor.sh   (necesita internet en el robot; 20-40 min)"
    echo "        Si ya tiene otro nombre: CONTENEDOR=<nombre> bash iniciar_puente.sh"
    exit 1
  fi
fi

[ "$PROGRAMA" = puente_voz.py ] && shift   # ya dentro del contenedor (o en el host con v1.1.0)
echo "== Revisión antes de arrancar $PROGRAMA$([ -f /run/.containerenv ] && echo " (dentro del contenedor)")"
if ip -4 addr 2>/dev/null | grep -q "10\.0\.1\.41/"; then ok "unidad de desarrollo (PC2, 10.0.1.41)"
else echo "  AVISO no se ve la IP 10.0.1.41: confirma que esta es la unidad de desarrollo (PC2)"; fi

# 3. ROS 2 Humble y AimDK
if [ -f /opt/ros/humble/setup.bash ]; then
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash && ok "ROS 2 Humble"
else
  falla "no está /opt/ros/humble (ROS 2 Humble)"
fi
AIMDK="${AIMDK:-$HOME/aimdk}"
if [ -f "$AIMDK/install/setup.bash" ]; then
  # shellcheck disable=SC1091
  source "$AIMDK/install/setup.bash" && ok "AimDK en $AIMDK"
else
  falla "AimDK no está compilado en $AIMDK/install. Como dice el manual (4.4.5), dentro del contenedor:
        cd $AIMDK && colcon build
        (o indica otra carpeta con AIMDK=/ruta bash iniciar_puente.sh)"
fi

# 4. Módulos de Python que usa el puente (todos vienen con ROS 2 y AimDK)
if [ "$PROGRAMA" = puente_voz.py ]; then
python3 - <<'EOF' || FALLAS=$((FALLAS + 1))
import sys
try:
    import rclpy  # noqa: F401
    import aimdk_msgs.msg as am, aimdk_msgs.srv as asrv
except Exception as e:  # noqa: BLE001
    print(f"  FALLA falta rclpy o aimdk_msgs ({e.__class__.__name__})")
    sys.exit(1)
faltan = [f"aimdk_msgs.srv.{n}" for n in ("PlayTts", "PlayEmoji", "RequestAudioFocus",
                                          "AbandonAudioFocus", "SetVolume") if not hasattr(asrv, n)]
faltan += [f"aimdk_msgs.msg.{n}" for n in ("AudioPlayback", "AudioInfo", "AudioData", "FocusRequester",
                                           "FocusResponse", "TtsPriorityLevel") if not hasattr(am, n)]
for f in faltan:
    print(f"  FALLA falta {f}")
if not faltan:
    print("  OK    módulos de Python y mensajes de voz y cara de AimDK")
sys.exit(1 if faltan else 0)
EOF
else
python3 - <<'EOF' || FALLAS=$((FALLAS + 1))
import importlib, sys
faltan = []
for m in ("rclpy", "numpy", "sensor_msgs_py.point_cloud2", "nav_msgs.msg", "geometry_msgs.msg",
          "aimdk_msgs.msg", "aimdk_msgs.srv"):
    try:
        importlib.import_module(m)
    except Exception as e:  # noqa: BLE001
        faltan.append(f"{m} ({e.__class__.__name__})")
if not faltan:
    import aimdk_msgs.msg as am, aimdk_msgs.srv as asrv
    for n in ("McLocomotionVelocity", "MessageHeader", "McInputAction", "McCommonState", "SmSystemState",
              "PostProcSigArray", "PmuState", "PncTaskRequest", "PncTaskResponse"):
        if not hasattr(am, n):
            faltan.append(f"aimdk_msgs.msg.{n}")
    if not hasattr(asrv, "SetMcInputSource"):
        faltan.append("aimdk_msgs.srv.SetMcInputSource")
for f in faltan:
    print(f"  FALLA falta {f}")
if not faltan:
    print("  OK    módulos de Python y mensajes de AimDK")
sys.exit(1 if faltan else 0)
EOF
fi

# 5. Que el robot esté publicando lo que usa el puente (sin crear nodos de más: uno solo)
if [ "$PROGRAMA" = puente_voz.py ] && command -v ros2 >/dev/null 2>&1; then
  SERVICIOS="$(timeout 10 ros2 service list 2>/dev/null)"
  for t in /aimdk_5Fmsgs/srv/PlayTts /aimdk_5Fmsgs/srv/PlayEmoji /aimdk_5Fmsgs/srv/RequestAudioFocus; do
    if grep -qx "$t" <<<"$SERVICIOS"; then ok "servicio $t"; else falla "no aparece el servicio $t"; fi
  done
elif command -v ros2 >/dev/null 2>&1; then
  TEMAS="$(timeout 10 ros2 topic list 2>/dev/null)"
  for t in /aima/mc/common/state /aima/sm/system_state /aima/hal/pmu/state \
           /aima/hal/sensor/lidar_chest_front/lidar_pointcloud /aima/mc/locomotion/velocity; do
    if grep -qx "$t" <<<"$TEMAS"; then ok "tema $t"; else falla "no aparece el tema $t"; fi
  done
  for t in /aima/hds/post_proc/signal /slam/lidar_odom /aima/pnc/pnc_task_response; do
    grep -qx "$t" <<<"$TEMAS" && ok "tema $t" || echo "  AVISO aún no aparece $t (normal si no hay alertas, mapa o navegación)"
  done
fi

if [ "$FALLAS" -gt 0 ]; then
  echo "== $FALLAS problema(s): el puente no se arranca."
  exit 1
fi
[ "${1:-}" = "--revisar" ] && { echo "== Todo listo (solo revisión)."; exit 0; }

# El contenedor comparte los procesos con PC2 (--pid=host): esto ve también un puente lanzado afuera
if command -v pgrep >/dev/null 2>&1 && pgrep -f "python3 .*$PROGRAMA" >/dev/null; then
  echo "== Ya hay un $PROGRAMA corriendo; no se abre otro. (pkill -f $PROGRAMA para cerrarlo)"
  exit 1
fi
if [ "$PROGRAMA" = puente_voz.py ]; then
  echo "== Arrancando el puente de voz y caras (sin movimiento; Ctrl+C lo detiene)"
else
  echo "== Arrancando el puente (Ctrl+C lo detiene y deshabilita la fuente de entrada)"
fi
exec python3 "$PROGRAMA" "$@"
