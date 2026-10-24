# N Club — Access Management

> Viene del repo [thaliahero/Web_BaseDatos_Nclub](https://github.com/thaliahero/Web_BaseDatos_Nclub)
> (commit `d220388`). Aquí vive junto a la app móvil (`../mobile`, la `App_registro_Nclub` que
> menciona la documentación), la simulación y las migraciones (`../supabase`).
>
> **En este repositorio:**
> - La conexión va en `js/config.js`, que no se sube (está en `.gitignore`). Se copia de
>   `js/config.example.js` con `EXPO_PUBLIC_SUPABASE_URL` y `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
>   de `mobile/.env`: el mismo proyecto que la app y la simulación. Sin ese archivo abre en modo
>   demostración. Con el Supabase falso (`node tests/serve-mock.js`) manda el falso.
> - En el proyecto real ya están aplicadas las migraciones 001 a 007 de `../supabase/migrations`,
>   así que `espacios` (006) existe y los avisos (007) también. Las propuestas 008 a 010 de
>   `supabase/propuestas/` **no** están aplicadas.
> - Para entrar hace falta una cuenta con rol `operador` o `admin`: se registra en la app móvil y
>   luego se le asigna el rol en el SQL Editor (P2 en `docs/SUPABASE.md`).
> - Con `python main.py --camara --supabase`, la simulación registra cada llegada en la base real:
>   lo que el robot deja pendiente de revisión aparece aquí, en eventos, para corregirlo.
> - **Avisos de llegada sin respuesta** (dashboard y campana): cuando el anfitrión o responsable no
>   confirma en la app el aviso que creó la base al llegar su invitado o externo, recepción lo ve
>   con su teléfono y correo para llamarlo, y puede abrir la visita. Lee la tabla `avisos` (007) de
>   las últimas 24 h, solo con rol que ve visitas (RLS: `es_operador()`); no la modifica. En el
>   Supabase falso se activa con `?avisos=1` (cuenta `operador@prueba.test`).

Panel web de recepción y administración del acceso a N Club. Está hecho solo con **HTML, CSS y JavaScript** (sin frameworks ni compilación) y usa la misma base Supabase que la app móvil `App_registro_Nclub`.

## Modos

| Modo | Cuándo | Datos |
| --- | --- | --- |
| **Demostración** | `js/supabase.js` sin configurar, o el botón «Explorar la demostración» | Ficticios, en memoria. Se puede cambiar de rol (admin, informática, operador) para ver qué permite cada uno |
| **Supabase** | Con la URL y la clave pública configuradas | Reales. Requiere iniciar sesión con una cuenta existente que tenga rol de panel |

## Ejecutar

**Con Live Server (VS Code):** clic derecho en `index.html` → *Open with Live Server*.

**Sin VS Code**, con cualquier servidor estático, por ejemplo:

```bash
npx serve .
```

Abrir `index.html` directamente como archivo también funciona en la demostración, pero Supabase Auth necesita un origen `http(s)`.

**Pruebas con un Supabase falso** (sin dependencias, no toca el proyecto real):

```bash
node tests/serve-mock.js
```

- http://localhost:5511: base actual (migraciones 001–005).
- http://localhost:5511/?migracion=009&espacios=1: con las propuestas aplicadas.
- http://localhost:5511/?espacios=1&avisos=1: como el proyecto real (migraciones 006 y 007).
- Cuentas de prueba y resultados: [docs/PRUEBAS.md](docs/PRUEBAS.md).

## Configurar Supabase

1. En `js/supabase.js`, completa `url` y `publishableKey` con `EXPO_PUBLIC_SUPABASE_URL` y `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` del `.env` de la app. **Nunca** uses la clave `service_role`: el archivo se descarga en el navegador y el panel la rechaza.
2. Inicia sesión con una cuenta de la app que tenga rol `admin` u `operador`. Con las migraciones propuestas, también `informatica`.
3. Para habilitar el rol informática, la administración de personas y la vigencia de 24 h exigida por la base, revisa y aprueba las migraciones de [`supabase/propuestas/`](supabase/propuestas/). **No están aplicadas.** Detalles en [docs/SUPABASE.md](docs/SUPABASE.md).

## Estructura

```
index.html                     Inicio de sesión, menú, las 9 secciones y la ventana modal
css/styles.css                 Estilos y diseño responsive
js/supabase.js                 Conexión: lecturas con columnas explícitas y escrituras solo por RPC
js/app.js                      Roles, tablas, formularios, modales, dashboard y demostración
supabase/propuestas/           Migraciones 008–010 y pruebas SQL de RLS (sin aplicar)
tests/mock-supabase.js         Supabase falso: esquema, RLS, RPC y errores
tests/serve-mock.js            Servidor local que sirve el panel con el Supabase falso
docs/SUPABASE.md               Esquema, roles, reglas, propuestas y problemas abiertos
docs/PRUEBAS.md                Pruebas realizadas y errores encontrados
```

## Qué incluye

- **Inicio de sesión** con Supabase Auth: sin registro público y con mensajes claros si la cuenta no tiene acceso, está suspendida o la sesión expiró.
- **Control por rol** (admin, informática, operador): el menú, las secciones y las acciones se adaptan, y la base de datos aplica la seguridad real (RLS y funciones).
- **Personas y eventos:** búsqueda, filtros, orden, paginación, detalle y exportación CSV.
- **Formularios** con validación, confirmación previa y estado de carga:
  - crear invitaciones y externos (vencen a las 24 h; el QR y el código de pase se muestran una sola vez);
  - revocar accesos y corregir eventos pendientes;
  - asignar roles y editar estado, vínculo, horario y vigencia (con la propuesta 009).
- **Políticas y sistema:** el estado real de las reglas del servidor (vigencia, limpieza, retención, roles y conexión).
- **Responsive:** tablas como tarjetas y modales como hojas inferiores en el móvil.

## Reglas de privacidad

- Los invitados y externos pierden el acceso 24 h después de su registro. El servidor borra sus datos personales con pg_cron, aunque el panel esté cerrado.
- El panel no lee fotos, huellas faciales, tokens ni sus hashes, y no guarda datos en el navegador (solo la sesión de Supabase).
- El historial de eventos tiene una política de retención propia (propuesta 009): sin datos personales a los 90 días y eliminado a los 365.
