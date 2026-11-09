"""Idiomas: español (base) e inglés. tr("texto en español") -> texto en el idioma actual."""
import json

from .core import DATA_DIR

LANG = "es"
from .lang_en import EN  # noqa: E402


def tr(s):
    if LANG == "es" or not s:
        return s
    return EN.get(s, s)


def set_lang(lang):
    global LANG
    LANG = lang if lang in ("es", "en") else "es"
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(DATA_DIR / "config.json", "w", encoding="utf-8") as f:
            json.dump({"lang": LANG}, f)
    except OSError:
        pass


def load_lang():
    global LANG
    try:
        with open(DATA_DIR / "config.json", encoding="utf-8") as f:
            LANG = json.load(f).get("lang", "es")
            return
    except (OSError, ValueError):
        pass
    try:
        from PySide6.QtCore import QLocale
        LANG = "es" if QLocale.system().name().lower().startswith("es") else "en"
    except Exception:
        LANG = "es"
