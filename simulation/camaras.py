"""Cámaras que se le pueden conectar al X2 de la simulación.

- CamaraDataset: entrega la foto de prueba del caso. El paso de foto a huella es SIMULADO.
- CamaraWebcam: la cámara del computador hace de cámara del X2, con el modelo facial REAL.
"""

import base64
import json

import cv2
import numpy as np

import dataset
from caras import Captura, ModeloFacial


# QR de la app móvil (repo app_registro_nclub): el QR personal y el del pase de invitado o externo
# solo traen el token (64 hex). En modo demostración la app muestra un QR con este prefijo.
QR_DEMO = "NCLUB-DEMO-NO-AUTORIZA-INGRESO"


def leer_pase(texto: str) -> dict | None:
    """Datos del código de pase "NC1.…" de la app (JSON en base64url), o None si no es un pase."""
    texto = texto.strip()
    if not texto.startswith("NC1."):
        return None
    cuerpo = texto[4:].split()[0]
    try:
        pase = json.loads(base64.urlsafe_b64decode(cuerpo + "=" * (-len(cuerpo) % 4)))
    except ValueError:
        return None
    return pase if isinstance(pase, dict) and isinstance(pase.get("token"), str) else None


def token_de_qr(texto: str) -> str:
    """Token que trae el QR: el QR personal es solo el token; el pase de invitados y externos trae
    además los datos de la visita, pero de él se usa solo el token: registrar_llegada vuelve a leer
    la visita desde la base, no se confía en lo que diga el código."""
    pase = leer_pase(texto)
    return pase["token"] if pase else texto.strip()


class CamaraDataset:
    def __init__(self):
        self.foto: dataset.Foto | None = None

    def __call__(self) -> Captura:
        f = self.foto
        return Captura(dataset.huella(f), f.valida, None if f.valida else "foto movida",
                       modo="simulado", modelo=dataset.MODELO, origen=f.ruta)


class CamaraWebcam:
    """Abre la cámara, muestra lo que ve en una ventana y entrega la huella al capturar."""

    VENTANA = "Camara del X2 (real)"
    CADA = 5    # cuadros entre una identificación en vivo y la siguiente

    def __init__(self, indice: int = 0):
        self.modelo = ModeloFacial()
        self.cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError("No se pudo abrir la cámara del computador.")
        self.cuadro: np.ndarray | None = None
        self.mensaje = "Espacio: el X2 toma la foto"
        self.ultima: Captura | None = None
        # identificar(captura) -> (texto, reconocida): lo pone el coordinador para la vista en vivo.
        self.identificar = None
        self.vivo: tuple[str, bool] | None = None
        self.n = 0
        # Lectura de QR: el coordinador pone buscar_qr = True y espera a que qr tenga el token.
        self.lector_qr = cv2.QRCodeDetector()
        self.buscar_qr = False
        self.qr: str | None = None
        self.pase: dict | None = None   # datos del pase si el QR es de invitado o externo

    def actualizar(self) -> int:
        """Lee un cuadro, dibuja la cara con quién parece ser y devuelve la tecla (-1 si ninguna)."""
        ok, cuadro = self.cap.read()
        if ok:
            self.cuadro = cv2.flip(cuadro, 1)   # como un espejo
            vista = self.cuadro.copy()
            self.n += 1
            if self.buscar_qr:
                # El QR se lee del cuadro sin espejo: invertido no se puede decodificar.
                texto, puntos, _ = self.lector_qr.detectAndDecode(cuadro)
                if puntos is not None:
                    puntos = puntos.reshape(-1, 2).astype(int)
                    puntos[:, 0] = vista.shape[1] - 1 - puntos[:, 0]
                    cv2.polylines(vista, [puntos], True, (255, 200, 0), 3)
                if texto:
                    self.qr, self.pase, self.buscar_qr = token_de_qr(texto), leer_pase(texto), False
            if self.identificar and self.n % self.CADA == 0:
                c = self.modelo.capturar(self.cuadro)
                self.vivo = self.identificar(c) if c.valida else (c.motivo, False)
            for cara in self.modelo.detectar(vista)[:1]:
                x, y, w, h = (int(v) for v in cara[:4])
                color = (80, 200, 80) if self.vivo and self.vivo[1] else (0, 170, 255)
                cv2.rectangle(vista, (x, y), (x + w, y + h), color, 2)
                if self.vivo:
                    cv2.rectangle(vista, (x, y - 26), (x + max(w, 9 * len(self.vivo[0])), y),
                                  color, -1)
                    cv2.putText(vista, self.vivo[0], (x + 4, y - 8), cv2.FONT_HERSHEY_SIMPLEX,
                                0.55, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.rectangle(vista, (0, vista.shape[0] - 34), (vista.shape[1], vista.shape[0]),
                          (0, 0, 0), -1)
            cv2.putText(vista, self.mensaje[:70], (8, vista.shape[0] - 11),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow(self.VENTANA, vista)
        return cv2.waitKey(1)

    def __call__(self) -> Captura:
        if self.cuadro is None:
            return Captura(None, False, "la cámara no ha entregado imagen")
        self.ultima = self.modelo.capturar(self.cuadro)
        return self.ultima

    def cerrar(self) -> None:
        self.cap.release()
        cv2.destroyAllWindows()
