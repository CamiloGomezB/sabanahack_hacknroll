"""Cómo habla el X2: adapta el mensaje a la persona y a su ánimo, sin API key.

- Reglas locales (siempre): eligen el tono, sugieren un nivel de ayuda y avisan a recepción si la
  persona parece necesitarlo. Son instantáneas y no necesitan internet.
- Ollama (opcional, `--ollama`): un modelo que corre en el computador reescribe el mensaje de las
  reglas para que suene más natural. Si no está instalado, tarda o responde algo raro, se usa el
  mensaje de las reglas.

El agente nunca decide quién entra ni a dónde va: eso ya lo resolvió registrar_llegada. Solo decide
cómo decirlo. El ánimo es una pista débil, no se guarda y el robot no lo menciona.

El trato es lo que la persona escribió en la app ("Cómo prefieres que el robot te hable"): usted o
tú, breve, nombre preferido. Solo cambia el tono, igual que el ánimo. Con el contexto de la llegada
(contexto_llegada) el X2 dice lo que sigue según el flujo de cada tipo (flujos.py): la reserva o
las dos opciones del VIP y del regular, el área, la tarea y la novedad del personal, y el aviso al
anfitrión o responsable del invitado o externo. Esas decisiones son reglas; Ollama solo redacta.
"""

import json
import re
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

from caras import Animo
import flujos
from recepcion import CATEGORIAS, Resolucion, mensaje_bienvenida

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODELO = "qwen2.5:3b"
ESPERA_OLLAMA = 4.0      # s: si el modelo tarda más, el X2 habla con el mensaje de las reglas
CONFIANZA_AVISO = 0.80   # ánimo tenso o triste con esta confianza: recepción recibe un aviso

# Si la versión de Ollama dice algo de esto y el mensaje de las reglas no, se descarta: son permisos,
# promesas o suposiciones (género, visitas anteriores) que el modelo inventó en las pruebas.
FRASES_RIESGOSAS = ["pasar", "pasa ", "pases", "entrada", "de nuevo", "otra vez", "seguro",
                    "bienvenid", "tranquil", "listo", "lista", "la acompaño", "le acompaño",
                    # el robot (sobre todo en la recepción fija) no lleva a nadie
                    "te acompaño", "te acompañaré", "lo acompaño",
                    "lo acompañaré", "te llevo", "te guío", "te guio",
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
- Si el mensaje base ofrece opciones o pide una confirmación, conserva exactamente esas opciones,
  esos lugares y esa pregunta.
- Si viene "trato", respétalo: si pide usted, trata de usted; si pide brevedad, sé breve; usa el
  nombre exactamente como aparece en el mensaje base.
- Responde solo con el mensaje, sin comillas ni explicaciones."""


@dataclass
class Trato:
    """Cómo prefiere la persona que le hable el robot, leído de su texto libre."""
    texto: str | None = None
    formal: bool = False
    breve: bool = False
    nombre: str | None = None


def leer_trato(texto: str | None) -> Trato:
    if not texto:
        return Trato()
    t = texto.lower()
    formal = bool(re.search(r"\busted\b|formal", t)) and not re.search(r"tut[eé]a|\btú\b", t)
    breve = bool(re.search(r"breve|cort[oa]s?\b|direct[oa]|prisa|r[aá]pid", t))
    m = re.search(r"(?i:ll[aá]m[ae]me)\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)", texto)
    return Trato(texto, formal, breve, m.group(1) if m else None)


# De tú a usted, en orden: primero las frases que dice el X2, después las palabras sueltas.
_A_USTED = [
    (r"¿Cómo prefieres que te ayude\?", "¿Cómo prefiere que le ayude?"),
    (r"Qué bueno verte", "Qué gusto verle"), (r"ayudarte", "ayudarle"),
    (r"Si necesitas algo, cuenta conmigo", "Si necesita algo, cuente conmigo"),
    (r"si quieres", "si quiere"), (r"Si prefieres", "Si prefiere"),
    (r"como prefieras", "como prefiera"),
    (r"No te preocupes", "No se preocupe"), (r"\bllegaste\b", "llegó"),
    (r"\bVe a\b", "Vaya a"), (r"sal a la izquierda y sigue", "salga a la izquierda y siga"),
    (r"\bMira\b", "Mire"), (r"\bPuedes\b", "Puede"), (r"\bpuedes\b", "puede"),
    (r"\bTienes\b", "Tiene"), (r"\btienes\b", "tiene"), (r"\bespera\b(?= en)", "espere"),
    (r"\bAcércate\b", "Acérquese"), (r"\bVienes\b", "Viene"), (r"\bquieres\b", "quiere"),
(r"prefieres", "prefiere"),
    (r"relajarte", "relajarse"), (r"\bMe confirmas\b", "Me confirma"),
    (r"\brecibiste\b", "recibió"), (r"\bTe\b", "Le"), (r"\bMuéstrame\b", "Muéstreme"),
    (r"\bte\b", "le"), (r"\bTu\b", "Su"), (r"\btu\b", "su"), (r"\btus\b", "sus"),
]


def ajustar(texto: str, trato: Trato | None) -> str:
    """Pasa a usted lo que dice el X2 si la persona lo pidió."""
    if not trato or not trato.formal:
        return texto
    for patron, nuevo in _A_USTED:
        texto = re.sub(patron, nuevo, texto)
    return texto


def espera_respuesta(r: Resolucion, ctx: dict | None) -> bool:
    """Invitado o externo con anfitrión o responsable: antes de orientar se espera su respuesta."""
    return bool(ctx and (ctx.get("visita") or {}).get("responsable")
                and r.categoria in ("invitado", "externo"))


def cierre(r: Resolucion) -> str:
    """Última frase: la pregunta por la ayuda, o el acompañamiento obligatorio del externo."""
    if len(r.ayuda_disponible) > 1:
        return "¿Cómo prefieres que te ayude?"
    if r.categoria == "externo":
        return "El D1 lleva tus herramientas y te acompaña hasta tu destino."
    return "El D1 te acompaña hasta tu destino."


@dataclass
class Plan:
    texto: str                     # lo que dice el X2
    ayuda_sugerida: str | None     # nivel de ayuda que el X2 ofrece primero
    aviso_recepcion: str | None    # nota para el panel de recepción
    fuente: str = "reglas"
    trato: Trato | None = None
    llamar: str | None = None      # nombre con el que el X2 le habla (el preferido, si lo dio)
    oferta: flujos.Oferta | None = None   # lo que sigue según el tipo de persona


def _saludo(ahora: datetime) -> str:
    return ("Buenos días" if ahora.hour < 12 else "Buenas tardes" if ahora.hour < 19
            else "Buenas noches")


def plan_por_reglas(r: Resolucion, animo: Animo | None, ahora: datetime,
                    ctx: dict | None = None) -> Plan:
    trato = leer_trato(ctx.get("trato") if ctx else None)
    plan = _plan_por_reglas(r, animo, ahora, ctx, trato)
    plan.texto, plan.trato = ajustar(plan.texto, trato), trato
    return plan


def _plan_por_reglas(r: Resolucion, animo: Animo | None, ahora: datetime, ctx: dict | None,
                     trato: Trato) -> Plan:
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
    nombre = trato.nombre or r.nombre
    disponibles = r.ayuda_disponible
    sugerida = None
    if r.requiere_tour or tono in ("tenso", "triste"):
        sugerida = "acompanamiento"
    elif tono == "contento":
        sugerida = "indicacion"
    if sugerida not in disponibles:
        sugerida = disponibles[0] if len(disponibles) == 1 else None

    if trato.breve:
        texto = f"{_saludo(ahora)}, {nombre} ({cat}{extra})."
    elif tono == "contento":
        texto = f"¡{_saludo(ahora)}, {nombre}! Qué bueno verte ({cat}{extra})."
    elif tono == "tenso":
        texto = f"{_saludo(ahora)}, {nombre} ({cat}{extra}). Con calma, estoy aquí para ayudarte."
    elif tono == "triste":
        texto = f"{_saludo(ahora)}, {nombre} ({cat}{extra}). Si necesitas algo, cuenta conmigo."
    else:
        texto = f"¡{_saludo(ahora)}, {nombre}! ({cat}{extra})."
    oferta = flujos.oferta(r, ctx, trato.breve)
    if oferta.texto:
        texto += " " + oferta.texto
    if r.requiere_tour:
        texto += " Es tu primera visita: si quieres, el D1 te muestra el club."
    elif sugerida == "acompanamiento" and len(disponibles) > 1:
        texto += " Si prefieres, el D1 te acompaña."
    # La pregunta por la ayuda va después: cuando responde el anfitrión, cuando eligió entre las
    # opciones o cuando confirmó la novedad. Una sola pregunta por vez.
    if not espera_respuesta(r, ctx) and not oferta.pregunta:
        texto += " " + cierre(r)
    return Plan(texto, sugerida, aviso, llamar=nombre, oferta=oferta)


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

    def planear(self, r: Resolucion, animo: Animo | None, ahora: datetime,
                ctx: dict | None = None) -> Plan:
        return plan_por_reglas(r, animo, ahora, ctx)

    def redactar(self, plan: Plan, r: Resolucion, animo: Animo | None,
                 con_decision: bool = True) -> Future | None:
        """Pide a Ollama una versión más natural del mensaje (en otro hilo, para no frenar la
        simulación). Devuelve None si Ollama no está disponible o todavía está cargando.
        con_decision=False no le manda puede_pasar: con él el modelo tiende a agregar
        "¿puedes pasar?" a un saludo que no lo decía (la recepción fija lo usa así)."""
        if not self.listo:
            return None
        datos = dict(mensaje_base=plan.texto, tono=animo.tono if animo else "neutral",
                     nombre=plan.llamar or r.nombre)
        if con_decision:
            datos["puede_pasar"] = r.habilitado
        if plan.trato and plan.trato.texto:
            datos["trato"] = plan.trato.texto
        return self._hilos.submit(self._chat, json.dumps(datos, ensure_ascii=False))

    @staticmethod
    def aceptar(plan: Plan, propuesta: str, r: Resolucion) -> Plan:
        """Usa la versión de Ollama solo si respeta lo esencial; si no, la de las reglas: conserva
        los nombres propios (persona, anfitrión, empresa), no inventa preguntas y no es larga.
        Los datos con números (horas, fechas) tienen que quedar idénticos; los nombres y lugares,
        sin importar mayúsculas ("Lobby" o "lobby"). Solo se exige lo que dice el mensaje base."""
        texto = propuesta.strip().strip('"“”').strip()
        base, nuevo = plan.texto.lower(), texto.lower()
        nombres = [n for n in (plan.llamar or r.nombre, r.responsable, r.empresa)
                   if n and r.habilitado and n.lower() in base]
        nombres += plan.oferta.claves if plan.oferta else []   # opciones y lugares del flujo
        inventa = any(f in nuevo and f not in base for f in FRASES_RIESGOSAS)
        valida = (0 < len(texto) <= 260
                  and all(n in texto if any(c.isdigit() for c in n) else n.lower() in nuevo
                          for n in nombres)
                  and texto.count("?") <= plan.texto.count("?")
                  and "\n" not in texto and not inventa
                  and not re.search(r"acompan(?!ñ)|accompan", nuevo))
        if not valida:
            return plan
        return Plan(texto, plan.ayuda_sugerida, plan.aviso_recepcion, "ollama", plan.trato,
                    plan.llamar, plan.oferta)
