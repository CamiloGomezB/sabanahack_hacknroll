"""Cliente de Supabase para el backend del robot y la simulación.

Usa la clave de servicio, que salta las reglas RLS: nunca debe llegar a la app ni a la web.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY. Copia .env.example como .env y llénalo."
        )
    return create_client(url, key)
