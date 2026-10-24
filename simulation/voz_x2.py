"""Voz y caras del X2 para la recepción fija, desde el portátil.

Habla con `robot_x2/puente_voz.py` (en el robot, por el túnel de conectar_voz.ps1, puerto 8766).
Hay tres formas de que el X2 diga algo:

- "audio" (la recomendada): el portátil genera la frase en español con la voz de Windows (Helena,
  es-ES) y la manda al parlante del robot. Suena en español seguro y sale del robot.
- "x2": la voz propia del robot (PlayTts). El manual de AimDK solo promete chino e inglés, así que
  hay que probar cómo suena en español antes de usarla en la demo.
- "pc": por los parlantes del portátil (sin robot o si el robot no responde).

Con "auto" usa "audio" si el puente de voz responde y "pc" si no. Si el robot falla a mitad de la
demo, esa frase y las siguientes salen por el portátil: la recepción no se queda muda.
"""

import base64
import hashlib
import json
import socket
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

MUESTREO = 16000
PUERTO_VOZ = 8766
CACHE = Path(tempfile.gettempdir()) / "anfitrion_voz"
LETRAS_POR_SEGUNDO = 14     # para estimar cuánto dura la voz propia del robot

# SAPI (System.Speech) de Windows: la primera voz en español, a 16 kHz mono 16 bits, en un WAV.
_SAPI = r"""
param([string]$Texto, [string]$Salida)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'es*' } | Select-Object -First 1
if (-not $v) { Write-Error 'No hay voz en español instalada en Windows'; exit 2 }
$s.SelectVoice($v.VoiceInfo.Name)
$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile($Salida, $f)
$s.Speak([IO.File]::ReadAllText($Texto, [Text.Encoding]::UTF8))
$s.Dispose()
"""


class ErrorVoz(RuntimeError):
    pass


def sintetizar(texto: str) -> Path:
    """WAV de la frase en español (16 kHz mono). Las frases repetidas salen de la caché."""
    CACHE.mkdir(exist_ok=True)
    wav = CACHE / (hashlib.sha1(texto.encode()).hexdigest()[:16] + ".wav")
    if wav.exists() and wav.stat().st_size > 44:
        return wav
    script, entrada = CACHE / "sapi.ps1", CACHE / "texto.txt"
    script.write_text(_SAPI, encoding="utf-8-sig")
    entrada.write_text(texto, encoding="utf-8")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                        "-Texto", str(entrada), "-Salida", str(wav)],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not wav.exists():
        raise ErrorVoz(f"Windows no pudo generar la voz: {r.stderr.strip()[:200]}")
    return wav


def pcm_de(wav: Path) -> bytes:
    with wave.open(str(wav)) as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (MUESTREO, 1, 2):
            raise ErrorVoz("el audio no quedó en 16 kHz mono 16 bits")
        return w.readframes(w.getnframes())


class PuenteVoz:
    """Cliente del puente de voz del robot: una línea JSON por orden."""

    def __init__(self, host="127.0.0.1", puerto=PUERTO_VOZ, timeout=4.0):
        self._sock = socket.create_connection((host, puerto), timeout=timeout)
        self._archivo = self._sock.makefile("rwb")
        self._lock = threading.Lock()
        self._id = 0
        self.estado = self.orden("estado")

    def orden(self, nombre, **datos):
        with self._lock:
            self._id += 1
            self._archivo.write((json.dumps({"id": self._id, "orden": nombre, **datos}) + "\n").encode())
            self._archivo.flush()
            linea = self._archivo.readline()
        if not linea:
            raise ErrorVoz("el puente de voz cerró la conexión")
        respuesta = json.loads(linea)
        if not respuesta.get("ok"):
            raise ErrorVoz(respuesta.get("error", "error desconocido"))
        return respuesta

    def cerrar(self):
        try:
            self._sock.close()
        except OSError:
            pass


class Voz:
    """Lo que dice y muestra el X2. `decir` devuelve cuántos segundos dura la frase, para no
    hablar encima de sí mismo."""

    def __init__(self, modo="auto", host="127.0.0.1", puerto=PUERTO_VOZ, volumen=None):
        self.modo, self.puente, self.nota = modo, None, ""
        if modo != "pc":
            try:
                self.puente = PuenteVoz(host, puerto)
                robot = self.puente.estado.get("robot", "X2")
                if volumen:
                    self.puente.orden("volumen", valor=volumen)
            except (OSError, ErrorVoz) as e:
                if modo in ("x2", "audio"):
                    raise ErrorVoz(f"no responde el puente de voz en {host}:{puerto} ({e}). "
                                   "¿Está abierto conectar_voz.ps1?") from e
                self.nota = "sin robot: la voz sale por el portátil"
        if self.puente is None:
            self.modo = "pc"
            self.nota = self.nota or "por los parlantes del portátil (español de Windows)"
        elif self.modo == "auto":
            self.modo = "audio"
        if self.puente is not None:
            self.nota = (f"voz por el robot ({robot}): "
                         + ("audio en español del portátil" if self.modo == "audio"
                            else "voz propia del X2 (PlayTts)"))

    def decir(self, texto: str) -> float:
        if self.modo == "x2":
            try:
                self.puente.orden("decir", texto=texto)
                return max(1.5, len(texto) / LETRAS_POR_SEGUNDO)
            except (OSError, ErrorVoz) as e:
                self._caer(e)
        wav = sintetizar(texto)
        pcm = pcm_de(wav)
        if self.modo == "audio":
            try:
                return float(self.puente.orden("audio", pcm=base64.b64encode(pcm).decode(),
                                               muestreo=MUESTREO, canales=1)["segundos"])
            except (OSError, ErrorVoz) as e:
                self._caer(e)
        self._sonar_local(wav)
        return len(pcm) / (2 * MUESTREO)

    def _caer(self, e):
        """El robot dejó de responder: desde aquí se habla por el portátil."""
        self.nota = f"el robot no respondió ({e}); la voz sigue por el portátil"
        self.modo = "pc"
        if self.puente:
            self.puente.cerrar()
        self.puente = None

    def _sonar_local(self, wav: Path):
        import winsound
        winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)

    def cara(self, emocion: str, repetir=False) -> None:
        """Expresión de la pantalla de la cara (solo con robot; si falla, se sigue sin ella)."""
        if self.puente is None:
            return
        try:
            self.puente.orden("cara", emocion=emocion, repetir=repetir)
        except ErrorVoz as e:
            self.nota = f"la cara no cambió ({e})"
        except OSError as e:
            self._caer(e)

    def callar(self) -> None:
        if self.puente is not None:
            try:
                self.puente.orden("callar")
            except (OSError, ErrorVoz):
                pass

    def preparar(self, frases) -> None:
        """Genera de antemano las frases fijas, para que la primera respuesta no tarde."""
        if self.modo == "x2":
            return
        for f in frases:
            try:
                sintetizar(f)
            except ErrorVoz:
                return

    def cerrar(self) -> None:
        if self.puente is not None:
            self.callar()
            self.puente.cerrar()


def esperar(segundos: float) -> None:
    time.sleep(max(0.0, segundos))
