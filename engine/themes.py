"""
themes.py — the settings model for the Book Formatter.

The core insight (see spec §2): a "theme" is just a settings object layered over
ONE normalized HTML source. The same settings drive both the print PDF (WeasyPrint
CSS Paged Media) and the EPUB (pandoc). The UI collects settings; the engine renders.

Resolution order (last wins):  BASE  <-  THEME  <-  per-book overrides

Fonts shipped in v1 are all free, embeddable Google Fonts (the team writes in Google
Docs). Body faces: EB Garamond, Lora, Merriweather, Libre Baskerville, Source Serif 4.
Heading sans option: Montserrat, Lato.
"""

from copy import deepcopy
from typing import Any, Dict

# --- Approved v1 fonts -------------------------------------------------------
# family -> the fc-list / CSS family name. Kept here so the UI font picker and the
# Dockerfile font bundle stay in sync with one source of truth.
BODY_FONTS = {
    "EB Garamond": "EB Garamond",
    "Lora": "Lora",
    "Merriweather": "Merriweather",
    "Libre Baskerville": "Libre Baskerville",
    "Source Serif 4": "Source Serif 4",
}
HEADING_FONTS = {
    "Montserrat": "Montserrat",
    "Lato": "Lato",
    # serif headings can reuse any body face too
}

# --- BASE: every overridable key, with sane book defaults --------------------
BASE: Dict[str, Any] = {
    # Trim size in inches (interior page size).
    "trim": {"w_in": 6.0, "h_in": 9.0},

    # Margins in inches. `inside` = spine/gutter edge (mirrored across facing
    # pages); `outside` = the open edge.
    "margins_in": {"top": 0.75, "bottom": 0.75, "inside": 0.875, "outside": 0.625},

    # Type
    "body_font": "EB Garamond",
    "body_pt": 11.5,
    "leading": 1.4,            # line-height multiple
    "heading_font": "EB Garamond",
    "justify": True,
    "hyphenate": True,
    "indent_em": 1.2,          # first-line paragraph indent (em); 0 = block style

    # Chapters
    "chapter_style": "centered",     # centered | modern_number | italic
    "drop_cap": True,
    "chapter_ornament": "❦",    # floral heart bullet; "" = none
    "scene_break": "⁂",         # asterism for *** ; rendered centered
    "start_chapters_on": "right",    # right (recto) | any

    # Furniture
    "running_heads": True,           # verso=title, recto=chapter title
    "page_numbers": True,            # bottom-center

    # Identity (manuscript metadata wins unless explicitly overridden)
    "title": "",
    "author": "",
    "publisher": "",
    "copyright_year": "",
}

# --- THEMES: deltas over BASE ------------------------------------------------
THEMES: Dict[str, Dict[str, Any]] = {
    "classic": {
        "_label": "Classic",
        "_blurb": "Centered small-caps chapter title, floral ornament, drop cap. "
                  "Traditional trade-book feel.",
        "body_font": "EB Garamond",
        "heading_font": "EB Garamond",
        "body_pt": 11.5,
        "leading": 1.4,
        "chapter_style": "centered",
        "drop_cap": True,
        "chapter_ornament": "❦",
        "scene_break": "⁂",
    },
    "modern": {
        "_label": "Modern",
        "_blurb": "Large chapter number, bold sans headings, no drop cap. "
                  "Clean and contemporary.",
        "body_font": "Source Serif 4",
        "heading_font": "Montserrat",
        "body_pt": 11.0,
        "leading": 1.5,
        "chapter_style": "modern_number",
        "drop_cap": False,
        "chapter_ornament": "",
        "scene_break": "— — —",  # em-dash trio
    },
    "memoir": {
        "_label": "Memoir",
        "_blurb": "Italic centered chapter title, star ornament, drop cap. "
                  "Warm and personal.",
        "body_font": "Lora",
        "heading_font": "Lora",
        "body_pt": 11.5,
        "leading": 1.45,
        "chapter_style": "italic",
        "drop_cap": True,
        "chapter_ornament": "★",          # star
        "scene_break": "★ ★ ★",
    },
}


def list_themes():
    """Theme list for the UI picker: id, label, blurb, and the resolved settings."""
    out = []
    for tid, delta in THEMES.items():
        out.append({
            "id": tid,
            "label": delta.get("_label", tid.title()),
            "blurb": delta.get("_blurb", ""),
            "settings": resolve_settings(tid),
        })
    return out


def resolve_settings(theme=None, overrides=None):
    """Merge BASE <- THEME <- overrides into one flat settings dict.

    Nested dicts (trim, margins_in) are deep-merged so a partial override like
    {"trim": {"w_in": 5.0}} keeps the other key.
    """
    s = deepcopy(BASE)

    if theme:
        delta = THEMES.get(theme.lower())
        if delta is None:
            raise ValueError(f"unknown theme '{theme}'. known: {list(THEMES)}")
        _merge(s, {k: v for k, v in delta.items() if not k.startswith("_")})

    if overrides:
        _merge(s, overrides)

    # Validate font choices against the approved sets (fall back, never crash).
    if s["body_font"] not in BODY_FONTS:
        s["body_font"] = BASE["body_font"]
    if s["heading_font"] not in BODY_FONTS and s["heading_font"] not in HEADING_FONTS:
        s["heading_font"] = s["body_font"]
    return s


def _merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge(dst[k], v)
        else:
            dst[k] = v
