"""Huellas faciales de las fotos que la gente sube desde la app móvil (Mi perfil → Foto para el
reconocimiento). La app solo sube la foto; este es el "backend del robot" que la convierte en huella
con el mismo modelo que reconoce en recepción (YuNet + SFace) y la guarda en Supabase.

Por cada foto pendiente: la baja del bucket privado, busca la cara (si no la ve, prueba girando la
foto, por si el celular la guardó de lado) y:
- si sirve, guarda la huella (guardar_huella → la foto queda "lista" y ya se reconoce);
- si no, la marca "sin_cara" con el motivo, y la app le pide a la persona que tome otra.

Una foto que se parece demasiado a OTRA persona ya registrada no se acepta: recepción tiene que
confirmar quién es (evita que alguien suba la cara de otro a su cuenta).

    python huellas_app.py            # procesa lo pendiente una vez
    python huellas_app.py --seguir   # sigue revisando cada 10 s (Ctrl+C para salir)

recepcion_fija.py --supabase ya hace esto solo mientras corre. Usa la clave de servicio del .env.
"""

import argparse
import json
import sys
import time

import cv2
import numpy as np

from base_real import BaseReal, ErrorBase
from caras import MODELO, ModeloFacial
from dataset import distancia
from recepcion import UMBRALES

GIROS = (None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180)
CADA = 10.0   # s entre revisiones con --seguir


def huella_de(modelo: ModeloFacial, datos: bytes):
    """(huella, None) o (None, motivo)."""
    imagen = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
    if imagen is None:
        return None, "el archivo no es una imagen"
    motivo = "no se ve ninguna cara"
    for giro in GIROS:
        c = modelo.capturar(imagen if giro is None else cv2.rotate(imagen, giro), origen="app")
        if c.valida:
            return c.embedding, None
        if giro is None:
            motivo = c.motivo     # el motivo de la foto tal como llegó es el que sirve
    return None, motivo[:1].upper() + motivo[1:]


def parecido_a_otra(huella, persona_id: str, registradas: list[dict]) -> str | None:
    """Nombre de otra persona registrada con una cara casi igual, o None."""
    umbral = UMBRALES[MODELO][0]
    for h in registradas:
        if h["persona_id"] != persona_id and distancia(np.array(json.loads(h["embedding"])), huella) < umbral:
            return h["persona"]["nombre_demo"]
    return None


def procesar(base: BaseReal, modelo: ModeloFacial, avisar=print) -> int:
    """Procesa las fotos pendientes. Devuelve cuántas quedaron listas."""
    pendientes = base.fotos_pendientes()
    if not pendientes:
        return 0
    registradas = base.huellas_registro(MODELO)
    listas = 0
    for f in pendientes:
        nombre = (f.get("persona") or {}).get("nombre_demo", "?")
        if not (f.get("persona") or {}).get("consentimiento_biometrico"):
            base.foto_sin_huella(f["id"], "Falta tu autorización para el reconocimiento facial")
            avisar(f"foto de {nombre}: sin consentimiento, no se procesa")
            continue
        try:
            huella, motivo = huella_de(modelo, base.descargar_foto(f["ruta"]))
        except ErrorBase as e:
            avisar(f"foto de {nombre}: no se pudo bajar ({e}); se reintenta luego")
            continue
        if huella is not None and (otra := parecido_a_otra(huella, f["persona_id"], registradas)):
            huella, motivo = None, "Se parece a otra persona registrada; recepción tiene que confirmarlo"
            avisar(f"foto de {nombre}: se parece a {otra}, no se acepta")
        if huella is None:
            base.foto_sin_huella(f["id"], motivo)
            avisar(f"foto de {nombre}: no sirve ({motivo})")
            continue
        base.guardar_huella(f["id"], huella, MODELO)
        registradas.append(dict(persona_id=f["persona_id"], persona={"nombre_demo": nombre},
                                embedding=json.dumps([round(float(x), 6) for x in huella])))
        listas += 1
        avisar(f"foto de {nombre}: huella lista ({MODELO})")
    return listas


def traer_de_base(base: BaseReal, datos: dict, modelo: ModeloFacial, avisar=print) -> set[str]:
    """Convierte en huella las fotos nuevas de la app y reemplaza las fotos de registro de `datos`
    por las de la base: quien se borró de la base deja de reconocerse y quien se registró desde la
    app empieza a reconocerse. Devuelve los nombres con cara. ErrorBase si la base no responde."""
    procesar(base, modelo, lambda t: avisar(f"app: {t}"))
    fotos, nombres = [], set()
    for h in base.huellas_registro(MODELO):
        p = h["persona"]
        persona = datos["personas"].setdefault(h["persona_id"], dict(id=h["persona_id"]))
        persona.update(nombre_demo=p["nombre_demo"], vinculo=p["vinculo"], estado=p["estado"],
                       consentimiento_biometrico=p["consentimiento_biometrico"])
        fotos.append(dict(id=h["id"], persona_id=h["persona_id"], uso="registro", autorizada=True,
                          modelo=MODELO, embedding=np.array(json.loads(h["embedding"]))))
        nombres.add(p["nombre_demo"])
    datos["fotografias"] = fotos
    return nombres


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Huellas de las fotos subidas desde la app móvil.")
    ap.add_argument("--seguir", action="store_true", help=f"revisa cada {CADA:.0f} s hasta Ctrl+C")
    args = ap.parse_args()
    base, modelo = BaseReal(), ModeloFacial()
    try:
        while True:
            try:
                n = procesar(base, modelo)
                if not args.seguir:
                    print(f"{n} foto(s) lista(s)." if n else "No hay fotos pendientes.")
                    return
            except ErrorBase as e:
                print(f"Supabase: {e}")
                if not args.seguir:
                    raise SystemExit(1)
            time.sleep(CADA)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
