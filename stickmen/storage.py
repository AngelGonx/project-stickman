"""Guardado: quiénes estaban en pantalla (sesión) y la biblioteca de personajes."""
import json
import os
import uuid

from .core import DATA_DIR, ROSTER

SESSION = "sesion.json"
LIBRARY = "personajes.json"

SPEC_KEYS = ("id", "name", "color", "accent", "eyes", "accs", "body")


def new_id():
    return uuid.uuid4().hex[:10]


def normalize(spec):
    """Rellena campos faltantes para que un personaje viejo o importado no truene."""
    s = dict(spec)
    if "accs" not in s:
        s["accs"] = [s["acc"]] if s.get("acc") else []
    s.pop("acc", None)
    s.setdefault("id", new_id())
    s.setdefault("name", "Stickman")
    s.setdefault("color", "#888888")
    s.setdefault("accent", "#FFFFFF")
    s.setdefault("eyes", "#111111")
    s.setdefault("body", "normal")
    s["accs"] = [a for a in s["accs"] if isinstance(a, str)]
    return {k: s[k] for k in SPEC_KEYS}


def _read(name, default):
    try:
        with open(DATA_DIR / name, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write(name, data):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = DATA_DIR / (name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_DIR / name)
    except OSError:
        pass


def load_session():
    data = _read(SESSION, None)
    if not isinstance(data, list):
        return None
    return [normalize(s) for s in data if isinstance(s, dict)]


def save_session(specs):
    _write(SESSION, [normalize(s) for s in specs])


def load_library():
    data = _read(LIBRARY, [])
    return [normalize(s) for s in data if isinstance(s, dict)] if isinstance(data, list) else []


def save_library(lib):
    _write(LIBRARY, [normalize(s) for s in lib])


def export_backup(path, library, session):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"tipo": "respaldo-desk-stickmen", "version": 1,
                   "personajes": [normalize(s) for s in library],
                   "en_pantalla": [normalize(s) for s in session]}, f, ensure_ascii=False, indent=2)


def import_backup(path):
    """Devuelve (personajes, en_pantalla) de un respaldo."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):           # también acepta una lista suelta de personajes
        return [normalize(s) for s in data if isinstance(s, dict)], []
    lib = [normalize(s) for s in data.get("personajes", []) if isinstance(s, dict)]
    ses = [normalize(s) for s in data.get("en_pantalla", []) if isinstance(s, dict)]
    return lib, ses


def default_specs():
    return [normalize(s) for s in ROSTER]


BUILD = "construcciones.json"


def load_build():
    data = _read(BUILD, [])
    return data if isinstance(data, list) else []


def save_build(items):
    _write(BUILD, items)
