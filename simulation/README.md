# Simulación (MuJoCo)

Simulación de N Club con el X2 Ultra en la recepción y el D1 guiando a las personas que lo
necesitan. **Todo lo que se ve aquí es simulado**: los robots, las personas, el reconocimiento facial y
los datos (de prueba, en `datos_falsos.py`).

El club tiene **habitaciones** (lobby, Sala VIP, piscina, canchas, restaurante, gimnasio, oficinas y
mantenimiento) con muros de 2,4 m, una puerta por zona y su mobiliario, **sin techo** para verlas desde
arriba. Mientras no llega nadie, el **X2 camina por el lobby buscando a quién recibir** (mueve la
cabeza de lado a lado); cuando alguien entra por la puerta, vuelve a su puesto junto al mapa, se gira
y lo saluda con la mano. La caminata es la misma cinemática inversa del video (`marcha_x2.py`).

## Cómo correrla

```bash
cd simulation
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

Opciones:

| Opción | Qué hace |
|---|---|
| `--hora 15:30` | Hora simulada de inicio (por defecto 10:00). Cambia quién puede entrar. |
| `--velocidad 2` | Corre la demo más rápido. |
| `--sin-cierre` | No cierra el pasillo central a mitad de la demo (por defecto se cierra antes del caso 7). |
| `--validar` | Sin ventana: corre los 17 casos y escribe `docs/validacion.md` (esperado frente a observado y métricas). |
| `--capturas carpeta/` | Sin ventana: guarda una imagen cada `--cada` segundos (`--vista visitante`: desde los ojos de quien entra). |

Teclas en el visor: **Espacio** = siguiente caso, **A** = modo automático/manual, **B** = cerrar o
abrir el pasillo central, **C** = cambiar cámara.

Cámaras (tecla **C**), en este orden:

1. **Visitante** (la inicial): los ojos de la persona que está entrando, o de la siguiente en la fila
   si no hay nadie. Cada figura lleva una cámara a 1,62 m mirando un poco hacia abajo (`vista_<i>`).
2. **General**: el club desde arriba, desde la entrada hacia el fondo.
3. **Recepción**: el X2 de frente con el mapa.
4. **D1**: sigue al cuadrúpedo.

El panel de la izquierda muestra el caso en curso como **evidencia → categoría → orientación**
(qué vio el robot, qué categoría confirmó y cómo orienta), además del **trato** que pidió la
persona, el **aviso en la app** de su anfitrión o responsable (SIMULADO) y lo que hace el D1. Arriba a
la derecha están el estado de **recepción** y la lista de casos con su resultado (OK si lo obtenido es
lo esperado).

## Video del X2 caminando (para la presentación)

```bash
python video_x2.py                              # 12 s, 1920×1080, 40 fps
python video_x2.py --segundos 20 --distancia 3  # más largo y con la cámara más lejos
```

Graba al X2 desde la espalda, con la cámara siguiéndolo, por un pasillo con piso de madera laminada.
El video queda en `videos/x2_caminando.mp4`; los `.mp4` no se suben al repositorio. Es solo material
visual: la caminata es una animación por cinemática inversa (los pies no resbalan sobre el piso), no
un controlador real del robot. La textura de la madera la genera el mismo script
(`texturas/madera_laminada.png`).

## Modelo del X2

El modelo oficial del X2 Ultra (`x2_ultra.xml` de `X2_URDF-v1.3.0` y sus mallas; el `X2-Ultra.xml` de v1.4.0 es la versión nueva, que no usamos) es de AgiBot y **no se sube al
repositorio**. Se carga desde la carpeta de la hackathon en el Escritorio, o desde la ruta que pongas en
`X2_MODELO` dentro del `.env`.

El D1 usa el modelo 3D del D1 Ultra (URDF de AgiBot, `ultra.urdf`, con 17 piezas STL) que el
equipo pasó en `D1_modelo_3D_simulacion.zip`. No declara licencia: va en `models/d1/` (`urdf/` y
`meshes/` juntas), que no se sube a git. De pie tiene el cuerpo a 0,31 m del piso (cadera 0,8 rad,
rodilla -1,6 rad) y trota con pares diagonales. Si `models/d1/urdf/ultra.urdf` no está, el D1 se
arma con figuras simples usando sus medidas reales (635 × 360 × 420 mm de pie).

## Qué muestra

Cada caso de `datos_falsos.CASOS` sigue el mismo flujo, y el panel de la izquierda muestra cada paso:

1. **Imagen**: una foto de prueba del dataset representa la llegada. El reconocimiento es
   voluntario: quien no quiere usar la cámara muestra su QR.
2. **Reconocimiento (SIMULADO)**: la foto se convierte en huella y se compara solo con las fotos de
   registro. Resultado: *identidad candidata*, *desconocida* (no equivale a "no miembro"),
   *ambigua* (entre umbrales o dos candidatos casi iguales) o *captura no válida*. Si no es
   fiable, el X2 pide el QR.
3. **Acreditación**: con la identidad candidata o el QR se consulta la membresía, el vínculo
   laboral, la invitación u orden de trabajo, y su vigencia. Reconocer una cara no prueba que la
   membresía esté activa (caso 16).
4. **Categoría confirmada y permisos** (igual a `registrar_llegada` en Supabase): orientado,
   rechazado o **pendiente de revisión**. Si la cara contradice el QR, la cara es ambigua sin QR o
   el servicio no responde, recepción ve la evidencia y corrige **dejando un motivo**. El robot no
   agrega al dataset la cara de quien mostró el QR.
5. **Nivel de ayuda**: la persona elige *indicación* (el X2 le explica), *mapa* (el X2 señala la
   zona, que parpadea) o *acompañamiento* (el D1 la guía). El X2 lo pregunta enseguida, con las tres
   opciones: al miembro apenas dice qué quiere hacer y al invitado en la bienvenida. El aviso al
   anfitrión o responsable sigue en segundo plano: nadie se queda esperando su respuesta; si no
   responde, recepción queda avisada. El trabajador externo no elige: va siempre con el D1.
6. **Ruta**: solo por pasillos autorizados para su categoría (el de servicio, en naranja, es para
   personal y externos). Si el pasillo central está cerrado (barrera roja), sale una **ruta alterna
   autorizada**. El D1 confirma la llegada; un regular nuevo hace el recorrido de bienvenida.

### Los cinco flujos: qué hace el X2 según el tipo de persona

Después de `registrar_llegada`, el coordinador consulta `contexto_llegada` (en Supabase, la función del
mismo nombre; aquí `recepcion.contexto_llegada`) y sigue el flujo de su tipo (`flujos.py`, la tabla de
flujos del equipo). Cada paso es una regla: qué opciones ofrece, si hay cupo, a quién avisa y a
dónde va. Ollama no decide nada de eso; si está activo, solo reescribe la bienvenida, y su versión
se descarta si pierde una opción, un lugar o un nombre.

| Tipo | Qué hace el X2 | Ejemplo |
|---|---|---|
| VIP: conserjería | Confirma su reserva, o le ofrece **mesa en el comedor reservado** o **sala privada**. La persona elige, el X2 revisa el cupo, la deja reservada (si no hay, ofrece la otra) y pregunta si quiere indicaciones o que el D1 la acompañe. Si trae maleta, el D1 la carga (caso 1). | "¿Vienes con un plan o quieres que preparemos algo? Puedo consultar una mesa en el comedor reservado o una sala privada." |
| Regular: aprovechar su membresía | Confirma su reserva, o le propone **spa** o **golf** (primero lo que dice su preferencia en la app), con cupos y costo, y lo reserva. Si trae su propio plan, lo orienta hacia allá (caso 6 elige el spa). | "¿Hoy prefieres relajarte o hacer deporte? Puedo consultar disponibilidad en el spa o una sesión de golf." |
| Invitado: sentirse esperado | Avisa a su anfitrión, confirma el punto de encuentro registrado y, cuando el anfitrión acepta, ofrece indicaciones o el D1. Sin confirmación espera en el lobby y recepción queda enterada (caso 17). | "Avisaré a Camila que llegaste. El encuentro registrado es en Restaurante." |
| Personal: empezar preparado | Dice su área y su primera tarea, la novedad de su área (o la primera del día), le muestra la ruta de servicio y le pide confirmar que recibió la novedad. Va a su área asignada (caso 3). | "Hoy tu área asignada es Restaurante; tu primera tarea es el montaje… Novedad: el montaje usa el acceso norte. ¿Me confirmas que recibiste la novedad?" |
| Externo: llegar listo para su tarea | Explica la orden, las zonas autorizadas (pasillo de servicio y su destino) y avisa al responsable. Sin su confirmación la visita queda en espera. Va siempre con el D1, que carga la **caja de herramientas**; la **geocerca** pulsa en naranja mientras dura el recorrido. | "Vienes al mantenimiento del aire acondicionado. Avisaré a tu responsable, Ana Martínez. El encuentro es en Mantenimiento…" |

Una pregunta por vez: si la bienvenida ya pregunta (plan o novedad), la de la ayuda llega después. En
el modo cámara se responde con las teclas: **1/2** eligen el plan (**3** = trae su propio plan),
**1** confirma la novedad y después **1/2/3** eligen la ayuda. Los espacios, cupos y costos del spa y
el golf son supuestos de la demo (en la maqueta el spa queda en Piscina y el golf en Canchas), y la
reserva que hace el X2 queda en la simulación: en Supabase `reservar_espacio` la hace la persona
desde su cuenta.

El aviso lo crea la base (trigger `visitas_avisar_llegada` en Supabase; aquí `recepcion._en_curso`)
cuando la visita queda en curso. En la app, el anfitrión lo ve en vivo y lo marca como **Recibido** o
**Voy en camino**; en la simulación esa respuesta es SIMULADA (en el modo cámara, **N** hace que el
anfitrión no responda).

### Cómo hablarle a cada persona (trato)

En la app, cada persona escribe en **Mi perfil → "Cómo prefieres que el robot te hable"**
(`personas.trato`, hasta 400 caracteres). El agente lo lee (`agente.leer_trato`):

- "usted" o "formal" → el X2 trata de usted ("¿Cómo prefiere que le ayude?"); "tutéame" lo evita.
- "breve", "corto", "directo", "prisa" → saludo corto y sin la información de más (actividades,
  novedades).
- "llámame Sebas" → el X2 usa ese nombre.

Solo cambia el tono, igual que el ánimo: nunca los permisos ni a dónde puede ir.

| # | Caso | Reconocimiento | Esperado |
|---|---|---|---|
| 1 | VIP con reserva y maleta | identidad candidata | VIP → Sala VIP, indicación; el D1 lleva la maleta |
| 2 | Regular nuevo | identidad candidata | Regular → recorrido + Gimnasio con el D1 |
| 3 | Personal en su turno | identidad candidata | Personal → Oficinas, mapa |
| 4 | Invitada | desconocida → QR | Invitado → Restaurante con el D1 |
| 5 | Externo que pide mapa | desconocida → QR | Externo → Mantenimiento, acompañamiento obligatorio con la caja de herramientas |
| 6 | Prefiere no usar la cámara | no usada → QR | Regular → Piscina, indicación |
| 7 | QR vencido | desconocida → QR | No pasa: explica el problema y va a recepción |
| 8 | QR revocado | desconocida → QR | No pasa: explica el problema y va a recepción |
| 9 | Se parece a otra persona | identidad candidata equivocada + QR | Pendiente → recepción: invitada → Piscina |
| 10 | Servicio caído | sin verificar | Pendiente → recepción: regular → Restaurante (ruta alterna) |
| 11 | Cara entre umbrales | ambigua | Pendiente → recepción: regular → Canchas |
| 12 | Personal fuera de turno | identidad candidata | No pasa (fuera de horario) |
| 13 | Persona no registrada | desconocida | No pasa: recepción (no se asigna a nadie) |
| 14 | Foto movida | captura no válida → QR | Regular → Gimnasio, mapa |
| 15 | Dos candidatos casi iguales | ambigua → QR | Regular → Restaurante, indicación |
| 16 | Membresía vencida | identidad candidata | No pasa: membresía vencida, recepción la renueva |
| 17 | Invitada cuyo anfitrión no confirma | QR | Invitado → espera en el lobby (aviso sin respuesta) |

`python main.py --validar` escribe [`docs/validacion.md`](../docs/validacion.md): esperado frente a
observado por caso, la matriz de categorías (incluye pendiente de revisión), las **métricas de la
propuesta** (tiempo de interacción, avisos emitidos y aceptados, casos con apoyo humano) y, **aparte**,
las métricas del reconocimiento sobre las 28 fotos de prueba.

## Dataset y reconocimiento simulado

`dataset.py` tiene 9 personas con consentimiento, cada una con 3 fotos de registro y 2 de prueba
distintas, más fotos de personas no registradas y los casos difíciles (parecido, entre umbrales,
dos candidatos, foto movida). Las fotos no existen: cada una trae una "receta" oculta con la que se
**simula** la huella que daría un modelo facial. Lo que viene después es real: la comparación por
distancia coseno con umbrales, la consulta de acreditaciones y las decisiones. El reconocimiento
recibe solo la huella; la persona esperada se usa solo para evaluar.

Las huellas se calculan con md5, así que Postgres produce exactamente los mismos vectores. Los
identificadores (personas, visitas, fotos) son UUID fijos compartidos con Supabase:

```bash
python semilla_supabase.py      # regenera supabase/seed_demo.sql con los datos de la demo
```

Para pasar a reconocimiento real basta con cambiar `dataset.huella()` por un modelo que convierta la
foto en un vector de 512 y guardar las huellas de registro con `guardar_huella`; el resto del flujo
no cambia. Las fotos reales van en `dataset/` (ignorado por git) o en el bucket privado `fotos`.

## Modo cámara: reconocimiento real con la cámara del computador

La cámara del computador hace de cámara del X2. La detección (YuNet) y la huella (SFace) son
reales, con OpenCV; la comparación, la acreditación y la orientación siguen el mismo camino que en
los casos.

1. Descarga los modelos en `models/` (no se suben a git) desde
   [opencv_zoo](https://github.com/opencv/opencv_zoo): `face_detection_yunet_2023mar.onnx`,
   `face_recognition_sface_2021dec.onnx` y, opcional, `facial_expression_recognition_mobilefacenet_2022july.onnx`
   (estado de ánimo).
2. Pon las fotos de registro en `dataset/caras/` (no se suben a git: son datos biométricos; solo
   de personas que aceptaron) y describe a cada persona en `dataset/caras/roles.json`:

   ```json
   [{"clave": "ana", "nombre": "Ana", "rol": "vip", "fotos": ["ana1.jpg"]}]
   ```

3. Registra las huellas (con `--supabase` también sube fotos y huellas, si la clave de servicio
   está en el `.env`):

   ```bash
   python registrar_caras.py
   ```

4. Genera los QR: uno personal por miembro o personal, uno de visita por invitado o externo. Con
   `--invitado` se invita a alguien sin cara registrada (por ejemplo, un mentor). Las imágenes
   quedan en `dataset/qr/` para mostrarlas desde el celular; `--subir` las guarda en Supabase (solo
   el hash). Volver a generar cambia los tokens.

   ```bash
   python generar_qr.py
   python generar_qr.py --invitado "Ana Mentora" --anfitrion camilo
   python generar_qr.py --subir
   ```

5. Si no reconoce bien a alguien, mira por qué con el diagnóstico en vivo:

   ```bash
   python diagnostico_caras.py              # caras de la copia local
   python diagnostico_caras.py --supabase   # caras de la base (incluye las de la app)
   ```

   Muestra el tamaño de la cara y la confianza del detector (en rojo si no alcanzan el mínimo) y
   las 3 personas más parecidas con su distancia (< 0.60 la reconoce). Deja cada medio segundo una
   línea en `diagnostico_caras.log` (no se sube a git) para calibrar con la cámara y la luz reales.

   Cómo analiza la webcam: la abre a 1280x720 (a 640x480 una cara a un metro mide ~55 px y quedaba
   rechazada), analiza el cuadro sin espejo (el espejo es solo para la ventana), acepta caras desde
   48 px y confianza 0.80, y entrega el promedio de las huellas de los últimos 2 s que son de la
   misma cara. Con 2 o 3 fotos de registro por persona (la app deja subir 3) reconoce mejor.

6. Corre la simulación con la cámara:

   ```bash
   python main.py --camara
   python main.py --camara --supabase   # decide la base real, como el robot
   ```

   Con `--supabase` las caras que se reconocen salen de la base, no de la copia local: se traen al
   iniciar (la consola dice cuáles) y cada 15 s, con las fotos nuevas de la app. Quien no tiene cara
   en la base aparece como "(solo QR)" en el panel.
   Con `--supabase` la decisión la toma Supabase en vivo (`registrar_llegada`, `contexto_llegada`,
   `registrar_orientacion` y `completar_tour`, con `fuente = 'simulacion'`) usando la clave de
   servicio del `.env`, con la hora real. Cada llegada queda en `eventos` y la ve recepción en el
   panel web; el aviso al anfitrión lo crea la base y le llega a la app móvil, y la simulación
   espera hasta 60 s a que lo acepte ahí (si no, lo marca `sin_respuesta`). Lo pendiente de
   revisión lo corrige el operador desde el panel web. Si la base no responde, el X2 no decide: la
   llegada queda pendiente para recepción, igual que el robot real.

   La ventana de la cámara muestra en vivo a quién se parece la cara (verde: reconocida; naranja:
   dudosa, desconocida o imagen que no sirve). **Espacio** (en cualquiera de las dos ventanas):
   llega la persona que está frente a la cámara: entra por la puerta del club (la vista inicial es
   la suya, Visitante 1) y el X2 deja de patrullar para recibirla. **1 / 2 / 3**: la persona elige
   indicación, mapa o acompañamiento. **N**: el anfitrión o responsable no responde el aviso.

   La identificación va por pasos de hasta 10 s de tiempo real (sin contar lo que dice el X2); al
   cambiar de paso se cancela el intento anterior, y en cuanto la credencial queda verificada se
   detiene y sigue el flujo de su categoría:

   | Paso | Qué hace | Qué dice el X2 |
   | --- | --- | --- |
   | 1. Cara (10 s) | Reconoce la cara; si no lo logra, pide el QR | "Podemos continuar con tu pase. Muéstrame el código QR frente a la cámara, por favor." |
   | 2. QR (10 s) | Lee y verifica el QR; si no lo lee, da instrucciones | "Todavía no pude leer el código. Prueba acercándolo o alejándolo un poco…" |
   | 3. QR (10 s) | Lo reintenta; si tampoco, pasa a recepción humana | "Vamos a continuar con ayuda de recepción. Acércate al punto de atención…" |

   Invitados y externos empiezan en el paso 2 (**I**: traigo invitación u orden; mostrar el QR
   durante el paso 1 también salta). **Q**: no tengo QR → recepción. Si el QR se lee pero está
   vencido, revocado, no existe, no corresponde a la cara o es el QR de demostración de la app, el
   X2 explica el problema y manda a recepción sin pedir otro intento. Recepción es el punto físico
   de atención humana.

   **Invitados y externos no se reconocen por la cara**: entran siempre con QR. Aunque el equipo
   tenga fotos de prueba de Mini, Samuel y Thalia, quedan con `uso = 'prueba'` (aquí y en
   Supabase), así que el X2 no los identifica y pide el QR. Su QR es un **pase** con el formato de
   la app (`NC1.` + JSON en base64url: token, nombre, tipo, anfitrión o empresa, destino y
   vigencia). En pantalla se ve lo que dice el pase, pero la decisión sale del token verificado en
   la base. `python generar_qr.py --pases` rehace esos QR sin cambiar los tokens y comprueba que el
   mismo lector del robot los lea, también reducidos a la mitad y algo borrosos.

   **App móvil** (repo `thaliahero/app_registro_nclub`): el X2 lee los QR que muestra la app (solo
   el token de 64 hex de `generar_mi_qr` / `crear_invitacion`; también acepta el código de pase
   `NC1.…`, del que usa solo el token). Los destinos que guarda la app (`terraza`, `salon-social`,
   `zona-servicio`…) se ubican en las zonas de la maqueta con `club.ESPACIOS_APP`, y el X2 dice el
   nombre de la app.

Los invitados y externos registrados entran con una invitación u orden de trabajo vigente que se
crea al iniciar. El trato y el punto de encuentro del equipo están en `dataset/caras/personas.json`
(`trato`, `punto_encuentro`), con los mismos valores que en Supabase; cada VIP tiene una reserva en
la Sala VIP y cada persona del personal, sus tareas (`datos_falsos.agenda`). Los umbrales de SFace (aceptar hasta 0.60 de distancia, ambigua hasta 0.70) están
en `recepcion.UMBRALES` y hay que ajustarlos con fotos de prueba reales.

## Cómo habla el X2: ánimo y agente (sin API key)

El agente (`agente.py`) solo decide **cómo** decir las cosas. Quién entra, a qué categoría y a
dónde va lo sigue decidiendo `registrar_llegada`, con reglas fijas que se pueden auditar.

- **Ánimo:** en el modo cámara, el modelo de expresiones de OpenCV Zoo corre sobre la misma cara
  alineada que usa SFace y da un tono (contento, neutral, tenso o triste). Por debajo de 60 % de
  confianza queda neutral. Es una pista débil (la expresión no es el ánimo), corre en el computador,
  no se guarda y el robot no la menciona. La ventana de la cámara la muestra en vivo.
- **Reglas locales (siempre):** saludo según la hora, con el trato que pidió la persona y lo que
  sigue según su perfil; con tono tenso o triste, el X2 habla con más
  calma, sugiere el acompañamiento del D1 y, si la confianza pasa de 80 %, avisa a recepción; con
  tono contento sugiere solo la indicación; un regular nuevo recibe la oferta del recorrido. La
  sugerencia aparece al elegir con 1/2/3, pero la persona decide.
- **Ollama (opcional):** un LLM que corre en el computador, sin clave ni internet, reescribe el
  mensaje de las reglas para que suene más natural. Si Ollama no está, tarda más de 4 s, todavía
  está cargando el modelo en la GPU (unos 20 s al arrancar) o la respuesta pierde un nombre o
  inventa una pregunta, el X2 usa el mensaje de las reglas. Ollama también recibe el trato. Con una RTX 3060, `qwen2.5:3b`
  responde en unos 2.5 s, pero a veces escribe mal ("acompanie") o agrega frases raras: para la
  demo frente al jurado, las reglas son lo más confiable.

  ```bash
  ollama pull qwen2.5:3b
  python main.py --camara --ollama
  python main.py --camara --ollama llama3.2:3b
  ```

## Recepción fija con el X2 real (sin movimiento)

`recepcion_fija.py` es la versión para el robot de verdad que no lo mueve: sin MuJoCo, con la cámara
del portátil como cámara del X2 y la voz y la cara en el robot (`robot_x2/puente_voz.py`).

```powershell
python recepcion_fija.py                         # decide la copia local; voz por el portátil
python recepcion_fija.py --supabase --voz audio  # decide la base real; voz por el parlante del X2
```

Cuando alguien se pone frente a la cámara: si es miembro o personal con su cara registrada, lo saluda
por su nombre y le da la bienvenida (con su reserva o su primera tarea); si no lo reconoce, le pide el
QR y lo lee; con un pase de invitado o externo avisa a su anfitrión o responsable por la app y espera
su respuesta; si no puede seguir, explica el motivo y lo manda al mostrador. No vuelve a saludar a la
misma persona mientras siga frente a la cámara (R lo fuerza). Teclas: Q no tengo QR, N el anfitrión
no responde (sin `--supabase`), Esc salir.

Con `--ollama` (opcional) Ollama reescribe la bienvenida y el "ya viene por ti" con el mismo
validador que la simulación, más los datos de la frase (hora, lugar, tarea, anfitrión…), que tienen
que quedar idénticos; si no, o si tarda más de 3,5 s, dice el texto fijo.

Con `--supabase` también procesa cada 15 s las fotos que la gente sube desde la app (Mi perfil →
Foto para el reconocimiento) y trae todas las huellas de la base: quien se registró desde la app se
reconoce sin reiniciar, y quien se borró de la base deja de reconocerse. Lo mismo, sin la recepción:
`python huellas_app.py` (una vez) o `python huellas_app.py --seguir`.

La voz en español la genera Windows (`voz_x2.py`, voz Helena es-ES, 16 kHz) y se guarda en caché en
la carpeta temporal. Despliegue en el robot, red y lo real frente a lo simulado: `robot_x2/README.md`,
sección "Recepción fija".

## Robots por separado

El X2 y el D1 son programas aparte con la misma interfaz (`robots/interfaz.py`): `main.py` es el
coordinador y solo les da órdenes ("patrulla el lobby", "vuelve a tu puesto", "captura", "señala
el mapa", "agáchate y carga la caja", "guía por estos puntos"). Hoy corren sus versiones simuladas (`robots/x2_sim.py`, `robots/d1_sim.py`); para
los robots reales se agregan `x2_aimdk.py` (ROS 2 / AimDK) y `d1_sdk.py` (SDK del D1) con los mismos
métodos, sin tocar el coordinador.

## Archivos

- `main.py`: coordinador de la recepción, panel, visor, modo cámara, capturas y validación.
- `huellas_app.py`: huellas de las fotos subidas desde la app (las guarda en Supabase).
- `recepcion_fija.py`: recepción con el X2 real quieto (cámara del portátil, Supabase, voz y cara del
  robot). `voz_x2.py`: voz en español de Windows y cliente del puente de voz del robot.
- `robots/`: interfaz del X2 y del D1 y sus versiones simuladas.
- `caras.py`: reconocimiento real (YuNet + SFace). `camaras.py`: cámara del dataset o del computador.
- `diagnostico_caras.py`: diagnóstico en vivo del reconocimiento (tamaño, confianza, distancias).
- `registrar_caras.py` / `supabase_demo.py`: registran las caras reales (local y en Supabase).
- `generar_qr.py`: QR del equipo e invitaciones sin cara (local y en Supabase).
- `agente.py`: cómo habla el X2 según la persona y su ánimo (reglas locales + Ollama opcional).
- `flujos.py`: los cinco flujos por tipo de persona (opciones, cupos, área y novedad, avisos).
- `dataset.py`: fotos de registro y de prueba, y la huella simulada.
- `recepcion.py`: reconocimiento por umbrales y la misma lógica de `registrar_llegada` /
  `corregir_evento` / `contexto_llegada` de Supabase, con el aviso al anfitrión; elección del nivel de
  ayuda.
- `datos_falsos.py`: personas (con su trato), visitas (con su punto de encuentro), credenciales,
  fotografías, reservas, actividades, tareas y novedades de prueba, y los 17 casos con su resultado
  esperado.
- `semilla_supabase.py`: genera `supabase/seed_demo.sql` con los mismos datos.
- `club.py`: plano inventado del club: zonas, grafo de pasillos con permisos por categoría y rutas.
- `escena.py`: arma el modelo de MuJoCo: habitaciones, muebles, robots, personas y sus cámaras.
- `animacion.py`: movimientos por cinemática (sin física ni control de caminata): caminata, saludo y
  señalar del X2; trote, postura agachada y carga del D1; geocerca; personas caminando.
- `marcha_x2.py`: caminata del X2 por cinemática inversa (la usan la simulación y el video).

## Pendiente

- Más fotos por persona (hoy hay una de registro por persona) para confirmar los umbrales de SFace.
- Usar la cámara del robot en lugar de la del portátil.
- Conectar el coordinador (`main.py`) con `robots/x2_aimdk.py` para el movimiento real.
- Versión para Meta Quest 3, si hay tiempo.
