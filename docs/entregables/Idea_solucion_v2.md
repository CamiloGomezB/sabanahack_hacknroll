# Hugo y Dogo — Propuesta de recepción robótica humanista para N Club

**Equipo:** Hack N' Roll · **Reto:** N Club · Sabana Hack 2026

**Hugo** es el humanoide AgiBot X2 que recibe en la entrada. **Dogo** es el cuadrúpedo AgiBot D1 que acompaña. En este documento, "Hugo" y "el humanoide" se refieren al X2, y "Dogo", "el D1" y "el perro robótico" se refieren al D1.

## Resumen ejecutivo

- **Problema:** el reconocimiento facial de N Club solo distingue miembros y no miembros. Todo lo demás (a qué viene cada persona, a quién busca, por dónde moverse) recae en la recepción.
- **Propuesta:** Hugo confirma la categoría de cada visitante con los registros del club y prepara su siguiente paso; Dogo acompaña a quien lo necesita. La interacción es por voz y gestos, sin pantallas, y siempre transparente: cualquier visitante puede pedir una persona.
- **Diferencial:** cinco flujos distintos para VIP, miembros regulares, invitados, personal y externos, con especial cuidado en quienes no son miembros, y un manejo cálido y honesto de la duda que nunca trata al visitante como intruso.
- **Estado:** app funcional y simulación de Hugo y Dogo atendiendo a los cinco perfiles (ver sección 7).
- **Inversión:** ≈ USD 115 mil iniciales y ≈ USD 33 mil al año de operación. El retorno depende de generar valor (reservas y retención de miembros), que se mediría en un piloto de tres meses.

## Contenido

1. Problema y propuesta
2. App y base de datos
3. Identificación y confirmación de la categoría
4. Los cinco flujos de atención
5. Funciones de Hugo y Dogo
6. Diferenciación, validación e impacto
7. Alcance del prototipo
8. Presupuesto e inversión
9. Benchmarking
10. Riesgos y mitigación
11. Siguientes pasos

**Anexo:** `Presupuesto_Hugo_y_Dogo.xlsx` (modelo de presupuesto y análisis financiero)

---

## 1. Problema y propuesta

N Club recibe cinco tipos de visitantes: miembros VIP, miembros regulares, invitados, personal del club y trabajadores externos. El reconocimiento facial existente distingue miembros y no miembros, pero esa información resulta insuficiente para confirmar la categoría específica y orientar correctamente a cada persona.

Nuestra propuesta es una **recepción robótica humanista que conecta la llegada con el siguiente paso de la visita**: confirma la categoría, consulta información relevante, coordina con las personas involucradas y ofrece orientación o acompañamiento poniendo siempre a la persona en el centro. La interacción es natural, cálida y "cero pantallas" (mediante voz, sensores táctiles y lenguaje corporal empático), **siempre transparente**: el visitante sabe que habla con un robot y puede pedir una persona en cualquier momento, en cualquier flujo. El robot adapta su ritmo a señales explícitas (la categoría, la hora del turno, si la persona dice que va de prisa o prefiere seguir sola), no a emociones inferidas de su rostro o su voz.

El sistema tendrá tres componentes:

- **Una app:** permite preparar visitas, consultar credenciales y recibir información y notificaciones (funcionando como soporte silencioso para no robar protagonismo a la interacción humana con los robots).
- **Una base de datos compartida:** reúne personas, acreditaciones, imágenes, visitas, destinos y novedades.
- **Una simulación robótica:** representa a Hugo, el humanoide AgiBot X2 que recibe y orienta con calidez, y a Dogo, el cuadrúpedo AgiBot D1 que acompaña, lleva objetos livianos de hasta 5 kg y guía por rutas autorizadas cuando se necesita.

**Hugo permanece principalmente en recepción. Cuando alguien necesita acompañamiento físico, apoyo para llevar un objeto liviano o guía hacia áreas técnicas, lo realiza Dogo.**

La idea central es que la visita esté coordinada desde la entrada:

- El invitado sabe dónde encontrarse con su anfitrión y este recibe aviso de su llegada.
- El trabajador externo conoce su tarea, su responsable y su recorrido autorizado, contando con apoyo para llevar herramientas livianas y un recorrido explicado desde el inicio.
- El personal empieza su jornada informado sobre asignaciones, eventos y novedades de forma ágil.
- Los miembros encuentran servicios y actividades adecuados a su membresía y preferencias sin fricción.

El trato será cercano, breve y respetuoso. La personalidad del robot debe facilitar la interacción sin convertir cada llegada en una conversación obligatoria.

### Supuestos generales

N Club dispone de registros de membresía, empleados, invitaciones y órdenes de trabajo. También puede registrar reservas, eventos, asignaciones y puntos de encuentro.

El prototipo utiliza datos controlados de demostración. No afirmamos conocer la operación real de un club específico.

La categoría determina opciones y restricciones. **La necesidad de orientación depende también del motivo de visita y de la elección de la persona.** Un VIP puede necesitar acompañamiento (incluyendo transporte de su maletín o bolso en el lomo del cuadrúpedo D1) y un invitado recurrente puede preferir continuar sin ayuda.

N Club tiene **una sola sede**. Toda la propuesta, incluido el presupuesto, se plantea para esa sede; el crecimiento se entiende como ampliar la flota de robots, no como abrir sedes.

---

## 2. App y base de datos

La app prepara la información que el robot necesita y permite continuar la experiencia desde el celular (actuando como soporte silencioso para mantener el protagonismo en la interacción humana y "cero pantallas" con los robots en recepción).

Su alcance principal incluye:

- Perfil y credencial.
- Próxima visita o reserva.
- Invitaciones.
- Destinos y servicios.
- Notificaciones relacionadas con llegadas (mostradas como avisos pop-up de apoyo durante la simulación).
- Información laboral para los perfiles correspondientes.

La propuesta no incluye una página independiente de service desk. Cuando exista una situación que requiera criterio humano, el robot solicitará apoyo al personal de recepción mediante el "Protocolo de Calidez ante la Duda". Si implementamos una acción administrativa, estará limitada al alcance acordado de la misma app.

### Para miembros

Los miembros pueden consultar su credencial, próximas actividades y visitas. También pueden crear una invitación indicando persona invitada, fecha, horario y punto de encuentro.

Registrarse en la app no otorga automáticamente una membresía. Para el prototipo asumimos que el club ya aprobó y registró a sus miembros. Afiliación, compra de acciones y pagos completos quedan fuera del desarrollo prioritario.

### Para invitados

La invitación identifica al anfitrión, la vigencia y el destino permitido. El invitado recibe o consulta una credencial QR.

El punto de encuentro puede estar preparado antes de su llegada. Esto reduce preguntas en recepción y permite que el anfitrión reciba un aviso relacionado con una visita concreta.

### Para personal y trabajadores externos

El personal consulta sus asignaciones y novedades.

Los externos cuentan con una orden registrada por alguien autorizado, que contiene tarea, responsable del club, horario, punto de encuentro y restricciones. Un externo no puede autorizarse a sí mismo.

### Información que debe compartir el sistema

| Información | Para qué sirve |
|---|---|
| Personas | Identificar a quién corresponde cada registro |
| Fotografías de referencia | Alimentar el reconocimiento facial |
| Acreditaciones | Confirmar categoría, estado y vigencia |
| Visitas y órdenes | Conocer motivo, destino, anfitrión o responsable |
| Eventos y novedades | Contextualizar la orientación del personal |
| Resultados y notificaciones | Comprobar qué decidió el sistema y qué ocurrió después |

Las fotografías se guardan en almacenamiento privado, vinculadas mediante identificadores a los registros. La base necesita conservar las referencias, sin duplicar imágenes dentro de cada tabla.

Los responsables de app, base y simulación deben utilizar los mismos identificadores de persona y visita.

---

## 3. Identificación y confirmación de la categoría

La solución separa tres decisiones:

**Identidad candidata → categoría confirmada → permisos y orientación de la visita.**

El reconocimiento facial compara una imagen de llegada con el dataset y propone una identidad. En la implementación física se apoyaría en la cámara de profundidad RGB-D `Orbbec Gemini335` del X2 para validar en tres dimensiones y evitar suplantaciones con fotos. Después se consulta información adicional para confirmar la categoría y comprobar qué puede hacer esa persona en esa visita.

**Quién se identifica por rostro y quién por QR:** solo los miembros y el personal que aceptaron el reconocimiento facial se identifican por rostro. Invitados y trabajadores externos se identifican por defecto con su código QR, sin que su rostro se compare con ninguna base. Cualquier persona puede pedir usar solo su QR, sin perder ningún servicio.

### Confirmación de las cinco categorías

| Categoría | Información adicional |
|---|---|
| VIP | Membresía activa y nivel VIP |
| Regular | Membresía regular activa |
| Invitado | Invitación vigente y anfitrión registrado |
| Personal | Vínculo laboral activo y asignación correspondiente |
| Externo | Orden de trabajo vigente y responsable registrado |

El nivel de membresía o la condición laboral proceden de registros autorizados. No se deducen de la apariencia.

### Dataset y comparación

El dataset se compone de fotos de integrantes del equipo o participantes que autoricen su utilización.

Para probar reconocimiento real, deben existir imágenes de referencia e imágenes de prueba distintas. No sirve evaluar únicamente con la misma fotografía que se cargó al registro, ni identificar a alguien por el nombre del archivo.

El sistema debe admitir:

- Coincidencia aceptada.
- Persona desconocida.
- Coincidencia ambigua.
- Imagen no válida o captura insuficiente.

### Alternativa QR y Protocolo de Calidez ante la Duda (Manejo de la incertidumbre con dignidad)

Una cara desconocida o una lectura ambigua no significa automáticamente que la persona no sea miembro, y jamás debe hacerse sentir al visitante como un intruso. Cuando el umbral de confianza facial sea bajo, el humanoide asume la responsabilidad con calidez y sin inventar causas: la falla es del sistema, nunca del visitante (ej. *"¡Qué gusto recibirte en N Club! No logré confirmar quién eres con mi cámara. ¿Me dices tu nombre o me muestras tu pase QR un segundo?"*). Luego consulta la existencia, vigencia, revocación y relación de la credencial con la visita.

El robot nunca da excusas falsas (como culpar a la luz) para suavizar la situación: la calidez se construye con honestidad.

El QR no debe contener una categoría que el sistema acepte sin verificar. Su función es permitir consultar una credencial válida.

Una credencial puede ser compartida: por eso, si contradice la identidad candidata o no permite confirmar lo necesario, se solicita apoyo humano de inmediato y sin fricción.

El sistema no actualiza automáticamente el dataset con la cara de alguien solo porque presentó un QR.

### Qué se simula en el prototipo

En el prototipo, el reconocimiento facial está simulado y así se indica en pantalla. Su salida sí alimenta las decisiones posteriores: la consulta de acreditaciones, la confirmación de la categoría y el flujo de atención.

Por eso validamos la lógica de acreditaciones y los flujos de orientación, pero no presentamos resultados de precisión facial como si se hubiera probado un algoritmo real.

---

## 4. Los cinco flujos de atención

La diferenciación debe producir acciones útiles, visibles y profundamente humanas: el humanoide AgiBot X2 recibe con lenguaje corporal acogedor (usando sus manos articuladas `OmniHand` para gestos naturales de bienvenida e indicación espacial y su sensor táctil de cabeza para confirmaciones rápidas sin pantallas), mientras el cuadrúpedo Agibot D1 adapta su postura (`ControlHead()`, `HighLowStance()`) y velocidad (`Move()`) al paso de la persona.

### A. Miembro VIP — Anticipación: la llegada ya está preparada

**Propósito del flujo:** anticipar. El VIP no debería tener que pedir nada: el club ya sabe que llega y lo está esperando.

**Necesidad:** entrar sin esperas ni filas, con su plan resuelto y sin tocar pantallas públicas.

Qué hace distinto este flujo:

1. **Aviso previo al personal:** al confirmar la identidad VIP, el sistema avisa al área de destino (restaurante, sala privada o maître) para que alguien lo reciba por su nombre.
2. **Plan ya resuelto:** si tiene reserva, el robot no pregunta; la confirma y le dice que ya lo esperan. Si no tiene, propone directamente la opción que coincide con su preferencia registrada (por ejemplo, su mesa habitual), en lugar de un menú de alternativas.
3. **Prioridad en el acompañamiento:** si el D1 está disponible, se asigna primero al VIP, que puede entregarle su maletín o bolso (hasta 5 kg) para llevarlo en el lomo.

Ejemplo:

“Bienvenida, Valentina. Tu mesa en el restaurante exclusivo está lista y ya avisé que vas en camino. ¿Te acompaña nuestro guía con tu bolso?”

La persona responde por voz o toque rápido. Cualquier reserva nueva o costo adicional requiere su confirmación antes de registrarse.

**Resultado visible:** área de destino avisada antes de su llegada, plan confirmado en una sola frase y acompañamiento prioritario con carga opcional.

### B. Miembro regular — Descubrimiento: encontrar qué hacer hoy

**Propósito del flujo:** descubrir. El regular viene a usar el club y el robot le ayuda a encontrar la mejor opción del día, sin menús complejos.

**Necesidad:** llegar a su actividad o descubrir una opción disponible acorde con su membresía, de forma breve y natural.

Qué hace distinto este flujo:

1. **Pregunta abierta y corta:** si no hay reserva, el robot pregunta qué quiere hacer hoy (relajarse, hacer deporte o comer) con lenguaje corporal abierto (manos `OmniHand`).
2. **Oferta según disponibilidad real:** propone actividades con cupo en ese momento (spa, golf, gastronomía), dentro de los permisos de su membresía, e informa si alguna tiene costo adicional.
3. **Novedades del club:** puede mencionar una actividad o evento del día que el miembro no conocía. Es aquí donde nace la reserva adicional que mide el piloto.

Ejemplo:

“Hola, Andrés. ¿Hoy prefieres relajarte o hacer deporte? Hay cupo en el spa a las cuatro y una clínica de golf a las cinco.”

El miembro confirma su elección por voz o con el sensor táctil de cabeza del humanoide, y recibe orientación o acompañamiento con el D1 si lo desea.

**Resultado visible:** actividad descubierta y reservada en el momento, con destino preparado.

**Diferencia clave:** al VIP el club se le adelanta; al regular el club le ayuda a descubrir. Uno llega con el plan resuelto, el otro encuentra el plan en la entrada.

### C. Invitado — Encuentro coordinado con su anfitrión

**Necesidad:** sentirse esperado, reducir la incertidumbre de una primera visita y llegar al encuentro con tranquilidad.

Este es uno de los ejes principales de la propuesta:

1. El robot recibe al invitado con un tono de voz pausado, hospitalario y tranquilizador, y confirma la invitación y su vigencia.
2. Consulta quién es el anfitrión y el punto de encuentro registrado.
3. Emite una notificación de llegada al anfitrión.
4. Informa al invitado dónde debe encontrarse con él, señalando cálidamente la dirección con sus manos articuladas.
5. Ofrece indicaciones o acompañamiento amigable con el perro D1 (que inclina la cabeza en señal de atención con `ControlHead()` y camina a su mismo ritmo).

Ejemplo:

“Bienvenida, Laura. Tu anfitriona es Camila y el encuentro está registrado en el restaurante Jardín. Le enviaré el aviso de tu llegada. ¿Prefieres ver el camino o que nuestro guía te acompañe?”

Si el anfitrión confirma un nuevo punto de encuentro, el sistema actualiza la orientación dentro de las zonas autorizadas.

**No suponemos seguimiento permanente de ubicación.** El robot informa el punto de encuentro o la ubicación compartida voluntariamente, con su estado de actualización.

Si no hay respuesta y el encuentro requiere confirmación, se indica una zona de espera apropiada o se solicita apoyo humano.

**Resultado visible:** aviso emitido, estado de respuesta y encuentro orientado con calidez.

### D. Personal del club — Inicio de jornada informado

**Necesidad:** conocer asignaciones y novedades relevantes para su trabajo con total agilidad (respetando su prisa al iniciar turno, sin conversaciones largas ni menús lentos).

El robot consulta el área correspondiente y comunica un resumen breve en pocos segundos:

- Asignación o tarea registrada.
- Evento relevante para su área.
- Cambio de acceso o recorrido.
- Novedad operativa que afecte su trabajo.

Ejemplo:

“Hola, Daniel. Hoy estás asignado a eventos. Hay una recepción de 120 asistentes prevista para las seis y el montaje utiliza el acceso norte. Tu coordinadora dejó una novedad para el equipo.”

Estos datos deben proceder del calendario y de registros de trabajo. La cifra del evento sería un dato ficticio de demostración, no una previsión inventada por el robot.

La persona confirma rápidamente (por voz o toque simple) que recibió la información y continúa. Puede solicitar indicaciones o acompañamiento si lo necesita.

**Resultado visible:** asignación consultada y novedad recibida sin demoras.

### E. Trabajador externo — Trabajo coordinado, asistencia de carga y recorrido seguro

**Necesidad:** recibir un trato digno y respetuoso, llegar a su responsable con comodidad y realizar una tarea concreta, conociendo desde el principio por dónde puede moverse.

**Principio:** las restricciones son de las zonas, no de las personas. Cualquier visitante, sea VIP o externo, recibe el mismo trato si se acerca a un área no autorizada para su visita. El D1 acompaña al externo como ayuda, no como vigilancia.

El robot:

1. Confirma la orden y su vigencia dando una bienvenida cordial.
2. Resume la tarea registrada valorando su apoyo.
3. Identifica al responsable del club.
4. Emite un aviso de llegada a ese responsable.
5. Explica desde el inicio, de forma amable y transparente, el punto de encuentro, el recorrido autorizado y el horario de la orden, para que el trabajador sepa por dónde moverse antes de empezar.
6. Ofrece al cuadrúpedo D1 como apoyo: el perro se agacha (`HighLowStance()`) para recibir en su lomo herramientas livianas o un maletín de hasta 5 kg, y lo guía por la ruta autorizada con navegación SLAM y LiDAR.
7. Si el recorrido se desvía hacia un área no autorizada, el D1 primero se detiene y pregunta si necesita ayuda o indicaciones; solo si el desvío continúa avisa al responsable del club. Nunca trata el desvío como una falta de entrada.

Ejemplo:

“¡Buen día, Luis! Gracias por venir a apoyarnos hoy con el mantenimiento del aire acondicionado. Ya le avisé a tu responsable en el club, Ana Martínez, que estás aquí. Tu recorrido es por el acceso técnico hasta la sala de máquinas. Si quieres, nuestro compañero D1 lleva tus herramientas livianas y te acompaña.”

El responsable del club no tiene por qué ser el empleador del trabajador. Debe quedar claro quién lo recibe y coordina su visita.

Si la orden exige que una persona lo reciba, el perro puede acompañarlo al punto de encuentro, pero no reemplaza esa autorización ni habilita acceso a otras áreas.

**Resultado visible:** tarea confirmada con trato humano, responsable avisado, recorrido explicado desde el inicio y acompañamiento con carga opcional.

---

## 5. Funciones de Hugo y Dogo

### Hugo (humanoide AgiBot X2): recepción humanista y coordinación

Permanece principalmente en la entrada y lidera la interacción "cero pantallas", poniendo a la persona en el centro mediante voz adaptativa, gestos corporales empáticos (`OmniHand 2025`) y confirmación táctil (`Sensor Táctil de Cabeza Awinic`):

- Recibe con contacto visual y lenguaje corporal acogedor, adaptando su ritmo a señales explícitas: la categoría, la hora del turno o si la persona dice que tiene prisa.
- Es transparente sobre lo que es: no finge ser una persona, y cualquier visitante puede pedir atención humana en cualquier momento.
- Utiliza el resultado del reconocimiento facial (en la versión física, con validación 3D de su cámara RGB-D `Orbbec Gemini335` para evitar suplantaciones).
- Solicita evidencia adicional cuando corresponde aplicando el "Protocolo de Calidez ante la Duda" (asumiendo con honestidad que la duda es del sistema, sin excusas inventadas, para nunca hacer sentir al visitante como un intruso).
- Confirma la categoría.
- Consulta la visita.
- Comunica información y opciones de forma conversacional.
- Coordina avisos.
- Da indicaciones físicas con sus brazos articulados o asigna acompañamiento.

### Dogo (cuadrúpedo AgiBot D1): acompañamiento, apoyo de carga y rutas seguras

Cuando la persona necesita acompañamiento y acepta, el humanoide asigna la misión al perro.

La misión necesita destino, recorrido permitido y estado. El perro no necesita disponer de todas las fotografías ni de toda la información personal. Además de guiar, adapta su postura para no intimidar (`ControlHead()` para inclinar la cabeza amistosamente y `Move()` al ritmo del paso humano), lleva objetos livianos en su lomo (agachándose con `HighLowStance()` para recibir maletines, bolsos o herramientas livianas de hasta 5 kg, la carga útil del D1 Edu) y respeta las rutas autorizadas mediante SLAM y LiDAR (geo-fencing por zona, igual para todos los visitantes). No está pensado para cajas de herramientas pesadas ni equipaje grande.

En la simulación se representa:

1. Asignación del acompañamiento.
2. Inicio del recorrido adaptando la postura y velocidad a la persona.
3. Desplazamiento al punto de destino por la ruta autorizada.
4. Llegada y finalización.
5. Disponibilidad para otra misión.

Si está ocupado, el sistema informa esa situación y ofrece mapa, espera o apoyo humano. No promete acompañamiento inmediato sin disponibilidad.

El robot debe respetar restricciones de ruta. Los movimientos y la interacción con personas se validarán progresivamente si se utiliza hardware real.

**Una animación del recorrido demuestra la lógica de acompañamiento; no demuestra navegación física autónoma ni seguridad de locomoción.**

**Estado actual:** el acompañamiento está representado en la simulación. Llevar objetos en el lomo y apoyar recorridos seguros con SLAM forman parte de la siguiente fase, junto con la integración con los robots físicos (ver sección 7).

---

## 6. Diferenciación, validación e impacto

Nuestros cuatro factores de diferenciación son:

- **Hospitalidad humanista y "Cero Pantallas" (HRI Multimodal):** Interacción empática mediante voz, sensores táctiles y lenguaje corporal (manos `OmniHand` y posturas adaptativas del D1), ajustando el ritmo y el tono a cada perfil según señales explícitas, sin obligar a usar pantallas y siendo siempre transparente sobre que es un robot.
- **Coordinación viva de encuentros y operación:** Invitados y externos dejan de depender de indicaciones desconectadas al notificar en tiempo real a anfitriones y responsables, mientras el personal recibe sus novedades operativas al instante.
- **Robótica colaborativa de asistencia y orientación (Hugo + Dogo):** Mientras Hugo recibe en la entrada, Dogo acompaña al ritmo humano, lleva objetos livianos de hasta 5 kg (maletines, bolsos o herramientas livianas) y respeta las rutas autorizadas de cada zona con SLAM/geo-fencing.
- **Gestión empática de la incertidumbre (Human-in-the-loop):** Con el "Protocolo de Calidez ante la Duda", el robot asume con honestidad que la duda es del sistema, sin incomodar al visitante ni inventar excusas, y escala a recepción humana cuando se requiere criterio.

Las notificaciones deben tener estados claros. “Aviso emitido” no significa “anfitrión enterado”. Si existe confirmación, se muestra como recibida o aceptada. Si simulamos la notificación, lo indicamos.

### Cómo validamos

Las pruebas cubren los cinco perfiles y los casos de excepción: desconocido, imagen ambigua, QR vencido, credencial revocada, contradicción y falta de respuesta del anfitrión o responsable.

Se registra:

- Categoría esperada y obtenida.
- Orientación esperada y ejecutada.
- Tiempo total de interacción.
- Avisos emitidos y confirmados.
- Acompañamientos completados.
- Casos que necesitaron apoyo humano.

Para comprobar la orientación, el resultado se compara con reglas y destinos definidos previamente. Para una prueba de identidad con reconocimiento real se deben usar fotografías distintas a las de referencia; en este prototipo la comparación facial está simulada.

**Resultados del prototipo:** en diez pruebas simuladas, [X] % de los casos se resolvieron correctamente, con un tiempo promedio de [Y] segundos.

### Impacto esperado

La hipótesis es reducir consultas rutinarias sobre destinos, encuentros, reservas, asignaciones y responsables.

El tiempo liberado podría dedicarse a atención especial, resolución de excepciones, coordinación de incidentes y seguimiento de solicitudes complejas.

Planteamos una **meta inicial de reducir 30 % el tiempo humano dedicado a las consultas rutinarias incluidas en el piloto**, dejándola expresamente como objetivo pendiente de validación.

Un porcentaje observado solo se presenta si existe una comparación medida, con número de pruebas y condiciones conocidas. No equivale automáticamente a una reducción del personal ni a ahorro financiero.

**Lectura económica del impacto (ver sección 8):** con datos de demostración (120 consultas rutinarias al día, 3 minutos cada una), la meta del 30 % libera unas 47 horas de recepción al mes, valoradas en ≈ USD 270, frente a un costo amortizado de Hugo y Dogo de ≈ USD 5.900 al mes. **El tiempo liberado no paga el robot**, y no lo presentamos como ahorro. El caso de negocio se defiende por experiencia del visitante, coordinación y seguridad. Como métrica de eficiencia usamos el **costo por interacción atendida (≈ USD 1,9)**.

---

## 7. Alcance del prototipo

El prototipo conecta una visita de principio a fin:

**Identificación (rostro o QR) → acreditación → categoría → acción diferenciada → orientación o acompañamiento → resultado registrado.**

| Real | Simulado | Siguiente fase |
|---|---|---|
| App funcional para N Club (credenciales QR, reservas e invitaciones) | Hugo y Dogo, con cinco flujos de atención diferenciados | Integración con los robots físicos |
| [Base de datos compartida, si funciona de verdad] | Reconocimiento facial | Dogo llevando objetos livianos de hasta 5 kg en su lomo |
| | Orientación y acompañamiento | Apoyo a recorridos seguros con SLAM, con las mismas reglas por zona para todos |

La disponibilidad de servicios, reservas, avisos y desplazamientos se simula para demostrar la integración, y su estado se indica con claridad.

**Fuera del alcance del prototipo:** afiliación completa, compra de acciones, pagos y navegación física avanzada.

---

## 8. Presupuesto e inversión

El detalle está en el anexo `Presupuesto_Hugo_y_Dogo.xlsx`. Todas las cifras se recalculan a partir de la hoja *Supuestos* (texto azul = entradas; fondo amarillo = supuestos clave). Cada concepto tiene tres escenarios: bajo, base y alto.

### Alcance del presupuesto

- **Modelo principal: N Club compra e implementa Hugo y Dogo.** El arrendamiento (Robots-as-a-Service) queda solo como alternativa a explorar.
- **Sede única de N Club.** El club no tiene sedes alternas.
- **Configuración de referencia:** 1 humanoide AgiBot X2 en recepción y 1 cuadrúpedo AgiBot D1 Edu de acompañamiento. Elegimos el D1 **Edu** porque incluye el SDK y la carga útil de 5 kg en la que se apoyan los flujos de maletines y herramientas.
- Cada concepto se clasifica como **Fijo** (no cambia con la flota) o **Por robot** (crece con cada X2 o D1 adicional).
- Todo se expresa en USD; los costos locales se ingresan en COP y se convierten con la TRM.

### Estructura: tres bloques

| Bloque | Qué incluye |
|---|---|
| **A. Prototipo (Sabana Hack)** | Robots prestados, simulador MuJoCo, créditos estudiantiles de nube, horas del equipo. Costo en caja ≈ 0, pero declaramos el valor de lo usado (≈ USD 37 mil). |
| **B. Inversión inicial (CAPEX)** | Hardware, importación, servidor edge, red y estaciones de carga, desarrollo e integración, mapeo SLAM, privacidad biométrica, capacitación, supervisión del piloto y contingencia. |
| **C. Operación anual (OPEX)** | Nube y base de datos, APIs de voz e IA, mantenimiento y repuestos, seguro, soporte de software, supervisión humana de excepciones, recapacitación y energía. |

### Cifras clave

| Cifra | Bajo | **Base** | Alto |
|---|---|---|---|
| Inversión inicial (CAPEX) | USD 70 mil | **USD 115 mil** | USD 222 mil |
| Operación anual (OPEX) | USD 13 mil | **USD 33 mil** | USD 77 mil |
| Costo mensual amortizado (36 meses) | USD 3.100 | **USD 5.900** | USD 12.600 |
| Costo total a 3 años (TCO) | USD 110 mil | **USD 213 mil** | USD 453 mil |
| Alternativa: mensualidad de arrendamiento | USD 3.700 | **USD 7.400** | USD 16.400 |
| Costo por interacción atendida | USD 1,5 | **USD 1,9** | USD 2,6 |

En pesos (escenario base, TRM 3.163,76): ≈ COP 364 millones de inversión inicial, ≈ COP 103 millones al año de operación y ≈ COP 18,7 millones al mes amortizado.

### Desglose de la inversión inicial (escenario base)

| Concepto | Tipo | USD |
|---|---|---|
| Humanoide AgiBot X2 | Por robot | 27.999 |
| Cuadrúpedo AgiBot D1 Edu | Por robot | 7.199 |
| Batería de repuesto del X2 | Por robot | 1.499 |
| Flete, seguro de transporte y aranceles (10 %) | Por robot | 3.670 |
| IVA de importación (19 %) | Por robot | 7.670 |
| Servidor edge de IA (reconocimiento facial local) | Fijo | 2.500 |
| Red WiFi, puntos de acceso y estaciones de carga | Fijo | 2.000 |
| Desarrollo e integración (4 personas × 4 meses) | Fijo | 40.458 |
| Mapeo SLAM, geo-fencing y pruebas en sitio | Fijo | 2.000 |
| Privacidad de datos biométricos (Ley 1581) | Fijo | 3.161 |
| Capacitación inicial del personal | Fijo | 1.264 |
| Supervisión humana durante el piloto (3 meses) | Fijo | 2.697 |
| Contingencia (12,5 %) | — | 12.765 |
| **Total inversión inicial** | | **≈ 114.881** |

El desarrollo es el rubro más incierto y el que más pesa después del hardware (USD 17–95 mil según escenario). Es el primer supuesto a afinar.

### Desglose de la operación anual (escenario base)

| Concepto | Tipo | USD/año |
|---|---|---|
| Nube, base de datos y almacenamiento | Fijo | 1.800 |
| APIs de voz e IA conversacional | Por robot (X2) | 1.800 |
| Mantenimiento y repuestos (12 % del hardware) | Por robot | 4.944 |
| Seguro todo riesgo (2 % del hardware) | Por robot | 824 |
| Soporte y evolución del software (0,5 persona) | Fijo | 15.172 |
| Supervisión humana de excepciones (2 h/día) | Fijo | 3.595 |
| Recapacitación anual | Fijo | 632 |
| Energía eléctrica | Por robot | 200 |
| Contingencia (12,5 %) | — | 3.621 |
| **Total operación anual** | | **≈ 32.588** |

### Escalamiento: ampliar la flota en la misma sede

Como N Club tiene una sola sede, escalar significa sumar robots según la demanda. Desarrollo, integración, privacidad y soporte se pagan una sola vez; cada robot adicional solo suma su hardware, importación, mantenimiento y seguro.

| Configuración | X2 | D1 | Inversión inicial | Operación anual | Costo mensual |
|---|---|---|---|---|---|
| Referencia: recepción + acompañamiento | 1 | 1 | USD 115 mil | USD 33 mil | USD 5.900 |
| Más acompañamientos simultáneos | 1 | 2 | USD 125 mil | USD 34 mil | USD 6.300 |
| Segundo punto de atención (acceso de personal y externos) | 2 | 2 | USD 169 mil | USD 41 mil | USD 8.100 |
| Cobertura ampliada en eventos y horas pico | 2 | 3 | USD 180 mil | USD 42 mil | USD 8.500 |

- Cada **D1 adicional** cuesta ≈ USD 10.600 de inversión y ≈ USD 1.250 al año: es la forma más barata de crecer.
- Cada **X2 adicional** cuesta ≈ USD 43.400 de inversión y ≈ USD 6.800 al año.
- Con más de dos X2 podría requerirse más capacidad en el servidor edge.

### Análisis financiero (el club como dueño)

Hoja `Analisis_Financiero` del anexo. Los costos usan el escenario base; los beneficios se plantean en tres escenarios (conservador, base y optimista) y son **hipótesis de demostración por validar en el piloto, no datos medidos de N Club**.

**Punto de partida honesto:** el valor de Hugo y Dogo no está en reemplazar tiempo de recepción. El tiempo liberado (≈ USD 270 al mes) no cubre ni la operación (≈ USD 2.700 al mes). Por eso planteamos el retorno a partir del valor que la solución debe generar, y de dónde podría venir.

**1. Retorno objetivo: valor mensual necesario para recuperar la inversión**

| Recuperar en | Valor mensual necesario |
|---|---|
| 2 años | ≈ USD 7.500 (COP 23,7 millones) |
| 3 años | ≈ USD 5.900 (COP 18,7 millones) |
| 4 años | ≈ USD 5.100 (COP 16,2 millones) |

**2. Fuentes de valor (hipótesis por validar)**

| Fuente | Supuesto base | USD/mes conservador | **Base** | Optimista |
|---|---|---|---|---|
| Reservas adicionales sugeridas por el robot (VIP y regulares) | 4 reservas/día, ticket COP 150.000, margen 35 % | 590 | **1.730** | 3.940 |
| Membresías retenidas por mejor experiencia | 2 al año, cuota COP 2 millones/mes | 470 | **1.260** | 2.370 |
| Tiempo de recepción liberado (meta 30 %) | 120 consultas/día, 3 min | 100 | **270** | 630 |
| Tiempo del personal en inicio de jornada | 40 empleados, 3 min cada uno | 110 | **260** | 500 |
| Acompañamiento de externos que asume el D1 | 6 externos/día, 15 min | 70 | **220** | 450 |
| **Total** | | **1.350** | **3.740** | **7.900** |
| Cobertura del valor necesario a 3 años | | 23 % | **63 %** | 134 % |

**3. Indicadores para el club (horizonte 3 años, tasa de descuento 12 %)**

| Indicador | Conservador | **Base** | Optimista |
|---|---|---|---|
| Flujo neto anual (valor − operación) | − USD 16.400 | **USD 12.300** | USD 62.200 |
| ROI a 3 años | −143 % | **−68 %** | 62 % |
| Valor presente neto (VPN) | − USD 154.200 | **− USD 85.300** | USD 34.400 |
| Tasa interna de retorno (TIR) | No aplica | **No aplica** | 29 % |
| Tiempo de retorno | No se recupera | **≈ 112 meses** | ≈ 22 meses |

**Lectura:** en el escenario base, Hugo y Dogo cubren su operación y deja un flujo positivo, pero tarda más que la vida útil del hardware en recuperar la inversión. Solo en el escenario optimista se recupera en menos de 2 años. El retorno depende sobre todo de las reservas adicionales y de la retención de miembros, que es justamente lo que el piloto debe medir.

**4. Punto de equilibrio**

Manteniendo las demás fuentes en su valor base, la solución se paga en 3 años si genera **≈ 9 reservas adicionales al día** (≈ 7 al día para pagarse en 4 años). Es una meta concreta y medible para el piloto.

**5. Sensibilidad: tiempo de retorno en meses**

| Costos \ Beneficios | Conservador | Base | Optimista |
|---|---|---|---|
| Costos bajos | ≈ 291 | ≈ 27 | ≈ 10 |
| Costos base | No se recupera | ≈ 112 | ≈ 22 |
| Costos altos | No se recupera | No se recupera | ≈ 150 |

Con costos bajos (X2 Neo, menos baterías, desarrollo más corto) y beneficios base, el retorno baja a ≈ 27 meses. Esto muestra que **controlar el costo de desarrollo e importación es la palanca más fuerte** junto con las reservas.

**ROIC:** no se calcula. Es una métrica de empresa (utilidad operativa sobre todo el capital invertido); para un solo proyecto equivale al ROI con otro nombre.

### Alternativa a explorar: arrendamiento (Robots-as-a-Service)

No es el modelo principal. Si el club prefiere no hacer la inversión inicial, se puede explorar con un proveedor un esquema de arrendamiento que incluya robots, software, mantenimiento y soporte, por una mensualidad estimada de ≈ USD 7.400 (costo mensual amortizado más un 25 % de margen del proveedor). Evita la inversión de entrada a cambio de un costo mensual mayor. A futuro, el mismo esquema podría ofrecerse a otros clubes como clientes nuevos.

### Supuestos principales (escenario base)

| Supuesto | Valor | Fuente |
|---|---|---|
| Precio AgiBot X2 | USD 27.999 (rango 25.600–42.999 Ultra) | AgiBot Store; GlobalDroneHQ |
| Precio AgiBot D1 Edu | USD 7.199 (rango 6.080–7.999) | AgiBot Store; GlobalDroneHQ |
| Batería de repuesto | USD 1.499 | GlobalDroneHQ |
| IVA | 19 % | Tarifa general en Colombia |
| TRM | COP 3.163,76 | TRM oficial del 21-oct-2026 (Portafolio) |
| Flete y aranceles | 10 % | Supuesto del equipo, por cotizar |
| Vida útil del hardware | 36 meses | Supuesto del equipo |
| Costo mensual por desarrollador | COP 8 millones | Supuesto del equipo |
| Costo mensual de un recepcionista | COP 3,5 millones | Supuesto del equipo |
| Mantenimiento / seguro | 12 % / 2 % del hardware al año | Supuesto del equipo |
| Contingencia | 12,5 % | Práctica usual (10–15 %) |
| Consultas rutinarias | 120 al día, 3 min cada una | Dato de demostración, no medido |
| Reservas adicionales / ticket / margen | 4 al día / COP 150.000 / 35 % | Dato de demostración, no medido |
| Membresías retenidas / cuota | 2 al año / COP 2 millones al mes | Dato de demostración, no medido |
| Tasa de descuento | 12 % anual | Supuesto del equipo |

Solo los precios de hardware, la TRM y el IVA tienen fuente pública. El resto son supuestos del equipo y se presentan con rango, no como cotizaciones.

### Fuentes

- AgiBot Store – X2: https://store.agibot.com/products/x2
- AgiBot Store – D1 Edu: https://store.agibot.com/products/d1-edu
- GlobalDroneHQ – AgiBot robot price guide 2026: https://globaldronehq.com/blogs/guides/agibot-robot-price-guide-2026
- Portafolio – Precio del dólar, 21 de octubre de 2026: https://www.portafolio.co/economia/finanzas/precio-del-dolar-hoy-en-colombia-la-divisa-inicia-cerca-de-3-160-este-21-de-octubre-504832

---

## 9. Benchmarking: alternativas que N Club podría elegir

Comparamos **alternativas reales que N Club podría elegir para resolver el mismo problema de recepción**, no marcas de robots entre sí. Cada una resuelve una parte del problema; ninguna lo resuelve completo.

### Alternativas y ejemplos reales

| Alternativa | Ejemplo real | Qué resuelve | Qué no resuelve | Costo de referencia |
|---|---|---|---|---|
| Recepcionista adicional | Personal de N Club | Criterio humano, trato cálido, casos dudosos | No escala en horas pico, no carga herramientas, sin trazabilidad automática | ≈ COP 3,5 millones/mes cargado (≈ USD 13.300/año; supuesto del modelo) |
| Sistema de gestión de visitantes | Envoy Visitors | Registro de invitados, aviso al anfitrión, credenciales impresas | Solo invitados y externos; depende de pantallas; no acompaña; verificación de documentos solo en plan Enterprise | Básico gratis (100 registros/mes); Premium USD 362/mes por sede, pago anual |
| Kiosco o tótem de autoservicio | NEC Smart Guest Check-in Kiosk (hoteles); kioscos de visitantes de HID | Registro rápido y credenciales | Pantalla obligatoria; no acompaña; no distingue las cinco categorías sin integración propia | Por cotización |
| Control de acceso facial | Sistema actual de N Club | Distingue miembro / no miembro | No confirma la categoría específica ni orienta (es el problema del reto) | Ya existe |
| Robot de recepción con pantalla | temi V3 | Saluda, responde en pantalla y guía a destinos guardados con LIDAR | Interacción centrada en pantalla de 13,3"; no declara carga útil; sin integración con datos del club | USD 4.499 (o arriendo desde USD 125/mes) |
| Robot de recepción y guía | Pudu KettyBot Pro (Welcome & Guide) | Recibe, guía a mesas, pantalla publicitaria de 18,5", bandejas de 10 kg | Pensado para restaurantes; interacción por pantalla; sin lógica de categorías | ≈ $15.900 (precio de lista en RobotShop Canadá) |
| Robot guía de gran formato | LG CLOi GuideBot (piloto en el aeropuerto DFW) | Escolta a destinos, dos pantallas de 27", reconocimiento de voz | Muy dependiente de pantallas; diseñado para aeropuertos; sin carga para el visitante | Por cotización |
| Humanoide social | SoftBank Pepper | Interacción social y conversacional | Producción suspendida en 2021 por baja demanda | Ya no se fabrica |
| Robot de seguridad | Knightscope (robot autónomo de seguridad) | Patrullaje 24/7 con mantenimiento incluido | Vigila, no recibe ni orienta; sin hospitalidad | Suscripción ≈ USD 0,75–9 por hora |
| Cuadrúpedo industrial | Boston Dynamics Spot | Locomoción robusta, hasta 14 kg de carga | Sobredimensionado y costoso para hospitalidad | ≈ USD 75 mil base (más de USD 100 mil con accesorios) |

### Comparación con los criterios del reto

| Alternativa | Confirma las 5 categorías | Coordina con anfitrión o responsable | Acompaña y carga | Sin pantallas | Costo relativo |
|---|---|---|---|---|---|
| Recepcionista adicional | Sí, con criterio | Parcial, manual | Acompaña; no escolta ni carga | Sí | Medio, recurrente |
| Gestión de visitantes (Envoy) | Solo invitados y externos | Sí, por notificación | No | No | Bajo |
| Kiosco de autoservicio | Parcial | Limitado | No | No | Bajo-medio |
| Control facial actual | No | No | No | Sí | Ya existe |
| Robot con pantalla (temi, KettyBot, CLOi) | Solo con integración propia | Limitado | Guía; carga limitada o nula para el visitante | No | Bajo-medio |
| Robot de seguridad (Knightscope, Spot) | No | No | Escolta sin hospitalidad | Sí | Alto |
| **Hugo y Dogo (X2 + D1)** | **Sí, con registros del club** | **Sí, con estados claros** | **Sí: guía, carga de 5 kg y geo-fencing** | **Sí** | **Alto** |

### Conclusiones

- **Cada alternativa resuelve una parte; ninguna conecta identificar la categoría, coordinar el encuentro y acompañar físicamente en una sola llegada.** Ese es el diferencial de Hugo y Dogo.
- **Lo honesto sobre el costo:** una combinación de temi y Envoy Premium costaría menos de USD 10 mil el primer año (USD 4.499 + USD 362 × 12), frente a USD 115 mil de Hugo y Dogo. Pero seguiría dependiendo de pantallas, no confirmaría las cinco categorías, no llevaría maletines ni herramientas livianas y no guiaría por rutas autorizadas. Hugo y Dogo son más caros porque hacen más, y por eso su retorno depende de generar valor (reservas, retención), no de ahorrar.
- **Lección de Pepper:** un robot social que solo saluda no se sostiene. Hugo y Dogo se diferencian porque cada interacción termina en una acción útil: un aviso, una reserva, un acompañamiento o una ruta segura.
- **Frente a Spot:** el D1 Edu cuesta cerca de una décima parte (USD 7.199 frente a ≈ USD 75 mil) y su carga de 5 kg basta para maletines y cajas de herramientas livianas.

### Ventajas y limitaciones

**Ventajas:**
- Atiende las cinco categorías con flujos distintos, confirmando la categoría con registros del club y no solo con el rostro.
- Coordina la visita: avisa al anfitrión o responsable con estados claros y orienta al punto de encuentro.
- Acompaña físicamente, lleva objetos livianos de hasta 5 kg y respeta rutas autorizadas por zona, sin pantallas.
- Maneja la duda con calidez y escala a recepción humana cuando se requiere criterio.

**Limitaciones:**
- Inversión alta frente a alternativas parciales (≈ USD 115 mil); el retorno depende de beneficios por validar en un piloto.
- El reconocimiento facial y el comportamiento de los robots están simulados; requieren validación con hardware real.
- Uso de datos biométricos que exige consentimiento y cumplimiento de la Ley 1581.

### Fuentes del benchmarking

- Envoy – Precios: https://envoy.com/pricing
- RobotLAB – temi: https://www.robotlab.com/store/temi-robot
- RobotShop – Pudu KettyBot Pro Welcome & Guide: https://ca.robotshop.com/products/pudu-kettybot-pro-welcome-guide-robot-white
- Future Travel Experience – LG CLOi GuideBot en DFW: https://www.futuretravelexperience.com/2022/07/dfw-airport-trials-lg-customer-service-robot/
- Fortune – SoftBank suspende Pepper: https://fortune.com/2021/06/29/softbank-shelves-pepper-robot-ai-emotions
- Knightscope – Precio de suscripción: https://knightscope.com/price
- Standard Bots – Precio de Spot: https://standardbots.com/articles/spot-robot
- NEC – Smart Guest Check-in Kiosk: https://latam.necam.com/files/ES/NEC Smart Guest Check-in Kiosk Brochure ES.pdf

---

## 10. Riesgos y mitigación

Principales riesgos identificados y cómo se mitigan:

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El retorno depende de beneficios no medidos (reservas, retención) | Alto | Piloto de 3 meses con métricas definidas antes de la inversión completa; alternativa de arrendamiento para no invertir de entrada. |
| Lo mostrado es simulado; el comportamiento en robots físicos puede diferir | Alto | Validación progresiva en hardware real, empezando por los flujos más simples. |
| Privacidad de datos biométricos (Ley 1581) | Alto | Reconocimiento facial solo con consentimiento; invitados y externos entran por QR por defecto; cualquier persona puede pedir usar solo QR; las imágenes de llegada se descartan tras la comparación. |
| Error de identificación o de categoría | Medio | La categoría se confirma con registros del club, no con la apariencia; ante duda, QR y luego escalamiento a recepción humana. |
| Límites físicos del D1: 5 kg de carga, batería, escaleras o césped | Medio | Uso solo para objetos livianos; rutas definidas por zona; si el D1 no está disponible, el humanoide lo informa y ofrece indicaciones, espera o una persona del equipo. |
| Rechazo de miembros o del personal hacia los robots | Medio | Transparencia (siempre se puede pedir una persona) y participación del personal en el diseño del piloto. |

---

## 11. Siguientes pasos

1. **Integración con los robots físicos:** llevar a Hugo y Dogo reales los flujos hoy simulados, validando primero los más simples.
2. **Piloto de tres meses en la entrada de N Club:** medir reservas sugeridas y aceptadas, tiempo de llegada por perfil, casos escalados a recepción y satisfacción de miembros, invitados y personal. Con esos datos el club decide si pasa a operación completa.
3. **Ampliar el papel de Dogo:** llevar objetos livianos en su lomo y apoyar recorridos seguros, con las mismas reglas por zona para todos los visitantes.

*En N Club, nadie llega como intruso.*
