# Sabana Hack 2026 · N Club — Recepción robótica

Reto de ANS ROBEX: un robot recibe a cada persona en la entrada de N Club, confirma a cuál de las
cinco categorías pertenece (miembro VIP, miembro regular, invitado, personal del club, trabajador
externo) y la orienta según su categoría.

## Idea general

1. El **X2 Ultra** recibe en el lobby e intenta reconocer la cara.
2. Si la cara no se reconoce, la persona muestra el **QR** de su app. Si el QR tampoco funciona,
   se pasa a la **página web** de recepción.
3. Con la persona identificada en la base de datos, el X2 la orienta señalando el mapa del lobby.
4. Si necesita acompañamiento (miembro regular nuevo, invitado o trabajador externo), el **D1** la guía.

## Estructura

| Carpeta | Contenido | Responsable |
|---|---|---|
| [`supabase/`](supabase/) | Esquema de la base de datos (migraciones SQL) | Camilo |
| [`backend/`](backend/) | Conexión a la base de datos y lógica del robot (Python) | Camilo |
| [`simulation/`](simulation/) | Simulación en MuJoCo con la misma lógica de la base de datos (datos de prueba) | Camilo |
| [`web/`](web/) | Página web de respaldo para recepción | Por importar |
| [`mobile/`](mobile/) | App móvil: registro, foto, QR e invitaciones | Por importar |
| [`docs/`](docs/) | Decisiones, supuestos y límites para la presentación | Equipo |

## Configuración

Copia `.env.example` como `.env` y llena las claves de Supabase. El archivo `.env` no se sube a git.
