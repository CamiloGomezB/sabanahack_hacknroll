# Supuestos y límites

El reto pide declarar los supuestos y separar con claridad lo real de lo simulado. No afirmamos
conocer la operación real de un club específico.

## Sobre N Club

- N Club tiene **una sola sede**. Toda la propuesta, incluido el [presupuesto](../PRESUPUESTO.md),
  se plantea para esa sede; crecer es ampliar la flota de robots.
- El club dispone de registros de membresía, empleados, invitaciones y órdenes de trabajo, y puede
  registrar reservas, actividades, tareas del personal, novedades y puntos de encuentro.
- El plano del club (lobby, Sala VIP, piscina, canchas, restaurante, gimnasio, oficinas y
  mantenimiento) es **inventado** para la demo (`simulation/club.py`). Los espacios de la app
  (`mobile/src/constants/spaces.ts`) también son provisionales; cada uno se ubica en la zona más
  parecida del plano.
- La recepción humana es un **punto físico de atención** en el lobby. El operador ve los casos y
  decide desde su panel web.

## Sobre las personas

- La categoría determina opciones y restricciones; cuánta ayuda necesita cada persona depende también
  de su motivo y de su elección (indicación, mapa o acompañamiento del D1).
- **Invitados y trabajadores externos entran siempre con QR.** No se les registra la cara: su
  visita es temporal. Sus fotos del equipo están marcadas `uso = 'prueba'`.
- El reconocimiento facial es **voluntario** (consentimiento en la app, Ley 1581). Quien no lo da
  entra con su QR personal.
- El **trato** ("Cómo prefieres que el robot te hable", `personas.trato`) lo escribe la persona en la
  app. Solo cambia el tono (usted o tú, breve, nombre preferido), nunca permisos ni decisiones.
- El **ánimo** que estima la cámara es una pista débil: solo ajusta el tono, no se guarda y el robot
  no lo menciona.

## Lo que decide el robot y lo que no

- El robot **no crea permisos ni resuelve dudas por intuición**. La decisión la toma
  `registrar_llegada` con la base (acreditación y visita vigentes). Lo que no puede confirmar pasa a
  recepción humana con su motivo y evidencia.
- Identificación por pasos de 10 s: cara → primer QR → segundo QR → recepción (30 s como máximo; 20 s
  si la persona empieza por el QR).
- Al invitado o externo se le **avisa a su anfitrión o responsable** (tabla `avisos`, en vivo en la
  app). "Emitido" no es "enterado": recibido y aceptado los marca la persona avisada. Si no responde,
  el invitado espera en la sala de espera del lobby y recepción queda enterada.

## Real y simulado

| Pieza | Estado |
|---|---|
| Base de datos (Supabase): reglas, RLS, `registrar_llegada`, avisos, reservas, tareas, `contexto_llegada` | **Real**, desplegada |
| App móvil (registro, QR, invitaciones, trato, avisos) | **Real** (Expo); reservas y tareas aún con datos simulados en la interfaz |
| Reconocimiento facial con la cámara del computador (SFace) | **Real** en `--camara`; en la validación automática las huellas son sintéticas |
| Lectura del QR y del pase de la app | **Real** |
| Robots X2 y D1, sus movimientos, el club y las personas | **Simulados** en MuJoCo (cinemática, no física) |
| Respuesta del anfitrión en la app durante la simulación | **Simulada** (en la app real la marca la persona) |
| Geocerca del externo | **Simulada** como ruta autorizada por pasillos; en el D1 real sería SLAM/LiDAR |
| Voz del X2 | Texto en pantalla; redacción con reglas y, si está, Ollama local |

## Límites conocidos

- Las métricas faciales de la validación usan huellas sintéticas: validan el flujo y los umbrales,
  no la precisión de un modelo real. No hay detección de vida.
- Los umbrales de SFace hay que confirmarlos con fotos reales del club.
- Los tiempos de la validación son simulados.
