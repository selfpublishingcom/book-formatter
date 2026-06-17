"""
app.py — FastAPI render worker for the Book Formatter.

Endpoints:
  GET  /health   liveness
  GET  /themes   theme list for the UI picker
  POST /import   multipart: file (.docx/.md) + optional title/author/publisher/year
                 -> { book_model }   (images inlined as data: URIs, self-contained)
  POST /render   JSON: { book_model, settings, make_epub } -> { pdf_base64, epub_base64 }
  POST /format   multipart one-shot (file -> pdf+epub); kept for quick tests

Stateless pure compute (no DB/Storage creds). n8n downloads inputs from Supabase,
calls these endpoints, and writes outputs back to Storage / the row.
"""

import base64
import io
import json
import os
import tempfile
import zipfile

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import JSONResponse, StreamingResponse

from engine import render_book, list_themes, resolve_settings, model as M

app = FastAPI(title="Book Formatter Worker", version="1.1")

MAX_BYTES = 60 * 1024 * 1024
ALLOWED_EXT = {".docx", ".md", ".markdown", ".html", ".htm", ".txt"}


@app.get("/health")
def health():
    return {"ok": True, "service": "book-formatter-worker", "version": "1.1"}


@app.get("/themes")
def themes():
    return {"themes": list_themes()}


@app.post("/import")
async def import_manuscript(
    file: UploadFile = File(...),
    title: str = Form(""),
    author: str = Form(""),
    publisher: str = Form(""),
    copyright_year: str = Form(""),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"unsupported file type '{ext}'")
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "file too large")

    meta_overrides = {"title": title, "author": author,
                      "publisher": publisher, "copyright_year": copyright_year}
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, f"manuscript{ext}")
        with open(src, "wb") as f:
            f.write(raw)
        try:
            book = M.import_book(src, os.path.join(tmp, "media"),
                                 meta_overrides=meta_overrides, inline_images=True)
        except Exception as e:
            raise HTTPException(500, f"import failed: {e}")
    return JSONResponse({"book_model": book})


@app.post("/render")
async def render(payload: dict = Body(...)):
    book = payload.get("book_model")
    if not isinstance(book, dict) or "chapters" not in book:
        raise HTTPException(400, "book_model (with chapters) is required")
    overrides = payload.get("settings") or {}
    make_epub = payload.get("make_epub", True)
    settings = resolve_settings(overrides.get("theme"), overrides)

    with tempfile.TemporaryDirectory() as tmp:
        try:
            result = render_book(None, settings, tmp, make_epub=make_epub, book=book)
        except Exception as e:
            raise HTTPException(500, f"render failed: {e}")
        pdf_bytes = open(result["pdf"], "rb").read()
        epub_bytes = open(result["epub"], "rb").read() if "epub" in result else b""

    return JSONResponse({
        "settings": settings,
        "pdf_base64": base64.b64encode(pdf_bytes).decode(),
        "epub_base64": base64.b64encode(epub_bytes).decode() if epub_bytes else None,
    })


@app.post("/format")
async def format_book(
    file: UploadFile = File(...),
    theme: str = Form("classic"),
    settings: str = Form("{}"),
    output: str = Form("json"),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"unsupported file type '{ext}'")
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "file too large")
    try:
        overrides = json.loads(settings) if settings else {}
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"settings is not valid JSON: {e}")
    resolved = resolve_settings(theme, overrides)

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, f"manuscript{ext}")
        with open(src, "wb") as f:
            f.write(raw)
        try:
            result = render_book(src, resolved, tmp, make_epub=True)
        except Exception as e:
            raise HTTPException(500, f"render failed: {e}")
        pdf_bytes = open(result["pdf"], "rb").read()
        epub_bytes = open(result["epub"], "rb").read() if "epub" in result else b""

    base = os.path.splitext(file.filename or "book")[0]
    if output == "zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"{base}.pdf", pdf_bytes)
            if epub_bytes:
                z.writestr(f"{base}.epub", epub_bytes)
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{base}.zip"'})

    return JSONResponse({
        "pdf_base64": base64.b64encode(pdf_bytes).decode(),
        "epub_base64": base64.b64encode(epub_bytes).decode() if epub_bytes else None,
    })
