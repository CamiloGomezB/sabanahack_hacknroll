"""Los cinco flujos de atención: qué hace el X2 después de clasificar a la persona.

registrar_llegada ya decidió quién es y si puede pasar. Aquí se decide qué sigue según el tipo,
como en la tabla de flujos del equipo:

- VIP (conserjería): confirma su reserva, o le ofrece dos opciones (mesa en el comedor reservado o
  sala privada), revisa la disponibilidad, la deja reservada y ofrece indicaciones o el D1.
- Regular (aprovechar su membresía): confirma su reserva, o le propone spa o golf según su
  preferencia, con cupos y costo, y ofrece indicaciones o el D1.
- Invitado (sentirse esperado): avisa al anfitrión y confirma el punto de encuentro. Si el anfitrión
  no confirma, espera en el lobby con recepción enterada (eso lo hace main.py con el aviso).
- Personal (empezar preparado): dice el área y la tarea asignadas y la novedad relevante para su
  trabajo, le muestra la ruta de servicio y le pide confirmar que recibió la novedad.
- Externo (llegar listo para su tarea): explica la orden, las zonas autorizadas y avisa al
  responsable. Sin su confirmación la visita queda en espera.

Son reglas, no el modelo de lenguaje: las decisiones (opciones, cupos, destino, a quién avisar)
tienen que ser siempre las mismas y verificables. Ollama, si está activo, solo reescribe la frase
de bienvenida, y agente.aceptar descarta su versión si pierde alguna opción o lugar.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from club import ZONAS, nombre_destino, zona_de_destino
from recepcion import Resolucion


@dataclass(frozen=True)
class Opcion:
    clave: str      # espacio: clave de la app (ESPACIOS_APP) o zona de la maqueta
    nombre: str     # como lo dice el X2
    gusto: str      # "relajarse", "deporte", "comer" o "privado": para ordenar por preferencia
    costo: str


# Supuesto de la demo: espacios, cupos y costos del club. En Supabase está el catálogo `espacios`
# (con capacidad) y `reservas`; el spa y el golf todavía no existen allá.
OPCIONES = {
    "vip": [Opcion("comedor-reservado", "una mesa en el comedor reservado", "comer",
                   "incluido en tu membresía"),
            Opcion("salon-privado", "una sala privada", "privado", "incluido en tu membresía")],
    "regular": [Opcion("spa", "el spa", "relajarse", "$80.000 la sesión"),
                Opcion("golf", "una sesión de golf", "deporte", "$60.000 la hora")],
}
CUPOS = {"comedor-reservado": 8, "salon-privado": 10, "spa": 6, "golf": 4}
DURACION = timedelta(hours=1)

PREFERENCIAS = {
    "relajarse": r"relaj|descans|spa|masaje|tranquil",
    "deporte": r"deport|golf|ejercicio|entren|activ",
    "comer": r"comer|almorz|cenar|restaurante|mesa",
    "privado": r"privad|reuni|trabaj|sala",
}

# Zonas por donde puede andar un externo: el pasillo de servicio y la de su orden.
ZONAS_EXTERNO = "el pasillo de servicio y"


@dataclass
class Oferta:
    texto: str = ""                                     # lo que añade el X2 a la bienvenida
    opciones: list[Opcion] = field(default_factory=list)  # la persona elige una
    confirmar_novedad: str | None = None                # novedad que el personal debe confirmar
    destino: str | None = None                          # a dónde va, si el flujo ya lo sabe
    claves: list[str] = field(default_factory=list)     # lo que Ollama no puede quitar

    @property
    def pregunta(self) -> bool:
        """La bienvenida ya termina en pregunta: la de la ayuda se hace después."""
        return bool(self.opciones or self.confirmar_novedad)


def _lugar(clave: str | None) -> str:
    if not clave:
        return "recepción"
    return nombre_destino(clave) if zona_de_destino(clave) else clave


def ordenar(opciones: list[Opcion], preferencia: str | None) -> list[Opcion]:
    """Primero lo que la persona prefiere (lo que escribió en la app); si no dijo nada, igual."""
    if not preferencia:
        return list(opciones)
    t = preferencia.lower()
    return sorted(opciones, key=lambda o: not re.search(PREFERENCIAS[o.gusto], t))


def _reserva(res: dict) -> str:
    return (f"Tienes una reserva en {_lugar(res['espacio'])} de {res['inicio']:%H:%M} a "
            f"{res['fin']:%H:%M}.")


def novedad_relevante(novedades: list[dict], area: str | None) -> dict | None:
    """La del área donde trabaja hoy; si no hay, la primera (afluencia, eventos, accesos)."""
    return next((n for n in novedades if area and n.get("area") == area),
                novedades[0] if novedades else None)


def oferta(r: Resolucion, ctx: dict | None, breve: bool = False) -> Oferta:
    """Qué dice el X2 después de saludar, según el tipo de persona (contexto_llegada)."""
    if not ctx or not r.habilitado:
        return Oferta()
    v = ctx.get("visita") or {}
    reservas = ctx.get("reservas") or []

    if r.categoria in ("vip", "regular"):
        if reservas:
            res = reservas[0]
            texto = _reserva(res)
            if r.categoria == "vip" and ctx.get("equipaje"):
                texto += " El D1 lleva tu maleta."
            return Oferta(texto, destino=res["espacio"], claves=[_lugar(res["espacio"])])
        opciones = ordenar(OPCIONES[r.categoria], ctx.get("preferencia") or ctx.get("trato"))
        a, b = opciones[0].nombre, opciones[1].nombre
        if r.categoria == "vip":
            texto = ("¿Vienes con un plan o quieres que preparemos algo? " if not breve else "") + \
                f"Puedo consultar {a} o {b}."
        else:
            gustos = {"relajarse": "relajarte", "deporte": "hacer deporte"}
            texto = (f"¿Hoy prefieres {gustos[opciones[0].gusto]} o {gustos[opciones[1].gusto]}? "
                     if not breve else "") + f"Puedo consultar disponibilidad en {a} o {b}."
        if r.categoria == "vip" and ctx.get("equipaje"):
            texto = "El D1 lleva tu maleta. " + texto
        return Oferta(texto, opciones, claves=[o.nombre for o in opciones])

    if r.categoria == "personal":
        tareas = ctx.get("tareas") or []
        if not tareas:
            return Oferta("Hoy no tienes tareas asignadas en el sistema; pasa por Oficinas del "
                          "personal.", destino="oficinas", claves=["Oficinas del personal"])
        t = tareas[0]
        area = t.get("area") if zona_de_destino(t.get("area")) else None
        hora = f" a las {t['hora']:%H:%M}" if t.get("hora") else ""
        texto = (f"Hoy tu área asignada es {_lugar(area)}" if area else "Hoy") + \
            f"; tu primera tarea es {t['titulo']}{hora}."
        claves = [_lugar(area)] if area else []
        n = novedad_relevante(ctx.get("novedades") or [], area)
        if n:
            texto += f" Novedad: {n['titulo']}."
        texto += " Te muestro la ruta de servicio."
        if n:
            texto += " ¿Me confirmas que recibiste la novedad?"
        return Oferta(texto, confirmar_novedad=n["titulo"] if n else None, destino=area,
                      claves=claves)

    lugar = _lugar(v.get("punto_encuentro"))
    if r.categoria == "invitado" and v.get("responsable"):
        return Oferta(f"Avisaré a {v['responsable']} que llegaste. El encuentro registrado es en "
                      f"{lugar}.", claves=[lugar])
    if r.categoria == "externo":
        motivo = v.get("motivo") or "la orden de trabajo registrada"
        if motivo[:1].isupper() and motivo[1:2].islower():
            motivo = motivo[0].lower() + motivo[1:]
        texto = f"Vienes al {motivo[3:]}." if motivo.startswith("el ") else f"Vienes a {motivo}."
        if v.get("responsable"):
            texto += f" Avisaré a tu responsable, {v['responsable']}."
        texto += (f" El encuentro es en {lugar} y solo puedes estar en {ZONAS_EXTERNO} {lugar}.")
        return Oferta(texto, claves=[lugar])
    return Oferta()


def cupos_libres(datos: dict, clave: str, inicio: datetime) -> int:
    """Cupos del espacio en la hora que empieza en `inicio` (reservas confirmadas que se cruzan)."""
    fin = inicio + DURACION
    ocupados = sum(1 for res in datos.get("reservas", [])
                   if res["espacio"] == clave and res["estado"] == "confirmada"
                   and res["inicio"] < fin and res["fin"] > inicio)
    return CUPOS.get(clave, 0) - ocupados


def confirmar(datos: dict, r: Resolucion, elegida: Opcion, opciones: list[Opcion],
              ahora: datetime) -> tuple[str, str | None]:
    """Revisa el cupo de lo que eligió y lo deja reservado. Si no hay, ofrece la otra opción con
    cupo; si ninguna tiene, recepción le ayuda. Devuelve (lo que dice el X2, espacio o None)."""
    inicio = ahora.replace(second=0, microsecond=0)
    for k, o in enumerate([elegida] + [x for x in opciones if x != elegida]):
        libres = cupos_libres(datos, o.clave, inicio)
        if libres <= 0:
            continue
        datos.setdefault("reservas", []).append(dict(
            persona_id=r.persona_id, espacio=o.clave, inicio=inicio, fin=inicio + DURACION,
            estado="confirmada"))
        antes = (f"{elegida.nombre[0].upper()}{elegida.nombre[1:]} no tiene cupo ahora. "
                 if k else "")
        return (f"{antes}Hay disponibilidad en {o.nombre} ({libres} "
                f"{'cupo' if libres == 1 else 'cupos'}, {o.costo}). Queda a tu nombre de "
                f"{inicio:%H:%M} a {inicio + DURACION:%H:%M}.", o.clave)
    return ("En este momento no hay cupo en ninguna de las dos; recepción te ayuda a buscar otro "
            "horario.", None)


def zona(clave: str | None) -> str | None:
    """Zona de la maqueta a la que lleva un espacio del flujo."""
    return zona_de_destino(clave) or (clave if clave in ZONAS else None)
