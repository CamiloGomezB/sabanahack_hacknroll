# Control a distancia del X2 Ultra

Mover el X2 Ultra real desde el portátil **solo con las funciones que ya trae AimDK**. No tocamos
motores, equilibrio ni modos. Le pedimos una velocidad al control de movimiento del robot (como en el
ejemplo 6.1.10 de AimDK) y vigilamos todas las protecciones que el robot publica: si alguna avisa
algo, o deja de llegar, el puente no mueve el robot.

```
portátil                                   X2 Ultra
control_x2.py ──túnel SSH (puerto 8765)──► puente_x2.py  (unidad de desarrollo PC2, 10.0.1.41)
                                              │  ROS 2 / AimDK
                                   órdenes    ├─► /aima/mc/locomotion/velocity   (velocidad, 50 Hz)
                                              ├─► SetMcInputSource               (fuente sdk_anfitrion_remoto, prioridad 30)
                                              ├─► /aima/te/pnc_task_request      (navegación del robot)
                                   vigila     ├─◄ /aima/mc/common/state          (modo, postura, protección, límites, mando)
                                              ├─◄ /aima/sm/system_state          (Business / EStop / OTA / apagado)
                                              ├─◄ /aima/hds/post_proc/signal     (alertas: caída, parada, temperatura)
                                              ├─◄ /aima/hal/pmu/state            (batería)
                                              ├─◄ /aima/hal/sensor/lidar_chest_front/lidar_pointcloud (obstáculos)
                                              ├─◄ /slam/lidar_odom               (posición, si hay mapa)
                                              └─◄ /aima/pnc/pnc_task_response    (cómo va la navegación)
```

| Archivo | Dónde corre | Qué hace |
|---|---|---|
| `puente_x2.py` | En el robot (PC2) | Recibe órdenes, revisa la seguridad y las convierte en velocidades de AimDK. Con `--simulado`, en cualquier computador. |
| `control_x2.py` | En el portátil | Consola de órdenes y mando con teclado. Solo usa la librería estándar de Python. |
| `desplegar.ps1` | En el portátil | Copia el puente a PC2 y corre la revisión del robot (no arranca nada). |
| `conectar_x2.ps1` | En el portátil | En una sola ventana: entra a PC2, arranca el puente y abre el túnel SSH (puerto 8765). |
| `iniciar_puente.sh` | En el robot (PC2) | Revisa que sea PC2 (se niega en PC1), que estén ROS 2, AimDK y los temas de seguridad, y arranca el puente. |
| `puente_voz.py` | En el robot (PC2) | Recepción fija: voz (`PlayTts` o audio del portátil por `AudioPlayback`), cara (`PlayEmoji`) y volumen. Nada de movimiento. Con `--simulado`, en cualquier computador. |
| `conectar_voz.ps1` | En el portátil | Como `conectar_x2.ps1`, pero arranca `puente_voz.py` (túnel 8766). |
| `contenedor/` | En el robot (PC2) | Solo si no existe `aimdk-dev`: Dockerfile con espejos internacionales, `run.sh` corregido, `crear_contenedor.sh` y `agente_robot.sh` (apagar o restaurar el asistente propio). |
| `../simulation/recepcion_fija.py` | En el portátil | Recepción fija: cámara del portátil, Supabase y la voz del X2. |
| `../simulation/robots/x2_aimdk.py` | En el portátil | El mismo X2 que usa la simulación (`ir_a`, `volver_al_puesto`, `patrullar`), pero moviendo el robot real. |

En el robot no hay que instalar nada: el puente usa Python, ROS 2 Humble, `numpy` y los mensajes de
AimDK (`aimdk_msgs`), que ya vienen. Así se respeta la regla de AgiBot de no modificar el sistema de
la unidad de desarrollo.

## Órdenes

| Orden | Ejemplo | Qué hace |
|---|---|---|
| avanzar | `avanzar 1` · `avanzar -0.5` · `avanzar 1 0.4` | Avanza esa distancia en metros; el último número es la velocidad (por defecto 0,3 m/s). Hacia atrás, máximo 0,5 m. |
| girar | `girar 90` · `girar -45` | Gira en el sitio esos grados (positivo = izquierda), a 0,3 rad/s. |
| teclado | `teclado` | W/S adelante y atrás, A/D girar, Q/E de lado, Espacio parar, Esc salir. |
| estado | `estado` | Posición, modo, postura, sistema, batería, distancia al obstáculo de delante, quién tiene el mando y, si no puede caminar, por qué. |
| navegar | `navegar 1773113429735 2.0 1.5` | Navegación propia del robot hasta (x, y) de un mapa ya hecho (ejemplo 6.1.30). |
| detener | `d` o Ctrl+C | Se detiene enseguida (también cancela la navegación). |

Cómo mide el metro: si el robot está relocalizado en un mapa, usa la odometría del LiDAR
(`/slam/lidar_odom`) y la distancia es real. Si no, la estima con la velocidad pedida y el tiempo;
`estado` dice cuál está usando (`odometria` o `estimada`). La estimación no ve que el robot tarda en
arrancar ni que resbale, así que en la primera prueba hay que medir con una cinta.

## Seguridad

Todo sale de los manuales y ejemplos de AgiBot: el manual de uso del X2 Ultra (v1.1.0, en
[Feishu](https://agirobot.feishu.cn/wiki/BRInwKudcif4yHky08Xc3NnSn2e)), AimDK con sus ejemplos en
Python y C++, la guía de la sala de exposición con sus límites, la guía de teleoperación y el manual
de ServiceTool. El puente **falla cerrado**: si un dato de
seguridad no llega, no se mueve.

### Lo que el puente revisa antes de cada orden y 50 veces por segundo mientras se mueve

| Qué | Dato de AimDK | Si falla |
|---|---|---|
| Modo de movimiento | `action_info.action_desc` = `STAND_DEFAULT` o `LOCOMOTION_DEFAULT` | No se mueve. El modo lo pone una persona con el control remoto o la app; el puente nunca cambia modos. |
| No está cambiando de modo | `action_info.status` ≠ 200 / 300 | No se mueve |
| Protección del robot | `fsm_state` = STABLE o MOVING (SAFE = protección activa) | Se detiene |
| Postura | `body_status` = de pie (no caída, sentado ni agachado) | Se detiene |
| Límites de velocidad del robot | `speed_status` (modo de velocidad y sus límites) | Nunca se piden velocidades fuera de esos límites; con el modo NONE no se mueve |
| Sistema | `/aima/sm/system_state` = `Business` y listo | Se detiene con EStop, OTA, apagado por batería baja, reinicio o fallas |
| Alertas de diagnóstico (HDS) | `robot_sig` de `/aima/hds/post_proc/signal` | Se detiene con parada de emergencia (17, 19), caída (42, 52), extremidades deshabilitadas (90), sobretemperatura (131, 132, 136), fallo del sistema (154), etc. Solo no bloquean las que no tienen que ver con caminar: cámara tapada (209), micrófono (210), aviso de batería mal mostrada (161). |
| Batería | `battery_remaining_capacity_percentage` | Con menos de 30 % no se mueve (el robot avisa "carga pronto" bajo 30 %; bajo 15 % se apaga y puede caer) |
| Carga | `battery_current` (positiva = cargando) | Mientras carga no se mueve (el manual lo prohíbe) |
| Tiempo caminando | Lo cuenta el puente | Tras 10 min caminando no se mueve hasta descansar 3 min (el manual pide no pasar de 10 min seguidos para que no se recaliente) |
| Obstáculo delante | LiDAR del pecho | No avanza con algo a menos de **1 m** delante (lo que pide la guía de AgiBot); si el LiDAR deja de llegar, no avanza (sí puede girar y retroceder) |
| Mando | `input_source` | Si la app o el control remoto toman el mando, se detiene. Con Linkswarm activo no se mueve. |
| Localización | `/slam/lidar_odom` | Si la posición salta más de 30 cm de golpe, se detiene |
| Datos al día | Estado del movimiento cada 0,5 s, sistema cada 3 s, batería cada 5 s y LiDAR cada 0,5 s | Si alguno se atrasa, se detiene |

### Paradas automáticas

- AimDK detiene el robot si pasan 200 ms sin órdenes de velocidad. Si pasan 2 s, vuelve solo a
  estar de pie en equilibrio.
- El mando con teclado dura 0,5 s si no se renueva.
- Si el portátil pasa 1 s sin enviar nada mientras el robot se mueve, o se cae la conexión, el puente
  lo detiene.
- Toda orden tiene un tiempo máximo: si el robot no llega (un obstáculo, por ejemplo), se detiene.

### Límites

| Límite | Valor | Por qué |
|---|---|---|
| Adelante | 0,5 m/s | La guía de AgiBot pide 0,5 m/s; el uso diario del X2 es ≤ 0,8 m/s |
| Atrás | 0,25 m/s y 0,5 m por orden | El LiDAR solo ve hacia adelante |
| De lado | 0,6 m/s | El robot necesita ~0,5 m/s para dar el primer paso de lado |
| Giro | 0,5 rad/s (0,3 por defecto) | Los manuales piden evitar giros rápidos |
| Distancia y giro | 5 m y 360° por orden | — |
| Aceleración | 0,5 m/s² y 1 rad/s² | AimDK pide órdenes de velocidad suaves y continuas |

### Prioridades

Nuestra fuente de entrada se llama `sdk_anfitrion_remoto` (AimDK pide el prefijo `sdk_`) y tiene
**prioridad 30**, la del rango de desarrollo (20-39). Por eso **el control remoto (80), la app (60) y
los módulos del robot siempre mandan más**: si alguien toca el control remoto, el robot le hace caso a
él y el puente se detiene. No tocamos las fuentes del sistema (`rc`, `app_proxy`, `linkswarm`, ...).

### Lo que NO hacemos (a propósito)

- No cambiamos modos (`SetMcAction`) ni entramos a modos de desarrollador (`Develop_MC`, etc.).
- No apagamos el control remoto. El ejemplo de teclado de AgiBot sugiere
  `aima em stop-app rc` para que el control no ocupe el canal; **no lo hagan**: el control remoto es
  la parada de emergencia (pasar a cero torque o amortiguado), y con prioridad 30 no hace falta
  quitarlo. Si el control ocupa el canal, `estado` muestra `mando: rc`; hay que soltarlo y esperar
  1 s.
- No mandamos órdenes a las articulaciones (`/aima/hal/joint/*`, que no tienen parada automática) ni
  detenemos el control de movimiento (`aima em stop-app mc`).
- Nada corre en la unidad de control de movimiento (PC1, 10.0.1.40); todo va en PC2.
- No lanzamos muchos nodos de ROS a la vez (AimDK advierte que eso puede hacer caer al robot): el
  puente es **un solo nodo**.

### Las personas

- Siempre una persona con el **control remoto** en la mano y otra con la **app abierta**. La parada de
  emergencia del control es **L1 + R1 + Create** (cero torque): el robot suelta todas las
  articulaciones y **cae**, así que es solo para emergencias. Para detenerlo normalmente basta
  soltar el control o `d` en el portátil. Para salir de la parada: L2 + X.
- El control remoto (mando PS5) tiene que estar cargado: con poca batería puede fallar el cambio de
  modo y el robot puede caerse.
- El manual pide que quien opera a distancia **vea el robot y su entorno en todo momento**: el
  portátil tiene que estar donde se vea el robot.
- Una sola fuente de control a la vez: no alternar entre la app, el control y el portátil. Si alguien
  toma el control o la app, el puente se detiene y no vuelve a mandar hasta que le den otra orden.
- Quien opera, **detrás del robot**, a 1-2 m. Nadie a menos de 1 m del robot ni en su camino.
- Piso duro, plano y que no resbale. Nada de alfombras, pasto, escaleras ni rampas. Temperatura de
  -10 °C a 40 °C.
- Antes de mover, quitar el plástico protector del LiDAR y de la cámara del pecho.
- Lo que el LiDAR del robot no ve bien, según la guía de AgiBot: obstáculos de menos de 15 cm
  (cables, bolsos), vidrio y espejos, patas delgadas de sillas, bordes de mesas a la altura del
  pecho, escalones y desniveles, rampas de más de 3°, pisos muy brillantes. En esos lugares, no
  mover el robot o hacerlo con alguien al lado.
- Pasillos de menos de 1,5 m: la navegación del robot los considera intransitables.

## Probar sin robot

En el portátil, desde `simulation/` (usa el mismo entorno de Python):

```bash
.venv\Scripts\python.exe ..\robot_x2\puente_x2.py --simulado
```

Y en otra terminal:

```bash
.venv\Scripts\python.exe ..\robot_x2\control_x2.py
```

`--sin-odometria` simula el robot sin mapa (la distancia se estima). Con `--simulado` existe además
la orden `simular`, que cambia el estado del robot de mentira (postura, alertas, batería, pared
delante, datos que dejan de llegar). Todas las protecciones se prueban de una vez con:

```bash
.venv\Scripts\python.exe ..\robot_x2\probar_seguridad.py
```

## Recepción fija (sin movimiento): lo recomendado para la demo

El X2 se queda quieto en su puesto (de pie o sentado, como lo deje el control remoto). Mira a quien
llega, lo reconoce y habla. No se usa nada de movimiento: ni `puente_x2.py`, ni velocidades, ni la
fuente de entrada.

```
portátil                                                   X2 Ultra (PC2, 10.0.1.41)
cámara del portátil ─► recepcion_fija.py ─túnel SSH 8766─► puente_voz.py ─► PlayTts / AudioPlayback (voz)
   (SFace real)            │  voz_x2.py: frase en español                  └─► PlayEmoji (cara en la pantalla)
                           │  con la voz de Windows (Helena, es-ES)
                           └─► Supabase: registrar_llegada, contexto_llegada, avisos (app móvil y panel web)
```

Qué hace con cada persona (decide la base, igual que en la simulación):

| Quién llega | Qué dice el X2 | Cara |
|---|---|---|
| Miembro VIP o regular con su cara registrada | "¡Buenas tardes, Camila! Te damos la bienvenida a N Club." y su reserva de hoy, si tiene | encantado / feliz |
| Personal en su turno | Bienvenida, su primera tarea y la novedad del día | feliz |
| Alguien que no reconoce | "No encuentro tu registro. Si traes invitación, pase u orden de trabajo, muéstrame el código QR…" (dos intentos) | parpadeo |
| Invitado o externo con QR válido | Bienvenida, "Ya le avisé a Camila que llegaste", punto de encuentro; espera la respuesta en la app (60 s) | feliz |
| QR vencido, falso, de demostración, membresía vencida, fuera de horario o cara dudosa | Explica el motivo sin acusar y lo manda al mostrador de recepción | aburrido |

Nunca promete moverse ni acompañar: cuando alguien necesita compañía, lo acompaña recepción.

**Pasos** (desde la carpeta `robot_x2`):

```powershell
.\desplegar.ps1 -Usuario agi             # una vez: copia los puentes y revisa el robot
.\conectar_voz.ps1 -Usuario agi          # deja esta ventana abierta: puente de voz + túnel 8766
```

Y en otra ventana, desde `simulation`:

```powershell
python recepcion_fija.py --supabase --voz audio
```

`--voz audio` (lo recomendado): el portátil genera la frase en español y la manda al parlante del
robot. `--voz x2`: la voz propia del robot (`PlayTts`); el manual solo promete chino e inglés, así
que hay que oírla antes de usarla. `--voz pc`: los parlantes del portátil. Con `--voz auto` usa el
robot si el puente responde y, si no, el portátil. Si el robot deja de responder en plena demo, la
voz sigue por el portátil. `--volumen 70` ajusta el volumen del X2. Sin `--supabase` decide la
copia local con las mismas personas, y la app del anfitrión se simula (acepta sola a los 4 s; la
tecla N la deja sin respuesta).

Para probar sin robot: `python puente_voz.py --simulado` en una ventana y `recepcion_fija.py` en
otra.

`--ollama` (Ollama corriendo en el portátil, `qwen2.5:3b` por defecto) reescribe con otro tono solo la
bienvenida y el "ya viene por ti". El robot no cambia: recibe el texto o el audio final. Cada dato
(nombre, hora y lugar de la reserva, tarea, novedad, empresa, anfitrión, punto de encuentro) tiene
que quedar idéntico; si cambia uno, o si agrega "¿puedes pasar?" u otra promesa, o si tarda más de
3,5 s, se dice el texto fijo. Los mensajes de QR y de recepción nunca se reescriben. En las pruebas,
`qwen2.5:3b` tardó unos 2,5 s y pasó la mitad de sus versiones (casi siempre las acorta);
`qwen2.5:7b` tardó unos 4 s e inventó más. El audio de esas frases se genera en el momento (unos
0,9 s más), porque no está en la caché.

### Red

Lo mejor: **cable al robot y el portátil en la WiFi del lugar**. `recepcion_fija.py --supabase`
necesita internet para llegar a Supabase, y conectado al punto de acceso del robot el portátil
probablemente se queda sin internet. El robot no necesita internet: con `--voz audio` el audio lo
genera el portátil (la voz propia del robot, `PlayTts`, sí podría necesitarla; entre sus códigos
de error está la pérdida de red).

Por WiFi del robot: `-PorWifi` salta por `192.168.88.88`. El manual no dice con qué usuario; los
scripts usan el mismo de PC2 y, si es otro, se pasa con `-UsuarioSalto <usuario>`.

### El asistente propio del robot

El X2 trae su propio asistente de voz (se despierta con "Hello, lumi") y puede contestarle a la
gente del lobby o hablar encima de la recepción. Hay que probarlo con el robot en el lobby. Si
estorba, se apaga dentro del contenedor (manual de AimDK, 8.1) y **se restaura al terminar**:

```bash
bash ~/aimdk/anfitrion_x2/contenedor/agente_robot.sh apagar      # modo only_voice
bash ~/aimdk/anfitrion_x2/contenedor/agente_robot.sh restaurar   # modo normal
```

### Si el robot no tiene el contenedor `aimdk-dev`

Primero se pregunta a soporte o a los organizadores si ya existe (`podman ps -a` en PC2). Si no,
`contenedor/` trae el `Dockerfile` del manual (4.4.1) con espejos internacionales (los del manual
están en China y desde Colombia pueden fallar) y el `run.sh` del manual corregido (Word le quitó
los `$` en el .docx). `desplegar.ps1` los copia; en PC2, con internet:

```bash
bash ~/aimdk/anfitrion_x2/contenedor/crear_contenedor.sh --revisar   # espejos y /etc/subgid
bash ~/aimdk/anfitrion_x2/contenedor/crear_contenedor.sh             # construye y arranca (20-40 min)
```

No compila OpenCV (solo lo usan los ejemplos C++ del SDK); si hiciera falta:
`podman build --build-arg CON_OPENCV=1 -t agi/aimdk-dev:dev .`. Después hay que compilar AimDK
dentro del contenedor como dice el manual (4.4.5); `iniciar_puente.sh --revisar` avisa si falta.

### Lo real y lo simulado (para la presentación)

| Parte | En la demo |
|---|---|
| Reconocimiento facial (SFace), lectura del QR | **Real**, con la cámara del portátil (no la del robot) |
| Decisión, eventos, avisos al anfitrión en la app, panel de recepción | **Real**, en Supabase |
| Voz del X2 y cara en su pantalla | **Real** en el robot (el audio en español lo genera el portátil) |
| Movimiento del X2 (patrullar, ir a la puerta) | No se usa en la recepción fija. Existe (`puente_x2.py`, `robots/x2_aimdk.py`) pero el coordinador de la simulación todavía no lo usa |
| Gestos del X2 (saludar, señalar el mapa) | Solo en la simulación (allá solo esperan su duración) |
| D1 (acompañar, cargar maletas) | Solo en la simulación; no se despliega |

## Despliegue en el X2 Ultra

Todo se hace desde este portátil. Esto es para el **X2 Ultra** (placa de la nuca terminada en "X2
Ultra"), no para el X2 Ultra (new version), cuya placa termina en "X2 Ultra -N". Los temas y servicios
de AimDK que usa el puente son los mismos en los dos; lo que cambia en la versión nueva (cuello de 2
ejes, UWB, puertos USB, cámara trasera girada) el puente no lo usa.

Lo que hay que pedirle al soporte de AgiBot o a los organizadores:

- **La contraseña SSH** de la unidad de desarrollo (PC2). El manual no la publica ("credentials require
  technical support"). El usuario parece ser `agi`, porque el SDK vive en `/home/agi/aimdk`. No pongas
  la contraseña en el repositorio.
- **La versión del firmware** y si ya existe el **contenedor de desarrollo** (`aimdk-dev`). Desde el
  firmware v1.2.0, AgiBot exige que los programas propios corran dentro de ese contenedor (manual de
  AimDK, 4.4 "Develop in a Container"); fuera de él quedan con permisos restringidos. Crearlo es una
  sola vez, en PC2, con `contenedor/crear_contenedor.sh` (ver "Si el robot no tiene el contenedor"
  arriba). Necesita internet y tarda, así que conviene que esté hecho antes. Si ya existe con otro
  nombre: `CONTENEDOR=<nombre>`.

**1. Conectarse al robot** (una de las dos):

- **Cable**: pon en el portátil la IP fija 10.0.1.2 (máscara 255.255.255.0) y conéctalo al puerto
  de desarrollo. PC2 queda en `10.0.1.41`.
- **WiFi**: activa el punto de acceso (AP Hotspot) en la app del robot y conéctate a esa red. PC2
  se alcanza pasando por `192.168.88.88`.

En el portátil no hay que instalar nada más: Windows ya trae `ssh` y `scp`, y `control_x2.py` solo
usa Python. La contraseña la pide `ssh` en la misma ventana; los scripts no la guardan.

**2. Copiar y revisar** (desde la carpeta `robot_x2`):

```powershell
.\desplegar.ps1 -Usuario agi            # por WiFi: agrega -PorWifi
```

Copia `puente_x2.py` e `iniciar_puente.sh` a `~/aimdk/anfitrion_x2` en PC2 (dentro de `~/aimdk`,
que es la única carpeta que el contenedor comparte con PC2) y corre `iniciar_puente.sh --revisar`, que
no arranca nada. El script entra solo al contenedor y desde ahí confirma que no es PC1, que están ROS 2
Humble, AimDK compilado, `numpy`, los mensajes que usa el puente y los temas de seguridad del robot. Si
dice FALLA, no sigas: cada falla dice qué hacer (crear o encender el contenedor, compilar AimDK con
`colcon build`). Solo con firmware v1.1.0, que aún permite correr fuera del contenedor, se puede usar
`ANFITRION_EN_HOST=1`.

El manual avisa que una actualización de firmware o un restablecimiento de fábrica pueden borrar
`~/aimdk`; si pasa, se vuelve a correr `desplegar.ps1`.

Si Windows no deja correr scripts, sin cambiar ninguna configuración:
`powershell -ExecutionPolicy Bypass -File .\desplegar.ps1 -Usuario agi`.

**3. Arrancar el puente y abrir el túnel**, **con el robot quieto** (esta ventana se queda abierta):

```powershell
.\conectar_x2.ps1 -Usuario agi          # por WiFi: agrega -PorWifi
```

Todo pasa desde el portátil: entra a PC2 por SSH, entra al contenedor, repite la revisión, arranca el
puente (no abre un segundo puente si ya hay uno) y en la misma conexión abre el túnel del puerto 8765.
El contenedor usa la red del robot (`--network=host`), así que el túnel llega igual. Debe decir "Fuente
de entrada registrada" y "Puente del X2 escuchando en 127.0.0.1:8765".

Ctrl+C en esa ventana, cerrarla o que se caiga la conexión cierran el puente: detiene el robot y
deshabilita la fuente de entrada. Si se cae solo el túnel, el puente deja de recibir noticias del
portátil y detiene el robot en 1 s.

**4. Poner el robot de pie** con el control remoto (R2 + X: de pie en equilibrio) y soltar el
control.

**5. Controlarlo desde el portátil**, en otra terminal:

```bash
python robot_x2\control_x2.py
```

### Primera prueba, paso a paso

1. `estado` con el robot de pie y quieto. Debe decir `modo STAND_DEFAULT · de pie · sistema
   Business`, la batería y **no** "NO PUEDE CAMINAR". Si lo dice, el motivo explica qué falta.
2. **Probar el LiDAR antes de caminar**: pon una caja de unos 40 cm de alto a 0,8 m delante del
   robot. `estado` debe decir `delante 0.8 m` (más o menos) y `avanzar 1` debe ser rechazado por el
   obstáculo. Quita la caja: debe decir `delante libre`. Si no coincide, el LiDAR está montado con
   otros ejes de los que supusimos (`OBSTACULO_ZONA` en `puente_x2.py`): **no caminar** hasta
   ajustarlo.
3. Probar la parada: `avanzar 1` y a mitad de camino Ctrl+C. Debe detenerse.
4. Probar el control remoto: `avanzar 2` y mover un joystick. El robot debe hacerle caso al control
   y el puente debe decir que otra fuente tomó el mando.
5. `girar 90`, `avanzar 0.5`, `avanzar 1`, midiendo con cinta.

## Siguiente paso: autónomo

1. **Mapear el lobby** con el robot (ejemplo 6.1.27 de AimDK; guía de la sala de exposición:
   moverse a 0,5 m/s, nada a 1 m delante, volver al punto de inicio). Relocalizarlo (6.1.28). Con
   eso `/slam/lidar_odom` publica la posición y `avanzar` mide distancias reales.
2. Medir en el mapa las coordenadas de los puntos del club (puesto, patrulla, puertas) y usar
   `navegar`: la navegación del robot planea la ruta y esquiva obstáculos con su propia percepción.
   En el mapa se pueden poner **paredes virtuales** y zonas prohibidas.
3. Conectar el coordinador de la simulación con `robots/x2_aimdk.py` en lugar de `x2_sim.py`.
   `ir_a`, `volver_al_puesto` y `patrullar` ya funcionan con el puente; falta llevar al robot la
   voz (TTS de AimDK, 6.1.20), los gestos y la cámara.

## Por confirmar en el robot real

Lo probamos con un robot simulado que responde como dice el manual, no con el X2. Hay que confirmar:

- Que `/aima/mc/common/state` reporta `STAND_DEFAULT` con el robot de pie y `fsm_state` STABLE.
- Que en uso normal el sistema reporta `Business` con estado listo (1). Si reporta otro estado
  estando bien, el puente no se moverá: anotar lo que dice `estado` y ajustar `SISTEMA_LISTO`.
- Los ejes del LiDAR del pecho (paso 2 de la primera prueba).
- Si `/slam/lidar_odom` publica sin relocalizar (el manual dice que no).
- Que el usuario SSH de PC2 es `agi`, la versión del firmware y que el contenedor `aimdk-dev` existe.
- Que el contenedor ve los temas del robot (`ros2 topic list` dentro de él, como dice el manual).
- Cómo suena `PlayTts` en español (si suena mal, se usa `--voz audio`).
- Si el asistente propio ("Hello, lumi") interrumpe la recepción (ver `agente_robot.sh`).
- Con qué usuario se entra al salto `192.168.88.88` por WiFi (`-UsuarioSalto`).
- Que `aimdk_msgs` trae `PmuState`, `SmSystemState`, `PostProcSigArray` y `PncTaskResponse` con
  esos nombres. Si falta alguno, el puente no arranca y dice cuál.
