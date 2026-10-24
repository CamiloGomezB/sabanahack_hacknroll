# Validación de la simulación

Generado con `python main.py --validar` (hora simulada 10:00).

**Qué es real y qué es simulado.** Simulados: los robots, las personas, el dataset y la conversión de foto a huella (reconocimiento simulado). Reales y probados: la comparación de huellas con umbrales, la consulta de acreditaciones y visitas, las decisiones, la revisión humana y las rutas; la misma lógica corre en Supabase (`registrar_llegada`) con los mismos identificadores. Por eso las métricas de categoría y orientación validan la integración, y las faciales se presentan aparte.

## Casos: esperado frente a observado

| # | Caso | Reconocimiento | Robot esperado | Robot observado | Recepción | Destino | Ayuda | Ruta | Aviso | Tiempo (s) | Llegada | OK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Miembro VIP con reserva y maleta (el D1 la lleva) | reconocida | Miembro VIP | Miembro VIP | — | sala_vip (esp. sala_vip) | indicacion (esp. indicacion) | normal | — | 8.6 | sí | ✅ |
| 2 | Miembro regular, primera visita (recorrido) | reconocida | Miembro regular | Miembro regular | — | gimnasio (esp. gimnasio) | acompanamiento (esp. acompanamiento) | normal | — | 8.0 | sí | ✅ |
| 3 | Personal en su turno: va a su área asignada | reconocida | Personal del club | Personal del club | — | piscina (esp. piscina) | mapa (esp. mapa) | normal | — | 10.2 | sí | ✅ |
| 4 | Invitada: cara desconocida, QR vigente | desconocida | Invitado | Invitado | — | restaurante (esp. restaurante) | acompanamiento (esp. acompanamiento) | normal | aceptado | 12.9 | sí | ✅ |
| 5 | Trabajador externo (acompañamiento obligatorio) | desconocida | Trabajador externo | Trabajador externo | — | mantenimiento (esp. mantenimiento) | acompanamiento (esp. acompanamiento) | normal | aceptado | 15.1 | sí | ✅ |
| 6 | Prefiere no usar la cámara: solo QR; elige el spa | no usada | Miembro regular | Miembro regular | — | piscina (esp. piscina) | indicacion (esp. indicacion) | normal | — | 12.5 | sí | ✅ |
| 7 | QR vencido | desconocida | No pasa / recepción | No pasa / recepción | — | — (esp. —) | — (esp. —) | — | — | 6.0 | — | ✅ |
| 8 | QR revocado por el anfitrión | desconocida | No pasa / recepción | No pasa / recepción | — | — (esp. —) | — (esp. —) | — | — | 6.0 | — | ✅ |
| 9 | Contradicción: la cara parece otra persona que la del QR | reconocida | Pendiente de revisión | Pendiente de revisión | Verificó documento: es Marta Ruiz, invitada de Laura | piscina (esp. piscina) | mapa (esp. mapa) | normal | aceptado | 20.0 | sí | ✅ |
| 10 | Servicio de verificación no disponible | sin verificar | Pendiente de revisión | Pendiente de revisión | Sin conexión: verificó el carné de miembro | restaurante (esp. restaurante) | indicacion (esp. indicacion) | alterna | — | 17.0 | sí | ✅ |
| 11 | Cara ambigua (entre umbrales), sin QR | ambigua | Pendiente de revisión | Pendiente de revisión | Corte de pelo nuevo: verificó documento | canchas (esp. canchas) | mapa (esp. mapa) | normal | — | 18.0 | sí | ✅ |
| 12 | Personal fuera de su turno | reconocida | No pasa / recepción | No pasa / recepción | — | — (esp. —) | — (esp. —) | — | — | 4.0 | — | ✅ |
| 13 | Cara desconocida sin credencial | desconocida | No pasa / recepción | No pasa / recepción | — | — (esp. —) | — (esp. —) | — | — | 3.0 | — | ✅ |
| 14 | Captura no válida: el robot pide el QR | captura no valida | Miembro regular | Miembro regular | — | gimnasio (esp. gimnasio) | mapa (esp. mapa) | normal | — | 13.0 | sí | ✅ |
| 15 | Dos candidatos muy parecidos: el robot pide el QR | ambigua | Miembro regular | Miembro regular | — | restaurante (esp. restaurante) | indicacion (esp. indicacion) | alterna | — | 12.0 | sí | ✅ |
| 16 | Reconocido, pero con la membresía vencida | reconocida | No pasa / recepción | No pasa / recepción | — | — (esp. —) | — (esp. —) | — | — | 4.1 | — | ✅ |
| 17 | Invitada: su anfitrión no confirma el aviso | no usada | Invitado | Invitado | — | lobby (esp. lobby) | — (esp. —) | — | sin respuesta | 14.7 | sí | ✅ |

**17 de 17 casos dieron el resultado esperado.**

## Clasificación del robot: categoría esperada (filas) frente a obtenida (columnas)

| | Miembro VIP | Miembro regular | Personal del club | Invitado | Trabajador externo | Pendiente de revisión | No pasa / recepción |
|---|---|---|---|---|---|---|---|
| **Miembro VIP** | 1 | · | · | · | · | · | · |
| **Miembro regular** | · | 4 | · | · | · | · | · |
| **Personal del club** | · | · | 1 | · | · | · | · |
| **Invitado** | · | · | · | 2 | · | · | · |
| **Trabajador externo** | · | · | · | · | 1 | · | · |
| **Pendiente de revisión** | · | · | · | · | · | 3 | · |
| **No pasa / recepción** | · | · | · | · | · | · | 5 |

## Orientación (aparte de la clasificación)

- Destino correcto: 12 de 12
- Nivel de ayuda correcto: 12 de 12
- Llegada confirmada: 12 de 12
- Casos que pasaron por recepción: 3 (todos con motivo registrado)

## Métricas de la propuesta

Tiempo de interacción: desde que la persona queda frente al X2 hasta que recibe la orientación (o pasa a recepción). Es tiempo simulado: los pasos con cámara real duran hasta 10 s cada uno y no están en esta corrida.

- Tiempo de interacción: promedio 10.9 s, máximo 20.0 s (17 casos)
- Avisos al anfitrión o responsable: 4 emitidos, 3 aceptados, 1 sin respuesta (SIMULADO: en la app los marca la persona avisada)
- Casos que necesitaron apoyo humano (recepción o espera del anfitrión): 7 de 17 (41 %)

## Reconocimiento facial (métrica aparte)

Dataset de demostración: 27 fotos de registro (9 personas con consentimiento, 3 cada una) y 28 fotos de prueba distintas, incluidas personas no registradas. El reconocimiento recibe solo la huella de la foto; la persona esperada se usa únicamente aquí, para evaluar, y el nombre del archivo no interviene.

Criterio: se acepta si la distancia coseno es ≤ 0.4 y el segundo candidato está al menos 0.05 más lejos; por encima de 0.5 es desconocida; en medio, o con dos candidatos cercanos, es ambigua y el robot pide otra validación. La distancia no es un porcentaje de certeza.

> **Importante:** las huellas de este dataset son sintéticas (modelo `simulado-v1`), así que estos números validan el flujo y los umbrales, **no la precisión de un modelo facial real**. Tampoco prueban detección de vida ni protección contra alguien que muestre una foto.

| Resultado | Fotos |
|---|---|
| acierto | 18 |
| desconocida correcta | 6 |
| falsa aceptación | 1 |
| pide otra validación | 3 |

| Foto de prueba | Persona esperada | Resultado | Distancia | 2.º candidato | Evaluación |
|---|---|---|---|---|---|
| demo/prueba/valentina_p1.jpg | Valentina Rojas | reconocida: Valentina Rojas | 0.155 | 0.933 | acierto |
| demo/prueba/valentina_p2.jpg | Valentina Rojas | reconocida: Valentina Rojas | 0.150 | 0.904 | acierto |
| demo/prueba/andres_p1.jpg | Andrés Gómez | reconocida: Andrés Gómez | 0.162 | 0.915 | acierto |
| demo/prueba/andres_p2.jpg | Andrés Gómez | reconocida: Andrés Gómez | 0.167 | 0.917 | acierto |
| demo/prueba/carlos_p1.jpg | Carlos Pérez | reconocida: Carlos Pérez | 0.150 | 0.892 | acierto |
| demo/prueba/carlos_p2.jpg | Carlos Pérez | reconocida: Carlos Pérez | 0.154 | 0.904 | acierto |
| demo/prueba/diana_p1.jpg | Diana López | reconocida: Diana López | 0.158 | 0.927 | acierto |
| demo/prueba/diana_p2.jpg | Diana López | reconocida: Diana López | 0.165 | 0.903 | acierto |
| demo/prueba/tomas_p1.jpg | Tomás Herrera | reconocida: Tomás Herrera | 0.156 | 0.950 | acierto |
| demo/prueba/tomas_p2.jpg | Tomás Herrera | reconocida: Tomás Herrera | 0.151 | 0.916 | acierto |
| demo/prueba/mateo_p1.jpg | Mateo Castro | reconocida: Mateo Castro | 0.155 | 0.877 | acierto |
| demo/prueba/mateo_p2.jpg | Mateo Castro | reconocida: Mateo Castro | 0.172 | 0.891 | acierto |
| demo/prueba/lucia_p1.jpg | Lucía Vargas | reconocida: Lucía Vargas | 0.159 | 0.891 | acierto |
| demo/prueba/lucia_p2.jpg | Lucía Vargas | reconocida: Lucía Vargas | 0.160 | 0.905 | acierto |
| demo/prueba/ricardo_p1.jpg | Ricardo Silva | reconocida: Ricardo Silva | 0.172 | 0.919 | acierto |
| demo/prueba/ricardo_p2.jpg | Ricardo Silva | reconocida: Ricardo Silva | 0.151 | 0.926 | acierto |
| demo/prueba/julian_p1.jpg | Julián Mora | reconocida: Julián Mora | 0.173 | 0.914 | acierto |
| demo/prueba/julian_p2.jpg | Julián Mora | reconocida: Julián Mora | 0.161 | 0.919 | acierto |
| demo/prueba/sofia_p1.jpg | Sofía Herrera (no registrada) | desconocida | 0.961 | 0.968 | desconocida correcta |
| demo/prueba/jorge_p1.jpg | Jorge Ramírez (no registrada) | desconocida | 0.927 | 0.949 | desconocida correcta |
| demo/prueba/pedro_p1.jpg | Pedro Castillo (no registrada) | desconocida | 0.899 | 0.928 | desconocida correcta |
| demo/prueba/ana_p1.jpg | Ana Torres (no registrada) | desconocida | 0.939 | 0.997 | desconocida correcta |
| demo/prueba/desconocido_p1.jpg | desconocido (no registrada) | desconocida | 0.858 | 0.889 | desconocida correcta |
| demo/prueba/visitante_p1.jpg | visitante (no registrada) | desconocida | 0.933 | 0.969 | desconocida correcta |
| demo/prueba/marta_p1.jpg | Marta Ruiz (no registrada) | reconocida: Valentina Rojas | 0.202 | 0.910 | falsa aceptación |
| demo/prueba/mateo_p3.jpg | Mateo Castro | ambigua: Mateo Castro | 0.467 | 0.895 | pide otra validación |
| demo/prueba/lucia_p3.jpg | Lucía Vargas | ambigua: Lucía Vargas | 0.333 | 0.380 | pide otra validación |
| demo/prueba/julian_p3.jpg | Julián Mora | captura no valida | — | — | pide otra validación |
