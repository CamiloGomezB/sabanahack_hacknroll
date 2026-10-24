"""Reconocimiento facial REAL con OpenCV: YuNet detecta la cara y SFace calcula la huella.

Los modelos (ONNX, de opencv_zoo) van en simulation/models/ y no se suben al repositorio:

    face_detection_yunet_2023mar.onnx
    face_recognition_sface_2021dec.onnx

SFace da 128 números; se completan con ceros hasta 512 para usar la misma columna de la base.
Los ceros no cambian la distancia coseno.

Opcional: facial_expression_recognition_mobilefacenet_2022july.onnx estima la expresión de la cara
para que el X2 adapte el tono. Es una pista débil (la expresión no es lo mismo que el ánimo): solo
se usa si la confianza es alta, nunca decide el acceso y no se guarda.
"""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

MODELOS = Path(__file__).resolve().parent / "models"
DETECTOR = MODELOS / "face_detection_yunet_2023mar.onnx"
RECONOCEDOR = MODELOS / "face_recognition_sface_2021dec.onnx"
EXPRESIONES = MODELOS / "facial_expression_recognition_mobilefacenet_2022july.onnx"
MODELO = "sface-2021dec"

# Salidas del modelo de expresiones, en orden, y el tono que le corresponde a cada una.
ETIQUETAS = ["enojo", "asco", "miedo", "alegria", "neutral", "tristeza", "sorpresa"]
TONO = dict(enojo="tenso", asco="tenso", miedo="tenso", alegria="contento", neutral="neutral",
            tristeza="triste", sorpresa="neutral")
CONFIANZA_ANIMO = 0.60   # por debajo, el tono queda neutral
DIM = 512

LADO_MINIMO = 80      # px: una cara más pequeña no sirve para comparar
CONFIANZA_MINIMA = 0.85
ANCHO_MAX = 640       # px: las imágenes más grandes se reducen antes de detectar


@dataclass
class Captura:
    """Lo que entrega la cámara del X2 al resto del sistema."""
    embedding: np.ndarray | None
    valida: bool
    motivo: str | None            # por qué no es válida
    caja: tuple[int, int, int, int] | None = None
    modo: str = "real"
    modelo: str = MODELO
    origen: str = "cámara"
    animo: "Animo | None" = None


@dataclass
class Animo:
    """Pista de tono a partir de la expresión. No se guarda en la base."""
    tono: str          # contento, neutral, tenso o triste
    expresion: str     # la expresión más probable
    confianza: float


class ModeloFacial:
    def __init__(self):
        if not (DETECTOR.exists() and RECONOCEDOR.exists()):
            raise FileNotFoundError(
                f"Faltan los modelos en {MODELOS}. Descárgalos de github.com/opencv/opencv_zoo "
                "(face_detection_yunet y face_recognition_sface).")
        self.detector = cv2.FaceDetectorYN.create(str(DETECTOR), "", (320, 320), 0.6, 0.3, 50)
        self.reconocedor = cv2.FaceRecognizerSF.create(str(RECONOCEDOR), "")
        self.expresiones = (cv2.dnn.readNet(str(EXPRESIONES)) if EXPRESIONES.exists() else None)

    def animo(self, alineada: np.ndarray) -> Animo | None:
        """Expresión de una cara ya alineada (112×112, la misma que usa SFace)."""
        if self.expresiones is None:
            return None
        x = (cv2.cvtColor(alineada, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0 - 0.5) / 0.5
        self.expresiones.setInput(cv2.dnn.blobFromImage(x))
        s = self.expresiones.forward()[0]
        p = np.exp(s - s.max())
        p /= p.sum()
        i = int(np.argmax(p))
        tono = TONO[ETIQUETAS[i]] if p[i] >= CONFIANZA_ANIMO else "neutral"
        return Animo(tono, ETIQUETAS[i], float(p[i]))

    def detectar(self, imagen: np.ndarray) -> np.ndarray:
        """Caras encontradas (una fila por cara: caja, 5 puntos y confianza), la más grande primero."""
        alto, ancho = imagen.shape[:2]
        self.detector.setInputSize((ancho, alto))
        _, caras = self.detector.detect(imagen)
        if caras is None:
            return np.zeros((0, 15))
        return caras[np.argsort(-caras[:, 2] * caras[:, 3])]

    def capturar(self, imagen: np.ndarray, origen: str = "cámara") -> Captura:
        """Huella de la cara principal, o una captura no válida con su motivo."""
        imagen = reducir(imagen)
        caras = self.detectar(imagen)
        if len(caras) == 0:
            return Captura(None, False, "no se ve ninguna cara", origen=origen)
        cara = caras[0]
        caja = tuple(int(v) for v in cara[:4])
        if cara[14] < CONFIANZA_MINIMA:
            return Captura(None, False, "cara poco clara", caja, origen=origen)
        if min(cara[2], cara[3]) < LADO_MINIMO:
            return Captura(None, False, "cara muy lejos de la cámara", caja, origen=origen)
        alineada = self.reconocedor.alignCrop(imagen, cara)
        huella = self.reconocedor.feature(alineada).flatten().astype(float)
        huella /= np.linalg.norm(huella)
        return Captura(np.pad(huella, (0, DIM - len(huella))), True, None, caja, origen=origen,
                       animo=self.animo(alineada))


def reducir(imagen: np.ndarray, ancho_max: int = ANCHO_MAX) -> np.ndarray:
    """YuNet detecta con más confianza en imágenes del tamaño de una cámara web; las fotos de
    celular (1200 px o más) se reducen antes."""
    alto, ancho = imagen.shape[:2]
    if ancho <= ancho_max:
        return imagen
    return cv2.resize(imagen, (ancho_max, round(alto * ancho_max / ancho)),
                      interpolation=cv2.INTER_AREA)


def leer_imagen(ruta: Path) -> np.ndarray:
    """cv2.imread no abre rutas con tildes en Windows; esto sí."""
    datos = np.fromfile(str(ruta), dtype=np.uint8)
    imagen = cv2.imdecode(datos, cv2.IMREAD_COLOR)
    if imagen is None:
        raise ValueError(f"No se pudo leer {ruta}")
    return imagen
