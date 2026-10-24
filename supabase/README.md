# Base de datos (Supabase)

Proyecto `nclub-sabanahack` (`https://htgcummucmswgileefxv.supabase.co`). Las migraciones van en
`migrations/`, en orden por nombre, y ya están aplicadas. El modelo actual es
`20261023000003_personas_credenciales_visitas.sql` más `20261023000004_fotografias_reconocimiento.sql`
(fotos del dataset y resultado facial). Las dos primeras (`miembros` / `accesos_temporales`)
quedan solo como historial.

`seed_demo.sql` carga los datos de la demo (los mismos de la simulación, con los mismos UUID): 15
personas, 5 visitas, 15 credenciales y 55 fotografías (27 de registro con huella simulada). **Ahora
no está cargado**: la base solo tiene las personas reales del equipo (ver abajo). Si se necesita otra
vez, se corre en el editor SQL (las ventanas de las visitas quedan relativas a ese momento). Lo genera `simulation/semilla_supabase.py`. Los QR de la
demo son predecibles (`qr-valentina`, `qr-sofia`…): sirven solo para esta base de prueba.

Datos cargados ahora: las 5 caras reales del equipo (huellas `sface-2021dec`, de
`simulation/registrar_caras.py`): Camilo (VIP), Felipe (regular), Juan (personal, turno 14–22),
Sebastián (invitado de Camilo, restaurante) y Thalia (externa de Climatizar SAS a cargo de Juan,
mantenimiento). También está "Mentor de prueba", invitado de Camilo sin cara registrada, que solo entra
con QR. Cada uno tiene un QR (los genera `simulation/generar_qr.py`; aquí solo está el hash): personal
para los miembros y el personal, de visita para los invitados y la externa. Las visitas de Sebastián y Thalia
valen hasta el 24/10 a las 22:00. Sus fotos están en el bucket `fotos`, en `equipo/<clave>/`.

## Modelo

La identidad, el vínculo con el club, la credencial y la visita son cosas distintas: una persona
puede ser miembro y además venir como invitada, o trabajar en el club y venir como miembro un fin de
semana. Las contraseñas las maneja Supabase Auth; las fotos van en el bucket privado `fotos`.

| Tabla | Qué guarda |
|---|---|
| `personas` | Quién es: `usuario_id` (Auth, opcional), nombre, contacto, `vinculo` (`ninguno`, `regular`, `vip`, `personal`) con su vigencia (`vinculo_hasta`), `rol` en la app (`usuario`, `operador`, `admin`), `estado`, horario, `requiere_tour` y consentimiento biométrico. |
| `fotografias` | Persona, ruta en el bucket privado `fotos`, fecha, `uso` (`registro` o `prueba`), autorización, huella (`embedding`, la calcula el backend) y `modelo` (`simulado-v1` o el real). Solo las de registro se usan para reconocer; las de prueba guardan la persona esperada para evaluar. |
| `visitas` | Por qué está hoy en el club: `categoria` (`regular`, `vip`, `personal`, `invitado`, `externo`), `responsable_id`, `destino`, `empresa`, ventana `inicio`–`fin`, `estado`, `nivel_ayuda`. La orientación corresponde siempre a la visita activa. |
| `credenciales` | QR personal o de visita. Solo se guarda el hash SHA-256 del token; se puede revocar con motivo. |
| `eventos` | Cada llegada: foto de llegada, si el reconocimiento fue `real` o `simulado`, identidad candidata, evidencia (cara / QR), categoría confirmada, resultado (`orientado`, `rechazado`, `pendiente_revision`, `corregido`), orientación dada, duración y, si recepción corrigió, quién, cuándo y por qué. |

Reglas:

- Horario: miembros de 06:00 a 21:00; personal con turno propio dentro de 04:00–22:00, de máximo 8 h.
- La huella facial solo existe si la foto está autorizada y la persona dio consentimiento (Ley 1581
  de 2012); si lo retira, sus huellas se borran solas. El reconocimiento es voluntario: el QR o
  recepción son la alternativa.
- Membresía o vínculo vencido (`vinculo_hasta` pasado): la cara se reconoce, pero no entra.
- Un invitado o externo que registró su cara entra reconocido con su visita activa, sin QR.
- El trabajador externo necesita empresa y responsable, y solo puede ir acompañado por el D1.
- Las personas sin vínculo (invitados, externos) se borran cuando ya no tienen visitas vigentes
  (tarea `limpiar-visitas-vencidas`, cada 5 minutos).

## Seguridad

- RLS en todas las tablas. `anon` no ve nada.
- Nadie se asigna a sí mismo VIP, personal ni admin: la app solo puede escribir en `personas` las
  columnas de nombre, contacto, foto y consentimiento. Vínculo, rol y horario los cambia un admin
  desde el panel de Supabase.
- Un miembro ve su perfil, sus visitas, sus credenciales y a sus invitados. Recepción (`operador`)
  ve todo y es la única que ve los eventos.
- La clave `service_role` solo la usa el backend del robot, nunca el navegador ni la app.

## Funciones

### Para la app y la web (usuario autenticado)

| Función | Qué hace |
|---|---|
| `generar_mi_qr()` | Revoca el QR personal anterior y devuelve uno nuevo (el token solo se ve esta vez). |
| `crear_invitacion(p_nombre, p_email, p_destino, p_inicio, p_fin, p_categoria default 'invitado', p_empresa, p_motivo)` | Regular o VIP invitan; personal u operador registran externos. Crea persona, visita y QR; devuelve `{visita_id, token}`. |
| `revocar_invitacion(p_visita, p_motivo)` | El anfitrión (u operador) cancela la visita y revoca su QR. |
| `corregir_evento(p_evento, p_categoria, p_motivo, p_persona default null)` | Solo operador: resuelve un caso pendiente; el motivo es obligatorio. |

Registro de un usuario: después del `signUp`, insertar su fila en `personas` con `usuario_id`,
`nombre_demo`, `email`, `telefono`, `consentimiento_biometrico` y `consentimiento_fecha` (queda como
miembro regular por defecto). `foto_ref` ya no existe.

Fotos desde la app: subir el archivo al bucket `fotos` dentro de la carpeta `<auth.uid()>/` e
insertar la fila en `fotografias` con `persona_id` y `cargada_por` = su persona, `ruta`,
`uso = 'registro'` y `autorizada = true`. La app no puede escribir la huella ni subir fotos de
prueba; el usuario sí puede borrar sus fotos.

### Para el robot (solo `service_role`)

| Función | Qué hace |
|---|---|
| `registrar_llegada(p_embedding, p_token, p_modo 'real', p_captura_valida true, p_foto, p_umbral 0.40, p_umbral_duda 0.50, p_margen 0.05, p_fuente 'robot', p_modelo)` (`p_modelo`: compara solo huellas de ese modelo, p. ej. `sface-2021dec`; los umbrales dependen del modelo) | Compara la huella con las fotos de registro (resultado: `reconocida`, `desconocida`, `ambigua` o `captura_no_valida`), revisa el QR y la acreditación vigente, decide y registra el evento. Devuelve solo lo que el robot necesita: resultado, motivo, evidencia, categoría, nombre, destino, empresa, `requiere_tour`, ayudas disponibles y horario. Contradicción cara/QR, cara ambigua o captura no válida sin QR quedan `pendiente_revision` para recepción. |
| `guardar_huella(p_foto, p_embedding, p_modelo)` | Guarda la huella de una foto de registro (la calcula el backend). |
| `registrar_orientacion(p_evento, p_nivel, p_destino, p_duracion_ms, p_ruta)` | Guarda qué ayuda eligió la persona y la ruta. |
| `completar_tour(p_persona)` | El D1 terminó el recorrido de bienvenida de un miembro regular nuevo. |

Las advertencias del asesor de seguridad sobre funciones `SECURITY DEFINER` ejecutables por
`authenticated` son intencionales: esas funciones validan por dentro quién llama.
