"""
worker_loop.py — self-contained Book Formatter worker (no n8n, no inbound).

It POLLS Supabase for work and writes results back, so it only needs OUTBOUND
internet + a Supabase service key. Run it anywhere (your laptop for testing, a
small host for production). No tunnel, no public URL required.

Two queues:
  - book_projects.status = 'importing'  -> download docx, parse to block model,
                                           write book_model + status='ready'
  - format_jobs.status   = 'queued'     -> render model+settings, upload PDF/EPUB
                                           to the 'formatted' bucket, mark 'done'

Env:
  SUPABASE_URL          e.g. https://tgfoylcsdxqfmyfcnrkc.supabase.co
  SUPABASE_SERVICE_KEY  service_role key (Dashboard > Project Settings > API)
  POLL_INTERVAL         seconds between polls (default 4)
"""

import os
import time
import tempfile
import traceback
from datetime import datetime, timezone

from supabase import create_client

from engine import render_book, resolve_settings, model as M

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
POLL = float(os.environ.get("POLL_INTERVAL", "4"))
MANUSCRIPTS = "manuscripts"
FORMATTED = "formatted"

sb = create_client(SUPABASE_URL, SERVICE_KEY)


def _now():
    return datetime.now(timezone.utc).isoformat()


def process_imports():
    rows = (sb.table("book_projects")
            .select("id, source_path, title, author, publisher, copyright_year")
            .eq("status", "importing").limit(5).execute()).data or []
    for p in rows:
        pid = p["id"]
        try:
            if not p.get("source_path"):
                raise RuntimeError("no source_path on project")
            blob = sb.storage.from_(MANUSCRIPTS).download(p["source_path"])
            ext = os.path.splitext(p["source_path"])[1].lower() or ".docx"
            with tempfile.TemporaryDirectory() as tmp:
                src = os.path.join(tmp, f"manuscript{ext}")
                with open(src, "wb") as f:
                    f.write(blob)
                book = M.import_book(
                    src, os.path.join(tmp, "media"),
                    meta_overrides={
                        "title": p.get("title", ""), "author": p.get("author", ""),
                        "publisher": p.get("publisher", ""),
                        "copyright_year": p.get("copyright_year", ""),
                    },
                    inline_images=True,
                )
            sb.table("book_projects").update(
                {"book_model": book, "status": "ready", "error": None}
            ).eq("id", pid).execute()
            print(f"[import] {pid} -> ready ({sum(len(c['blocks']) for c in book['chapters'])} blocks)")
        except Exception as e:
            traceback.print_exc()
            sb.table("book_projects").update(
                {"status": "error", "error": str(e)[:500]}
            ).eq("id", pid).execute()
            print(f"[import] {pid} -> error: {e}")


def process_renders():
    jobs = (sb.table("format_jobs")
            .select("id, book_project_id, settings_snapshot")
            .eq("status", "queued").limit(5).execute()).data or []
    for j in jobs:
        jid, pid = j["id"], j["book_project_id"]
        try:
            sb.table("format_jobs").update({"status": "running"}).eq("id", jid).execute()
            proj = (sb.table("book_projects").select("book_model")
                    .eq("id", pid).single().execute()).data
            book = proj["book_model"]
            if not book or "chapters" not in book:
                raise RuntimeError("project has no parsed book_model yet")
            overrides = j.get("settings_snapshot") or {}
            settings = resolve_settings(overrides.get("theme"), overrides)
            with tempfile.TemporaryDirectory() as tmp:
                res = render_book(None, settings, tmp, make_epub=True, book=book)
                pdf = open(res["pdf"], "rb").read()
                epub = open(res["epub"], "rb").read()
            pdf_path = f"{pid}/{jid}.pdf"
            epub_path = f"{pid}/{jid}.epub"
            sb.storage.from_(FORMATTED).upload(
                pdf_path, pdf, {"content-type": "application/pdf", "upsert": "true"})
            sb.storage.from_(FORMATTED).upload(
                epub_path, epub, {"content-type": "application/epub+zip", "upsert": "true"})
            sb.table("format_jobs").update({
                "status": "done", "pdf_path": pdf_path, "epub_path": epub_path,
                "error": None, "finished_at": _now(),
            }).eq("id", jid).execute()
            print(f"[render] job {jid} -> done ({len(pdf)}B pdf, {len(epub)}B epub)")
        except Exception as e:
            traceback.print_exc()
            sb.table("format_jobs").update(
                {"status": "error", "error": str(e)[:500], "finished_at": _now()}
            ).eq("id", jid).execute()
            print(f"[render] job {jid} -> error: {e}")


def main():
    print(f"book-formatter worker polling {SUPABASE_URL} every {POLL}s ...")
    while True:
        try:
            process_imports()
            process_renders()
        except Exception:
            traceback.print_exc()
        time.sleep(POLL)


if __name__ == "__main__":
    main()
