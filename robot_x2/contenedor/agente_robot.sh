#!/bin/bash
# Agente de voz propio del X2 (palabra de activación "Hello, lumi"): puede contestarle a la gente
# del lobby y hablar encima de la recepción. Manual de AimDK, 8.1.
#   bash agente_robot.sh apagar        # modo only_voice: el agente propio deja de conversar
#   bash agente_robot.sh restaurar     # vuelve al modo normal (hacerlo al terminar la demo)
# Cambia la configuración local del robot hasta que se restaure. Correr en PC2 (no en PC1), dentro
# del contenedor aimdk-dev o en el robot mismo, donde estén ros2 y aima. No toca el movimiento.
# Después de apagarlo, probar que la voz del robot (PlayTts) sigue hablando; con
# recepcion_fija.py --voz audio no se depende de ella.
set -eo pipefail

# El setup.bash de ROS falla con set -u: se carga sin él.
for s in /opt/ros/humble/setup.bash "$HOME/aimdk/install/setup.bash"; do
  if [ -f "$s" ]; then
    # shellcheck disable=SC1090
    source "$s"
  else
    echo "FALLA no está $s (¿AimDK compilado? manual 4.4.5)"; exit 1
  fi
done
set -u
command -v ros2 >/dev/null || { echo "FALLA no está ros2"; exit 1; }
if ! command -v aima >/dev/null; then
  echo "FALLA no está el comando aima. El manual lo corre en el robot (fuera del contenedor):"
  echo "      sal del contenedor (exit) y corre este script en PC2."
  exit 1
fi

modo() {
  ros2 service call /aimdk_5Fmsgs/srv/SetAgentPropertiesRequest \
    aimdk_msgs/srv/SetAgentPropertiesRequest "
contents:
  properties:
    - key:
        value: 2
      value: '$1'
"
  # Si esto falla dentro del contenedor, correr el script en el robot mismo (como el manual).
  aima em stop-app agent
  aima em start-app agent
}

case "${1:-}" in
  apagar)
    modo only_voice
    echo "== Agente propio en only_voice. Al terminar: bash agente_robot.sh restaurar" ;;
  restaurar)
    modo normal
    echo "== Agente propio en modo normal." ;;
  *)
    echo "uso: bash agente_robot.sh apagar|restaurar"
    exit 2 ;;
esac
