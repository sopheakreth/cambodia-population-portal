"""One place for every on-screen word.

All visible text is written in English in the code, wrapped as ``t("English text")``.
``locales/km.json`` maps that English text to Khmer. To change any wording, edit
that one file and refresh the page (no restart needed). A missing entry shows the
English text, so nothing breaks while you translate.

Placeholders: ``t("Hello {name}", name=x)`` — keep ``{name}`` unchanged in Khmer.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src import config

LOCALE_FILE: Path = config.ROOT / "locales" / "km.json"
_cache: dict = {"mtime": None, "data": {}}

KHMER_FONT = "'Noto Sans Khmer', 'Khmer OS Battambang', 'Khmer Sangam MN', 'Leelawadee UI', sans-serif"


def _table() -> dict[str, str]:
    try:
        mtime = LOCALE_FILE.stat().st_mtime
    except OSError:
        return {}
    if _cache["mtime"] != mtime:  # reload automatically when the file is saved
        _cache["data"] = json.loads(LOCALE_FILE.read_text(encoding="utf-8"))
        _cache["mtime"] = mtime
    return _cache["data"]


def t(text: str, **fmt) -> str:
    """Khmer text for `text` (falls back to the English). Fills {placeholders}."""
    s = _table().get(text) or text
    if fmt:
        try:
            return s.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return text.format(**fmt)
    return s


def columns(df: pd.DataFrame, value_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    """Translate column headers (and the values of `value_cols`, e.g. province names)."""
    out = df.copy()
    for c in value_cols:
        if c in out:
            out[c] = out[c].map(lambda v: t(v) if isinstance(v, str) else v)
    return out.rename(columns={c: t(c) for c in out.columns if isinstance(c, str)})


def style_plotly(fig):
    """Apply a Khmer-capable font to a Plotly figure."""
    fig.update_layout(font=dict(family=KHMER_FONT))
    return fig
