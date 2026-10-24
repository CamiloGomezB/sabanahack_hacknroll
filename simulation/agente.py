"""Cómo habla el X2: adapta el mensaje a la persona y a su ánimo, sin API key.

- Reglas locales (siempre): eligen el tono, sugieren un nivel de ayuda y avisan a recepción si la
  persona parece necesitarlo. Son instantáneas y no necesitan internet.
- Ollama (opcional, `--ollama`): un modelo que corre en el computador reescribe el mensaje de las
  reglas para que suene más natural. Si no está instalado, tarda o responde algo raro, se usa el
  mensaje de las reglas.

El agente nunca decide quién entra ni a dónde va: eso ya lo resolvió registrar_llegada. Solo decide
cómo decirlo. El ánimo es una pista débil, no se guarda y el robot no lo menciona.
"""

import json
import re
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

from caras import Animo
from recepcion import CATEGORIAS, Resolucion, mensaje_bienvenida

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODELO = "qwen2.5:3b"
ESPERA_OLLAMA = 4.0      # s: si el modelo tarda más, el X2 habla con el mensaje de las reglas
CONFIANZA_AVISO = 0.80   # ánimo tenso o triste con esta confianza: recepción recibe un aviso

# Si la versión de Ollama dice algo de esto y el mensaje de las reglas no, se descarta: son permisos,
# promesas o suposiciones (género, visitas anteriores) que el modelo inventó en las pruebas.
FRASES_RIESGOSAS = ["pasar", "pasa ", "pases", "entrada", "de nuevo", "otra vez", "seguro",
                    "bienvenid", "tranquil", "listo", "lista", "la acompaño", "le acompaño",
                    "la acompañaré", "le acompañaré"]

SISTEMA = """Eres la voz del robot recepcionista X2 del N Club, un club social en Colombia.
Reescribe el mensaje base en español, cálido y natural, en máximo 2 frases y 35 palabras.
Reglas:
- No cambies ni agregues datos: nombre, categoría, destino, horario, empresa, anfitrión y la decisión
  (si puede pasar o no) deben quedar exactamente como en el mensaje base.
- No prometas nada que no esté en el mensaje base.
- No menciones emociones ni que observaste a la persona; solo ajusta el tono que se te indica.
- Usa lenguaje neutro en género: no supongas si la persona es hombre o mujer (evita "tranquilo",
  "bienvenido", "listo" y similares).
- No agregues preguntas nuevas. Escribe con ortografía correcta en español (ñ y tildes).
- Responde solo con el mensaje, sin comillas ni explicaciones."""


@dataclass
class Plan:
    texto: str                     # lo que dice el X2
    ayuda_sugerida: str | None     # nivel de ayuda que el X2 ofrece primero
    aviso_recepcion: str | None    # nota para el panel de recepción
    fuente: str = "reglas"


def _saludo(ahora: datetime) -> str:
    return ("Buenos días" if ahora.hour < 12 else "Buenas tardes" if ahora.hour < 19
            else "Buenas noches")


def plan_por_reglas(r: Resolucion, animo: Animo | None, ahora: datetime) -> Plan:
    tono = animo.tono if animo else "neutral"
    seguro = animo is not None and animo.confianza >= CONFIANZA_AVISO
    aviso = None
    if tono in ("tenso", "triste") and seguro:
        aviso = f"parece {'tensa' if tono == 'tenso' else 'triste'}, estar pendiente"

    if not r.habilitado:
        base = (f"{PROBLEMA_QR[r.motivo]} {A_RECEPCION}" if r.motivo in PROBLEMA_QR
                else mensaje_bienvenida(r))
        if tono == "tenso":
            base = "No te preocupes. " + base
        return Plan(base, None, aviso)

    cat = CATEGORIAS.get(r.categoria, "")
    extra = (f" de {r.empresa}" if r.empresa else
             f" de {r.responsable}" if r.responsable else "")
    disponibles = r.ayuda_disponible
    sugerida = None
    if r.requiere_tour or tono in ("tenso", "triste"):
        sugerida = "acompanamiento"
    elif tono == "contento":
        sugerida = "indicacion"
    if sugerida not in disponibles:
        sugerida = disponibles[0] if len(disponibles) == 1 else None

    if tono == "contento":
        texto = f"¡{_saludo(ahora)}, {r.nombre}! Qué bueno verte ({cat}{extra})."
    elif tono == "tenso":
        texto = f"{_saludo(ahora)}, {r.nombre} ({cat}{extra}). Con calma, estoy aquí para ayudarte."
    elif tono == "triste":
        texto = f"{_saludo(ahora)}, {r.nombre} ({cat}{extra}). Si necesitas algo, cuenta conmigo."
    else:
        texto = f"¡{_saludo(ahora)}, {r.nombre}! ({cat}{extra})."
    if r.requiere_tour:
        texto += " Es tu primera visita: si quieres, el D1 te muestra el club."
    elif sugerida == "acompanamiento" and len(disponibles) > 1:
        texto += " Si prefieres, el D1 te acompaña."
    texto += (" ¿Cómo prefieres que te ayude?" if len(disponibles) > 1
              else " El D1 te acompaña hasta tu destino.")
    return Plan(texto, sugerida, aviso)


REINTENTO_QR = ("Todavía no pude leer el código. Prueba acercándolo o alejándolo un poco y mantén "
                "la pantalla quieta frente a la cámara.")
A_RECEPCION = ("Vamos a continuar con ayuda de recepción. Acércate al punto de atención que te "
               "muestro; allí podrán ayudarte con tu identificación.")
QR_DE_DEMOSTRACION = "Ese es un QR de demostración de la app; no autoriza el ingreso."
# El QR se leyó pero no sirve: acercarlo o alejarlo no ayuda, se explica y se pasa a recepción.
PROBLEMA_QR = {
    "credencial_vencida": "Tu código QR está vencido.",
    "credencial_revocada": "Tu código QR ya no es válido.",
    "credencial_no_encontrada": "No encuentro ese código QR en el sistema.",
    "credencial_aun_no_valida": "Tu código QR todavía no está vigente.",
    "contradiccion_cara_credencial": "El código QR no corresponde a la persona que veo.",
}


def pedir_qr(animo: Animo | None) -> str:
    calma = "Con calma, no pasa nada. " if animo and animo.tono == "tenso" else ""
    return calma + ("Podemos continuar con tu pase. Muéstrame el código QR frente a la cámara, "
                    "por favor.")


def a_recepcion(r: Resolucion) -> bool:
    """La persona no sigue sola: recepción humana la atiende en el punto de atención."""
    return r.resultado == "pendiente_revision" or r.motivo in PROBLEMA_QR or \
        r.motivo == "no_identificado"


class Agente:
    """Reglas siempre; Ollama si se pidió y está disponible."""

    def __init__(self, ollama_modelo: str | None = None, url: str = OLLAMA_URL):
        self.url, self.modelo, self.listo = url, None, False
        self.estado = "reglas locales"
        self._hilos = ThreadPoolExecutor(max_workers=1)
        if ollama_modelo:
            self._conectar(ollama_modelo)

    def _conectar(self, modelo: str) -> None:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=1.0) as r:
                instalados = {m["name"] for m in json.load(r)["models"]}
        except OSError:
            self.estado = "reglas locales (Ollama no está corriendo)"
            return
        if modelo not in instalados and f"{modelo}:latest" not in instalados:
            self.estado = f"reglas locales (falta el modelo: ollama pull {modelo})"
            return
        self.modelo = modelo
        self.estado = f"reglas + Ollama ({modelo}; cargando en la GPU, mientras tanto reglas)"
        self._hilos.submit(self._calentar)

    def _calentar(self) -> None:
        """La primera respuesta tarda 20-25 s mientras el modelo sube a la GPU. Hasta que termine,
        redactar() no le pide nada a Ollama (el X2 habla con las reglas) para no hacer cola."""
        try:
            self._chat(json.dumps(dict(mensaje_base="¡Hola, Ana! ¿Cómo prefieres que te ayude?",
                                       tono="neutral", nombre="Ana", puede_pasar=True)),
                       espera=120)
            self.listo = True
            self.estado = f"reglas + Ollama ({self.modelo})"
        except OSError:
            self.estado = f"reglas locales (Ollama no respondió al cargar {self.modelo})"

    def _chat(self, contenido: str, espera: float = 10) -> str:
        cuerpo = json.dumps(dict(
            model=self.modelo, stream=False, keep_alive="15m",
            options=dict(temperature=0.2, num_predict=120),
            messages=[dict(role="system", content=SISTEMA), dict(role="user", content=contenido)],
        )).encode()
        pedido = urllib.request.Request(f"{self.url}/api/chat", data=cuerpo,
                                        headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(pedido, timeout=espera) as r:
            return json.load(r)["message"]["content"].strip()

    def planear(self, r: Resolucion, animo: Animo | None, ahora: datetime) -> Plan:
        return plan_por_reglas(r, animo, ahora)

    def redactar(self, plan: Plan, r: Resolucion, animo: Animo | None) -> Future | None:
        """Pide a Ollama una versión más natural del mensaje (en otro hilo, para no frenar la
        simulación). Devuelve None si Ollama no está disponible o todavía está cargando."""
        if not self.listo:
            return None
        datos = dict(mensaje_base=plan.texto, tono=animo.tono if animo else "neutral",
                     nombre=r.nombre, puede_pasar=r.habilitado)
        return self._hilos.submit(self._chat, json.dumps(datos, ensure_ascii=False))

    @staticmethod
    def aceptar(plan: Plan, propuesta: str, r: Resolucion) -> Plan:
        """Usa la versión de Ollama solo si respeta lo esencial; si no, la de las reglas: conserva
        los nombres propios (persona, anfitrión, empresa), no inventa preguntas y no es larga."""
        texto = propuesta.strip().strip('"“”').strip()
        nombres = [n for n in (r.nombre, r.responsable, r.empresa) if n and r.habilitado]
        base, nuevo = plan.texto.lower(), texto.lower()
        inventa = any(f in nuevo and f not in base for f in FRASES_RIESGOSAS)
        valida = (0 < len(texto) <= 260
                  and all(n in texto for n in nombres)
                  and texto.count("?") <= plan.texto.count("?")
                  and "\n" not in texto and not inventa
                  and not re.search(r"acompan(?!ñ)|accompan", nuevo))
        if not valida:
            return plan
        return Plan(texto, plan.ayuda_sugerida, plan.aviso_recepcion, "ollama")
