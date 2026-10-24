# Integración con Supabase

El panel usa la base de datos que ya usa la app móvil (`App_registro_Nclub`). **No se ha aplicado ninguna migración ni se ha cambiado nada en la base remota.** Los cambios necesarios están en `supabase/propuestas/` y esperan aprobación.

## 1. Fuentes revisadas

| Fuente | Observación |
| --- | --- |
| `App_registro_Nclub/supabase/migrations/` 001–005 | Esquema vigente. Son idénticas a las del zip `archivos.zip` |
| `archivos.zip` → 006 y 007 | No están en el repo de la app (allí hay otra versión de la 006 en `proposed/`). No se sabe si están aplicadas. El panel trata `espacios` (006) como opcional y no usa nada de la 007 |
| `App_registro_Nclub/src/` | La app usa `signUp`, `personas`, `visitas`, `credenciales.token_hash` (lo compara con el token guardado en el teléfono) y las RPC `crear_invitacion`, `revocar_invitacion` y `generar_mi_qr`. Su QR codifica solo el token y comparte pases `NC1.<base64url>` |

## 2. Esquema vigente (001–005)

- **`personas`**: `id`, `usuario_id` (→ `auth.users`), `nombre_demo`, `email`, `telefono`, `vinculo` (`ninguno|regular|vip|personal`), `rol` (`usuario|operador|admin`), `estado` (`activa|suspendida`), `requiere_tour`, `horario_inicio`, `horario_fin`, `vinculo_hasta`, `consentimiento_biometrico`, `consentimiento_fecha`, `creado_en`, `actualizado_en`.
- **`visitas`**: `id`, `persona_id`, `responsable_id`, `categoria`, `motivo`, `empresa`, `destino`, `inicio`, `fin`, `estado`, `nivel_ayuda`, `creado_en`.
- **`credenciales`**: `id`, `persona_id`, `visita_id`, `tipo`, `token_hash` 🔒, `valido_desde`, `valido_hasta`, `revocada_en`, `motivo_revocacion`, `restricciones`, `creado_en`.
- **`eventos`**: `id`, `visita_id`, `persona_candidata_id`, `credencial_id`, `fuente`, `evidencia`, `categoria`, `resultado`, `motivo`, `orientacion`, `duracion_ms`, `creado_en`, `corregido_por`, `correccion_motivo`, `corregido_en`, `foto_id` 🔒, `modo_reconocimiento`.
- **`fotografias`** 🔒: rutas del bucket y embeddings faciales.

🔒 = el panel nunca lo lee.

**RLS actual:**
- `anon` no tiene acceso a nada.
- `authenticated` lee lo suyo, y todo si `es_operador()` (rol `operador` o `admin`, persona activa).
- `eventos` solo lo leen los operadores.
- No hay `insert`, `update` ni `delete` directos, salvo las columnas personales del propio perfil.
- `limpiar_visitas_vencidas()` corre en pg_cron cada 5 minutos y borra a los invitados y externos sin visita vigente, junto con sus visitas y credenciales en cascada.

## 3. Modelo de roles del panel

**Verificación del modelo existente:** no existe el rol `informatica`, y la base no distingue a un administrador de un operador: ambos pasan por `es_operador()`. Por eso el panel funciona en dos niveles:

| | Base actual (001–005) | Con las propuestas 008 y 009 |
| --- | --- | --- |
| Quién entra | `operador` y `admin` activos | `admin`, `informatica` y `operador` activos y con el vínculo vigente (`mi_rol_panel()`) |
| Qué decide los permisos | `es_operador()` | `panel_permisos()` + RLS + comprobaciones dentro de cada función |
| Administración | No disponible: el panel lo explica | `asignar_rol()` y `admin_actualizar_persona()`, con auditoría |

| Permiso | Admin | Informática | Operador | Lo aplica |
| --- | --- | --- | --- | --- |
| Ver miembros y personal | ✓ | ✓ | ✓ | RLS `personas` (009 añade la política de informática, sin invitados) |
| Ver invitados, externos y credenciales | ✓ | — | ✓ | RLS `visitas` y `credenciales` (`es_operador()`) |
| Ver eventos | ✓ | ✓ | ✓ | RLS `eventos` (009 añade la de informática) |
| Crear invitaciones y externos | ✓ | — | ✓ | `crear_invitacion()` (009: informática cuenta como usuario) |
| Revocar | ✓ | — | ✓ | `revocar_invitacion()` (responsable o `es_operador()`) |
| Corregir eventos | ✓ | — | ✓ | `corregir_evento()` (`es_operador()`) |
| Asignar roles | ✓ | ✓ (sin tocar admin) | — | `asignar_rol()` (009) |
| Editar estado, vínculo, horario y vigencia | ✓ | — | — | `admin_actualizar_persona()` (009) |
| Ver auditoría | ✓ | ✓ | — | RLS `auditoria_panel` (009) |

Como cualquier persona del personal, informática puede seguir registrando externos desde la app. Es la regla existente de `crear_invitacion()`.

## 4. Qué lee y escribe el panel (`js/supabase.js`)

**Lee**, siempre con columnas explícitas:
- `personas` (incluye `usuario_id`, solo para saber si hay cuenta);
- `visitas` y `credenciales` sin `token_hash`, solo si el rol las ve;
- `eventos` sin `foto_id` ni `credencial_id`, de los últimos 30 días y como máximo 1000;
- `espacios` y `auditoria_panel`, si existen.

**Escribe** solo con RPC:
- existentes: `crear_invitacion`, `revocar_invitacion`, `corregir_evento`;
- de la 009: `asignar_rol`, `admin_actualizar_persona`.

No hay `insert`, `update` ni `delete` directos.

**Nunca:** `signUp`, `token_hash`, `fotografias`, `auth.users` ni el bucket `fotos`. El token de una invitación nueva se muestra **una sola vez** (QR y código de pase compatible con la app), no se guarda y se borra del DOM al cerrar la ventana.

**Sesión:** Supabase Auth con correo y contraseña. La sesión se guarda en `localStorage` con la clave `nclub-panel-auth`, separada de la app. Si la cuenta no tiene un rol de panel, se cierra la sesión y se explica el motivo.

## 5. Reglas pedidas y cómo se cumplen

| Regla | Estado | Dónde |
| --- | --- | --- |
| Seguridad respaldada por RLS | Lecturas por RLS; escrituras por funciones que validan el rol. El panel solo oculta lo que no corresponde | 003 + propuesta 009 |
| Sin registro público | El panel no tiene registro. **El registro del proyecto sigue activo porque la app lo usa** (B6 en `PRUEBAS.md`). Una cuenta nueva queda como `usuario` y no entra al panel | `index.html`, `js/app.js` |
| Invitados y externos pierden el acceso exactamente 24 h después del registro | Hoy el panel envía `fin` = registro + 24 h. Para que la base lo **exija** a todos (también a la app) hacen falta los triggers de la 009 | Propuestas 009 y 010 |
| Eliminación de datos en el servidor | Ya existe: pg_cron cada 5 min (`limpiar_visitas_vencidas`), sin depender del panel. Falta la limpieza de archivos de Storage (B8) | 003 |
| Historial con política independiente y sin datos innecesarios | Propuesta: job diario `aplicar_retencion_historial()` (desvincula a los 90 días, elimina a los 365). El panel limita el texto libre a 300 caracteres y avisa que no se escriban datos personales | Propuesta 009 |
| No cambiar el reconocimiento facial ni el QR | No se tocan `registrar_llegada()`, `generar_mi_qr()`, `hash_token()` ni `fotografias`. Los triggers solo fijan fechas de vigencia, que `registrar_llegada()` ya respeta | — |

**Impacto en la app de los triggers de 24 h:**
- `InvitationForm` deja elegir una fecha futura. Una invitación que empiece 24 h o más después de crearse será rechazada con el mensaje «La visita debe empezar antes de…».
- Además, el «Hasta» que la app guarda en el pase puede ser distinto del que fija la base.

La app no se modificó. Conviene ajustar su formulario a la regla.

## 6. Migraciones propuestas (`supabase/propuestas/`)

| Archivo | Qué hace | ¿Destructiva? |
| --- | --- | --- |
| `20261025000008_rol_informatica.sql` | Añade `informatica` a `rol_app` | No |
| `20261025000009_panel_permisos_vigencia_retencion.sql` | Funciones de rol, políticas para informática, `auditoria_panel`, `asignar_rol`, `admin_actualizar_persona`, `panel_permisos`, `crear_invitacion` ajustada, triggers de 24 h y job de retención | Al aplicarse, no. El **job de retención borra eventos** cuando se cumplen los plazos: revísalos antes |
| `20261025000010_ajuste_visitas_existentes.sql` | Cancela o recorta las invitaciones existentes que no cumplen las 24 h | **Sí, modifica filas.** Incluye una consulta de vista previa |
| `pruebas_rls_panel.sql` | 10 pruebas de RLS y reglas, en una transacción con `ROLLBACK` | No (solo en una base de pruebas) |

**Orden sugerido**, después de aprobarlo:
1. Probar en una rama de Supabase o en local: 008, luego 009, luego `pruebas_rls_panel.sql`.
2. Aplicar 008 y 009 en producción.
3. Revisar la vista previa de la 010 y aplicarla.

**Consultas de verificación** (solo lectura, para el SQL Editor):
```sql
select version, name from supabase_migrations.schema_migrations order by version;
select jobname, schedule from cron.job;   -- debe existir limpiar-visitas-vencidas
select to_regclass('public.espacios') as espacios, to_regclass('public.auditoria_panel') as auditoria;
```

## 7. Problemas abiertos

- **P2 · Primera cuenta de panel:** si el club aún no tiene un operador o admin, alguien con acceso al SQL Editor debe asignarlo, después de que esa persona se registre en la app:
  ```sql
  update public.personas set rol = 'admin' where email = 'correo@dominio' and usuario_id is not null and vinculo = 'personal';
  ```
- **P3 · Columnas sensibles por la API:** con sesión de operador se pueden pedir `fotografias.embedding` y `credenciales.token_hash`. La app no lee `fotografias`, así que se puede restringir esa tabla por columnas. `token_hash` lo lee la app (`useMemberQr.ts`), así que primero habría que cambiar la app.
- **B7 · Vínculos vencidos:** `es_operador()` no revisa `vinculo_hasta`.
- **B8 · Fotos en Storage:** las fotos de los invitados borrados quedan en el bucket.

## 8. Configuración

1. En `js/supabase.js`, completa `url` y `publishableKey` con `EXPO_PUBLIC_SUPABASE_URL` y `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` del `.env` de la app. **Nunca** la `service_role`: el archivo la rechaza.
2. En Supabase → Authentication → URL Configuration, añade el origen donde se publique el panel si vas a usar enlaces de correo. Para iniciar sesión con contraseña no hace falta.
3. Asegúrate de que exista al menos una cuenta con rol de panel (P2).
