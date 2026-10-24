# Pruebas del panel y errores encontrados

Fecha: 24 de octubre de 2026. Todas las pruebas usaron **datos ficticios**. No se tocó el proyecto Supabase real ni se aplicó ninguna migración.

## 1. Cómo se probó

| Entorno | Qué cubre | Cómo ejecutarlo |
| --- | --- | --- |
| **Demostración** (`index.html` sin configurar Supabase) | Interfaz completa y reglas imitadas en memoria (roles, 24 h, limpieza y retención) | Abrir con Live Server |
| **Supabase falso** (`tests/mock-supabase.js`) | El código real de `js/supabase.js`: inicio de sesión, RLS, RPC, errores de PostgREST y de red | `node tests/serve-mock.js` → http://localhost:5511 (base actual) o `?migracion=009&espacios=1` |
| **SQL** (`supabase/propuestas/pruebas_rls_panel.sql`) | RLS y funciones reales en Postgres | En una base local o una rama de Supabase. **No ejecutado:** no hay Postgres disponible en este equipo |

Cuentas del Supabase falso (solo existen en `tests/mock-supabase.js`; contraseña de prueba `prueba-nclub-2026`):
`admin@prueba.test`, `operador@prueba.test`, `informatica@prueba.test` (solo entra con `?migracion=009`), `miembro@prueba.test` (rol usuario) y `suspendido@prueba.test`.

## 2. Resultados

**Demostración: 48 comprobaciones, todas correctas.**
- Crear invitación:
  - valida campos obligatorios y rechaza un inicio fuera de la ventana de 24 h;
  - pide confirmación y bloquea los campos mientras tanto;
  - muestra el QR y el código de pase `NC1.` una sola vez (se decodifica con el formato de la app);
  - la visita vence a las 24 h exactas y el token desaparece del DOM al cerrar.
- Revocar (confirmación roja), corregir un evento, cambiar un rol con auditoría y editar con validación de horario.
- Nadie puede suspenderse a sí mismo ni cambiar su propio rol.
- **Informática:**
  - no ve invitados ni externos y la ruta `#invitados` la redirige;
  - los eventos de invitados aparecen sin datos personales;
  - no puede invitar ni tocar administradores;
  - sí asigna roles y ve la auditoría.
- **Operador:** sin «Usuarios y roles» ni auditoría; puede invitar y registrar externos (empresa y motivo obligatorios).
- **Limpieza simulada:** al vencer la visita se borran la persona y la visita, y el evento queda sin vínculos.

**Supabase falso, base actual (001–005): 30 comprobaciones, todas correctas.**
- Inicio de sesión:
  - campos vacíos y contraseña incorrecta;
  - miembro rechazado («no tiene acceso al panel»), cuenta suspendida rechazada;
  - informática rechazada sin la 009.
- Operador:
  - entra con el modelo actual;
  - la lectura respeta RLS y aparece el aviso de que falta `espacios`;
  - nunca pide `token_hash`, `fotografias`, `foto_id` ni `*`, y no hace escrituras directas.
- Crear (RPC `crear_invitacion` con fin = registro + 24 h), revocar y corregir por RPC.
- Errores:
  - un fallo de red se muestra en el formulario y se puede reintentar;
  - `asignar_rol` sin la 009 responde «falta aplicar la migración»;
  - una sesión expirada vuelve al inicio de sesión con aviso.

**Supabase falso con la 009: 15 comprobaciones, todas correctas.**
- Informática entra, sin acceso a visitas, y asigna operador por RPC.
- La base le impide quitar un admin o invitar.
- Admin cambia el vínculo con un resumen previo y suspende con confirmación; la base le impide suspenderse a sí mismo.
- La auditoría se completa.
- El trigger fija 24 h aunque se pidan 7 días.
- La sesión se restaura al recargar.

**Responsive:** sin desplazamiento horizontal a 375 px en ninguna sección. El formulario se muestra como hoja inferior.

## 3. Errores encontrados

### En la base de datos y los permisos (propuestas sin aplicar)

| # | Problema | Riesgo | Propuesta |
| --- | --- | --- | --- |
| B1 | `rol_app` solo tiene `usuario`, `operador` y `admin`: **no existe `informatica`** | No se puede implementar el rol pedido | Migración 008 (añade el valor al enum) |
| B2 | `crear_invitacion()` solo bloquea el rol `usuario`, así que un rol nuevo podría invitar | Informática tendría permisos de recepción en el servidor | 009 la reemplaza con la misma firma y lógica, contando a informática como usuario |
| B3 | La base **no limita la vigencia** de invitados y externos: acepta el `p_fin` que envíe la app (hasta días después) | Incumple la regla de 24 h | 009: triggers que fijan `fin` y `valido_hasta` en registro + 24 h; 010 ajusta las filas existentes |
| B4 | No hay funciones para cambiar rol, estado, vínculo, horario ni vigencia; `authenticated` no puede escribir esas columnas | El panel no puede administrar personas | 009: `asignar_rol()` y `admin_actualizar_persona()`, validadas en el servidor y auditadas |
| B5 | Los eventos se conservan sin límite, con texto libre (`correccion_motivo`) | Se guardan datos personales más tiempo del necesario | 009: retención independiente (desvincular a los 90 días, eliminar a los 365) |
| B6 | El registro público (`signUp`) está activo y **la app móvil lo usa** (`register.tsx`) | Desactivarlo en Supabase rompería el registro de miembros | No se desactivó. El panel no ofrece registro y exige un rol asignado en la base |
| B7 | `es_operador()` no revisa `vinculo_hasta` | Un empleado con contrato vencido conserva el acceso de operador | `mi_rol_panel()` sí lo revisa. Cambiar `es_operador()` afecta a la app: queda como decisión pendiente |
| B8 | Las fotos de Storage de un invitado no se borran cuando la base borra su fila | Quedan imágenes personales huérfanas | Limpieza del bucket con el backend o una Edge Function (no incluida) |
| B9 | Un operador puede pedir `token_hash` y `embedding` directamente a la API | Exposición de datos sensibles | Ver P3 en `SUPABASE.md`. `token_hash` requiere cambiar primero la app |

### En el prototipo (corregidos)

| # | Problema | Corrección |
| --- | --- | --- |
| U1 | Había acciones sin respaldo en la base: crear miembros, regenerar QR, reenviar QR y editar la configuración | Se eliminaron. Solo quedan las operaciones que permiten la base actual o la 009 |
| U2 | La configuración permitía cambiar horarios y umbrales que en realidad son restricciones de la base o parámetros del robot | Ahora es «Políticas y sistema», de solo lectura, con el estado real de cada regla |
| U3 | La demo mostraba invitados finalizados de días anteriores, que en la base real ya estarían borrados | La demo genera filas con la forma de las tablas y aplica la misma limpieza |
| U4 | El mensaje de confirmación quedaba fuera de la vista al final del formulario | Se movió arriba y el formulario se desplaza hasta él |
| U5 | Al crear una invitación, el foco saltaba al código y ocultaba el aviso y el QR | La ventana abre arriba, con el foco en «Listo» |

## 4. Limitaciones

- El Supabase falso **imita** RLS en JavaScript. Para verificar las políticas reales hay que ejecutar `supabase/propuestas/pruebas_rls_panel.sql` en una base de pruebas.
- No se probó con el proyecto real: `js/supabase.js` no tiene URL ni clave configuradas.
- La lectura del QR generado por el panel con el robot no se probó. El panel codifica el token igual que la app (`QrCard`: solo el token, nivel de corrección M).
