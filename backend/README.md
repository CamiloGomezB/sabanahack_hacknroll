# Backend (Python)

Conexión a Supabase y, más adelante, la lógica del robot: reconocimiento facial, validación de QR,
decisión de categoría y flujos de orientación.

- `db/`: cliente de Supabase y consultas a las tablas.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Usa las variables de `.env` en la raíz del repositorio (ver `.env.example`).
