"""Datos de mentira con la misma forma de las tablas de Supabase: personas (con su trato),
fotografías, credenciales, visitas (con su punto de encuentro), reservas, tareas del personal,
novedades y avisos. Los casos de validación están en CASOS, cada uno con su resultado esperado.

Los identificadores son UUID fijos (uuid5), los mismos que usa la semilla de Supabase
(`semilla_supabase.py`), para que la simulación y la base hablen de las mismas personas y visitas.

Las ventanas de las visitas se arman relativas a la hora simulada, para que siempre haya
invitaciones vigentes, vencidas y revocadas.
"""

import hashlib
import json
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path

import numpy as np

import dataset

_NS = uuid.UUID("6f1c2a52-3b0e-4d1a-9a57-0c1ab5e7d201")


def pid(clave: str) -> str:
    return str(uuid.uuid5(_NS, f"persona:{clave}"))


def vid(clave: str) -> str:
    return str(uuid.uuid5(_NS, f"visita:{clave}"))


def fid(clave: str) -> str:
    return str(uuid.uuid5(_NS, f"foto:{clave}"))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _persona(clave, nombre, vinculo, inicio=None, fin=None, tour=False, hasta=None, trato=None):
    return dict(id=pid(clave), clave=clave, nombre_demo=nombre, vinculo=vinculo, estado="activa",
                requiere_tour=tour, horario_inicio=inicio, horario_fin=fin, vinculo_hasta=hasta,
                consentimiento_biometrico=clave in dataset.CON_BIOMETRIA, trato=trato)


def _a_la_hora(ahora: datetime, hh: int, mm: int = 0) -> datetime:
    return ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)


def agenda(datos: dict, ahora: datetime) -> None:
    """Lo que consulta contexto_llegada: reserva de hoy de cada VIP, tareas del día de cada persona
    del personal, actividades del club y novedades. Sirve para los datos de mentira y para el
    equipo real; no pisa lo que ya exista."""
    datos.setdefault("reservas", [])
    datos.setdefault("tareas", [])
    datos.setdefault("avisos", [])
    con_reserva = {r["persona_id"] for r in datos["reservas"]}
    con_tareas = {t["persona_id"] for t in datos["tareas"]}
    inicio = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    for p in datos["personas"].values():
        if p["vinculo"] == "vip" and p["id"] not in con_reserva:
            datos["reservas"].append(dict(persona_id=p["id"], espacio="sala_vip", inicio=inicio,
                                          fin=inicio + timedelta(hours=2), estado="confirmada"))
        if p["vinculo"] == "personal" and p["id"] not in con_tareas:
            base = p["horario_inicio"].hour if p["horario_inicio"] else ahora.hour
            datos["tareas"] += [
                dict(persona_id=p["id"], titulo="revisar el inventario de toallas", area="piscina",
                     hora=time(min(base + 2, 23)), estado="pendiente"),
                dict(persona_id=p["id"], titulo="recibir al técnico del aire acondicionado",
                     area="mantenimiento", hora=time(min(base + 4, 23)), estado="pendiente"),
            ]
    datos.setdefault("actividades", [
        dict(zona="gimnasio", titulo="clase de spinning", hora=_a_la_hora(ahora, 11)),
        dict(zona="piscina", titulo="clase de natación", hora=_a_la_hora(ahora, 12)),
        dict(zona="canchas", titulo="torneo de tenis", hora=_a_la_hora(ahora, 15)),
        dict(zona="gimnasio", titulo="clase de yoga", hora=_a_la_hora(ahora, 18)),
    ])
    datos.setdefault("novedades", [
        dict(titulo="la piscina cierra de 14:00 a 16:00 por limpieza", area="piscina",
             tipo="operativa"),
        dict(titulo="hay un técnico externo en Mantenimiento", area="mantenimiento",
             tipo="acceso"),
    ])


def cargar(ahora: datetime) -> dict:
    socio = dict(inicio=time(6), fin=time(21))
    personas = [
        _persona("valentina", "Valentina Rojas", "vip", trato="Háblame de usted, por favor.",
                 **socio),
        _persona("andres", "Andrés Gómez", "regular", tour=True, trato="Trato cercano.", **socio),
        _persona("carlos", "Carlos Pérez", "personal", time(6), time(14),
                 trato="Directo y breve, voy con prisa."),
        _persona("laura", "Laura Martínez", "regular", **socio),   # no dio consentimiento
        _persona("diana", "Diana López", "personal", time(14), time(22)),
        _persona("tomas", "Tomás Herrera", "regular", **socio),
        _persona("mateo", "Mateo Castro", "regular", **socio),
        _persona("lucia", "Lucía Vargas", "regular", **socio),
        _persona("julian", "Julián Mora", "regular", **socio),
        # La membresía de Ricardo venció hace 10 días: su cara se reconoce, pero no está activa.
        _persona("ricardo", "Ricardo Silva", "regular", hasta=ahora.date() - timedelta(days=10),
                 **socio),
        # Invitados y externos: sin cuenta, sin biometría, existen mientras dure su visita.
        *[_persona(c, n, "ninguno") for c, n in [
            ("sofia", "Sofía Herrera"), ("jorge", "Jorge Ramírez"), ("pedro", "Pedro Castillo"),
            ("ana", "Ana Torres"), ("marta", "Marta Ruiz"), ("elena", "Elena Prieto")]],
    ]
    h = timedelta(hours=1)

    def visita(clave, responsable, categoria, destino, inicio, fin, estado="programada",
               empresa=None, motivo=None, punto_encuentro=None):
        return dict(id=vid(clave), clave=clave, persona_id=pid(clave), responsable_id=pid(responsable),
                    categoria=categoria, destino=destino, empresa=empresa, motivo=motivo,
                    inicio=inicio, fin=fin, estado=estado, punto_encuentro=punto_encuentro)

    visitas = [
        visita("sofia", "valentina", "invitado", "restaurante", ahora - h, ahora + 3 * h,
               motivo="Almuerzo"),
        visita("jorge", "carlos", "externo", "mantenimiento", ahora - h / 2, ahora + 4 * h,
               empresa="Climatizar SAS", motivo="Orden de trabajo OT-1042: revisar el aire"),
        visita("pedro", "laura", "invitado", "piscina", ahora - 27 * h, ahora - 24 * h),
        visita("ana", "andres", "invitado", "piscina", ahora, ahora + 2 * h, estado="cancelada"),
        visita("marta", "laura", "invitado", "piscina", ahora - h, ahora + 2 * h),
        visita("elena", "tomas", "invitado", "restaurante", ahora - h, ahora + 3 * h,
               motivo="Reunión", punto_encuentro="sala_vip"),
    ]
    personales = ["valentina", "andres", "carlos", "laura", "diana", "tomas", "mateo", "lucia",
                  "julian", "ricardo"]
    credenciales = [
        dict(id=str(uuid.uuid5(_NS, f"credencial:{p}")), persona_id=pid(p), visita_id=None,
             tipo="qr_personal", token_hash=hash_token(f"qr-{p}"), valido_desde=ahora - 300 * h,
             valido_hasta=None, revocada_en=None)
        for p in personales
    ] + [
        dict(id=str(uuid.uuid5(_NS, f"credencial:{v['clave']}")), persona_id=v["persona_id"],
             visita_id=v["id"], tipo="qr_visita", token_hash=hash_token(f"qr-{v['clave']}"),
             valido_desde=v["inicio"], valido_hasta=v["fin"],
             revocada_en=ahora - h if v["estado"] == "cancelada" else None)
        for v in visitas
    ]
    # Solo las fotos de registro llevan huella. Las de prueba guardan la persona esperada para
    # evaluar, pero el reconocimiento no las usa.
    fotografias = [
        dict(id=fid(f.clave), clave=f.clave, ruta=f.ruta, uso=f.uso,
             persona_id=pid(f.persona) if f.persona else None, autorizada=True,
             embedding=dataset.huella(f) if f.uso == "registro" else None,
             modelo=dataset.MODELO if f.uso == "registro" else None)
        for f in dataset.FOTOS.values()
    ]
    datos = dict(personas={p["id"]: p for p in personas}, visitas={v["id"]: v for v in visitas},
                 credenciales=credenciales, fotografias=fotografias, eventos=[])
    agenda(datos, ahora)
    return datos


# --- Caras reales del equipo ------------------------------------------------------------------
# registrar_caras.py guarda aquí las huellas (no las fotos) de las personas reales. La carpeta
# dataset/ no se sube al repositorio: son datos biométricos.
CARAS_REALES = Path(__file__).resolve().parent / "dataset" / "caras" / "personas.json"


def agregar_caras_reales(datos: dict, ahora: datetime) -> list[dict]:
    """Agrega a los datos las personas registradas con su cara real y sus visitas: los invitados
    y externos llegan con una invitación u orden de trabajo vigente. Devuelve esas personas."""
    if not CARAS_REALES.exists():
        return []
    registro = json.loads(CARAS_REALES.read_text(encoding="utf-8"))
    socio = dict(inicio=time(6), fin=time(21))
    # Anfitrión del invitado: un miembro del equipo; responsable del externo: alguien del personal.
    roles = {r["rol"]: r["clave"] for r in reversed(registro["personas"])}
    anfitrion = roles.get("vip") or roles.get("regular") or "valentina"
    responsable = roles.get("personal") or anfitrion
    nuevas = []
    for r in registro["personas"]:
        clave, rol = r["clave"], r["rol"]
        if rol in ("vip", "regular"):
            p = _persona(clave, r["nombre"], rol, trato=r.get("trato"), **socio)
        elif rol == "personal":
            # Para la demo, el turno que cubre la hora de la prueba.
            turno = (time(6), time(14)) if ahora.hour < 14 else (time(14), time(22))
            p = _persona(clave, r["nombre"], "personal", *turno, trato=r.get("trato"))
        else:
            p = _persona(clave, r["nombre"], "ninguno", trato=r.get("trato"))
            h = timedelta(hours=1)
            v = dict(id=vid(clave), clave=clave, persona_id=pid(clave), categoria=rol,
                     inicio=ahora - h, fin=ahora + 4 * h, estado="programada",
                     responsable_id=pid(anfitrion if rol == "invitado" else responsable),
                     destino="restaurante" if rol == "invitado" else "mantenimiento",
                     empresa=None if rol == "invitado" else "Climatizar SAS",
                     motivo="Almuerzo" if rol == "invitado" else "Orden de trabajo OT-1043",
                     punto_encuentro=r.get("punto_encuentro"))
            datos["visitas"][v["id"]] = v
        p["consentimiento_biometrico"] = True
        datos["personas"][p["id"]] = p
        # Invitados y externos entran siempre con QR: su foto (de las pruebas) no se usa para
        # reconocerlos, como en Supabase (uso = 'prueba').
        uso = "prueba" if rol in ("invitado", "externo") else "registro"
        for k, foto in enumerate(r["fotos"], 1):
            datos["fotografias"].append(dict(
                id=fid(f"{clave}_real{k}"), clave=f"{clave}_real{k}", ruta=foto["ruta"],
                uso=uso, persona_id=p["id"], autorizada=True,
                embedding=np.array(foto["embedding"]), modelo=registro["modelo"]))
        nuevas.append(p)
    return nuevas


# generar_qr.py guarda aquí los invitados sin cara registrada y el hash de cada QR (nunca el token).
QR_REALES = CARAS_REALES.parent / "qr.json"


def cid(clave: str) -> str:
    return str(uuid.uuid5(_NS, f"credencial:real:{clave}"))


def agregar_qr_reales(datos: dict, ahora: datetime) -> list[dict]:
    """Agrega los invitados sin cara (con su invitación) y los QR de la demo. Llamar después de
    agregar_caras_reales. Devuelve los invitados agregados."""
    if not QR_REALES.exists():
        return []
    qr = json.loads(QR_REALES.read_text(encoding="utf-8"))
    h = timedelta(hours=1)
    invitados = []
    for i in qr["invitados"]:
        p = _persona(i["clave"], i["nombre"], "ninguno")
        p["consentimiento_biometrico"] = False
        datos["personas"][p["id"]] = p
        datos["visitas"][vid(i["clave"])] = dict(
            id=vid(i["clave"]), clave=i["clave"], persona_id=p["id"], categoria="invitado",
            responsable_id=pid(i["anfitrion"]), destino=i["destino"], empresa=None,
            motivo="Invitación", inicio=ahora - h, fin=ahora + 4 * h, estado="programada",
            punto_encuentro=i.get("punto_encuentro"))
        invitados.append(p)
    for c in qr["credenciales"]:
        if pid(c["clave"]) not in datos["personas"]:
            continue
        visita = datos["visitas"].get(vid(c["clave"]))
        datos["credenciales"].append(dict(
            id=cid(c["clave"]), persona_id=pid(c["clave"]),
            visita_id=visita["id"] if visita else None,
            tipo="qr_visita" if visita else "qr_personal", token_hash=c["token_hash"],
            valido_desde=ahora - h, valido_hasta=visita["fin"] if visita else None,
            revocada_en=None))
    return invitados


# --- Casos de validación ------------------------------------------------------------------------
# persona: quién llega de verdad. Solo sirve para dibujar la figura y para evaluar; nunca se entrega
#   al reconocimiento ni a la decisión.
# foto: foto de prueba que representa la llegada (None = la persona prefiere no usar la cámara).
# qr: token que muestra si el robot se lo pide. servicio: False = la verificación no responde.
# ayuda: lo que elige la persona. destino: a dónde va (los miembros lo eligen al llegar).
# correccion: lo que decide recepción si el caso queda pendiente.
# equipaje: el VIP trae maleta y el D1 se la lleva. anfitrion_responde: False = el anfitrión no
#   confirma el aviso de la app y el invitado espera en el lobby.
# esperado: lo que debe resolver el robot (categoría, "pendiente_revision" o "rechazado"), y
#   categoría final, destino y nivel de ayuda.
def _caso(n, titulo, persona, etiqueta, foto, qr=None, **resto):
    return dict(n=n, titulo=titulo, persona=persona, etiqueta=etiqueta, foto=foto, qr=qr, **resto)


CASOS = [
    _caso(1, "Miembro VIP con reserva y maleta (el D1 la lleva)", "valentina", "Valentina Rojas",
          "valentina_p1", ayuda="indicacion", destino="sala_vip", equipaje=True,
          esperado=dict(robot="vip", destino="sala_vip", ayuda="indicacion")),
    _caso(2, "Miembro regular, primera visita (recorrido)", "andres", "Andrés Gómez", "andres_p1",
          ayuda="acompanamiento", destino="gimnasio",
          esperado=dict(robot="regular", destino="gimnasio", ayuda="acompanamiento")),
    _caso(3, "Personal en su turno", "carlos", "Carlos Pérez", "carlos_p1", ayuda="mapa",
          destino="oficinas", esperado=dict(robot="personal", destino="oficinas", ayuda="mapa")),
    _caso(4, "Invitada: cara desconocida, QR vigente", "sofia", "Sofía Herrera", "sofia_p1",
          "qr-sofia", ayuda="acompanamiento",
          esperado=dict(robot="invitado", destino="restaurante", ayuda="acompanamiento")),
    _caso(5, "Trabajador externo (acompañamiento obligatorio)", "jorge", "Jorge Ramírez",
          "jorge_p1", "qr-jorge", ayuda="mapa",
          esperado=dict(robot="externo", destino="mantenimiento", ayuda="acompanamiento")),
    _caso(6, "Prefiere no usar la cámara: solo QR", "laura", "Laura Martínez", None, "qr-laura",
          ayuda="indicacion", destino="piscina",
          esperado=dict(robot="regular", destino="piscina", ayuda="indicacion")),
    _caso(7, "QR vencido", "pedro", "Pedro Castillo", "pedro_p1", "qr-pedro",
          esperado=dict(robot="rechazado")),
    _caso(8, "QR revocado por el anfitrión", "ana", "Ana Torres", "ana_p1", "qr-ana",
          esperado=dict(robot="rechazado")),
    _caso(9, "Contradicción: la cara parece otra persona que la del QR", "marta", "Marta Ruiz",
          "marta_p1", "qr-marta", ayuda="mapa",
          correccion=dict(persona="marta", categoria="invitado",
                          motivo="Verificó documento: es Marta Ruiz, invitada de Laura"),
          esperado=dict(robot="pendiente_revision", final="invitado", destino="piscina",
                        ayuda="mapa")),
    _caso(10, "Servicio de verificación no disponible", "tomas", "Tomás Herrera", "tomas_p1",
          servicio=False, ayuda="indicacion", destino="restaurante",
          correccion=dict(persona="tomas", categoria="regular",
                          motivo="Sin conexión: verificó el carné de miembro"),
          esperado=dict(robot="pendiente_revision", final="regular", destino="restaurante",
                        ayuda="indicacion")),
    _caso(11, "Cara ambigua (entre umbrales), sin QR", "mateo", "Mateo Castro", "mateo_p3",
          ayuda="mapa", destino="canchas",
          correccion=dict(persona="mateo", categoria="regular",
                          motivo="Corte de pelo nuevo: verificó documento"),
          esperado=dict(robot="pendiente_revision", final="regular", destino="canchas",
                        ayuda="mapa")),
    _caso(12, "Personal fuera de su turno", "diana", "Diana López", "diana_p1",
          esperado=dict(robot="rechazado")),
    _caso(13, "Cara desconocida sin credencial", "visitante", "Visitante", "visitante_p1",
          esperado=dict(robot="rechazado")),
    _caso(14, "Captura no válida: el robot pide el QR", "julian", "Julián Mora", "julian_p3",
          "qr-julian", ayuda="mapa", destino="gimnasio",
          esperado=dict(robot="regular", destino="gimnasio", ayuda="mapa")),
    _caso(15, "Dos candidatos muy parecidos: el robot pide el QR", "lucia", "Lucía Vargas",
          "lucia_p3", "qr-lucia", ayuda="indicacion", destino="restaurante",
          esperado=dict(robot="regular", destino="restaurante", ayuda="indicacion")),
    _caso(16, "Reconocido, pero con la membresía vencida", "ricardo", "Ricardo Silva",
          "ricardo_p1", esperado=dict(robot="rechazado")),
    _caso(17, "Invitada: su anfitrión no confirma el aviso", "elena", "Elena Prieto", None,
          "qr-elena", ayuda="indicacion", anfitrion_responde=False,
          esperado=dict(robot="invitado", destino="lobby", ayuda=None)),
]
