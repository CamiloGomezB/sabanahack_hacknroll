# Simulación (MuJoCo)

Simulación del lobby de N Club con el X2 Ultra en la recepción y el D1 guiando a las personas que lo
necesitan. **Todo lo que se ve aquí es simulado**: los robots, las personas, el reconocimiento facial y
los datos (de prueba, en `datos_falsos.py`).

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
| `--validar` | Sin ventana: corre los 16 casos y escribe `docs/validacion.md` (esperado frente a observado). |
| `--capturas carpeta/` | Sin ventana: guarda una imagen cada `--cada` segundos. |

Teclas en el visor: **Espacio** = siguiente caso, **A** = modo automático/manual, **B** = cerrar o
abrir el pasillo central, **C** = cambiar cámara (general, recepción, seguir al D1).

El panel de la izquierda muestra el caso en curso como **evidencia → categoría → orientación**
(qué vio el robot, qué categoría confirmó y cómo orienta). Arriba a la derecha están el estado de
**recepción** y la lista de casos con su resultado (OK si lo obtenido es lo esperado).

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

El modelo oficial del X2 Ultra (`X2-Ultra.xml` v1.4.0 y sus mallas) es de AgiBot y **no se sube al
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
   zona, que parpadea) o *acompañamiento* (el D1 la guía). El trabajador externo solo puede ir
   acompañado.
6. **Ruta**: solo por pasillos autorizados para su categoría (el de servicio, en naranja, es para
   personal y externos). Si el pasillo central está cerrado (barrera roja), sale una **ruta alterna
   autorizada**. El D1 confirma la llegada; un regular nuevo hace el recorrido de bienvenida.

| # | Caso | Reconocimiento | Esperado |
|---|---|---|---|
| 1 | VIP | identidad candidata | VIP → Sala VIP, indicación |
| 2 | Regular nuevo | identidad candidata | Regular → recorrido + Gimnasio con el D1 |
| 3 | Personal en su turno | identidad candidata | Personal → Oficinas, mapa |
| 4 | Invitada | desconocida → QR | Invitado → Restaurante con el D1 |
| 5 | Externo que pide mapa | desconocida → QR | Externo → Mantenimiento, acompañamiento obligatorio |
| 6 | Prefiere no usar la cámara | no usada → QR | Regular → Piscina, indicación |
| 7 | QR vencido | desconocida → QR | Rechazado |
| 8 | QR revocado | desconocida → QR | Rechazado |
| 9 | Se parece a otra persona | identidad candidata equivocada + QR | Pendiente → recepción: invitada → Piscina |
| 10 | Servicio caído | sin verificar | Pendiente → recepción: regular → Restaurante (ruta alterna) |
| 11 | Cara entre umbrales | ambigua | Pendiente → recepción: regular → Canchas |
| 12 | Personal fuera de turno | identidad candidata | Rechazado |
| 13 | Persona no registrada | desconocida | Rechazado (no se asigna a nadie) |
| 14 | Foto movida | captura no válida → QR | Regular → Gimnasio, mapa |
| 15 | Dos candidatos casi iguales | ambigua → QR | Regular → Restaurante, indicación |
| 16 | Membresía vencida | identidad candidata | Rechazado: acreditación vencida |

`python main.py --validar` escribe [`docs/validacion.md`](../docs/validacion.md): esperado frente a
observado por caso, la matriz de categorías (incluye pendiente de revisión) y, **aparte**, las
métricas del reconocimiento sobre las 28 fotos de prueba.

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

5. Corre la simulación con la cámara:

   ```bash
   python main.py --camara
   ```

   La ventana de la cámara muestra en vivo a quién se parece la cara (verde: reconocida; naranja:
   dudosa, desconocida o imagen que no sirve). **Espacio** (en cualquiera de las dos ventanas):
   llega la persona que está frente a la cámara. **1 / 2 / 3**: la persona elige indicación,
   mapa o acompañamiento.

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
   tenga fotos de prueba de Juan, Sebastián y Thalia, quedan con `uso = 'prueba'` (aquí y en
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
crea al iniciar. Los umbrales de SFace (aceptar hasta 0.60 de distancia, ambigua hasta 0.70) están
en `recepcion.UMBRALES` y hay que ajustarlos con fotos de prueba reales.

## Cómo habla el X2: ánimo y agente (sin API key)

El agente (`agente.py`) solo decide **cómo** decir las cosas. Quién entra, a qué categoría y a
dónde va lo sigue decidiendo `registrar_llegada`, con reglas fijas que se pueden auditar.

- **Ánimo:** en el modo cámara, el modelo de expresiones de OpenCV Zoo corre sobre la misma cara
  alineada que usa SFace y da un tono (contento, neutral, tenso o triste). Por debajo de 60 % de
  confianza queda neutral. Es una pista débil (la expresión no es el ánimo), corre en el computador,
  no se guarda y el robot no la menciona. La ventana de la cámara la muestra en vivo.
- **Reglas locales (siempre):** saludo según la hora; con tono tenso o triste, el X2 habla con más
  calma, sugiere el acompañamiento del D1 y, si la confianza pasa de 80 %, avisa a recepción; con
  tono contento sugiere solo la indicación; un regular nuevo recibe la oferta del recorrido. La
  sugerencia aparece al elegir con 1/2/3, pero la persona decide.
- **Ollama (opcional):** un LLM que corre en el computador, sin clave ni internet, reescribe el
  mensaje de las reglas para que suene más natural. Si Ollama no está, tarda más de 4 s, todavía
  está cargando el modelo en la GPU (unos 20 s al arrancar) o la respuesta pierde un nombre o
  inventa una pregunta, el X2 usa el mensaje de las reglas. Con una RTX 3060, `qwen2.5:3b`
  responde en unos 2.5 s, pero a veces escribe mal ("acompanie") o agrega frases raras: para la
  demo frente al jurado, las reglas son lo más confiable.

  ```bash
  ollama pull qwen2.5:3b
  python main.py --camara --ollama
  python main.py --camara --ollama llama3.2:3b
  ```

## Robots por separado

El X2 y el D1 son programas aparte con la misma interfaz (`robots/interfaz.py`): `main.py` es el
coordinador y solo les da órdenes ("mira al visitante", "captura", "señala el mapa", "guía por
estos puntos"). Hoy corren sus versiones simuladas (`robots/x2_sim.py`, `robots/d1_sim.py`); para
los robots reales se agregan `x2_aimdk.py` (ROS 2 / AimDK) y `d1_sdk.py` (SDK del D1) con los mismos
métodos, sin tocar el coordinador.

## Archivos

- `main.py`: coordinador de la recepción, panel, visor, modo cámara, capturas y validación.
- `robots/`: interfaz del X2 y del D1 y sus versiones simuladas.
- `caras.py`: reconocimiento real (YuNet + SFace). `camaras.py`: cámara del dataset o del computador.
- `registrar_caras.py` / `supabase_demo.py`: registran las caras reales (local y en Supabase).
- `generar_qr.py`: QR del equipo e invitaciones sin cara (local y en Supabase).
- `agente.py`: cómo habla el X2 según la persona y su ánimo (reglas locales + Ollama opcional).
- `dataset.py`: fotos de registro y de prueba, y la huella simulada.
- `recepcion.py`: reconocimiento por umbrales y la misma lógica de `registrar_llegada` /
  `corregir_evento` de Supabase; elección del nivel de ayuda.
- `datos_falsos.py`: personas, visitas, credenciales y fotografías de prueba, y los 16 casos con su
  resultado esperado.
- `semilla_supabase.py`: genera `supabase/seed_demo.sql` con los mismos datos.
- `club.py`: plano inventado del club: zonas, grafo de pasillos con permisos por categoría y rutas.
- `escena.py`: arma el modelo de MuJoCo.
- `animacion.py`: movimientos por cinemática (sin física ni control de caminata): saludo y señalar
  del X2, trote del D1, personas caminando.

## Pendiente

- Reconocimiento real con las fotos del equipo (3 de registro y 2 de prueba por persona).
- Llamar a `registrar_llegada` de Supabase desde la simulación (`fuente = 'simulacion'`).
- Versión para Meta Quest 3, si hay tiempo.
