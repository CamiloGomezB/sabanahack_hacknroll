"""Simulación de la recepción de N Club en MuJoCo.

    python main.py                      # visor interactivo
    python main.py --hora 15:30         # otra hora simulada (cambia quién puede entrar)
    python main.py --validar            # sin ventana: corre los 16 casos y escribe docs/validacion.md
    python main.py --capturas salida/   # sin ventana: guarda imágenes de la demo
    python main.py --camara             # la cámara del computador es la del X2 (reconocimiento real)

main.py es el coordinador de la recepción. El X2 y el D1 son programas aparte (robots/), que aquí
corren en su versión simulada dentro de la misma escena de MuJoCo.
"""

import argparse
import textwrap
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import mujoco
import numpy as np

import agente as voz
import dataset
import datos_falsos
from agente import OLLAMA_MODELO, Agente
from animacion import Mundo
from camaras import QR_DEMO, CamaraDataset
from caras import MODELO as MODELO_REAL
from club import (BASE_D1, ENTRADA, POS_ANTE_RECEPCION, POS_VISITANTE, RECORRIDO_TOUR,
                  SALIDA_VISITANTE, TRAMO_BLOQUEABLE, ZONAS, nodo_de_zona, nombre_destino, puntos,
                  ruta, usa_tramo, zona_de_destino)
from datos_falsos import pid
from escena import ascii, construir
from recepcion import (AYUDAS, CATEGORIAS, MARGEN, MOTIVOS, UMBRAL, UMBRAL_DUDA, corregir,
                       elegir_ayuda, reconocer, registrar_llegada)
from robots.d1_sim import D1Simulado
from robots.x2_sim import X2Simulado

RAIZ = Path(__file__).resolve().parents[1]


def categoria_real(caso: dict, datos: dict) -> str | None:
    """Categoría verdadera de la persona del caso (solo para colorear la figura)."""
    p = datos["personas"].get(pid(caso["persona"]))
    if p is None:
        return None
    if p["vinculo"] != "ninguno":
        return p["vinculo"]
    return next((v["categoria"] for v in datos["visitas"].values() if v["persona_id"] == p["id"]),
                None)


def describir_reconocimiento(rec: dict) -> str:
    """Primer resultado del proceso: identidad candidata (posible miembro) o no identificada."""
    cara = rec["cara"]
    if cara == "reconocida":
        return (f"identidad candidata {rec['candidato']} (distancia {rec['distancia']:.2f})"
                " → posible miembro; falta confirmar la acreditación")
    if cara == "desconocida":
        return "desconocida: no se pudo identificar (no equivale a no miembro)"
    if cara == "ambigua":
        if rec["detalle"] == "candidatos_cercanos":
            return (f"ambigua: dos candidatos casi iguales ({rec['distancia']:.2f} y "
                    f"{rec['distancia_segundo']:.2f})")
        return f"ambigua: distancia {rec['distancia']:.2f}, entre umbrales"
    if cara == "captura_no_valida":
        return "captura no válida: la foto no sirve para comparar"
    if cara == "sin_verificar":
        return "sin verificar: el servicio no responde"
    return "no usada: la persona prefirió el QR"


def describir_acreditacion(r, datos: dict) -> str:
    """Segunda consulta: qué acreditación vigente respalda la categoría."""
    ev = r.evidencia
    if ev["qr"] not in ("no_presentado", "valida", "sin_verificar"):
        return f"QR {ev['qr'].replace('_', ' ')}: no hay acreditación válida"
    if r.motivo == "acreditacion_vencida":
        return f"membresía vencida el {r.vinculo_hasta:%d/%m}"
    if r.motivo == "fuera_de_horario":
        return f"vínculo laboral vigente, turno {r.horario}: fuera de horario"
    if r.motivo in ("visita_cancelada", "sin_visita_activa"):
        return MOTIVOS[r.motivo]
    if not r.habilitado:
        return "sin consultar: primero hay que saber quién es"
    v = datos["visitas"].get(r.visita_id, {})
    if r.categoria == "invitado":
        return f"invitación de {r.responsable} vigente hasta {v['fin']:%H:%M}"
    if r.categoria == "externo":
        return f"{v.get('motivo') or 'orden de trabajo'} ({r.empresa}), responsable {r.responsable}"
    if r.categoria == "personal":
        return f"vínculo laboral vigente, turno {v['fin']:%H:%M} de salida"
    return f"membresía {'VIP' if r.categoria == 'vip' else 'regular'} vigente"


def describir_evidencia(ev: dict) -> str:
    partes = [f"cara {ev['cara'].replace('_', ' ')}"]
    if ev["qr"] != "no_presentado":
        partes.append(f"QR {ev['qr'].replace('_', ' ')}")
    return ", ".join(partes)


def en_paralelo(*acciones):
    """Avanza varias acciones a la vez (p. ej. el D1 guiando y la persona siguiéndolo)."""
    activas = list(acciones)
    while activas:
        for a in list(activas):
            try:
                next(a)
            except StopIteration:
                activas.remove(a)
        if activas:
            yield


# Destino por defecto de quien llega por la cámara (los invitados y externos traen el suyo).
DESTINO_POR_CATEGORIA = {"vip": "sala_vip", "regular": "piscina", "personal": "oficinas",
                         "invitado": "restaurante", "externo": "mantenimiento"}
TECLAS_AYUDA = {ord("1"): "indicacion", ord("2"): "mapa", ord("3"): "acompanamiento"}
# Modo cámara: cada paso dura hasta 10 s de tiempo real (la persona es real), sin contar lo que dice
# el X2. 1) cara → 2) primer QR → 3) segundo QR → recepción. Quien llega con invitación u orden
# (tecla I, o mostrando el QR desde el principio) empieza en el paso 2: 20 s como máximo.
ESPERA_PASO = 10.0


class Escenario:
    """Coordinador de la recepción: decide con la misma lógica de Supabase (recepcion.py) y le da
    órdenes al X2 y al D1 a través de robots.interfaz. No mueve a los robots directamente."""

    PUESTOS_CAMARA = 10   # figuras que se reciclan para las llegadas por cámara

    def __init__(self, hora: str, bloquear_en: int | None = 7, webcam=None,
                 agente: Agente | None = None):
        self.webcam = webcam
        self.agente = agente or Agente()
        h, mnt = (int(x) for x in hora.split(":"))
        self.inicio = datetime.now().replace(hour=h, minute=mnt, second=0, microsecond=0)
        if webcam is None:
            self.datos = datos_falsos.cargar(self.inicio)
            self.llegadas = list(datos_falsos.CASOS)
            figuras = [(c["etiqueta"], categoria_real(c, self.datos)) for c in self.llegadas]
        else:
            # Modo cámara: solo las personas reales del equipo, como en Supabase.
            self.datos = dict(personas={}, visitas={}, credenciales=[], fotografias=[], eventos=[])
            self.registradas = datos_falsos.agregar_caras_reales(self.datos, self.inicio)
            self.invitados = datos_falsos.agregar_qr_reales(self.datos, self.inicio)
            webcam.identificar = self._quien
            self.llegadas = []
            figuras = [(f"Visitante {k + 1}", None) for k in range(self.PUESTOS_CAMARA)]
            bloquear_en = None
        self.model = construir(figuras)
        self.data = mujoco.MjData(self.model)
        self.mundo = Mundo(self.model, self.data, len(figuras))

        # Cada robot es un programa aparte con su interfaz; aquí van sus versiones simuladas.
        self.x2 = X2Simulado(self.mundo, al_hablar=lambda texto: self.hud.__setitem__("X2 dice",
                                                                                       texto))
        self.d1 = D1Simulado(self.mundo)
        self.camara_dataset = CamaraDataset()
        self.x2.camara = webcam if webcam is not None else self.camara_dataset

        self.bloquear_en = bloquear_en  # caso antes del cual se cierra el pasillo central
        self.siguiente = 0
        self.actual = None          # generador del caso que se está atendiendo
        self.fondo = []             # tareas en paralelo (el D1 volviendo a su base)
        self.d1_ocupado = False
        self.d1_nodo = None         # nodo donde quedó el D1 al terminar de guiar
        self.automatico = webcam is None
        self.pedir_siguiente = False
        self.eleccion = None        # nivel de ayuda elegido con las teclas 1/2/3 (modo cámara)
        self.con_invitacion = False # tecla I: trae invitación u orden y empieza por el QR
        self.espera = 1.0
        self.hud = {}
        self.recepcion = "sin casos pendientes"
        self.resultados = []
        for k in range(len(figuras)):
            self.mundo.personas[k]["xy"] = (np.array(self._puesto_fila(k), dtype=float)
                                            if webcam is None else np.array([-40.0, k]))

    def _puesto_fila(self, k: int) -> tuple[float, float]:
        return (ENTRADA[0] - 1.5 - (k - self.siguiente) * 0.9, 0.0)

    def _figura(self, i: int) -> int:
        return i % len(self.mundo.personas)

    def ahora(self) -> datetime:
        return self.inicio + timedelta(seconds=self.mundo.t)

    @property
    def bloqueados(self) -> set[tuple[str, str]]:
        return {tuple(sorted(TRAMO_BLOQUEABLE))} if self.mundo.bloqueado else set()

    def alternar_bloqueo(self) -> None:
        self.mundo.bloqueado = not self.mundo.bloqueado
        self.hud["Aviso"] = ("Mantenimiento cerró el pasillo central (Sala VIP - Piscina)"
                             if self.mundo.bloqueado else "Pasillo central abierto de nuevo")

    def _quien(self, captura) -> tuple[str, bool]:
        """Vista en vivo de la cámara: a quién se parece la cara (y su tono), sin registrar ninguna
        llegada."""
        rec = reconocer(self.datos, captura.embedding, True, "real", MODELO_REAL)
        tono = f" · {captura.animo.tono}" if captura.animo else ""
        if rec["candidato"] is None:
            return (f"Desconocido ({rec['distancia']:.2f}){tono}" if rec["distancia"]
                    else f"Desconocido{tono}"), False
        p = self.datos["personas"][rec["candidato"]]
        categoria = next((v["categoria"] for v in self.datos["visitas"].values()
                          if v["persona_id"] == p["id"]), p["vinculo"])
        texto = f"{p['nombre_demo']} - {categoria} ({rec['distancia']:.2f}){tono}"
        if rec["cara"] != "reconocida":
            texto = f"Dudoso: {texto}"
        # cv2.putText no dibuja tildes
        return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode(), \
            rec["cara"] == "reconocida"

    def _paso_cara(self):
        """Paso 1 (10 s): el X2 intenta reconocer la cara. Si en ese tiempo le muestran un QR o la
        persona dice que trae invitación u orden (tecla I), pasa directo al QR.
        Devuelve la mejor captura (la última válida)."""
        x2, w = self.x2, self.webcam
        w.qr, w.pase, w.buscar_qr, self.con_invitacion = None, None, True, False
        w.mensaje = "Mira a la camara (I: traigo invitacion u orden QR)"
        self.hud["Paso"] = "1/3 cara"
        mejor, inicio = None, time.perf_counter()
        while (time.perf_counter() - inicio < ESPERA_PASO and not w.qr
               and not self.con_invitacion):
            yield from x2.mirar_visitante(0.3)
            c = x2.capturar()
            if c.valida:
                mejor = c
                if reconocer(self.datos, c.embedding, True, c.modo, c.modelo)["cara"] == "reconocida":
                    break
            else:
                mejor = mejor if mejor and mejor.valida else c
                w.mensaje = f"{c.motivo}: mira de frente a la camara (I: traigo QR)"
        w.buscar_qr = False      # al cambiar de paso se cancela el intento anterior
        return mejor or x2.capturar()

    def _pasos_qr(self, animo):
        """Pasos 2 y 3 (10 s cada uno): el X2 pide el QR y lo lee con la misma cámara; si no lo
        logra leer, da instrucciones y lo intenta una vez más. Devuelve el token leído, o None si no
        se pudo leer o la persona dice que no tiene QR (tecla Q)."""
        x2, w = self.x2, self.webcam
        for paso, texto in ((2, voz.pedir_qr(animo)), (3, voz.REINTENTO_QR)):
            x2.decir(texto)
            w.qr, w.pase, w.buscar_qr = None, None, True
            w.mensaje = "Muestra tu QR a la camara (Q: no tengo QR)"
            self.hud["Paso"] = f"{paso}/3 QR"
            self.hud["QR"] = "esperando el QR…" if paso == 2 else "segundo intento…"
            inicio = time.perf_counter()
            while w.buscar_qr and time.perf_counter() - inicio < ESPERA_PASO:
                yield from x2.esperar(0.1)
            sin_qr = w.buscar_qr is False and w.qr is None and \
                time.perf_counter() - inicio < ESPERA_PASO
            w.buscar_qr = False
            if w.qr:
                return w.qr
            if sin_qr:           # tecla Q: no tiene QR, no tiene sentido otro intento
                break
        self.hud["QR"] = "no se pudo leer"
        return None

    def _hablar(self, r, animo):
        """El X2 dice el mensaje del agente. Con Ollama espera hasta ESPERA_OLLAMA segundos a la
        versión redactada; si no llega o no sirve, habla con la de las reglas."""
        plan = self.agente.planear(r, animo, self.ahora())
        pedido = self.agente.redactar(plan, r, animo)
        if pedido is not None:
            self.hud["X2 dice"] = "(pensando…)"
            inicio = time.perf_counter()     # tiempo real: Ollama no corre en tiempo simulado
            while not pedido.done() and time.perf_counter() - inicio < voz.ESPERA_OLLAMA:
                yield from self.x2.esperar(0.1)
            if pedido.done() and pedido.exception() is None:
                plan = self.agente.aceptar(plan, pedido.result(), r)
            else:
                pedido.cancel()
        self.hud["Agente"] = (f"{plan.fuente}" + (f" · sugiere {AYUDAS[plan.ayuda_sugerida]}"
                                                  if plan.ayuda_sugerida else ""))
        self.x2.decir(plan.texto)
        return plan

    def nueva_llegada(self) -> None:
        """Modo cámara: llega la persona que está frente a la cámara del computador."""
        n = len(self.llegadas) + 1
        self.llegadas.append(dict(n=n, titulo=f"Llegada {n} por la cámara", camara=True, qr=None,
                                  ayuda=None, destino=None, correccion=None, esperado=None))
        i = self._figura(n - 1)
        self.mundo.personas[i]["xy"] = np.array([POS_VISITANTE[0] - 2.5, 0.0])

    # --- flujo de una llegada -----------------------------------------------------------------
    def atender(self, i: int):
        mundo, x2, d1, caso = self.mundo, self.x2, self.d1, self.llegadas[i]
        fig = self._figura(i)
        fila = dict(n=caso["n"], titulo=caso["titulo"], esperado=caso["esperado"], robot=None,
                    final=None, destino=None, ayuda=None, ruta=None, llegada=None,
                    correccion=None, cara=None)
        self.resultados.append(fila)
        self.hud = {k: v for k, v in self.hud.items() if k == "Aviso"}
        self.hud.update({"Caso": f"{caso['n']}" + ("" if caso.get("camara") else
                                                   f"/{len(self.llegadas)}") + f": {caso['titulo']}",
                         "Persona": "llegando…" if caso.get("camara") else
                         f"{caso['etiqueta']} (llegando)"})
        yield from mundo.caminar(fig, [POS_VISITANTE] if caso.get("camara")
                                 else [ENTRADA, POS_VISITANTE])
        mundo.personas[fig]["yaw"] = 0.0

        # 1. Imagen de llegada → reconocimiento. Con el dataset es SIMULADO; con la cámara del
        #    computador es REAL. En ambos casos el resultado sigue el mismo camino.
        servicio = caso.get("servicio", True)
        captura = None
        if caso.get("camara"):
            self.webcam.mensaje = "Mira a la camara..."
            self.hud["Imagen"] = "cámara del computador (cámara del X2)"
            self.hud["Reconocimiento"] = "REAL · buscando la cara…"
            captura = yield from self._paso_cara()
            caso["qr"] = self.webcam.qr      # QR mostrado durante el paso 1 (invitados, externos)
        elif caso["foto"] is not None:
            self.camara_dataset.foto = dataset.FOTOS[caso["foto"]]
            self.hud["Imagen"] = f"{self.camara_dataset.foto.ruta} (dataset de prueba)"
            self.hud["Reconocimiento"] = "SIMULADO · comparando con las fotos de registro…"
            yield from x2.mirar_visitante(1.5)
            captura = x2.capturar()
        else:
            self.hud["Imagen"] = "no usa la cámara (el reconocimiento es voluntario)"
            yield from x2.esperar(1.0)
        modo = captura.modo if captura else "simulado"
        modelo = captura.modelo if captura else dataset.MODELO
        embedding = captura.embedding if captura else None
        valida = captura.valida if captura else True
        etiqueta = "REAL" if modo == "real" else "SIMULADO"
        if servicio:
            rec = reconocer(self.datos, embedding, valida, modo, modelo)
            if rec["candidato"]:
                rec["candidato"] = self.datos["personas"][rec["candidato"]]["nombre_demo"]
        else:
            rec = dict(cara="sin_verificar")
        texto = describir_reconocimiento(rec)
        if captura is not None and not captura.valida:
            texto += f" ({captura.motivo})"
        self.hud["Reconocimiento"] = f"{etiqueta} · {texto}"
        if self.webcam is not None and caso.get("camara"):
            self.webcam.mensaje = texto
        sin_qr = False
        if caso.get("camara") and servicio and rec["cara"] != "reconocida" and not caso["qr"]:
            caso["qr"] = yield from self._pasos_qr(captura.animo if captura else None)
            sin_qr = caso["qr"] is None
        if caso.get("camara") and caso["qr"]:
            pase = self.webcam.pase
            # Lo que dice el pase solo se muestra; la decisión la toma registrar_llegada con la base.
            self.hud["QR"] = (f"pase de {pase.get('nombre')} ({pase.get('tipo')}, "
                              f"de {pase.get('empresa') or pase.get('anfitrion')}); verificando…"
                              if pase else "leído; verificando…")
            yield from x2.esperar(0.5)
        elif caso["qr"] and rec["cara"] != "reconocida":
            x2.decir("No pude confirmar quién eres con la cámara. ¿Me muestras tu QR?"
                     if captura else "Muéstrame tu QR, por favor.")
            yield from x2.esperar(2.0)
            x2.decir("Leyendo el QR…")
            yield from x2.esperar(1.0)

        # 2. Consulta de la acreditación y la visita vigentes → categoría confirmada.
        r = registrar_llegada(self.datos, embedding, caso["qr"], self.ahora(),
                              captura_valida=valida, servicio=servicio, modo=modo, modelo=modelo)
        fila["robot"] = r.categoria if r.resultado == "orientado" else r.resultado
        fila["cara"] = r.evidencia["cara"]
        self.hud["Acreditación"] = describir_acreditacion(r, self.datos)
        if r.resultado == "orientado":
            self.hud["Categoría"] = CATEGORIAS[r.categoria]
            self.hud["Permisos"] = "ayuda: " + ", ".join(AYUDAS[a] for a in r.ayuda_disponible)
        elif voz.a_recepcion(r):
            self.hud["Categoría"] = f"a recepción: {MOTIVOS[r.motivo]}"
        else:
            self.hud["Categoría"] = f"no pasa: {MOTIVOS[r.motivo]}"
        if caso.get("camara") or r.habilitado:
            self.hud["Persona"] = r.nombre or "sin identificar"
        # El agente decide CÓMO decirlo (tono, ayuda sugerida, aviso a recepción); qué pasa ya lo
        # decidió registrar_llegada. El ánimo solo vive en esta llegada: no se guarda.
        animo = captura.animo if captura else None
        if animo:
            self.hud["Ánimo"] = animo.tono      # solo para el tono; no se guarda
        self.hud.pop("Paso", None)       # identificado o derivado: se detienen los temporizadores
        qr_demo = bool(caso["qr"]) and caso["qr"].startswith(QR_DEMO)
        if sin_qr or qr_demo:
            # Sin QR legible tras los intentos, o con el QR de demostración de la app: no es un
            # rechazo, sigue con recepción humana.
            x2.decir((voz.QR_DE_DEMOSTRACION + " " if qr_demo else "") + voz.A_RECEPCION)
            plan = None
        else:
            plan = yield from self._hablar(r, animo)
        if plan and plan.aviso_recepcion:
            self.recepcion = f"caso {caso['n']}: {plan.aviso_recepcion}"
        if self.webcam is not None and caso.get("camara"):
            self.webcam.mensaje = (f"{r.nombre}: {CATEGORIAS[r.categoria]}" if r.habilitado
                                   else self.hud["Categoría"])

        if r.resultado == "rechazado" and not voz.a_recepcion(r):
            yield from x2.negar(2.5)
            yield from mundo.caminar(fig, [ENTRADA, (ENTRADA[0] - 2.5, 3.0)])
            mundo.personas[fig]["xy"] = np.array([-40.0, fig])
            return

        # 2b. Incertidumbre o QR que no sirve: el robot no orienta; recepción (el punto físico de
        #     atención humana) recibe el contexto y decide.
        if voz.a_recepcion(r):
            yield from x2.negar(1.5)
            self.recepcion = (f"caso {caso['n']} EN REVISIÓN: {MOTIVOS[r.motivo]}; "
                              f"evidencia {describir_evidencia(r.evidencia)}")
            yield from mundo.caminar(fig, [POS_ANTE_RECEPCION])
            mundo.personas[fig]["yaw"] = np.pi / 2
            yield from x2.esperar(3.0)
            k = caso.get("correccion")
            if k is None:
                # Con la cámara real no hay corrección guionada: decide el operador en la web.
                self.recepcion += " → el operador decide desde el panel web"
                fila["llegada"] = False
                return
            r = corregir(self.datos, r, pid(k["persona"]), k["categoria"], k["motivo"],
                         self.ahora())
            fila["correccion"] = k["motivo"]
            self.recepcion = f"caso {caso['n']} CORREGIDO → {CATEGORIAS[r.categoria]}: {k['motivo']}"
            self.hud["Categoría"] = f"{CATEGORIAS[r.categoria]} (confirmó recepción)"
            self.hud["Persona"] = r.nombre
            self.hud["Acreditación"] = describir_acreditacion(r, self.datos)
            self.hud["Permisos"] = "ayuda: " + ", ".join(AYUDAS[a] for a in r.ayuda_disponible)
            yield from mundo.caminar(fig, [POS_VISITANTE])
            mundo.personas[fig]["yaw"] = 0.0
            plan = yield from self._hablar(r, animo)
        fila["final"] = r.categoria

        # 3. La persona decide cuánta ayuda necesita (en el modo cámara, con las teclas 1/2/3).
        self.hud["Orientación"] = "eligiendo ayuda…"
        yield from x2.saludar(2.0)
        preferida = caso["ayuda"]
        if preferida is None:
            self.eleccion = None
            sugerida = (f" (sugerido: {list(TECLAS_AYUDA.values()).index(plan.ayuda_sugerida) + 1})"
                        if plan.ayuda_sugerida else "")
            self.hud["Orientación"] = "elige 1 indicación · 2 mapa · 3 D1" + sugerida
            if self.webcam is not None:
                self.webcam.mensaje = "Elige: 1 indicacion, 2 mapa, 3 acompanamiento" + sugerida
            while self.eleccion is None:
                yield
            preferida = self.eleccion
        nivel, nota = elegir_ayuda(r, preferida)
        # El destino puede venir de la app móvil (clave de sus espacios) o de la simulación.
        pedido = r.destino or caso["destino"]
        destino = zona_de_destino(pedido) or DESTINO_POR_CATEGORIA[r.categoria]
        lugar_nombre = nombre_destino(pedido if zona_de_destino(pedido) else destino)
        tour = r.categoria == "regular" and r.requiere_tour and nivel == "acompanamiento"
        self.hud["Orientación"] = (f"{lugar_nombre} · {AYUDAS[nivel]}"
                                   + (" · recorrido" if tour else ""))
        fila["destino"], fila["ayuda"] = destino, nivel

        paradas = (RECORRIDO_TOUR if tour else []) + [destino]
        tramos, origen = [], "salida"
        for zona in paradas:
            camino = ruta(origen, nodo_de_zona(zona), r.categoria, self.bloqueados)
            tramos.append(camino)
            origen = camino[-1]
        sin_cierre = ruta("salida", nodo_de_zona(destino), r.categoria, set())
        alterna = self.mundo.bloqueado and usa_tramo(sin_cierre, TRAMO_BLOQUEABLE)
        fila["ruta"] = "alterna" if alterna else "normal"
        cerca_cierre = self.mundo.bloqueado and not alterna
        self.hud["Ruta"] = ("ruta alterna autorizada (pasillo central cerrado)" if alterna
                            else "no pasa por el pasillo cerrado" if cerca_cierre
                            else "ruta habitual")
        lugar = self._lugar_en_zona(i, destino)

        if nivel == "indicacion":
            x2.decir(f"Ve a {lugar_nombre}: sal a la izquierda y sigue "
                     + ("el pasillo alterno; el central está cerrado." if alterna
                        else "la señalización."))
            yield from x2.esperar(2.0)
        elif nivel == "mapa":
            x2.decir(f"Mira el mapa: {lugar_nombre} es la zona que parpadea.")
            yield from x2.senalar_mapa(destino, 3.0)

        if nivel != "acompanamiento":
            self.hud["D1"] = "no hace falta"
            yield from mundo.caminar(fig, [SALIDA_VISITANTE] + puntos(tramos[0]) + [lugar])
            fila["llegada"] = True
            return

        # 4. Acompañamiento: el coordinador le pasa al D1 solo la ruta.
        while self.d1_ocupado:
            self.hud["D1"] = "ocupado; espera a que vuelva"
            yield
        self.d1_ocupado = True
        primera = [SALIDA_VISITANTE] + puntos(tramos[0])
        self.hud["D1"] = "viene a recoger a la persona"
        yield from d1.ir_a([tuple(mundo.punto_de_encuentro(fig, primera))])
        for k, (zona, camino) in enumerate(zip(paradas, tramos)):
            self.hud["D1"] = (f"recorrido: {ZONAS[zona].nombre}" if tour and k < len(paradas) - 1
                              else f"acompañando a {ZONAS[zona].nombre}")
            yield from self._guiar(fig, primera if k == 0 else puntos(camino[1:]))
            if k < len(paradas) - 1:
                yield from x2.esperar(1.0)
        self.d1_nodo = tramos[-1][-1]
        self.hud["D1"] = f"confirmó la llegada a {lugar_nombre}; vuelve a la base"
        fila["llegada"] = True
        if tour:
            self.datos["personas"][r.persona_id]["requiere_tour"] = False
            self.hud["Base de datos"] = f"completar_tour({r.persona_id}) → requiere_tour = false"
        self.fondo.append(self._d1_vuelve())
        yield from mundo.caminar(fig, [lugar])

    def _guiar(self, fig: int, pts):
        """El D1 recorre la ruta; la persona (parte del mundo simulado) camina detrás."""
        guiando = {"activo": True}

        def guia():
            yield from self.d1.guiar(pts)
            guiando["activo"] = False

        inicio = self.d1.posicion
        yield from en_paralelo(guia(), self.mundo.seguir(fig, inicio, pts, lambda: self.d1.avance,
                                                         lambda: guiando["activo"]))

    def _d1_vuelve(self):
        camino = ruta(self.d1_nodo, "salida", "personal", self.bloqueados)
        yield from self.d1.ir_a(puntos(camino[1:]) + [BASE_D1])
        self.d1.descansar()
        self.d1_ocupado = False

    def _lugar_en_zona(self, i: int, zona: str) -> tuple[float, float]:
        cx, cy = ZONAS[zona].centro
        return (cx + ((i % 3) - 1) * 0.9, cy + ((i // 3) % 2 - 0.5) * 0.8)

    # --- un cuadro ------------------------------------------------------------------------------
    @property
    def terminado(self) -> bool:
        return self.siguiente >= len(self.llegadas) and self.actual is None and not self.fondo

    def paso(self, dt: float) -> None:
        self.mundo._dt = dt
        if self.actual is None and self.siguiente < len(self.llegadas):
            self.espera -= dt
            if (self.automatico and self.espera <= 0) or self.pedir_siguiente or \
                    self.llegadas[self.siguiente].get("camara"):
                self.pedir_siguiente = False
                if self.bloquear_en and self.llegadas[self.siguiente]["n"] == self.bloquear_en \
                        and not self.mundo.bloqueado:
                    self.alternar_bloqueo()
                self.actual = self.atender(self.siguiente)
                self.siguiente += 1
        if self.actual is not None:
            try:
                next(self.actual)
            except StopIteration:
                self.actual, self.espera = None, 1.5
                if self.webcam is not None:
                    self.webcam.mensaje = "Espacio: el X2 toma la foto de la siguiente persona"
        for tarea in list(self.fondo):
            try:
                next(tarea)
            except StopIteration:
                self.fondo.remove(tarea)
        # La fila avanza sola.
        if self.webcam is None:
            for k in range(self.siguiente, len(self.llegadas)):
                p = self.mundo.personas[k]
                objetivo = np.array(self._puesto_fila(k))
                p["xy"] = p["xy"] + (objetivo - p["xy"]) * min(1.0, dt * 2)
                p["yaw"] = 0.0
        self.mundo.aplicar(dt)

    def _categoria_de(self, p: dict) -> str:
        if p["vinculo"] != "ninguno":
            return CATEGORIAS[p["vinculo"]]
        return next((CATEGORIAS[v["categoria"]] for v in self.datos["visitas"].values()
                     if v["persona_id"] == p["id"]), "")

    def textos(self):
        # Solo lo esencial: quién es, qué es, cómo se ve, qué dice el X2 y a dónde va. El detalle
        # (evidencia, acreditación, ruta, D1) queda en self.hud para las capturas y el informe.
        filas = [("Hora", f"{self.ahora():%H:%M}")]
        for clave, titulo in [("Paso", "Paso"), ("Persona", "Persona"), ("Categoría", "Categoría"),
                              ("Ánimo", "Ánimo"), ("QR", "QR"), ("X2 dice", "X2 dice"),
                              ("Orientación", "Va a"), ("Aviso", "Aviso")]:
            if clave in self.hud:
                lineas = textwrap.wrap(self.hud[clave], 44) or [""]
                filas.append((titulo, lineas[0]))
                filas += [("", l) for l in lineas[1:5 if clave == "X2 dice" else 2]]
        izq = "\n".join(f for f, _ in filas)
        der = "\n".join(v for _, v in filas)

        lado = ["RECEPCION"] + textwrap.wrap(self.recepcion, 36)[:3]
        if self.webcam is None:
            hechos = [f for f in self.resultados if evaluar(f) is not None]
            bien = sum(1 for f in hechos if evaluar(f))
            lado += ["", f"VALIDACION {bien}/{len(hechos)} OK de {len(self.llegadas)}"]
            lado += [f"{f['n']:>2}. X {f['titulo'][:30]}" for f in hechos if not evaluar(f)]
            teclas = f"Espacio: siguiente · A: {'auto' if self.automatico else 'manual'}"
        else:
            lado += ["", "REGISTRADOS"] + [f"{p['nombre_demo']}: " + self._categoria_de(p)
                                           for p in self.registradas + self.invitados]
            teclas = "Espacio: llegada · I: traigo QR · Q: sin QR · 1/2/3: ayuda"
        textos = [
            (mujoco.mjtGridPos.mjGRID_TOPLEFT, "N CLUB\n" + izq, "\n" + der),
            (mujoco.mjtGridPos.mjGRID_TOPRIGHT, "\n".join(lado), ""),
            (mujoco.mjtGridPos.mjGRID_BOTTOMLEFT,
             "REAL: cámara, reconocimiento y decisiones · SIMULADO: robots y club" if self.webcam
             else "SIMULADO: robots, club y huellas · REAL: decisiones (igual que Supabase)", ""),
            (mujoco.mjtGridPos.mjGRID_BOTTOMRIGHT,
             teclas + "\nB: pasillo · C: cámara", ""),
        ]
        return [(mujoco.mjtFontScale.mjFONTSCALE_150, pos, ascii(a), ascii(b))
                for pos, a, b in textos]


# --- Validación -------------------------------------------------------------------------------
def evaluar(f: dict) -> bool | None:
    """True si el caso dio lo esperado; None si todavía no termina."""
    e = f["esperado"]
    if f["robot"] is None:
        return None
    if f["robot"] != e["robot"]:
        return False
    if e["robot"] == "rechazado":
        return True
    if f["llegada"] is None:
        return None
    return (f["final"] == e.get("final", e["robot"]) and f["destino"] == e["destino"]
            and f["ayuda"] == e["ayuda"] and f["llegada"])


def metricas_faciales(datos: dict) -> list[str]:
    """Pasa cada foto de prueba por el reconocimiento, sin decirle quién es, y compara con la
    persona esperada. Va aparte de las métricas de categoría y orientación."""
    registradas = {pid(p) for p in dataset.CON_BIOMETRIA}
    nombres = {p["id"]: p["nombre_demo"] for p in datos["personas"].values()}
    filas, cuenta = [], {}
    for foto in dataset.FOTOS.values():
        if foto.uso != "prueba":
            continue
        esperado = pid(foto.persona) if foto.persona else None
        rec = reconocer(datos, dataset.huella(foto), foto.valida)
        if rec["cara"] == "reconocida":
            resultado = ("acierto" if rec["candidato"] == esperado else
                         "falsa aceptación" if esperado not in registradas else "confusión")
        elif rec["cara"] == "desconocida":
            resultado = "desconocida correcta" if esperado not in registradas else "falso rechazo"
        else:
            resultado = "pide otra validación"
        cuenta[resultado] = cuenta.get(resultado, 0) + 1
        quien = (nombres.get(esperado, foto.persona) + ("" if esperado in registradas
                                                        else " (no registrada)"))
        obtenido = rec["cara"].replace("_", " ") + (f": {nombres[rec['candidato']]}"
                                                     if rec["candidato"] else "")
        dist = "—" if rec["distancia"] is None else f"{rec['distancia']:.3f}"
        dist2 = "—" if rec["distancia_segundo"] is None else f"{rec['distancia_segundo']:.3f}"
        filas.append(f"| {foto.ruta} | {quien} | {obtenido} | {dist} | {dist2} | {resultado} |")
    n_reg = sum(1 for f in dataset.FOTOS.values() if f.uso == "registro")
    total = sum(cuenta.values())
    return [
        "## Reconocimiento facial (métrica aparte)", "",
        f"Dataset de demostración: {n_reg} fotos de registro ({len(dataset.CON_BIOMETRIA)} personas "
        f"con consentimiento, 3 cada una) y {total} fotos de prueba distintas, incluidas personas "
        "no registradas. El reconocimiento recibe solo la huella de la foto; la persona esperada se "
        "usa únicamente aquí, para evaluar, y el nombre del archivo no interviene.",
        "",
        f"Criterio: se acepta si la distancia coseno es ≤ {UMBRAL} y el segundo candidato está al "
        f"menos {MARGEN} más lejos; por encima de {UMBRAL_DUDA} es desconocida; en medio, o con dos "
        "candidatos cercanos, es ambigua y el robot pide otra validación. La distancia no es un "
        "porcentaje de certeza.",
        "",
        "> **Importante:** las huellas de este dataset son sintéticas (modelo `simulado-v1`), así "
        "que estos números validan el flujo y los umbrales, **no la precisión de un modelo facial "
        "real**. Tampoco prueban detección de vida ni protección contra alguien que muestre una "
        "foto.",
        "",
        "| Resultado | Fotos |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in sorted(cuenta.items())],
        "",
        "| Foto de prueba | Persona esperada | Resultado | Distancia | 2.º candidato | Evaluación |",
        "|---|---|---|---|---|---|",
        *filas, "",
    ]


def escribir_validacion(resultados: list[dict], datos: dict, ruta_md: Path, hora: str) -> None:
    etiquetas = ["vip", "regular", "personal", "invitado", "externo", "pendiente_revision",
                 "rechazado"]
    nombres = {**{k: CATEGORIAS[k] for k in etiquetas[:5]},
               "pendiente_revision": "Pendiente de revisión", "rechazado": "Rechazado"}
    l = [
        "# Validación de la simulación",
        "",
        f"Generado con `python main.py --validar` (hora simulada {hora}).",
        "",
        "**Qué es real y qué es simulado.** Simulados: los robots, las personas, el dataset y la "
        "conversión de foto a huella (reconocimiento simulado). Reales y probados: la comparación "
        "de huellas con umbrales, la consulta de acreditaciones y visitas, las decisiones, la "
        "revisión humana y las rutas; la misma lógica corre en Supabase (`registrar_llegada`) con "
        "los mismos identificadores. Por eso las métricas de categoría y orientación validan la "
        "integración, y las faciales se presentan aparte.",
        "",
        "## Casos: esperado frente a observado",
        "",
        "| # | Caso | Reconocimiento | Robot esperado | Robot observado | Recepción | Destino "
        "| Ayuda | Ruta | Llegada | OK |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in resultados:
        e = f["esperado"]
        esp_dest = e.get("destino", "—")
        l.append(
            f"| {f['n']} | {f['titulo']} | {(f['cara'] or '—').replace('_', ' ')} | "
            f"{nombres[e['robot']]} | {nombres.get(f['robot'], f['robot'])} | "
            f"{(f['correccion'] or '—')} | {f['destino'] or '—'} (esp. {esp_dest}) | "
            f"{f['ayuda'] or '—'} (esp. {e.get('ayuda', '—')}) | {f['ruta'] or '—'} | "
            f"{'sí' if f['llegada'] else '—'} | {'✅' if evaluar(f) else '❌'} |")
    total = sum(1 for f in resultados if evaluar(f))
    l += ["", f"**{total} de {len(resultados)} casos dieron el resultado esperado.**", "",
          "## Clasificación del robot: categoría esperada (filas) frente a obtenida (columnas)",
          "", "| | " + " | ".join(nombres[k] for k in etiquetas) + " |",
          "|---" * (len(etiquetas) + 1) + "|"]
    for fila_k in etiquetas:
        cuenta = [sum(1 for f in resultados if f["esperado"]["robot"] == fila_k
                      and f["robot"] == col) for col in etiquetas]
        l.append(f"| **{nombres[fila_k]}** | " + " | ".join(str(c) if c else "·" for c in cuenta)
                 + " |")
    orientados = [f for f in resultados if f["destino"]]
    bien_destino = sum(1 for f in orientados if f["destino"] == f["esperado"].get("destino"))
    bien_ayuda = sum(1 for f in orientados if f["ayuda"] == f["esperado"].get("ayuda"))
    llegadas = sum(1 for f in orientados if f["llegada"])
    l += ["", "## Orientación (aparte de la clasificación)", "",
          f"- Destino correcto: {bien_destino} de {len(orientados)}",
          f"- Nivel de ayuda correcto: {bien_ayuda} de {len(orientados)}",
          f"- Llegada confirmada: {llegadas} de {len(orientados)}",
          f"- Casos que pasaron por recepción: "
          f"{sum(1 for f in resultados if f['correccion'])} (todos con motivo registrado)", ""]
    l += metricas_faciales(datos)
    ruta_md.parent.mkdir(parents=True, exist_ok=True)
    ruta_md.write_text("\n".join(l), encoding="utf-8")


# --- Modos de ejecución -----------------------------------------------------------------------
def camara_general(cam: mujoco.MjvCamera) -> None:
    cam.lookat[:] = [3.5, 0, 0]
    cam.distance = 25
    cam.azimuth = -25
    cam.elevation = -50


def camara_recepcion(cam: mujoco.MjvCamera) -> None:
    """Vista del visitante: el X2 de frente y el mapa a su lado."""
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = [-4.2, 0.5, 1.1]
    cam.distance = 4.2
    cam.azimuth = -25
    cam.elevation = -12


def con_visor(esc: Escenario, velocidad: float) -> None:
    import mujoco.viewer

    camaras = ["general", "recepcion", "d1"]
    cambio = {"pendiente": False, "actual": 0}
    bloqueo = {"pendiente": False}

    def tecla(codigo: int) -> None:
        if codigo == 32 and esc.webcam is not None:
            esc.nueva_llegada()
        elif codigo == ord("Q") and esc.webcam is not None:
            esc.webcam.buscar_qr = False      # la persona no tiene QR
        elif codigo == ord("I") and esc.webcam is not None:
            esc.con_invitacion = True         # trae invitación u orden: salta al QR
        elif codigo in TECLAS_AYUDA:
            esc.eleccion = TECLAS_AYUDA[codigo]
        elif codigo == 32:        # espacio
            esc.pedir_siguiente = True
        elif codigo == ord("A"):
            esc.automatico = not esc.automatico
        elif codigo == ord("B"):
            bloqueo["pendiente"] = True
        elif codigo == ord("C"):
            cambio["pendiente"] = True

    def poner_camara(cam: mujoco.MjvCamera) -> None:
        nombre = camaras[cambio["actual"]]
        if nombre == "general":
            cam.type = mujoco.mjtCamera.mjCAMERA_FREE
            camara_general(cam)
        elif nombre == "recepcion":
            camara_recepcion(cam)
        else:
            cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
            cam.trackbodyid = esc.model.body("d1").id
            cam.distance, cam.elevation = 5.0, -25

    with mujoco.viewer.launch_passive(esc.model, esc.data, key_callback=tecla,
                                      show_left_ui=False, show_right_ui=False) as visor:
        visor.opt.label = mujoco.mjtLabel.mjLABEL_SITE
        camara_general(visor.cam)
        cuadro = 1 / 60
        while visor.is_running():
            t0 = time.perf_counter()
            with visor.lock():
                if cambio["pendiente"]:
                    cambio["pendiente"] = False
                    cambio["actual"] = (cambio["actual"] + 1) % len(camaras)
                    poner_camara(visor.cam)
                if bloqueo["pendiente"]:
                    bloqueo["pendiente"] = False
                    esc.alternar_bloqueo()
                esc.paso(cuadro * velocidad)
            if esc.webcam is not None:
                codigo = esc.webcam.actualizar()
                if codigo != -1:
                    tecla(ord(chr(codigo & 0xFF).upper()) if codigo & 0xFF != 32 else 32)
            visor.set_texts(esc.textos())
            visor.sync()
            time.sleep(max(0.0, cuadro - (time.perf_counter() - t0)))


def con_capturas(esc: Escenario, carpeta: Path, cada: float) -> None:
    """Corre la demo completa sin ventana y guarda una imagen cada `cada` segundos simulados."""
    from PIL import Image

    carpeta.mkdir(parents=True, exist_ok=True)
    render = mujoco.Renderer(esc.model, 900, 1600)
    opciones = mujoco.MjvOption()
    opciones.label = mujoco.mjtLabel.mjLABEL_SITE
    cam = mujoco.MjvCamera()
    camara_general(cam)
    dt, proxima, n = 1 / 30, 0.0, 0
    while not esc.terminado:
        esc.paso(dt)
        if esc.mundo.t >= proxima:
            render.update_scene(esc.data, cam, opciones)
            Image.fromarray(render.render()).save(carpeta / f"{n:03d}.png")
            print(f"{n:03d}  t={esc.mundo.t:5.1f}s  " + "  |  ".join(
                f"{k}: {v}" for k, v in esc.hud.items()))
            n, proxima = n + 1, proxima + cada


def validar(esc: Escenario, hora: str) -> None:
    """Corre todos los casos sin ventana (con la animación completa) y escribe el informe."""
    while not esc.terminado:
        esc.paso(1 / 20)
    for f in esc.resultados:
        ok = evaluar(f)
        print(f"{f['n']:>2}. {'OK ' if ok else 'X  '} {f['titulo']:<58} robot={f['robot']:<18} "
              f"final={f['final'] or '-':<9} destino={f['destino'] or '-':<13} "
              f"ayuda={f['ayuda'] or '-':<14} ruta={f['ruta'] or '-'}")
    salida = RAIZ / "docs" / "validacion.md"
    escribir_validacion(esc.resultados, esc.datos, salida, hora)
    print(f"\n{sum(1 for f in esc.resultados if evaluar(f))}/{len(esc.resultados)} casos OK. "
          f"Informe: {salida}  ({esc.mundo.t:.0f} s simulados)")


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("--hora", default="10:00", help="hora simulada de inicio (HH:MM)")
    args.add_argument("--velocidad", type=float, default=1.0, help="1 = tiempo real")
    args.add_argument("--sin-cierre", action="store_true",
                      help="no cerrar el pasillo central durante la demo")
    args.add_argument("--validar", action="store_true", help="correr los casos y escribir el informe")
    args.add_argument("--capturas", type=Path, help="carpeta para guardar imágenes, sin ventana")
    args.add_argument("--cada", type=float, default=4.0, help="segundos entre capturas")
    args.add_argument("--camara", nargs="?", const=0, type=int, metavar="N",
                      help="usar la cámara N del computador como cámara del X2 (por defecto 0)")
    args.add_argument("--ollama", nargs="?", const=OLLAMA_MODELO, metavar="MODELO",
                      help=f"redactar lo que dice el X2 con Ollama local (por defecto {OLLAMA_MODELO})")
    a = args.parse_args()
    agente = Agente(a.ollama)
    print(f"Agente del X2: {agente.estado}")
    if a.camara is not None:
        from camaras import CamaraWebcam
        webcam = CamaraWebcam(a.camara)
        try:
            con_visor(Escenario(a.hora, webcam=webcam, agente=agente), a.velocidad)
        finally:
            webcam.cerrar()
        return
    esc = Escenario(a.hora, bloquear_en=None if a.sin_cierre else 7, agente=agente)
    if a.validar:
        validar(esc, a.hora)
    elif a.capturas:
        con_capturas(esc, a.capturas, a.cada)
    else:
        con_visor(esc, a.velocidad)


if __name__ == "__main__":
    main()
