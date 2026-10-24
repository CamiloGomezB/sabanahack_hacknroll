# Backend (Python)

Cliente de Supabase para el robot real.

- `db/`: cliente de Supabase y consultas a las tablas.

Hoy la lógica de recepción vive en dos lugares que dan el mismo resultado: en Supabase
(`registrar_llegada`, `contexto_llegada`, avisos; ver `../supabase/migrations/`) y en la simulación
(`../simulation/recepcion.py` y `../simulation/main.py`, que replican esas funciones sobre datos de
prueba). Cuando se conecte el X2 real, el coordinador de la simulación llamará a esas funciones con
la clave de servicio desde aquí; los robots no guardan claves.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Usa las variables de `.env` en la raíz del repositorio (ver `.env.example`). La clave de servicio
solo va en ese `.env`, nunca en la app ni en el repositorio.
