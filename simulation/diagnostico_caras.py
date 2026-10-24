"""Diagnóstico del reconocimiento facial con la webcam, para ver POR QUÉ no reconoce a alguien.

Abre la cámara igual que la recepción (1280x720, sin espejo para analizar) y en cada cuadro muestra:
- el tamaño de la cara y la confianza del detector (en rojo si no alcanzan el mínimo);
- las 3 personas registradas más parecidas, con su distancia (< aceptar = la reconoce);
- la huella promediada de los últimos 2 s, que es la que usa la recepción.

Cada medio segundo escribe una línea en diagnostico_caras.log para calibrar los umbrales con datos
reales de esta cámara y esta luz.

    python diagnostico_caras.py               # caras de la copia local (dataset/caras)
    python diagnostico_caras.py --supabase    # caras de la base (incluye las fotos de la app)
    python diagnostico_caras.py --camara 1

Teclas: Q o Esc para salir.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import caras
import datos_falsos
from camaras import CamaraWebcam
from caras import MODELO
from dataset import distancia
from recepcion import UMBRALES

LOG = Path(__file__).resolve().parent / "diagnostico_caras.log"
REGISTRAR_CADA = 0.5   # s entre líneas del log


def referencias(supabase: bool) -> list[tuple[str, np.ndarray]]:
    """(nombre, huella) de cada foto de registro."""
    if supabase:
        from base_real import BaseReal
        return [(h["persona"]["nombre_demo"], np.array(json.loads(h["embedding"])))
                for h in BaseReal().huellas_registro(MODELO)]
    datos = dict(personas={}, visitas={}, credenciales=[], fotografias=[], eventos=[])
    datos_falsos.agregar_caras_reales(datos, datetime.now())
    return [(datos["personas"][f["persona_id"]]["nombre_demo"], f["embedding"])
            for f in datos["fotografias"] if f.get("modelo") == MODELO and f.get("embedding") is not None]


def cercanas(refs, huella, n=3) -> list[tuple[float, str]]:
    """Las n personas más parecidas (la mejor foto de cada una)."""
    mejor: dict[str, float] = {}
    for nombre, e in refs:
        mejor[nombre] = min(mejor.get(nombre, 2.0), distancia(e, huella))
    return sorted((d, nombre) for nombre, d in mejor.items())[:n]


def texto(vista, linea, y, color=(255, 255, 255)):
    cv2.putText(vista, linea, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(vista, linea, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1, cv2.LINE_AA)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--supabase", action="store_true", help="usar las caras registradas en la base")
    ap.add_argument("--camara", type=int, default=0, help="índice de la webcam")
    args = ap.parse_args()

    refs = referencias(args.supabase)
    aceptar, ambiguo, margen = UMBRALES[MODELO]
    print(f"{len(refs)} fotos de registro: {', '.join(sorted({n for n, _ in refs}))}")
    cam = CamaraWebcam(args.camara)
    alto, ancho = cam.cap.read()[1].shape[:2]
    print(f"cámara: {ancho}x{alto} | aceptar < {aceptar} | mínimo: cara {caras.LADO_MINIMO} px, "
          f"confianza {caras.CONFIANZA_MINIMA} | log en {LOG.name}")
    VERDE, ROJO, AMARILLO = (80, 220, 80), (60, 60, 255), (0, 200, 255)
    ultimo = 0.0
    with LOG.open("a", encoding="utf-8") as log:
        log.write(f"# {datetime.now():%Y-%m-%d %H:%M:%S} cámara {ancho}x{alto}, {len(refs)} fotos\n")
        log.write("# hora lado confianza valida | 1 cuadro: nombre dist | promedio: nombre dist margen\n")
        while True:
            ok, crudo = cam.cap.read()
            if not ok:
                continue
            cam.crudo = crudo
            vista = cv2.flip(crudo, 1)
            detectadas = cam.modelo.detectar(crudo)
            if len(detectadas) == 0:
                texto(vista, "No se ve ninguna cara", 30, ROJO)
            else:
                c0 = detectadas[0]
                lado, conf = int(min(c0[2], c0[3])), float(c0[14])
                x, y, w, h = (int(v) for v in c0[:4])
                x = vista.shape[1] - x - w
                suelto = cam.modelo.capturar(crudo, ancho_max=caras.ANCHO_WEBCAM)
                prom = cam.huella()
                top1 = cercanas(refs, suelto.embedding) if suelto.valida else []
                topp = cercanas(refs, prom.embedding) if prom.valida else []
                reconocida = bool(topp) and topp[0][0] < aceptar and (
                    len(topp) < 2 or topp[1][0] - topp[0][0] >= margen)
                cv2.rectangle(vista, (x, y), (x + w, y + h), VERDE if reconocida else AMARILLO, 2)
                texto(vista, f"cara {lado}px (min {caras.LADO_MINIMO})", 30,
                      VERDE if lado >= caras.LADO_MINIMO else ROJO)
                texto(vista, f"confianza {conf:.2f} (min {caras.CONFIANZA_MINIMA})", 55,
                      VERDE if conf >= caras.CONFIANZA_MINIMA else ROJO)
                if not prom.valida:
                    texto(vista, f"no sirve: {prom.motivo}", 85, ROJO)
                for i, (d, nombre) in enumerate(topp):
                    color = VERDE if d < aceptar else (AMARILLO if d < ambiguo else (200, 200, 200))
                    texto(vista, f"{i + 1}. {nombre}: {d:.2f}", 85 + 25 * i, color)
                if topp:
                    texto(vista, "RECONOCIDA" if reconocida else "no la reconoce", 170,
                          VERDE if reconocida else AMARILLO)
                if time.monotonic() - ultimo >= REGISTRAR_CADA:
                    ultimo = time.monotonic()
                    uno = f"{top1[0][1]} {top1[0][0]:.3f}" if top1 else f"- ({suelto.motivo})"
                    pr = (f"{topp[0][1]} {topp[0][0]:.3f} "
                          f"{(topp[1][0] - topp[0][0]) if len(topp) > 1 else 1:.3f}") if topp else "-"
                    log.write(f"{datetime.now():%H:%M:%S.%f}"[:-3]
                              + f" {lado} {conf:.2f} {int(prom.valida)} | {uno} | {pr}\n")
                    log.flush()
            texto(vista, "Q: salir", vista.shape[0] - 15)
            cv2.imshow("Diagnostico de caras", cv2.resize(vista, None, fx=0.75, fy=0.75))
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q"), 27):
                break
    cam.cerrar()


if __name__ == "__main__":
    main()
