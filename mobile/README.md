# N Club · App móvil (prototipo)

Importada del repo [thaliahero/app_registro_nclub](https://github.com/thaliahero/app_registro_nclub)
(commit `4a9f6f0`) sin cambios de lógica. Las migraciones de la app eran idénticas a las de
`../supabase/migrations/`, así que se usan esas. Su propuesta de reservas quedó aplicada como
`../supabase/migrations/20261024000006_reservas_tareas_servicios.sql` (con las zonas del club en el
catálogo); el original sigue en `../supabase/proposed/` como referencia.

Prototipo en **React Native + Expo (SDK 58) + TypeScript estricto + Expo Router + Supabase** para los
cinco perfiles de N Club: miembro regular, miembro VIP, personal del club, invitado y trabajador externo.
El diseño sigue el PDF "Miembro Regular" (fotografía a pantalla completa oscurecida, monograma "N"
dorado en círculo blanco, botones blancos tipo píldora, campos subrayados, Poppins + serif + script).

## Puesta en marcha

Requisitos: Node 20+ y la app **Expo Go** (compatible con SDK 58) en el teléfono.

```bash
npm install
```

```bash
copy .env.example .env
```

Edita `.env` con la URL y la **clave pública** (publishable / anon) de tu proyecto de Supabase. Sin
`.env` la app arranca igual y solo ofrece el modo de demostración.

```bash
npx expo start
```

Escanea el QR de la terminal con Expo Go (Android) o con la cámara (iOS). Si el teléfono no está en
la misma red, usa `npx expo start --tunnel`.

Otros comandos: `npm run typecheck`, `npm run lint`, `npm run web` (vista web de desarrollo).

### Variables de entorno

| Variable | Uso |
| --- | --- |
| `EXPO_PUBLIC_SUPABASE_URL` | URL del proyecto |
| `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Clave pública. También se acepta `EXPO_PUBLIC_SUPABASE_ANON_KEY` |

Nunca pongas la clave `service_role` en la app: todo lo `EXPO_PUBLIC_*` se empaqueta en el cliente.

## Base de datos

`../supabase/migrations/` contiene las cinco migraciones entregadas, sin cambios (solo se quitó el
sufijo " (1)" del nombre de archivo). El esquema vigente tras la migración 3 es
`personas / visitas / credenciales / eventos` (+ `fotografias` en la 4); `miembros` y
`accesos_temporales` ya no existen y la app no los usa.

Lo que la app usa desde el cliente (todo permitido a `authenticated` y protegido por RLS):

| Necesidad | Objeto |
| --- | --- |
| Perfil y rol | `personas` (select propio; insert/update solo de columnas permitidas) |
| QR personal | `generar_mi_qr()` + `credenciales` (se compara el sha256 del token local con `token_hash`) |
| Invitar / registrar externo | `crear_invitacion(...)` con `p_categoria` `invitado` o `externo` |
| Listar / revocar | `visitas` (RLS por `responsable_id`) y `revocar_invitacion(...)` |
| Consentimiento biométrico | `personas.consentimiento_biometrico` (el trigger borra las huellas al retirarlo) |

No se llaman `registrar_llegada`, `registrar_orientacion`, `completar_tour` ni `guardar_huella`
(reservadas a `service_role`; las usa el robot/backend).

### Reservas, tareas, avisos y trato (aplicado)

- `20261024000006_reservas_tareas_servicios.sql`: `espacios`, `reglas_reserva`, `reservas` (sin
  solapes), `tareas_personal`, `solicitudes_servicio` y sus funciones (`disponibilidad_espacio`,
  `reservar_espacio`, `cancelar_reserva`, `marcar_tarea`, `resolver_solicitud`) con RLS. Con una
  cuenta real, la pantalla de reservas usa el catálogo `espacios`, `reglas_reserva` y esas funciones
  (`src/services/supabase/reservas.ts`), y las tareas del personal salen de `tareas_personal` y se
  marcan con `marcar_tarea` (`src/services/supabase/tareas.ts`). El robot ve esas reservas y tareas
  al recibir a la persona (`contexto_llegada`).
- `20261024000009_estado_huella_fotos_app.sql` — **foto para el reconocimiento**: en **Mi perfil**,
  con el consentimiento activo, la persona toma hasta 3 fotos con la cámara frontal (`expo-camera`,
  funciona en Expo Go). La app sube la foto al bucket privado `fotos/<auth.uid()>/` y crea la fila de
  `fotografias` (uso `registro`, autorizada); **la huella no la calcula la app**: la calcula el backend
  del robot (`simulation/huellas_app.py`, o `recepcion_fija.py --supabase` mientras corre) y la app
  muestra el estado de cada foto: *Procesando*, *Lista para reconocerte* o *No sirvió* con el motivo
  (no se ve la cara, muy lejos, o se parece a otra persona registrada). Se puede borrar cada foto.
  Retirar el consentimiento borra las huellas (trigger de la migración 4).
- `20261024000007_anfitrion_avisos_trato.sql`:
  - `personas.trato`: "Cómo prefieres que el robot te hable" en **Mi perfil** (solo el tono).
  - `avisos`: cuando el robot registra la llegada de un invitado o externo, su anfitrión o
    responsable recibe el aviso en el inicio de la app (en vivo con Realtime) y lo marca como
    **Recibido** o **Voy en camino** (`responder_aviso`).
  - `visitas.punto_encuentro` + `cambiar_punto_encuentro()`, `novedades` del personal y
    `contexto_llegada()` (solo backend) para que el robot prepare el siguiente paso.

Además, para que el invitado vea su pase sin depender del código compartido, haría falta una
**Edge Function** (p. ej. `pase-invitado`) que reciba el token, lo valide con `hash_token` usando la
clave de servicio en el servidor y devuelva solo nombre, anfitrión, destino y vigencia. Lo mismo para
enviar la invitación por correo.

## Perfiles y flujo

Bienvenida → inicio de sesión / registro / "Tengo un pase" / modo demostración → panel según perfil.

- **Perfil real**: sale de `personas.vinculo` (`regular`, `vip`, `personal`), que el usuario no puede
  modificar (sin grant de columna). Un registro nuevo queda como `regular`.
- **Invitado / externo**: no tienen cuenta (`usuario_id` null). El anfitrión comparte un código
  `NC1.…` con el token y los datos de la visita; la persona lo pega en "Tengo un pase".
- **Demostración**: perfiles locales sin Supabase, con franja "MODO DEMOSTRACIÓN" en todas las
  pantallas y QR marcados "no autoriza el ingreso".

### Funciones reales frente a simuladas

| Función | Con cuenta real | Demo |
| --- | --- | --- |
| Registro, login, logout | Real (Supabase Auth + `personas`) | — |
| QR personal | Real (`generar_mi_qr`, token en llavero del teléfono) | QR demo |
| Invitar (regular / VIP) | Real (`crear_invitacion`) | Local |
| Registrar trabajador externo | Real (`crear_invitacion` con empresa) | Local |
| Revocar invitación | Real (`revocar_invitacion`) | Local |
| Turno del personal | Real (`horario_inicio` / `horario_fin`) | Demo |
| Consentimiento biométrico | Real | Solo visual |
| Reservas | **Reales**: disponibilidad, reserva y cancelación en Supabase, con las reglas del plan | Disponibilidad simulada, guardada en el teléfono |
| Tareas del personal | **Reales**: las asignadas para hoy en `tareas_personal`; marcarlas queda en la base | Simuladas, estado local |
| Consulta / contratación de externos | **Pendiente**: se prepara y comparte, no se registra | Igual |
| Espacios del club | **Supuestos** configurables en `src/constants/spaces.ts` | Igual |
| Datos personales (nombre, teléfono) | **Reales**: Mi perfil → Mis datos | Solo visual |
| Foto para reconocimiento facial | **Real**: Mi perfil → Foto para el reconocimiento (cámara frontal, `expo-camera`) | No se sube |

## Estructura

```
src/
  app/                      rutas de Expo Router
    (public)/               bienvenida, login, register, pase, demo
    (app)/                  home, invitar, invitaciones, acceso/[id], reservar, externos, perfil
  components/               Screen, Logo, PillButton, UnderlineField, QrCard, Card, ChipSelector…
  constants/                theme, config, profiles, spaces (reglas por perfil)
  features/
    auth/                   SessionProvider (real / pase / demo), permisos
    memberships/            estado de membresía, QR personal, panel regular/VIP
    invitations/            servicio real/demo, validación, formulario
    reservations/           repositorio real (Supabase) y demo, pantalla
    staff/                  turno, tareas, solicitud de servicio externo, panel
    temporary-access/       pase (código, estado), almacenamiento, pantalla de invitado/externo
    demo/                   datos de demostración
  hooks/                    useAsync, useNow
  services/                 supabase (client, personas, credentials, visitas), storage seguro
  types/                    tipos del esquema
  utils/                    hora de Colombia, validación, formato
../supabase/migrations/     SQL entregado (sin cambios)
../supabase/proposed/       propuesta original de la app (ya aplicada como 006)
```

## Seguridad

- Solo clave pública en el cliente; las reglas reales las aplican RLS y las funciones `security definer`.
- El QR contiene únicamente el token (64 hex), nunca datos personales. Los tokens se guardan en
  `expo-secure-store` y no se escriben en logs ni en mensajes de error.
- Las pantallas comprueban permisos (no solo ocultan botones); el servidor vuelve a validar todo.

## Con el robot (X2)

- El X2 lee con su cámara los QR que muestra la app: el QR personal (solo el token) y el del pase de
  invitado o externo. Si le muestran el código de pase `NC1.…`, usa solo su token: la visita la
  vuelve a leer `registrar_llegada` en Supabase.
- Invitados y externos no se reconocen por la cara: entran siempre con su QR.
- Un QR del modo demostración (`NCLUB-DEMO-NO-AUTORIZA-INGRESO:…`) no deja entrar: el X2 manda a
  recepción.
- Los destinos de la app (`terraza`, `salon-social`, `zona-servicio`…) se ubican en el mapa del
  club con `simulation/club.py` (`ESPACIOS_APP`). Ver `../simulation/README.md`.
