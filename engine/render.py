"""render.py — orchestration: book model + settings -> print PDF + EPUB."""
import os, subprocess, tempfile
from typing import Any, Dict
from weasyprint import HTML
from .themes import resolve_settings
from . import model as M

_PANDOC_MAJOR = None
def _pandoc_major():
    global _PANDOC_MAJOR
    if _PANDOC_MAJOR is None:
        try:
            out = subprocess.run(["pandoc","--version"],capture_output=True).stdout.decode()
            _PANDOC_MAJOR = int(out.split("\n",1)[0].split()[-1].split(".")[0])
        except Exception:
            _PANDOC_MAJOR = 2
    return _PANDOC_MAJOR

def _epub_split_args():
    return ["--split-level=1"] if _pandoc_major() >= 3 else ["--epub-chapter-level=1"]


def _css(s):
    tw, th = s["trim"]["w_in"], s["trim"]["h_in"]
    m = s["margins_in"]
    body_font = s["body_font"]; head_font = s["heading_font"]
    leading = s["leading"]; body_pt = s["body_pt"]; indent = s["indent_em"]
    justify = "justify" if s["justify"] else "left"
    hyphens = "auto" if s["hyphenate"] else "manual"
    rh_verso = 'string(booktitle)' if s["running_heads"] else '""'
    rh_recto = 'string(chaptitle)' if s["running_heads"] else '""'
    page_num = '' if s["page_numbers"] else 'content: none;'
    style = s["chapter_style"]
    if style == "modern_number":
        chap_css = f"""
        .chapter h2.chap-title {{ font-family:"{head_font}",sans-serif; font-weight:700;
            font-size:20pt; text-align:left; margin:0 0 1.5em 0; line-height:1.1; }}
        .chapter .chap-num {{ font-family:"{head_font}",sans-serif; font-weight:800;
            font-size:64pt; line-height:1; color:#111; margin:0 0 0.1em 0; }}"""
    elif style == "italic":
        chap_css = f"""
        .chapter h2.chap-title {{ font-family:"{head_font}",serif; font-style:italic;
            font-weight:400; font-size:22pt; text-align:center; margin:0 0 1.4em 0; }}
        .chapter .chap-num {{ font-family:"{head_font}",serif; font-style:italic;
            font-size:13pt; text-align:center; letter-spacing:0.15em; color:#444; margin:0 0 0.4em 0; }}"""
    else:
        chap_css = f"""
        .chapter h2.chap-title {{ font-family:"{head_font}",serif; font-weight:600;
            font-size:18pt; text-align:center; font-variant:small-caps; letter-spacing:0.06em;
            margin:0 0 1.4em 0; }}
        .chapter .chap-num {{ font-family:"{head_font}",serif; font-size:12pt; text-align:center;
            letter-spacing:0.25em; text-transform:uppercase; color:#555; margin:0 0 0.6em 0; }}"""
    drop_cap_css = ""
    if s["drop_cap"]:
        drop_cap_css = f"""
        .chapter p.first::first-letter {{ font-family:"{head_font}",serif; float:left;
            font-size:3.2em; line-height:0.66; padding:0.05em 0.16em 0 0; margin-top:0.04em; font-weight:600; }}"""
    ornament_css = ""
    if s["chapter_ornament"]:
        ornament_css = ".chapter .chap-ornament { text-align:center; font-size:14pt; color:#777; margin:0 0 1.6em 0; }"
    start_break = "right" if s["start_chapters_on"] == "right" else "auto"
    return f"""
    @page {{ size:{tw}in {th}in;
        margin:{m['top']}in {m['outside']}in {m['bottom']}in {m['inside']}in;
        @bottom-center {{ {page_num} content:counter(page); font-family:"{body_font}",serif;
            font-size:9.5pt; color:#333; }} }}
    @page :left {{ margin-left:{m['outside']}in; margin-right:{m['inside']}in;
        @top-left {{ content:{rh_verso}; font-family:"{body_font}",serif; font-size:8.5pt;
            font-style:italic; color:#555; text-transform:uppercase; letter-spacing:0.08em; }} }}
    @page :right {{ margin-left:{m['inside']}in; margin-right:{m['outside']}in;
        @top-right {{ content:{rh_recto}; font-family:"{body_font}",serif; font-size:8.5pt;
            font-style:italic; color:#555; text-transform:uppercase; letter-spacing:0.08em; }} }}
    @page front {{ @top-left {{ content:""; }} @top-right {{ content:""; }} @bottom-center {{ content:""; }} }}
    html {{ hyphens:{hyphens}; }}
    body {{ font-family:"{body_font}",serif; font-size:{body_pt}pt; line-height:{leading};
        text-align:{justify}; hyphens:{hyphens}; margin:0; }}
    .frontmatter {{ page:front; }}
    .half-title, .title-page {{ page-break-after:always; text-align:center; }}
    .half-title h1 {{ margin-top:33%; font-family:"{head_font}",serif; font-weight:500;
        font-size:18pt; font-variant:small-caps; letter-spacing:0.08em; }}
    .title-page .tp-title {{ margin-top:28%; font-family:"{head_font}",serif; font-weight:600;
        font-size:30pt; line-height:1.1; }}
    .title-page .tp-author {{ margin-top:1.6em; font-size:15pt; }}
    .title-page .tp-pub {{ margin-top:30%; font-size:10pt; color:#444; }}
    .copyright-page {{ page:front; page-break-after:always; font-size:9pt; color:#333; }}
    .copyright-page p {{ text-indent:0; margin:0.4em 0; text-align:left; }}
    .chapter {{ page:chapter; break-before:{start_break}; }}
    .chapter .chap-opener {{ padding-top:12%; margin-bottom:1.2em; }}
    {chap_css}
    {ornament_css}
    {drop_cap_css}
    h3.subhead {{ font-family:"{head_font}",serif; font-weight:600; font-size:13pt;
        text-align:left; margin:1.4em 0 0.4em 0; text-indent:0; }}
    p {{ margin:0; text-indent:{indent}em; orphans:2; widows:2; }}
    .chapter p.first, p.scene-break + p, h3.subhead + p {{ text-indent:0; }}
    .scene-break {{ text-align:center; text-indent:0; margin:1.2em 0; color:#777; letter-spacing:0.3em; }}
    figure.img {{ margin:1.2em 0; text-align:center; break-inside:avoid; }}
    figure.img img {{ max-width:100%; height:auto; }}
    figure.img figcaption {{ font-size:9pt; color:#555; font-style:italic; margin-top:0.4em; text-indent:0; }}
    .table {{ margin:1.2em 0; break-inside:avoid; }}
    .table table {{ width:100%; border-collapse:collapse; font-size:9.5pt; }}
    .table th, .table td {{ border:0.5pt solid #999; padding:4pt 6pt; text-align:left; text-indent:0; }}
    .table th {{ font-family:"{head_font}",serif; font-weight:700; background:#f2f2f2; }}
    .rich {{ text-indent:0; margin:0.8em 0; }}
    .rich ul, .rich ol {{ margin:0.6em 0 0.6em 1.6em; }}
    blockquote {{ margin:1em 1.4em; font-style:italic; text-indent:0; }}
    em {{ font-style:italic; }} strong {{ font-weight:700; }}
    """


def render_book(src_path, settings, out_dir, make_epub=True, book=None):
    if "trim" not in settings:
        settings = resolve_settings(settings.get("theme"), settings)
    os.makedirs(out_dir, exist_ok=True)
    media_dir = os.path.join(out_dir, "media")
    if book is None:
        book = M.import_book(src_path, media_dir)
    if book.get("settings"):
        merged = dict(book["settings"]); merged.update(settings); settings = merged
    css = _css(settings)
    doc_html = M.render_html(book, settings, css)
    base = os.path.splitext(os.path.basename(src_path or "book"))[0]
    pdf_path = os.path.join(out_dir, f"{base}.pdf")
    out = {"pdf": pdf_path, "book": book}
    HTML(string=doc_html, base_url=out_dir).write_pdf(pdf_path)
    if make_epub:
        epub_path = os.path.join(out_dir, f"{base}.epub")
        with tempfile.NamedTemporaryFile("w", suffix=".css", delete=False) as cf:
            cf.write(_epub_css(settings)); css_file = cf.name
        meta = book.get("meta", {})
        meta_args = []
        if meta.get("title") or settings.get("title"):
            meta_args += ["-M", f"title={meta.get('title') or settings.get('title')}"]
        if meta.get("author") or settings.get("author"):
            meta_args += ["-M", f"author={meta.get('author') or settings.get('author')}"]
        _pandoc_run(["-f","html","-t","epub3",*_epub_split_args(),"--resource-path",out_dir,
                     "--css",css_file,*meta_args,"-o",epub_path], input_bytes=doc_html.encode("utf-8"))
        os.unlink(css_file)
        out["epub"] = epub_path
    return out


def _epub_css(s):
    return f"""
    body {{ font-family:"{s['body_font']}",serif; line-height:{s['leading']}; }}
    h1,h2 {{ font-family:"{s['heading_font']}",sans-serif; text-align:center; }}
    p {{ text-indent:{s['indent_em']}em; margin:0; }}
    p.first, h1+p, h2+p, h3+p {{ text-indent:0; }}
    figure {{ text-align:center; margin:1em 0; }} img {{ max-width:100%; }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border:1px solid #999; padding:4px; }}
    .scene-break {{ text-align:center; text-indent:0; margin:1.2em 0; }}
    """


def _pandoc_run(args, input_bytes=None):
    proc = subprocess.run(["pandoc", *args], input=input_bytes, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"pandoc failed: {proc.stderr.decode('utf-8','replace')}")
    return proc.stdout
