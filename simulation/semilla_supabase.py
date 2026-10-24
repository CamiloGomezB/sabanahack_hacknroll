"""Genera supabase/seed_demo.sql: las personas, visitas, credenciales y fotografías de la demo con los
mismos UUID de la simulación. Las huellas de las fotos de registro se calculan dentro de Postgres con
la misma fórmula de dataset.py, así que el archivo es corto y da exactamente los mismos vectores.

    python semilla_supabase.py         # escribe el archivo; luego se corre en el editor SQL

Se puede correr varias veces: borra y vuelve a crear los datos de la demo. Las ventanas de las
visitas quedan relativas al momento en que se corre.
"""

from datetime import datetime
from pathlib import Path

import dataset
import datos_falsos as df

SALIDA = Path(__file__).resolve().parents[1] / "supabase" / "seed_demo.sql"


def q(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    return "'" + str(v).replace("'", "''") + "'"


def relativo(t: datetime, ahora: datetime) -> str:
    return f"now() + interval '{int((t - ahora).total_seconds())} seconds'"


def main() -> None:
    ahora = datetime(2026, 1, 1, 12, 0)
    d = df.cargar(ahora)
    personas, visitas = d["personas"], d["visitas"]
    l = ["-- Generado por simulation/semilla_supabase.py. Datos de DEMOSTRACIÓN: personas inventadas",
         "-- y huellas simuladas (modelo 'simulado-v1'). No son fotos ni huellas reales.",
         "begin;", "",
         "create or replace function pg_temp.c(s text) returns float8[] language sql as $$",
         "  select array_agg(((('x' || substr(md5(s || ':' || i), 1, 8))::bit(32)::bigint)::float8",
         "                    / 4294967295 * 2 - 1) order by i) from generate_series(0, 511) i $$;",
         "create or replace function pg_temp.huella(r jsonb) returns extensions.vector",
         "language sql as $$",
         "  select (select array_agg(s order by i) from (",
         "    select i, sum((e ->> 1)::float8 * (pg_temp.c(e ->> 0))[i]) as s",
         "      from jsonb_array_elements(r) e, generate_series(1, 512) i group by i) t",
         "  )::extensions.vector $$;", "",
         "delete from public.fotografias where id in ("
         + ", ".join(q(f["id"]) for f in d["fotografias"]) + ");",
         "delete from public.personas where id in (" + ", ".join(q(p) for p in personas) + ");", ""]

    l.append("insert into public.personas (id, nombre_demo, vinculo, estado, requiere_tour, "
             "horario_inicio, horario_fin, vinculo_hasta, consentimiento_biometrico, "
             "consentimiento_fecha) values")
    filas = []
    for p in personas.values():
        hasta = ("null" if p["vinculo_hasta"] is None else
                 f"current_date - {(ahora.date() - p['vinculo_hasta']).days}")
        filas.append(f"  ({q(p['id'])}, {q(p['nombre_demo'])}, {q(p['vinculo'])}, 'activa', "
                     f"{q(p['requiere_tour'])}, {q(p['horario_inicio'])}, {q(p['horario_fin'])}, "
                     f"{hasta}, {q(p['consentimiento_biometrico'])}, "
                     f"{'now()' if p['consentimiento_biometrico'] else 'null'})")
    l += [",\n".join(filas) + ";", ""]

    l.append("insert into public.visitas (id, persona_id, responsable_id, categoria, motivo, "
             "empresa, destino, inicio, fin, estado) values")
    l += [",\n".join(
        f"  ({q(v['id'])}, {q(v['persona_id'])}, {q(v['responsable_id'])}, {q(v['categoria'])}, "
        f"{q(v['motivo'])}, {q(v['empresa'])}, {q(v['destino'])}, {relativo(v['inicio'], ahora)}, "
        f"{relativo(v['fin'], ahora)}, {q(v['estado'])})" for v in visitas.values()) + ";", ""]

    l.append("insert into public.credenciales (id, persona_id, visita_id, tipo, token_hash, "
             "valido_desde, valido_hasta, revocada_en, motivo_revocacion) values")
    l += [",\n".join(
        f"  ({q(c['id'])}, {q(c['persona_id'])}, {q(c['visita_id'])}, {q(c['tipo'])}, "
        f"{q(c['token_hash'])}, {relativo(c['valido_desde'], ahora)}, "
        f"{'null' if c['valido_hasta'] is None else relativo(c['valido_hasta'], ahora)}, "
        f"{'null' if c['revocada_en'] is None else relativo(c['revocada_en'], ahora)}, "
        f"{q('Visita cancelada por el anfitrión') if c['revocada_en'] else 'null'})"
        for c in d["credenciales"]) + ";", ""]

    l.append("insert into public.fotografias (id, persona_id, ruta, uso, autorizada, "
             "autorizacion_fecha, embedding, modelo) values")
    filas = []
    for f in d["fotografias"]:
        foto = dataset.FOTOS[f["clave"]]
        persona = f["persona_id"] if f["persona_id"] in personas else None
        receta = "[" + ", ".join(f'["{s}", {w}]' for s, w in foto.receta) + "]"
        huella = (f"pg_temp.huella('{receta}')" if f["uso"] == "registro" else "null")
        filas.append(f"  ({q(f['id'])}, {q(persona)}, {q(f['ruta'])}, {q(f['uso'])}, true, now(), "
                     f"{huella}, {q(dataset.MODELO) if f['uso'] == 'registro' else 'null'})")
    l += [",\n".join(filas) + ";", "", "commit;", ""]
    SALIDA.write_text("\n".join(l), encoding="utf-8")
    print(f"Escrito {SALIDA}")


if __name__ == "__main__":
    main()
