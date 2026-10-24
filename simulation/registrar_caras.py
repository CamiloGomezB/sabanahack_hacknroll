"""Registra las caras reales del equipo para el modo cámara.

1. Pon las fotos en simulation/dataset/caras/ (esa carpeta no se sube a git).
2. Escribe simulation/dataset/caras/roles.json, una entrada por persona:

    [{"clave": "camilo", "nombre": "Camilo", "rol": "vip", "fotos": ["camilo1.jpg", "camilo2.jpg"]}]

   rol: vip, regular, personal, invitado o externo. Solo personas que aceptaron el uso de su cara.
3. python registrar_caras.py

Calcula la huella de cada foto con el modelo real (SFace) y la guarda en personas.json. Si una foto
no sirve (sin cara, varias caras, muy pequeña) lo dice y no la usa. Con --supabase, y la clave de
servicio en .env, además sube las fotos al bucket privado y guarda personas, visitas y huellas.
"""

import argparse
import json
from pathlib import Path

from caras import MODELO, ModeloFacial, leer_imagen, reducir
from datos_falsos import CARAS_REALES

CARPETA = CARAS_REALES.parent
# Campos opcionales de roles.json que pasan tal cual a personas.json: anfitrion (clave del miembro
# que invita a un invitado), responsable (clave de quien recibe a un externo), trato y
# punto_encuentro. Sin anfitrion o responsable se usa el primer miembro o persona del personal.
OPCIONALES = ("anfitrion", "responsable", "trato", "punto_encuentro")


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("--supabase", action="store_true", help="subir también a Supabase")
    args.add_argument("--solo", help="con --supabase: claves a subir, separadas por coma (p. ej. "
                                     "las personas nuevas); las demás no se tocan")
    a = args.parse_args()

    roles = json.loads((CARPETA / "roles.json").read_text(encoding="utf-8"))
    modelo = ModeloFacial()
    personas = []
    for r in roles:
        fotos = []
        for archivo in r["fotos"]:
            ruta = CARPETA / archivo
            imagen = leer_imagen(ruta)
            caras = [c for c in modelo.detectar(reducir(imagen)) if c[14] >= 0.85]
            captura = modelo.capturar(imagen, origen=archivo)
            if not captura.valida:
                print(f"  ✗ {archivo}: {captura.motivo}; no se usa")
                continue
            aviso = f" (hay {len(caras)} caras; se usa la más grande)" if len(caras) > 1 else ""
            print(f"  ✓ {archivo}{aviso}")
            fotos.append(dict(archivo=archivo, ruta=f"equipo/{r['clave']}/{archivo}",
                              embedding=[round(float(x), 6) for x in captura.embedding]))
        if not fotos:
            print(f"✗ {r['nombre']}: ninguna foto sirve; no queda registrada")
            continue
        print(f"✓ {r['nombre']} → {r['rol']} ({len(fotos)} foto(s))")
        extra = {k: r[k] for k in OPCIONALES if r.get(k)}
        personas.append(dict(clave=r["clave"], nombre=r["nombre"], rol=r["rol"], **extra,
                             fotos=fotos))

    CARAS_REALES.write_text(json.dumps(dict(modelo=MODELO, personas=personas), ensure_ascii=False),
                            encoding="utf-8")
    print(f"\nGuardado {CARAS_REALES} ({len(personas)} personas)")
    if a.supabase:
        from generar_qr import VENCE_INVITACION
        from supabase_demo import subir_caras
        solo = {c.strip() for c in a.solo.split(",")} if a.solo else None
        subir_caras(personas, CARPETA, solo, VENCE_INVITACION)


if __name__ == "__main__":
    main()
