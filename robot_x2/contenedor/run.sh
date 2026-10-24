#!/bin/bash
# run.sh del manual de AimDK (4.4.1), con los "$" que Word se comió en el .docx devueltos a su
# lugar. Arranca agi/aimdk-dev:dev con el ROS, CUDA, cuDNN/TRT y aima del robot montados.
set -euo pipefail

IMAGE="${IMAGE:-agi/aimdk-dev:dev}"
NAME="${NAME:-aimdk-dev}"

# ---- solo agrega un -v si la ruta existe en el robot ----
# Uso: m <origen> [destino (= origen)] [opciones: ro|rw|rslave (ro)]
MOUNTS=()
m() {
  local src="$1" dst="${2:-$1}" opts="${3:-ro}"
  if [ -e "$src" ]; then
    MOUNTS+=("-v" "$src:$dst:$opts")
  else
    echo "  mount $src NOT present, skipping" >&2
  fi
}

# Grupos del robot que son dueños de los dispositivos.
HOST_GIDS=(
  20    # dialout - /dev/ttyUSB*
  29    # audio   - /dev/snd
  44    # video   - /dev/nvmap, /dev/nvhost-* (required by CUDA)
  106   # input   - /dev/input/event*
  109   # render  - /dev/dri/renderD*
  995   # debug   - /dev/nvhost-dbg-*
  1000  # run     - /agibot/data/var/MapManagerModule
)

# GID del robot -> GID dentro del contenedor (mapeo de podman sin root).
GROUP_ADDS=()
MAP_RAW=$(podman info --format '{{.Host.IDMappings.GIDMap}}')
for HG in "${HOST_GIDS[@]}"; do
  CG=$(echo "$MAP_RAW" | grep -oE '\{[0-9]+ '"$HG"' [0-9]+\}' | head -1 \
       | grep -oE '^\{[0-9]+' | tr -d '{' || true)
  if [ -z "$CG" ]; then
    echo "GID $HG not mapped in /etc/subgid, skipping" >&2
  else
    GROUP_ADDS+=("--group-add" "$CG")
    echo "  $HG (host) -> $CG (container)" >&2
  fi
done

# Bibliotecas de CUDA del robot (cuDNN, TensorRT, cuBLAS, cuFFT...).
for f in /usr/lib/aarch64-linux-gnu/libcudnn*.so* \
         /usr/lib/aarch64-linux-gnu/libnvinfer*.so* \
         /usr/lib/aarch64-linux-gnu/libnvonnxparser*.so* \
         /usr/lib/aarch64-linux-gnu/libnvparsers*.so* \
         /usr/lib/aarch64-linux-gnu/libnvcaffe_parser*.so* \
         /usr/lib/aarch64-linux-gnu/libcublas*.so* \
         /usr/lib/aarch64-linux-gnu/libcufft*.so* \
         /usr/lib/aarch64-linux-gnu/libcurand*.so* \
         /usr/lib/aarch64-linux-gnu/libcusolver*.so* \
         /usr/lib/aarch64-linux-gnu/libcusparse*.so* \
         /usr/lib/aarch64-linux-gnu/libcupti*.so* \
         /usr/lib/aarch64-linux-gnu/libnpp*.so* \
         /usr/lib/aarch64-linux-gnu/libnvjpeg*.so* \
         /usr/lib/aarch64-linux-gnu/libnvToolsExt*.so* \
         /usr/lib/aarch64-linux-gnu/libnvrtc*.so* ; do
  m "$f"
done
echo "  CUDA libs to bind-mount: $(ls /usr/lib/aarch64-linux-gnu/libcuda*.so* 2>/dev/null | wc -l) files" >&2

# ncurses (ejemplo del teclado).
for f in /usr/include/curses.h /usr/include/ncurses*.h /usr/include/term.h \
         /usr/include/termcap.h /usr/include/unctrl.h /usr/include/eti.h \
         /usr/lib/aarch64-linux-gnu/libncurses*.so* /usr/lib/aarch64-linux-gnu/libtinfo*.so* \
         /usr/lib/aarch64-linux-gnu/pkgconfig/ncurses*.pc /usr/lib/aarch64-linux-gnu/pkgconfig/tinfo*.pc; do
  m "$f"
done

# include de Python (numpy...) que los CMake de /opt/ros nombran con ruta absoluta.
while read -r d; do
  m "$d"
done < <(grep -rhoE '/[A-Za-z0-9_./+-]*(dist|site)-packages/[A-Za-z0-9_./+-]*include' \
           --include='*.cmake' /opt/ros/humble/share 2>/dev/null | sort -u)

# Variables AGIBOT_* del bashrc que administra el firmware.
AGIBOT_BASHRC="/home/agi/.aima/env/bashrc"
ENV_FILE=$(mktemp /tmp/aimdk-env.XXXXXX)
trap 'rm -f "$ENV_FILE"' EXIT
if [ -r "$AGIBOT_BASHRC" ]; then
  sed -nE "s/^export (AGIBOT_[A-Z_]+)='(.*)'\$/\1=\2/p" "$AGIBOT_BASHRC" > "$ENV_FILE"
  echo "  AGIBOT env vars: $(wc -l < "$ENV_FILE") loaded from $AGIBOT_BASHRC" >&2
else
  echo "  $AGIBOT_BASHRC not readable, skipping AGIBOT_* env" >&2
fi

# Quita un contenedor anterior con el mismo nombre.
if podman ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "stopping & removing old $NAME..."
  podman rm -f "$NAME" >/dev/null
fi

# Configuración DDS del firmware (descubrimiento compartido con el robot).
m /home/agi/.aima/env/ros_dds_configuration.xml /etc/ros_dds_configuration.xml

# La carpeta del SDK, siempre, de lectura y escritura.
m /home/agi/aimdk /home/agi/aimdk rw

echo "starting $NAME from $IMAGE..."
podman run -d --name "$NAME" \
  --ipc=host --network=host --pid=host \
  --device nvidia.com/gpu=all \
  "${GROUP_ADDS[@]}" \
  -e HOME=/home/agi \
  -e FASTRTPS_DEFAULT_PROFILES_FILE=/etc/ros_dds_configuration.xml \
  -e PATH=/opt/ros/humble/bin:/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  -e LD_LIBRARY_PATH=/usr/local/lib:/usr/local/cuda/lib64:/opt/ros/humble/lib:/host-libs/aarch64-linux-gnu \
  --env-file "$ENV_FILE" \
  -v /etc/machine-id:/etc/machine-id:ro \
  -v /usr/lib/aarch64-linux-gnu:/host-libs/aarch64-linux-gnu:ro \
  -v /opt/ros:/opt/ros:ro \
  -v /usr/local/bin/aima:/usr/local/bin/aima:ro \
  -v /dev:/dev:rslave \
  -v /run/dbus:/run/dbus:rslave \
  "${MOUNTS[@]}" \
  "$IMAGE"
