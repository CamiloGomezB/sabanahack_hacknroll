"""Conexión en vivo con Supabase para el modo cámara (`python main.py --camara --supabase`).

Con esta opción la decisión no la toma la copia local (recepcion.py) sino la base real, igual que
lo hará el robot: registrar_llegada, contexto_llegada y registrar_orientacion. Así cada llegada
queda en `eventos`, la visita pasa a en curso, el aviso al anfitrión lo crea el trigger de la base
y le llega a la app móvil, y lo pendiente de revisión aparece en el panel web de recepción.

Usa SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY del .env de la raíz: es el papel del backend del
robot (esas funciones solo las puede llamar el servicio). La clave nunca va a la app ni a la web.
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, time
from pathlib import Path

from dotenv import load_dotenv

from recepcion import UMBRALES, Resolucion

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class ErrorBase(Exception):
    pass


def _fecha(texto):
    return datetime.fromisoformat(texto).astimezone() if texto else None


def _hora(texto):
    return time.fromisoformat(texto) if texto else None


class BaseReal:
    def __init__(self, tiempo_espera: float = 5.0):
        self.url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self._clave = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.url or not self._clave:
            raise SystemExit("--supabase necesita SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el .env")
        self.tiempo_espera = tiempo_espera

    def _pedir(self, metodo: str, ruta: str, cuerpo=None, extra: dict | None = None):
        pedido = urllib.request.Request(
            f"{self.url}{ruta}", method=metodo,
            data=None if cuerpo is None else json.dumps(cuerpo).encode(),
            headers={"apikey": self._clave, "Authorization": f"Bearer {self._clave}",
                     "Content-Type": "application/json", **(extra or {})})
        try:
            with urllib.request.urlopen(pedido, timeout=self.tiempo_espera) as r:
                texto = r.read().decode()
        except urllib.error.HTTPError as e:
            raise ErrorBase(f"Supabase respondió {e.code} en {ruta}: {e.read().decode()[:300]}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ErrorBase(f"sin conexión con Supabase ({e})") from e
        return json.loads(texto) if texto else None

    def _rpc(self, funcion: str, **args):
        return self._pedir("POST", f"/rest/v1/rpc/{funcion}", args)

    def _uno(self, tabla: str, columnas: str, **filtros) -> dict | None:
        q = "&".join(f"{k}=eq.{v}" for k, v in filtros.items())
        filas = self._pedir("GET", f"/rest/v1/{tabla}?select={columnas}&{q}&limit=1")
        return filas[0] if filas else None

    def disponible(self) -> bool:
        try:
            self._pedir("GET", "/rest/v1/espacios?select=clave&limit=1")
            return True
        except ErrorBase:
            return False

    # --- lo que el robot le pide a la base ----------------------------------------------------
    def registrar_llegada(self, datos: dict, embedding, token: str | None, captura_valida: bool,
                          modo: str, modelo: str) -> Resolucion:
        """public.registrar_llegada. Deja en `datos` la visita real para que el resto de la
        simulación (acreditación, aviso) la encuentre con el mismo id que en la base."""
        umbral, duda, margen = UMBRALES.get(modelo, UMBRALES["simulado-v1"])
        j = self._rpc(
            "registrar_llegada",
            p_embedding=None if embedding is None else "[" + ",".join(f"{x:.6f}" for x in embedding) + "]",
            p_token=token, p_modo=modo, p_captura_valida=captura_valida, p_umbral=umbral,
            p_umbral_duda=duda, p_margen=margen, p_fuente="simulacion", p_modelo=modelo)
        r = Resolucion(j["resultado"], j.get("evidencia") or {}, j.get("motivo"), j.get("categoria"),
                       nombre=j.get("nombre"), visita_id=j.get("visita_id"), destino=j.get("destino"),
                       empresa=j.get("empresa"), requiere_tour=bool(j.get("requiere_tour")),
                       horario=j.get("horario"), ayuda_disponible=j.get("ayuda_disponible") or [])
        r.evento_id = j.get("evento_id")
        ev = self._uno("eventos", "persona_candidata_id", id=r.evento_id) if r.evento_id else None
        r.persona_id = ev and ev["persona_candidata_id"]
        p = self._uno("personas", "nombre_demo,vinculo_hasta", id=r.persona_id) if r.persona_id else None
        r.evidencia["candidato"] = p and p["nombre_demo"]
        if p and p["vinculo_hasta"]:
            r.vinculo_hasta = datetime.fromisoformat(p["vinculo_hasta"]).date()
        if r.visita_id:
            v = self._uno("visitas", "id,persona_id,responsable_id,categoria,motivo,empresa,destino,"
                          "inicio,fin,estado,punto_encuentro", id=r.visita_id)
            if v:
                v.update(inicio=_fecha(v["inicio"]), fin=_fecha(v["fin"]))
                datos["visitas"][v["id"]] = v
                if v["responsable_id"]:
                    resp = self._uno("personas", "nombre_demo", id=v["responsable_id"])
                    r.responsable = resp and resp["nombre_demo"]
        return r

    def contexto_llegada(self, persona_id: str | None, visita_id: str | None) -> dict:
        """public.contexto_llegada, con fechas y horas como en la copia local."""
        ctx = self._rpc("contexto_llegada", p_persona=persona_id, p_visita=visita_id) or {}
        for res in ctx.get("reservas") or []:
            res.update(inicio=_fecha(res["inicio"]), fin=_fecha(res["fin"]))
        for t in ctx.get("tareas") or []:
            t["hora"] = _hora(t.get("hora"))
        ctx.setdefault("reservas", [])
        ctx.setdefault("tareas", [])
        ctx.setdefault("novedades", [])
        return ctx

    def registrar_orientacion(self, evento_id: str, nivel: str, destino: str | None,
                              duracion_ms: int | None, ruta: list | None = None) -> None:
        self._rpc("registrar_orientacion", p_evento=evento_id, p_nivel=nivel, p_destino=destino,
                  p_duracion_ms=duracion_ms, p_ruta=ruta)

    def completar_tour(self, persona_id: str) -> None:
        self._rpc("completar_tour", p_persona=persona_id)

    # --- avisos al anfitrión (los responde la persona en la app móvil) ------------------------
    def aviso_de(self, visita_id: str | None) -> dict | None:
        if not visita_id:
            return None
        filas = self._pedir("GET", "/rest/v1/avisos?select=id,mensaje,estado,punto_encuentro"
                                   f"&visita_id=eq.{visita_id}&order=creado_en.desc&limit=1")
        return filas[0] if filas else None

    def aviso_sin_respuesta(self, aviso_id: str) -> None:
        """Nadie respondió a tiempo: queda así para que recepción lo vea en el panel web."""
        self._pedir("PATCH", f"/rest/v1/avisos?id=eq.{aviso_id}&estado=in.(emitido,recibido)",
                    {"estado": "sin_respuesta", "actualizado_en": datetime.now().astimezone().isoformat()},
                    {"Prefer": "return=minimal"})

    # --- fotos de registro que sube la app móvil (las procesa huellas_app.py) -----------------
    def fotos_pendientes(self) -> list[dict]:
        """Fotos de registro autorizadas que todavía no tienen huella."""
        return self._pedir(
            "GET", "/rest/v1/fotografias?select=id,ruta,persona_id,"
                   "persona:personas!fotografias_persona_id_fkey(nombre_demo,consentimiento_biometrico)"
                   "&uso=eq.registro&autorizada=is.true&huella_estado=eq.pendiente&embedding=is.null"
                   "&order=creado_en.asc&limit=20") or []

    def descargar_foto(self, ruta: str) -> bytes:
        pedido = urllib.request.Request(
            f"{self.url}/storage/v1/object/fotos/{ruta}",
            headers={"apikey": self._clave, "Authorization": f"Bearer {self._clave}"})
        try:
            with urllib.request.urlopen(pedido, timeout=max(self.tiempo_espera, 15)) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            raise ErrorBase(f"Storage respondió {e.code} al bajar {ruta}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ErrorBase(f"sin conexión con Supabase ({e})") from e

    def guardar_huella(self, foto_id: str, embedding, modelo: str) -> None:
        self._rpc("guardar_huella", p_foto=foto_id, p_modelo=modelo,
                  p_embedding="[" + ",".join(f"{x:.6f}" for x in embedding) + "]")

    def foto_sin_huella(self, foto_id: str, motivo: str) -> None:
        """La foto no sirvió: la app se lo muestra a la persona para que tome otra."""
        self._pedir("PATCH", f"/rest/v1/fotografias?id=eq.{foto_id}",
                    {"huella_estado": "sin_cara", "huella_detalle": motivo},
                    {"Prefer": "return=minimal"})

    def huellas_registro(self, modelo: str) -> list[dict]:
        """Todas las huellas de registro de un modelo, con su persona (para reconocer en vivo)."""
        return self._pedir(
            "GET", "/rest/v1/fotografias?select=id,persona_id,embedding,"
                   "persona:personas!fotografias_persona_id_fkey(nombre_demo,vinculo,estado,"
                   "consentimiento_biometrico)"
                   f"&uso=eq.registro&autorizada=is.true&modelo=eq.{modelo}&embedding=not.is.null") or []
