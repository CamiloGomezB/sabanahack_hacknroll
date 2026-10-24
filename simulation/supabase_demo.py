"""Sube a Supabase las caras reales registradas con registrar_caras.py.

Usa SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY del .env de la raíz. La clave de servicio salta las
reglas de acceso: solo se usa desde este computador, nunca en la app ni en la web.
"""

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import datos_falsos

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _peticion(metodo: str, ruta: str, cuerpo: bytes, tipo: str, extra: dict | None = None):
    url, clave = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not clave:
        raise SystemExit("Falta SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el .env")
    pedido = urllib.request.Request(f"{url}{ruta}", data=cuerpo, method=metodo, headers={
        "apikey": clave, "Authorization": f"Bearer {clave}", "Content-Type": tipo, **(extra or {})})
    try:
        with urllib.request.urlopen(pedido) as r:
            return r.status
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Supabase respondió {e.code} en {metodo} {ruta}: {e.read().decode()}")


def _upsert(tabla: str, filas: list[dict]) -> None:
    _peticion("POST", f"/rest/v1/{tabla}", json.dumps(filas, default=str).encode(),
              "application/json", {"Prefer": "resolution=merge-duplicates,return=minimal"})


def subir_caras(personas: list[dict], carpeta: Path) -> None:
    datos = dict(personas={}, visitas={}, fotografias=[])
    ahora = datetime.now().astimezone()
    nuevas = datos_falsos.agregar_caras_reales(datos, ahora)
    _upsert("personas", [dict(
        id=p["id"], nombre_demo=p["nombre_demo"], vinculo=p["vinculo"], estado="activa",
        requiere_tour=False, horario_inicio=p["horario_inicio"], horario_fin=p["horario_fin"],
        consentimiento_biometrico=True, consentimiento_fecha=ahora.isoformat()) for p in nuevas])
    if datos["visitas"]:
        _upsert("visitas", [{k: v[k] for k in ("id", "persona_id", "responsable_id", "categoria",
                                                "motivo", "empresa", "destino", "inicio", "fin",
                                                "estado")} for v in datos["visitas"].values()])
    archivos = {f["ruta"]: carpeta / f["archivo"] for p in personas for f in p["fotos"]}
    for ruta, archivo in archivos.items():
        _peticion("POST", f"/storage/v1/object/fotos/{ruta}", archivo.read_bytes(), "image/jpeg",
                  {"x-upsert": "true"})
        print(f"  subida {ruta}")
    _upsert("fotografias", [dict(
        id=f["id"], persona_id=f["persona_id"], ruta=f["ruta"], uso=f["uso"], autorizada=True,
        autorizacion_fecha=ahora.isoformat(), modelo=f["modelo"],
        embedding="[" + ",".join(f"{x:.6f}" for x in f["embedding"]) + "]")
        for f in datos["fotografias"]])
    print(f"Supabase: {len(nuevas)} personas, {len(datos['visitas'])} visitas, "
          f"{len(datos['fotografias'])} fotos con huella")


def subir_qr(vence: str) -> None:
    """Guarda los invitados sin cara, sus invitaciones y los QR (solo el hash). Las invitaciones y
    los QR de visita valen desde ahora hasta `vence`; los QR personales no vencen."""
    datos = dict(personas={}, visitas={}, fotografias=[], credenciales=[])
    ahora = datetime.now().astimezone()
    datos_falsos.agregar_caras_reales(datos, ahora)
    invitados = datos_falsos.agregar_qr_reales(datos, ahora)
    if invitados:
        _upsert("personas", [dict(
            id=p["id"], nombre_demo=p["nombre_demo"], vinculo="ninguno", estado="activa",
            requiere_tour=False, horario_inicio=None, horario_fin=None,
            consentimiento_biometrico=False) for p in invitados])
        ids = {p["id"] for p in invitados}
        _upsert("visitas", [dict({k: v[k] for k in ("id", "persona_id", "responsable_id",
                                                    "categoria", "motivo", "destino", "estado")},
                                 inicio=ahora.isoformat(), fin=vence)
                            for v in datos["visitas"].values() if v["persona_id"] in ids])
    _upsert("credenciales", [dict(
        id=c["id"], persona_id=c["persona_id"], visita_id=c["visita_id"], tipo=c["tipo"],
        token_hash=c["token_hash"], valido_desde=ahora.isoformat(),
        valido_hasta=vence if c["visita_id"] else None) for c in datos["credenciales"]])
    print(f"Supabase: {len(invitados)} invitados, {len(datos['credenciales'])} QR")
