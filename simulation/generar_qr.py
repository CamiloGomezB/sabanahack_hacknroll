"""Genera los QR de la demo con la cámara: uno por persona registrada y uno por invitado sin cara.

    python generar_qr.py                                # QR del equipo (personas.json)
    python generar_qr.py --invitado "Ana Mentora"       # invitación de Camilo, sin cara registrada
    python generar_qr.py --invitado "Ana" --anfitrion felipe --destino piscina
    python generar_qr.py --subir                        # solo sube a Supabase lo ya generado
    python generar_qr.py --pases                        # rehace los pases sin cambiar los tokens

- Miembros y personal: QR personal (solo el token), sin vencimiento.
- Invitados y externos: pase de su visita, con el mismo formato que la app móvil (repo
  app_registro_nclub, "NC1." + JSON en base64url): trae el token y los datos de la visita (nombre,
  anfitrión, destino, vigencia). Ellos no se reconocen por la cara: entran siempre con este QR. El
  robot solo confía en el token; los datos los vuelve a leer de la base.

Las imágenes quedan en dataset/qr/<clave>.png (no se suben a git): se abren en el celular y se le
muestran a la cámara. Solo se guarda el hash del token, como en Supabase. Volver a correr el script
cambia los tokens: los QR anteriores dejan de servir.
"""

import argparse
import base64
import json
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np

from datos_falsos import CARAS_REALES, QR_REALES, hash_token

CARPETA = CARAS_REALES.parent.parent / "qr"
VENCE_INVITACION = "2026-10-24T22:00:00-05:00"   # fin de la hackathon


def _clave(nombre: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return "_".join(sin_tildes.lower().split())


def _legible(imagen: np.ndarray, texto: str) -> bool:
    """Lo lee el mismo lector del robot, también reducido y algo borroso (como lo ve la webcam)."""
    lector = cv2.QRCodeDetector()
    chica = cv2.GaussianBlur(cv2.resize(imagen, None, fx=0.5, fy=0.5,
                                        interpolation=cv2.INTER_AREA), (3, 3), 0)
    return all(lector.detectAndDecode(im)[0] == texto for im in (imagen, chica))


def imagen_qr(texto: str, nombre: str) -> np.ndarray:
    """QR con el nombre debajo. Prueba niveles de corrección y tamaños hasta que se pueda leer."""
    for nivel in (cv2.QRCodeEncoder_CORRECT_LEVEL_M, cv2.QRCodeEncoder_CORRECT_LEVEL_L,
                  cv2.QRCodeEncoder_CORRECT_LEVEL_Q):
        params = cv2.QRCodeEncoder.Params()
        params.correction_level = nivel
        modulos = cv2.QRCodeEncoder.create(params).encode(texto)
        for escala in (10, 12, 8):
            qr = cv2.resize(modulos, None, fx=escala, fy=escala, interpolation=cv2.INTER_NEAREST)
            qr = cv2.copyMakeBorder(qr, 60, 60, 60, 60, cv2.BORDER_CONSTANT, value=255)
            if _legible(qr, texto):
                qr = cv2.copyMakeBorder(qr, 0, 50, 0, 0, cv2.BORDER_CONSTANT, value=255)
                qr = cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)
                cv2.putText(qr, nombre, (60, qr.shape[0] - 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                            (0, 0, 0), 2, cv2.LINE_AA)
                return qr
    raise SystemExit(f"No logré un QR legible para {nombre}.")


def pase(token: str, persona: dict, invitados: list[dict], equipo: list[dict]) -> str:
    """Código de pase de la app móvil (AccessPass v1) para un invitado o externo."""
    nombres = {p["clave"]: p["nombre"] for p in equipo}
    rol = persona.get("rol", "invitado")
    datos = next((i for i in invitados if i["clave"] == persona["clave"]), {})
    anfitrion = datos.get("anfitrion") or next(p["clave"] for p in equipo
                                                if p["rol"] in ("vip", "regular"))
    externo = rol == "externo"
    desde = datetime.now(timezone.utc) - timedelta(hours=1)
    cuerpo = dict(v=1, kind="real", tipo=rol, token=token, nombre=persona["nombre"],
                  empresa="Climatizar SAS" if externo else None, anfitrion=nombres[anfitrion],
                  destino=datos.get("destino") or ("mantenimiento" if externo else "restaurante"),
                  motivo="Orden de trabajo OT-1043" if externo else None,
                  desde=desde.isoformat(timespec="seconds").replace("+00:00", "Z"),
                  hasta=datetime.fromisoformat(VENCE_INVITACION).astimezone(timezone.utc)
                  .isoformat(timespec="seconds").replace("+00:00", "Z"),
                  visitaId=None)
    cuerpo = {k: v for k, v in cuerpo.items() if v is not None}   # más corto: QR menos denso
    texto = json.dumps(cuerpo, ensure_ascii=False, separators=(",", ":")).encode()
    return "NC1." + base64.urlsafe_b64encode(texto).decode().rstrip("=")


def contenido(token: str, persona: dict, invitados: list[dict], equipo: list[dict]) -> str:
    if persona.get("rol", "invitado") in ("invitado", "externo"):
        return pase(token, persona, invitados, equipo)
    return token


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("--invitado", help="nombre de un invitado nuevo, sin cara registrada")
    args.add_argument("--anfitrion", default="camilo", help="clave del miembro que invita")
    args.add_argument("--destino", default="restaurante")
    args.add_argument("--subir", action="store_true",
                      help="no genera nada: sube a Supabase los invitados y QR ya generados")
    args.add_argument("--pases", action="store_true",
                      help="rehace los QR de invitados y externos como pase, con el mismo token")
    a = args.parse_args()
    if a.subir:
        from supabase_demo import subir_qr
        subir_qr(VENCE_INVITACION)
        return

    equipo = json.loads(CARAS_REALES.read_text(encoding="utf-8"))["personas"]
    actual = (json.loads(QR_REALES.read_text(encoding="utf-8")) if QR_REALES.exists()
              else dict(invitados=[], credenciales=[]))
    invitados = actual["invitados"]
    if a.invitado:
        if a.anfitrion not in {p["clave"] for p in equipo if p["rol"] in ("vip", "regular")}:
            raise SystemExit(f"{a.anfitrion} no es miembro VIP o regular del equipo: no puede invitar")
        clave = _clave(a.invitado)
        invitados = [i for i in invitados if i["clave"] != clave]
        invitados.append(dict(clave=clave, nombre=a.invitado, anfitrion=a.anfitrion,
                              destino=a.destino))
        quienes = [(clave, a.invitado)]          # solo cambia el QR del invitado nuevo
    else:
        quienes = [(p["clave"], p["nombre"]) for p in equipo] + \
                  [(i["clave"], i["nombre"]) for i in invitados]

    CARPETA.mkdir(parents=True, exist_ok=True)
    credenciales = {c["clave"]: c for c in actual["credenciales"]}
    personas = {p["clave"]: p for p in equipo} | {i["clave"]: i for i in invitados}
    if a.pases:
        # Lee el token del QR que ya existe (la base solo tiene su hash) y lo vuelve pase.
        lector = cv2.QRCodeDetector()
        quienes = [(c, personas[c]["nombre"]) for c in personas
                   if personas[c].get("rol", "invitado") in ("invitado", "externo")]
    for clave, nombre in quienes:
        if a.pases:
            from camaras import token_de_qr
            leido = lector.detectAndDecode(cv2.imread(str(CARPETA / f"{clave}.png")))[0]
            if not leido:
                raise SystemExit(f"No pude leer {CARPETA / f'{clave}.png'}; genera uno nuevo.")
            token = token_de_qr(leido)
        else:
            token = secrets.token_hex(32)   # mismo formato que nuevo_token() de la base y la app
        credenciales[clave] = dict(clave=clave, token_hash=hash_token(token))
        texto = contenido(token, personas[clave], invitados, equipo)
        imagen = imagen_qr(texto, _clave(nombre).replace("_", " "))
        cv2.imwrite(str(CARPETA / f"{clave}.png"), imagen)
        print(f"  QR de {nombre}{' (pase)' if texto != token else ''}: {CARPETA / f'{clave}.png'}")

    QR_REALES.write_text(json.dumps(dict(invitados=invitados,
                                         credenciales=list(credenciales.values())),
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Guardado {QR_REALES}. Para guardarlos en Supabase: python generar_qr.py --subir")


if __name__ == "__main__":
    main()
