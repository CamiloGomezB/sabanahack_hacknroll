# Sabana Hack 2026 · N Club — ANFITRIÓN

Reto de ANS ROBEX: un robot recibe a cada persona en la entrada de N Club, confirma a cuál de las
cinco categorías pertenece (miembro VIP, miembro regular, invitado, personal del club, trabajador
externo) y la orienta según su categoría.

## Idea general

1. El **X2 Ultra** recorre el lobby buscando a quién recibir; cuando alguien entra, vuelve a su
   puesto y saluda.
2. Identificación por pasos de 10 s: **cara** → **QR** de la app → segundo intento del QR →
   **recepción humana** (el punto físico de atención). Invitados y externos entran siempre con QR.
3. Con la persona identificada en la base de datos, el X2 le habla con el **trato** que ella eligió
   en la app y le dice lo que sigue:
   - VIP: su reserva (o dos opciones) y el D1 lleva su maleta.
   - Regular: la actividad del día; si es nuevo, recorrido con el D1.
   - Personal: sus tareas y las novedades del turno.
   - Invitado: avisa a su anfitrión por la app y le dice el punto de encuentro.
   - Externo: avisa a su responsable, resume la orden y el D1 lleva sus herramientas por el pasillo
     de servicio (geocerca).
4. La persona elige la ayuda: indicación, mapa (el X2 lo señala) o acompañamiento del **D1**.

## Estructura

| Carpeta | Contenido | Responsable |
|---|---|---|
| [`supabase/`](supabase/) | Base de datos: migraciones SQL, RLS y funciones (`registrar_llegada`, avisos, reservas, `contexto_llegada`) | Camilo |
| [`simulation/`](simulation/) | Simulación en MuJoCo: club con habitaciones, X2 y D1, la misma lógica de la base y vista en primera persona | Camilo |
| [`mobile/`](mobile/) | App móvil (Expo): registro, QR, invitaciones, trato y avisos de llegada | Equipo de la app |
| [`robot_x2/`](robot_x2/) | Control a distancia del X2 Ultra real con AimDK (avanzar, girar, teclado, navegación) | Camilo |
| [`backend/`](backend/) | Cliente de Supabase en Python para el robot real | Camilo |
| [`web/`](web/) | Panel web de recepción y administración (HTML, CSS y JS, sin compilar), del repo [Web_BaseDatos_Nclub](https://github.com/thaliahero/Web_BaseDatos_Nclub) | Equipo de la web |
| [`docs/`](docs/) | [Supuestos](docs/supuestos.md), [validación](docs/validacion.md) y capturas | Equipo |
| [`PRESUPUESTO.md`](PRESUPUESTO.md) | Inversión, operación y escalamiento | Equipo |

## Configuración

Copia `.env.example` como `.env` y llena las claves de Supabase. El archivo `.env` no se sube a git.
