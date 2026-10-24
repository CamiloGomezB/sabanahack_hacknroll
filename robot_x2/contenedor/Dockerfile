# Imagen agi/aimdk-dev:dev del manual de AimDK (4.4.1), con espejos internacionales: los del
# manual (ngc.nju.edu.cn, mirrors.aliyun.com, pypi.tuna.tsinghua.edu.cn, gitee) están en China y
# desde Colombia pueden fallar o ir muy lentos. Solo hace falta si el robot NO tiene ya el
# contenedor aimdk-dev (revisar primero: podman ps -a). Se construye en el robot (PC2, aarch64):
#   bash crear_contenedor.sh
FROM nvcr.io/nvidia/l4t-base:r36.2.0

LABEL agi.image.purpose="ROS Humble base, no CUDA bundled (mount /usr/local/cuda + /usr/lib/.../libcudnn,libnvinfer at runtime)"
LABEL agi.image.base="l4t-base:r36.2.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Bogota

# La imagen ya usa ports.ubuntu.com (internacional). Solo se apaga la fuente apt de NVIDIA L4T:
# la imagen no instala paquetes l4t.
RUN if [ -f /etc/apt/sources.list.d/nvidia-l4t-apt-source.list ]; then \
        sed -i -E 's@^[[:space:]]*deb@# deb@' /etc/apt/sources.list.d/nvidia-l4t-apt-source.list; \
    fi

# ROS 2 desde packages.ros.org con la llave oficial. ros-humble-ros-core trae las dependencias
# del sistema; /opt/ros se reemplaza al correr por el del robot (montaje de run.sh).
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg2 lsb-release ca-certificates && \
    curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/ros2.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends ros-humble-ros-core && \
    apt-get install -y --no-install-recommends \
        usbutils iproute2 tini python3-pip \
        build-essential binutils git \
        python3-opencv python3-numpy \
        libjpeg-dev libpng-dev libtiff-dev \
        libavcodec-dev libavformat-dev libavutil-dev libswscale-dev \
        libgtk-3-dev \
        openssh-client \
        libboost-python1.74.0 \
        bluez \
        cmake ninja-build \
        python3-colcon-common-extensions \
        libcurl4-openssl-dev \
        libncurses-dev \
        pkg-config && \
    pip3 install --no-cache-dir -U pip packaging && \
    pip3 install --no-cache-dir "scikit-build-core<0.10" nanobind && \
    pip3 install --no-cache-dir --no-build-isolation ruckig==0.15.3 && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# OpenCV 4.8 compilado (lo usan los ejemplos C++ del SDK, no los puentes de este repo, que son
# Python). Tarda mucho en el robot; por eso va aparte y apagado: --build-arg CON_OPENCV=1.
ARG CON_OPENCV=0
RUN if [ "$CON_OPENCV" = 1 ]; then \
      cd /opt && \
      curl -fSL --retry 3 --retry-delay 5 -m 1800 -o /tmp/opencv-4.8.0.tar.gz \
           https://github.com/opencv/opencv/archive/refs/tags/4.8.0.tar.gz && \
      tar -xzf /tmp/opencv-4.8.0.tar.gz -C /opt && rm -f /tmp/opencv-4.8.0.tar.gz && \
      cd /opt/opencv-4.8.0 && mkdir -p build && cd build && \
      cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
            -DBUILD_PYTHON_SUPPORT=OFF -DBUILD_EXAMPLES=OFF -DBUILD_TESTS=OFF -DBUILD_PERF_TESTS=OFF \
            -DWITH_GTK=ON \
            -DBUILD_LIST=core,imgproc,imgcodecs,videoio,highgui,calib3d,features2d,photo,video,objdetect \
            -DOPENCV_GENERATE_PKGCONFIG=ON .. && \
      make -j"$(nproc)" && make install && \
      rm -rf /opt/opencv-4.8.0; \
    fi

# Las shells interactivas cargan el ROS montado del robot.
RUN echo 'if [ -f /opt/ros/humble/setup.bash ]; then source /opt/ros/humble/setup.bash; fi' \
        >> /etc/bash.bashrc

# Rutas de CUDA montadas desde el robot.
RUN echo "/usr/local/cuda/lib64" > /etc/ld.so.conf.d/cuda.conf && \
    echo "/usr/local/cuda/targets/aarch64-linux/lib" >> /etc/ld.so.conf.d/cuda.conf

WORKDIR /home/agi
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]
