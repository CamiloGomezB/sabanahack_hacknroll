"""Cámaras que se le pueden conectar al X2 de la simulación.

- CamaraDataset: entrega la foto de prueba del caso. El paso de foto a huella es SIMULADO.
- CamaraWebcam: la cámara del computador hace de cámara del X2, con el modelo facial REAL.
"""

import base64
import json
import time
from collections import deque

import cv2
import numpy as np

import dataset
from caras import ANCHO_WEBCAM, Captura, ModeloFacial, promedio


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
    # A 640x480 una cara a un metro mide ~55 px y no alcanza para comparar: se pide 1280x720.
    RESOLUCION = (1280, 720)
    # La huella que se entrega es el promedio de los cuadros de los últimos segundos que son de la
    # misma cara: un cuadro suelto puede salir movido, de lado o a media luz.
    JUNTAR_S = 2.0
    MISMA_CARA = 0.45   # distancia máxima a la captura actual para entrar en el promedio

    def __init__(self, indice: int = 0):
        self.modelo = ModeloFacial()
        self.cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError("No se pudo abrir la cámara del computador.")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.RESOLUCION[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.RESOLUCION[1])
        self.cuadro: np.ndarray | None = None   # lo que se muestra (en espejo)
        self.crudo: np.ndarray | None = None    # lo que se analiza (tal como lo ve la cámara)
        self.recientes: deque[tuple[float, Captura]] = deque(maxlen=12)
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
            self.crudo = cuadro
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
                c = self.huella()
                self.vivo = self.identificar(c) if c.valida else (c.motivo, False)
            # El recuadro se busca a media resolución (~10 ms en vez de ~47): es solo para dibujar.
            esc = max(1, cuadro.shape[1] // 640)
            chico = cuadro if esc == 1 else cv2.resize(cuadro, None, fx=1 / esc, fy=1 / esc,
                                                       interpolation=cv2.INTER_AREA)
            for cara in self.modelo.detectar(chico)[:1]:
                x, y, w, h = (int(v * esc) for v in cara[:4])
                x = vista.shape[1] - x - w      # la caja se dibuja sobre la vista en espejo
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

    def huella(self) -> Captura:
        """Captura del cuadro actual, promediada con las recientes que son de la misma cara."""
        c = self.modelo.capturar(self.crudo, ancho_max=ANCHO_WEBCAM)
        if not c.valida:
            return c
        ahora = time.monotonic()
        self.recientes.append((ahora, c))
        juntas = [r for t, r in self.recientes if ahora - t <= self.JUNTAR_S
                  and dataset.distancia(r.embedding, c.embedding) <= self.MISMA_CARA]
        return promedio(juntas)

    def __call__(self) -> Captura:
        if self.crudo is None:
            return Captura(None, False, "la cámara no ha entregado imagen")
        self.ultima = self.huella()
        return self.ultima

    def cerrar(self) -> None:
        self.cap.release()
        cv2.destroyAllWindows()
