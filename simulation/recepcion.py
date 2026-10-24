"""Lógica de recepción. Replica registrar_llegada / registrar_orientacion / corregir_evento de
Supabase sobre los datos de mentira, para que la simulación tome las mismas decisiones que el robot.

Se separan tres cosas: la identidad candidata (lo que dice el reconocimiento facial), la categoría
confirmada (lo que dice la acreditación vigente en la base) y los permisos de la visita (ayuda y
zonas). Reconocer una cara no prueba que la membresía esté activa.

El robot orienta con base en reglas: no crea permisos ni resuelve contradicciones por intuición.
Lo que no puede confirmar queda "pendiente de revisión" y pasa a recepción.
"""

from dataclasses import dataclass, field
import uuid
from datetime import datetime, timedelta

import numpy as np

from dataset import distancia
from datos_falsos import hash_token

UMBRAL = 0.40        # hasta aquí la cara se acepta
UMBRAL_DUDA = 0.50   # más allá de esto la cara es desconocida; entre ambos, ambigua
MARGEN = 0.05        # si los dos mejores candidatos están más cerca que esto, es ambigua

# Umbrales por modelo (distancia coseno). Solo se comparan huellas del mismo modelo.
# SFace publica similitud >= 0.363 para "misma persona" (distancia <= 0.637); aceptamos hasta 0.60
# para ser más estrictos y dejamos 0.60-0.70 como ambigua. Hay que confirmarlos con fotos reales.
UMBRALES = {
    "simulado-v1": (UMBRAL, UMBRAL_DUDA, MARGEN),
    "sface-2021dec": (0.60, 0.70, 0.05),
}

CATEGORIAS = {
    "vip": "Miembro VIP",
    "regular": "Miembro regular",
    "personal": "Personal del club",
    "invitado": "Invitado",
    "externo": "Trabajador externo",
}

AYUDAS = {"indicacion": "indicación", "mapa": "mapa", "acompanamiento": "acompañamiento del D1"}

MOTIVOS = {
    "contradiccion_cara_credencial": "la cara no coincide con el titular del QR",
    "identidad_ambigua": "la cara no permite decidir quién es",
    "captura_no_valida": "la foto no sirve para reconocer",
    "verificacion_no_disponible": "el servicio de verificación no responde",
    "credencial_vencida": "QR vencido",
    "credencial_revocada": "QR revocado",
    "credencial_no_encontrada": "QR inexistente",
    "credencial_aun_no_valida": "QR todavía no vigente",
    "no_identificado": "no se pudo identificar y no trae QR",
    "acreditacion_vencida": "su membresía o vínculo no está vigente",
    "persona_suspendida": "cuenta suspendida",
    "visita_cancelada": "visita cancelada",
    "sin_visita_activa": "no tiene una visita activa",
    "fuera_de_horario": "fuera de su horario",
}


@dataclass
class Resolucion:
    resultado: str                   # orientado | rechazado | pendiente_revision | corregido
    evidencia: dict
    motivo: str | None = None
    categoria: str | None = None
    persona_id: str | None = None
    nombre: str | None = None
    visita_id: str | None = None
    destino: str | None = None
    empresa: str | None = None
    responsable: str | None = None
    requiere_tour: bool = False
    horario: str | None = None
    correccion: str | None = None
    vinculo_hasta: object = None
    ayuda_disponible: list[str] = field(default_factory=list)

    @property
    def habilitado(self) -> bool:
        return self.resultado in ("orientado", "corregido")


def ayuda_disponible(categoria: str) -> list[str]:
    # El externo siempre va acompañado: entra a zonas restringidas.
    return ["acompanamiento"] if categoria == "externo" else ["indicacion", "mapa", "acompanamiento"]


def _en_horario(p: dict, ahora: datetime) -> bool:
    return p["horario_inicio"] <= ahora.time() < p["horario_fin"]


def _nueva_visita(datos: dict, persona: dict, categoria: str, ahora: datetime,
                  fin: datetime) -> dict:
    v = dict(id=str(uuid.uuid4()), persona_id=persona["id"],
             responsable_id=None, categoria=categoria, destino=None, empresa=None, inicio=ahora,
             fin=fin, estado="en_curso")
    datos["visitas"][v["id"]] = v
    return v


def _con_visita(r: Resolucion, datos: dict, v: dict) -> Resolucion:
    r.visita_id, r.categoria, r.destino, r.empresa = v["id"], v["categoria"], v["destino"], v["empresa"]
    if v["responsable_id"]:
        r.responsable = datos["personas"][v["responsable_id"]]["nombre_demo"]
    r.ayuda_disponible = ayuda_disponible(v["categoria"])
    return r


def _visita_activa(datos: dict, persona: dict, ahora: datetime) -> dict | None:
    return max((v for v in datos["visitas"].values()
                if v["persona_id"] == persona["id"] and v["categoria"] in ("invitado", "externo")
                and v["estado"] in ("programada", "en_curso") and v["inicio"] <= ahora <= v["fin"]),
               key=lambda v: v["inicio"], default=None)


def reconocer(datos: dict, embedding: np.ndarray | None, captura_valida: bool,
              modo: str = "simulado", modelo: str = "simulado-v1") -> dict:
    """Compara la huella de llegada solo contra las fotos de registro autorizadas, del mismo modelo,
    de personas con consentimiento. Resultado: reconocida (identidad candidata), desconocida,
    ambigua o captura_no_valida. Recibe solo la huella: no sabe quién es la persona esperada."""
    umbral, umbral_duda, margen = UMBRALES[modelo]
    vacio = dict(detalle=None, candidato=None, distancia=None, distancia_segundo=None,
                 modelo=modelo)
    if not captura_valida:
        return dict(cara="captura_no_valida", modo=modo, **vacio)
    if embedding is None:
        return dict(cara="no_usada", modo=None, **vacio)
    mejor: dict[str, float] = {}
    for f in datos["fotografias"]:
        p = datos["personas"].get(f["persona_id"])
        if (f["uso"] == "registro" and f["autorizada"] and f["embedding"] is not None
                and f["modelo"] == modelo and p and p["consentimiento_biometrico"]):
            d = distancia(f["embedding"], embedding)
            mejor[f["persona_id"]] = min(d, mejor.get(f["persona_id"], 2.0))
    orden = sorted(mejor.items(), key=lambda x: x[1])
    cand, dist = orden[0] if orden else (None, None)
    dist2 = orden[1][1] if len(orden) > 1 else None
    detalle = None
    if dist is None or dist > umbral_duda:
        cara, cand = "desconocida", None
    elif dist2 is not None and dist2 - dist < margen:
        cara, detalle = "ambigua", "candidatos_cercanos"
    elif dist > umbral:
        cara, detalle = "ambigua", "entre_umbrales"
    else:
        cara = "reconocida"
    return dict(cara=cara, detalle=detalle, candidato=cand, distancia=dist,
                distancia_segundo=dist2, modo=modo, modelo=modelo)


def registrar_llegada(datos: dict, embedding: np.ndarray | None, token: str | None,
                      ahora: datetime, captura_valida: bool = True, servicio: bool = True,
                      modo: str = "simulado", modelo: str = "simulado-v1") -> Resolucion:
    """Misma decisión que public.registrar_llegada en Supabase."""
    personas = datos["personas"]

    # 1. Reconocimiento facial.
    rec = reconocer(datos, embedding, captura_valida, modo, modelo)
    estado_cara = rec["cara"]
    cand = personas[rec["candidato"]] if rec["candidato"] else None
    evidencia = {k: rec[k] for k in ("cara", "detalle", "distancia", "distancia_segundo", "modo",
                                     "modelo")}
    evidencia["candidato"] = cand["nombre_demo"] if cand else None
    evidencia["qr"] = "no_presentado"

    if not servicio:
        # Sin conexión con la base el robot no decide: queda pendiente y recepción verifica.
        # Las huellas también están en la base, así que la cara tampoco se puede comparar.
        evidencia.update(cara="sin_verificar", detalle=None, distancia=None, candidato=None,
                         distancia_segundo=None, qr="sin_verificar" if token else "no_presentado")
        return _registrar(datos, Resolucion("pendiente_revision", evidencia,
                                            "verificacion_no_disponible"), ahora)

    # 2. Credencial.
    cred = None
    if token is not None:
        cred = next((c for c in datos["credenciales"] if c["token_hash"] == hash_token(token)), None)
        if cred is None:
            evidencia["qr"] = "no_encontrada"
        elif cred["revocada_en"] is not None:
            evidencia["qr"] = "revocada"
        elif ahora < cred["valido_desde"]:
            evidencia["qr"] = "aun_no_valida"
        elif cred["valido_hasta"] is not None and ahora > cred["valido_hasta"]:
            evidencia["qr"] = "vencida"
        else:
            evidencia["qr"] = "valida"
    qr = evidencia["qr"]

    # 3. Decisión.
    persona = None
    if qr == "valida" and estado_cara == "reconocida" and cand["id"] != cred["persona_id"]:
        r = Resolucion("pendiente_revision", evidencia, "contradiccion_cara_credencial")
    elif qr in ("no_encontrada", "revocada", "aun_no_valida", "vencida"):
        r = Resolucion("rechazado", evidencia, f"credencial_{qr}")
    elif qr == "valida":
        persona = personas[cred["persona_id"]]
        r = Resolucion("orientado", evidencia)
    elif estado_cara == "reconocida":
        persona = cand
        r = Resolucion("orientado", evidencia)
    elif estado_cara == "ambigua":
        r = Resolucion("pendiente_revision", evidencia, "identidad_ambigua")
    elif estado_cara == "captura_no_valida":
        r = Resolucion("pendiente_revision", evidencia, "captura_no_valida")
    else:
        r = Resolucion("rechazado", evidencia, "no_identificado")

    if persona is not None:
        r.persona_id = persona["id"]
        if persona["estado"] != "activa":
            r.resultado, r.motivo = "rechazado", "persona_suspendida"

    # 4. Visita activa.
    if r.resultado == "orientado":
        if cred is not None and cred["tipo"] == "qr_visita":
            v = datos["visitas"][cred["visita_id"]]
            if v["estado"] == "cancelada":
                r.resultado, r.motivo = "rechazado", "visita_cancelada"
            else:
                v["estado"] = "en_curso"
                _con_visita(r, datos, v)
        elif (v := _visita_activa(datos, persona, ahora)) is not None:
            # Invitado o externo reconocido por cara: entra con su invitación u orden de trabajo.
            v["estado"] = "en_curso"
            _con_visita(r, datos, v)
        elif persona["vinculo"] == "ninguno":
            r.resultado, r.motivo = "rechazado", "sin_visita_activa"
        elif persona["vinculo_hasta"] is not None and persona["vinculo_hasta"] < ahora.date():
            r.resultado, r.motivo = "rechazado", "acreditacion_vencida"
            r.categoria = persona["vinculo"]
        elif not _en_horario(persona, ahora):
            r.resultado, r.motivo, r.categoria = "rechazado", "fuera_de_horario", persona["vinculo"]
            r.horario = f"{persona['horario_inicio']:%H:%M}-{persona['horario_fin']:%H:%M}"
        else:
            fin = datetime.combine(ahora.date(), persona["horario_fin"])
            _con_visita(r, datos, _nueva_visita(datos, persona, persona["vinculo"], ahora, fin))

    if persona is not None:
        r.vinculo_hasta = persona["vinculo_hasta"]
    if r.habilitado:
        r.nombre = persona["nombre_demo"]
        r.requiere_tour = persona["requiere_tour"]
    return _registrar(datos, r, ahora)


def _registrar(datos: dict, r: Resolucion, ahora: datetime) -> Resolucion:
    datos["eventos"].append(dict(creado_en=ahora, resultado=r.resultado, motivo=r.motivo,
                                 categoria=r.categoria, evidencia=dict(r.evidencia)))
    return r


def corregir(datos: dict, r: Resolucion, persona_id: str, categoria: str, motivo: str,
             ahora: datetime) -> Resolucion:
    """Recepción confirma quién es y deja motivo (corregir_evento en Supabase)."""
    persona = datos["personas"][persona_id]
    v = next((v for v in datos["visitas"].values()
              if v["persona_id"] == persona_id and v["estado"] in ("programada", "en_curso")
              and v["inicio"] <= ahora <= v["fin"]), None)
    if v is None:
        v = _nueva_visita(datos, persona, categoria, ahora, ahora + timedelta(hours=4))
    r.resultado, r.correccion, r.persona_id = "corregido", motivo, persona_id
    r.nombre, r.requiere_tour = persona["nombre_demo"], persona["requiere_tour"]
    _con_visita(r, datos, v)
    r.categoria = categoria
    datos["eventos"][-1].update(resultado="corregido", categoria=categoria,
                                correccion_motivo=motivo)
    return r


def elegir_ayuda(r: Resolucion, preferida: str) -> tuple[str, str | None]:
    """La persona decide cuánta ayuda necesita, dentro de lo que su visita permite."""
    if preferida in r.ayuda_disponible:
        return preferida, None
    nivel = r.ayuda_disponible[0]
    return nivel, f"para {CATEGORIAS[r.categoria].lower()} la ayuda es {AYUDAS[nivel]}"


def mensaje_bienvenida(r: Resolucion) -> str:
    cat = CATEGORIAS.get(r.categoria, "")
    if not r.habilitado:
        if r.resultado == "pendiente_revision":
            return "Necesito que recepción confirme tu identidad. Te acompaño al mostrador."
        if r.motivo == "fuera_de_horario":
            return f"Tu horario es {r.horario}; ahora no puedo dejarte pasar."
        if r.motivo == "no_identificado":
            return ("No pude identificarte; eso no significa que no seas miembro. "
                    "Muestra tu QR o recepción te ayuda.")
        if r.motivo == "acreditacion_vencida":
            return (f"Te reconozco, pero tu membresía venció el {r.vinculo_hasta:%d/%m}. "
                    "Recepción te ayuda a renovarla.")
        return f"No puedo dejarte pasar: {MOTIVOS[r.motivo]}. Recepción te puede ayudar."
    extra = f", {r.empresa}" if r.empresa else (f", invitado por {r.responsable}"
                                                 if r.responsable else "")
    return f"¡Hola, {r.nombre}! ({cat}{extra}). ¿Cómo prefieres que te ayude?"
