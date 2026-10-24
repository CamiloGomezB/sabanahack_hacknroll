#!/bin/bash
# Solo si el robot NO tiene el contenedor aimdk-dev. Corre en PC2 (no en PC1). No toca el
# movimiento. Necesita que el robot tenga internet mientras construye.
#   bash crear_contenedor.sh             # revisa, construye la imagen y arranca el contenedor
#   bash crear_contenedor.sh --revisar   # solo revisa
set -uo pipefail
cd "$(dirname "$0")"
NAME="${NAME:-aimdk-dev}"

if podman ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$NAME"; then
  echo "== Ya existe el contenedor $NAME: no hace falta crearlo."
  echo "   (si está detenido: podman start $NAME)"
  exit 0
fi

echo "== Espejos internacionales (200 o 401; nvcr.io responde 401 sin sesión, es normal)"
FALLA=0
for u in https://nvcr.io/v2/ \
         http://ports.ubuntu.com/ubuntu-ports/dists/jammy/Release \
         http://packages.ros.org/ros2/ubuntu/dists/jammy/Release \
         https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
         https://pypi.org/simple/pip/ ; do
  c=$(curl -s -o /dev/null -w '%{http_code}' -m 15 "$u")
  printf "  %-62s %s\n" "$u" "$c"
  case "$c" in 200|401) ;; *) FALLA=1 ;; esac
done
[ "$FALLA" = 1 ] && echo "  FALLA: el robot no llega a internet o a algún espejo."

echo "== /etc/subgid (ninguna línea puede terminar en espacio; manual 4.4.1)"
if grep -qE '[[:space:]]+$' /etc/subgid 2>/dev/null; then
  echo "  FALLA: hay espacios al final. Arreglo (lo corre la persona en el robot):"
  echo "    sudo sed -i 's/[[:space:]]*\$//' /etc/subgid && podman system migrate"
  FALLA=1
else
  echo "  OK"
fi

[ "${1:-}" = "--revisar" ] && exit "$FALLA"
[ "$FALLA" = 1 ] && { echo "== No se construye: arregla lo de arriba primero."; exit 1; }

echo "== Construyendo agi/aimdk-dev:dev (puede tardar 20-40 min)"
podman build -t agi/aimdk-dev:dev . || exit 1
echo "== Arrancando el contenedor"
bash run.sh || exit 1
podman exec "$NAME" bash -lc 'source /opt/ros/humble/setup.bash && ros2 topic list | head -5'
echo "== Listo. Siguiente, desde el portátil: .\\conectar_voz.ps1 (o bash ../iniciar_puente.sh --voz --revisar)"
