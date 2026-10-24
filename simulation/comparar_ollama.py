"""Compara modelos de Ollama para la voz del X2: velocidad y cuántas respuestas pasan la validación.

    python comparar_ollama.py qwen2.5:3b llama3.2:3b qwen2.5:7b

Para cada modelo: lo carga en la GPU, redacta los mismos mensajes (varias personas, tonos y
resultados) dos veces y muestra lo que dijo, cuánto tardó y si el agente lo aceptaría. Las
respuestas que tardan más que ESPERA_OLLAMA cuentan como rechazadas, porque en la demo el X2 habría
hablado con las reglas.
"""

import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path

import agente
from caras import Animo
from recepcion import Resolucion

AHORA = datetime(2026, 10, 24, 10, 0)
TODAS = ["indicacion", "mapa", "acompanamiento"]


def _res(nombre, categoria, resultado="orientado", motivo=None, **resto) -> Resolucion:
    r = Resolucion(resultado, {}, motivo)
    r.nombre, r.categoria, r.requiere_tour = nombre, categoria, False
    r.ayuda_disponible = ["acompanamiento"] if categoria == "externo" else TODAS
    for k, v in resto.items():
        setattr(r, k, v)
    return r


def _fuera_de_horario() -> Resolucion:
    r = _res(None, "vip", "rechazado", "fuera_de_horario")
    r.horario = "06:00-21:00"
    return r


CASOS = [
    ("VIP contento", _res("Camilo", "vip"), Animo("contento", "alegria", .95)),
    ("Regular tenso", _res("Felipe", "regular"), Animo("tenso", "miedo", .90)),
    ("Personal neutral", _res("Juan", "personal"), Animo("neutral", "neutral", .80)),
    ("Invitado triste", _res("Sebastián", "invitado", responsable="Camilo"),
     Animo("triste", "tristeza", .85)),
    ("Externa", _res("Thalia", "externo", empresa="Climatizar SAS"), None),
    ("Regular nuevo", _res("Andrés", "regular", requiere_tour=True), Animo("contento", "alegria", .9)),
    ("Fuera de horario, tenso", _fuera_de_horario(), Animo("tenso", "enojo", .90)),
    ("Pendiente de recepción", _res(None, None, "pendiente_revision", "identidad_ambigua"), None),
]


def _vram(modelo: str) -> str:
    ollama = Path.home() / "AppData/Local/Programs/Ollama/ollama.exe"
    try:
        salida = subprocess.run([str(ollama), "ps"], capture_output=True, text=True,
                                timeout=10).stdout
    except OSError:
        return "?"
    fila = next((l for l in salida.splitlines() if l.startswith(modelo)), "")
    return " ".join(fila.split()[2:5]) if fila else "?"


def probar(modelo: str, repeticiones: int) -> dict:
    a = agente.Agente(modelo)
    if a.modelo is None:
        print(f"\n### {modelo}: {a.estado}")
        return {}
    t0 = time.time()
    while not a.listo and time.time() - t0 < 180:
        time.sleep(0.2)
    print(f"\n### {modelo} (cargó en {time.time() - t0:.0f} s; {_vram(modelo)})")
    tiempos, aceptadas, total = [], 0, 0
    for titulo, r, animo in CASOS:
        plan = a.planear(r, animo, AHORA)
        print(f"\n{titulo} [{animo.tono if animo else 'neutral'}]\n  reglas: {plan.texto}")
        for _ in range(repeticiones):
            t = time.time()
            texto = a.redactar(plan, r, animo).result()
            dt = time.time() - t
            ok = dt <= agente.ESPERA_OLLAMA and a.aceptar(plan, texto, r).fuente == "ollama"
            tiempos.append(dt)
            aceptadas += ok
            total += 1
            print(f"  {dt:4.1f}s {'✓' if ok else '✗'} {texto}")
    tiempos.sort()
    return dict(modelo=modelo, mediana=tiempos[len(tiempos) // 2], peor=tiempos[-1],
                aceptadas=aceptadas, total=total)


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("modelos", nargs="+")
    args.add_argument("--repeticiones", type=int, default=2)
    a = args.parse_args()
    resumen = [r for m in a.modelos if (r := probar(m, a.repeticiones))]
    print("\n## Resumen")
    for r in resumen:
        print(f"{r['modelo']:<14} mediana {r['mediana']:.1f}s · peor {r['peor']:.1f}s · "
              f"aceptadas {r['aceptadas']}/{r['total']}")


if __name__ == "__main__":
    main()
