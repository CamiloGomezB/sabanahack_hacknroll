# Presupuesto e inversión · ANFITRIÓN para N Club

El presupuesto separa el **prototipo de la hackathon** de la **operación futura** y considera
hardware, integración, infraestructura, mantenimiento, supervisión y capacitación. Usar robots
prestados durante el evento no significa que desplegarlos sea gratuito.

**Herramienta:** `Presupuesto_ANFITRION.xlsx`. Solo se edita la hoja *Supuestos* (texto azul =
entradas; fondo amarillo = supuestos a revisar); todo lo demás se recalcula. Cada concepto tiene tres
escenarios: bajo, base y alto.

## Resumen (para el formulario de entrega)

> ≈ USD 115 mil de inversión inicial + USD 33 mil/año de operación para N Club (1 AgiBot X2 + 1 AgiBot
> D1); rango USD 70–222 mil. Desglose y supuestos en el repositorio.

## Alcance

- **Sede única de N Club.** El club no tiene sedes alternas; crecer es ampliar la flota de robots.
- **Configuración de referencia:** 1 humanoide AgiBot X2 en recepción y 1 cuadrúpedo AgiBot D1 Edu de
  acompañamiento. Elegimos el D1 **Edu** porque incluye el SDK y la carga útil de 5 kg en la que se
  apoyan los flujos de maletines y herramientas.
- Cada concepto es **Fijo** (no cambia con la flota) o **Por robot** (crece con cada X2 o D1).
- Todo en USD; los costos locales se ingresan en COP y se convierten con la TRM.

## Estructura: tres bloques

| Bloque | Qué incluye |
|---|---|
| **A. Prototipo hackathon** | Robots prestados, simulador MuJoCo, créditos estudiantiles de nube, horas del equipo. Costo en caja ≈ 0, pero declaramos el valor de lo usado (≈ USD 37 mil). |
| **B. Inversión inicial (CAPEX)** | Hardware, importación, servidor edge, red y estaciones de carga, desarrollo e integración, mapeo SLAM, privacidad biométrica, capacitación, supervisión del piloto y contingencia. |
| **C. Operación anual (OPEX)** | Nube y base de datos, APIs de voz e IA, mantenimiento y repuestos, seguro, soporte de software, supervisión humana de excepciones, recapacitación y energía. |

## Cifras clave

| Cifra | Bajo | **Base** | Alto |
|---|---|---|---|
| Inversión inicial (CAPEX) | USD 70 mil | **USD 115 mil** | USD 222 mil |
| Operación anual (OPEX) | USD 13 mil | **USD 33 mil** | USD 77 mil |
| Costo mensual amortizado (36 meses) | USD 3.100 | **USD 5.900** | USD 12.600 |
| Costo total a 3 años (TCO) | USD 110 mil | **USD 213 mil** | USD 453 mil |
| Precio mensual Robots-as-a-Service | USD 3.700 | **USD 7.400** | USD 16.400 |
| Costo por interacción atendida | USD 1,5 | **USD 1,9** | USD 2,6 |

En pesos (escenario base, TRM 3.163,76): ≈ COP 364 millones de inversión inicial, ≈ COP 103 millones
al año de operación y ≈ COP 18,7 millones al mes amortizado.

## Inversión inicial (escenario base)

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

El desarrollo es el rubro más incierto y el que más pesa después del hardware (USD 17–95 mil según
escenario). Es el primer supuesto a afinar.

## Operación anual (escenario base)

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

## Escalamiento: más robots en la misma sede

Desarrollo, integración, privacidad y soporte se pagan una sola vez; cada robot adicional solo suma su
hardware, importación, mantenimiento y seguro.

| Configuración | X2 | D1 | Inversión inicial | Operación anual | Costo mensual |
|---|---|---|---|---|---|
| Referencia: recepción + acompañamiento | 1 | 1 | USD 115 mil | USD 33 mil | USD 5.900 |
| Más acompañamientos simultáneos | 1 | 2 | USD 125 mil | USD 34 mil | USD 6.300 |
| Segundo punto de atención (acceso de personal y externos) | 2 | 2 | USD 169 mil | USD 41 mil | USD 8.100 |
| Cobertura ampliada en eventos y horas pico | 2 | 3 | USD 180 mil | USD 42 mil | USD 8.500 |

- Cada **D1 adicional** cuesta ≈ USD 10.600 de inversión y ≈ USD 1.250 al año: es la forma más
  barata de crecer.
- Cada **X2 adicional** cuesta ≈ USD 43.400 de inversión y ≈ USD 6.800 al año.
- Con más de dos X2 podría requerirse más capacidad en el servidor edge.

## Modelo de negocio: Robots-as-a-Service

El club paga una mensualidad (≈ USD 7.400 en el escenario base, con un margen del 25 % sobre el costo
mensual) que incluye robots, software, mantenimiento y soporte. Evita la inversión inicial y traslada
el riesgo tecnológico al proveedor. El mismo modelo puede ofrecerse a otros clubes (fuera de este
presupuesto).

## Supuestos principales (escenario base)

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

Solo los precios de hardware, la TRM y el IVA tienen fuente pública. El resto son supuestos del equipo
y se presentan con rango, no como cotizaciones.

## Pendientes antes de entregar

- Actualizar la TRM el día de la entrega.
- Afinar el costo de desarrollo (personas, meses y tarifa): es el que más mueve el resultado.
- Si hay tiempo, conseguir una cotización de importación para reemplazar el 10 % de flete y aranceles.

## Fuentes

- AgiBot Store – X2: https://store.agibot.com/products/x2
- AgiBot Store – D1 Edu: https://store.agibot.com/products/d1-edu
- GlobalDroneHQ – AgiBot robot price guide 2026: https://globaldronehq.com/blogs/guides/agibot-robot-price-guide-2026
- Portafolio – Precio del dólar, 21 de octubre de 2026: https://www.portafolio.co/economia/finanzas/precio-del-dolar-hoy-en-colombia-la-divisa-inicia-cerca-de-3-160-este-21-de-octubre-504832
