"""model.py — canonical ID-addressable document model + import + HTML build."""
import os, re, html, uuid, base64, mimetypes, subprocess
from typing import Any, Dict, List
from bs4 import BeautifulSoup


def new_id(prefix="b"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


_SCENE_TEXT = re.compile(r"^\s*(?:\*\s*\*\s*\*|#\s*#\s*#|\*{3,}|—{3,}|⁂|★(?:\s*★)*)\s*$")


def _pandoc(args, input_bytes=None):
    proc = subprocess.run(["pandoc", *args], input=input_bytes, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"pandoc failed: {proc.stderr.decode('utf-8','replace')}")
    return proc.stdout


def docx_to_html(src_path, media_dir):
    ext = os.path.splitext(src_path)[1].lower()
    fmt = {".docx":"docx",".md":"markdown",".markdown":"markdown",".html":"html",
           ".htm":"html",".txt":"markdown"}.get(ext,"docx")
    os.makedirs(media_dir, exist_ok=True)
    return _pandoc(["-f",fmt,"-t","html5","--wrap=none",f"--extract-media={media_dir}",src_path]).decode("utf-8")


def import_book(src_path, media_dir, meta_overrides=None, inline_images=False):
    raw_html = docx_to_html(src_path, media_dir)
    soup = BeautifulSoup(raw_html, "lxml")
    root = soup.body or soup
    chapters = []
    current = None

    def ensure_chapter(title=""):
        nonlocal current
        current = {"id": new_id("ch"), "title": title, "blocks": []}
        chapters.append(current)
        return current

    for el in root.find_all(recursive=False):
        name = (el.name or "").lower()
        if name == "h1":
            ensure_chapter(el.get_text(" ", strip=True)); continue
        if current is None:
            ensure_chapter("")
        block = _element_to_block(el, name)
        if block:
            current["blocks"].append(block)
    if not chapters:
        ensure_chapter("")

    meta = _extract_meta(src_path)
    if meta_overrides:
        meta.update({k: v for k, v in meta_overrides.items() if v})
    if inline_images:
        _inline_images(chapters)
    return {"meta": meta, "settings": {}, "chapters": chapters}


def _inline_images(chapters):
    for ch in chapters:
        for b in ch.get("blocks", []):
            if b.get("type") == "image":
                uri = _to_data_uri(b.get("src", ""))
                if uri:
                    b["src"] = uri


def _to_data_uri(path):
    if not path or path.startswith("data:") or not os.path.isfile(path):
        return path
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def _element_to_block(el, name):
    if name in ("h2","h3","h4"):
        return {"id": new_id("h"), "type": "heading", "level": int(name[1]),
                "text": el.get_text(" ", strip=True), "overrides": {}}
    if name == "p":
        imgs = el.find_all("img"); text = el.get_text(" ", strip=True)
        if imgs and not text:
            img = imgs[0]
            return {"id": new_id("img"), "type": "image", "src": img.get("src",""),
                    "alt": img.get("alt",""), "caption": "", "overrides": {}}
        if _SCENE_TEXT.match(text or ""):
            return {"id": new_id("sb"), "type": "scene_break", "overrides": {}}
        return {"id": new_id("p"), "type": "paragraph", "html": el.decode_contents().strip(), "overrides": {}}
    if name == "figure":
        img = el.find("img"); cap = el.find("figcaption")
        return {"id": new_id("img"), "type": "image",
                "src": img.get("src","") if img else "", "alt": img.get("alt","") if img else "",
                "caption": cap.get_text(" ", strip=True) if cap else "", "overrides": {}}
    if name == "table":
        return {"id": new_id("tbl"), "type": "table", "html": str(el), "overrides": {}}
    if name == "hr":
        return {"id": new_id("sb"), "type": "scene_break", "overrides": {}}
    if name in ("ul","ol","blockquote","pre","div","section"):
        return {"id": new_id("rich"), "type": "rich", "html": str(el), "overrides": {}}
    text = el.get_text(" ", strip=True)
    if text:
        return {"id": new_id("p"), "type": "paragraph", "html": html.escape(text), "overrides": {}}
    return None


def _extract_meta(src_path):
    try:
        import json
        doc = json.loads(_pandoc(["-f","docx","-t","json",src_path]).decode("utf-8"))
        meta = doc.get("meta", {})
        def flat(node):
            if isinstance(node, dict):
                t = node.get("t")
                if t == "MetaInlines": return "".join(flat(x) for x in node.get("c", []))
                if t == "Str": return node.get("c", "")
                if t == "Space": return " "
                return "".join(flat(v) for v in node.values() if isinstance(v,(list,dict)))
            if isinstance(node, list): return "".join(flat(x) for x in node)
            return ""
        out = {k: flat(v) for k, v in meta.items()}
        return {"title": out.get("title",""), "author": out.get("author",""),
                "publisher": out.get("publisher",""), "copyright_year": out.get("date","")}
    except Exception:
        return {"title":"","author":"","publisher":"","copyright_year":""}


def _override_style(ov):
    if not ov: return ""
    css = []
    if ov.get("align") in ("left","right","center","justify"): css.append(f"text-align:{ov['align']}")
    if ov.get("keep_with_next"): css.append("break-after:avoid")
    if ov.get("letter_spacing") is not None: css.append(f"letter-spacing:{ov['letter_spacing']}em")
    if ov.get("margin_top") is not None: css.append(f"margin-top:{ov['margin_top']}em")
    return f' style="{";".join(css)}"' if css else ""


def _css_str(text):
    return text.replace("\\","\\\\").replace("'","\\'")


def _front_matter_html(meta, settings):
    title = meta.get("title") or settings.get("title") or "Untitled"
    author = meta.get("author") or settings.get("author") or ""
    publisher = meta.get("publisher") or settings.get("publisher") or ""
    year = meta.get("copyright_year") or settings.get("copyright_year") or ""
    lines = []
    if year or author:
        lines.append(f"Copyright © {html.escape(str(year))} {html.escape(author)}".strip())
    lines.append("All rights reserved.")
    if publisher: lines.append(html.escape(publisher))
    lines.append("No part of this book may be reproduced in any form without written permission from the author.")
    cp = "".join(f"<p>{l}</p>" for l in lines)
    pub = f'<div class="tp-pub">{html.escape(publisher)}</div>' if publisher else ""
    return f"""
    <div class="frontmatter">
      <div class="half-title"><h1>{html.escape(title)}</h1></div>
      <div class="title-page">
        <div class="tp-title">{html.escape(title)}</div>
        <div class="tp-author">{html.escape(author)}</div>
        {pub}
      </div>
      <div class="copyright-page">{cp}</div>
    </div>"""


def _block_html(block, settings, is_first_para):
    t = block.get("type"); ov = block.get("overrides", {}); style = _override_style(ov)
    if t == "heading":
        lvl = block.get("level", 2)
        return f'<h{lvl} class="subhead"{style}>{html.escape(block.get("text",""))}</h{lvl}>'
    if t == "paragraph":
        cls = ' class="first"' if is_first_para else ""
        content = block.get("html","")
        if is_first_para and settings.get("drop_cap"):
            content = _inject_dropcap(content)
        return f'<p{cls}{style}>{content}</p>'
    if t == "image":
        width = ov.get("width"); wstyle = f' style="width:{width}"' if width else ""
        cap = block.get("caption",""); caphtml = f'<figcaption>{html.escape(cap)}</figcaption>' if cap else ""
        return (f'<figure class="img"{style}><img src="{html.escape(block.get("src",""))}" '
                f'alt="{html.escape(block.get("alt",""))}"{wstyle}/>{caphtml}</figure>')
    if t == "table":
        return f'<div class="table"{style}>{block.get("html","")}</div>'
    if t == "scene_break":
        return f'<p class="scene-break">{html.escape(settings.get("scene_break","* * *"))}</p>'
    if t == "pagebreak":
        return '<div style="break-after:page"></div>'
    if t == "rich":
        return f'<div class="rich"{style}>{block.get("html","")}</div>'
    return ""


def _chapter_html(idx, chapter, settings):
    title = chapter.get("title",""); style = settings["chapter_style"]; ornament = settings["chapter_ornament"]
    opener = ['<div class="chap-opener">']
    if title:
        if style == "modern_number":
            opener.append(f'<div class="chap-num">{idx}</div>')
        else:
            opener.append(f'<div class="chap-num">{html.escape("Chapter " + str(idx))}</div>')
        opener.append(f'<h2 class="chap-title">{html.escape(title)}</h2>')
        if ornament:
            opener.append(f'<div class="chap-ornament">{html.escape(ornament)}</div>')
    opener.append("</div>")
    first_done = False; body = []
    for b in chapter.get("blocks", []):
        is_first = (b.get("type") == "paragraph" and not first_done)
        if is_first: first_done = True
        body.append(_block_html(b, settings, is_first))
    chap_title_css = f'<div style="string-set: chaptitle \'{_css_str(title)}\';"></div>'
    return f'<section class="chapter">{chap_title_css}{"".join(opener)}{"".join(body)}</section>'


def render_html(book, settings, css):
    meta = book.get("meta", {})
    title = meta.get("title") or settings.get("title") or "Untitled"
    parts = [_front_matter_html(meta, settings)]
    idx = 0
    for ch in book.get("chapters", []):
        if ch.get("title"):
            idx += 1
            parts.append(_chapter_html(idx, ch, settings))
        else:
            first_done = False; body = []
            for b in ch.get("blocks", []):
                is_first = (b.get("type") == "paragraph" and not first_done)
                if is_first: first_done = True
                body.append(_block_html(b, settings, is_first))
            parts.append(f'<section class="chapter">{"".join(body)}</section>')
    booktitle_css = f"body {{ string-set: booktitle '{_css_str(title)}'; }}"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
{css}
{booktitle_css}
</style></head><body>
{''.join(parts)}
</body></html>"""


import re as _re_dc
def _inject_dropcap(html_content):
    # wrap the first visible letter (after any leading tags/opening quote) in a span
    m = _re_dc.match(r'^(\s*(?:<[^>]+>\s*)*["\u201c\u2018\']?)([A-Za-z])', html_content)
    if not m:
        return html_content
    pre, letter = m.group(1), m.group(2)
    rest = html_content[m.end():]
    return f'{pre}<span class="dropcap">{letter}</span>{rest}'
