FROM python:3.11-slim

# System deps: pandoc (EPUB + manuscript ingest) + WeasyPrint runtime libs
# (pango/cairo/gdk-pixbuf) + fontconfig.
RUN apt-get update && apt-get install -y --no-install-recommends \
        pandoc \
        libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
        libcairo2 libgdk-pixbuf-2.0-0 libffi-dev \
        fontconfig \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Bundle the v1 book fonts (all free, embeddable Google Fonts).
# Body: EB Garamond, Lora, Merriweather, Libre Baskerville, Source Serif 4.
# Headings: Montserrat, Lato.
COPY fonts/ /usr/share/fonts/book/
RUN find /usr/share/fonts/book -type f -size -1k -delete && fc-cache -f

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ ./engine/
COPY app.py worker_loop.py ./

# Default: run the polling worker (no inbound needed; only Supabase env required).
# To run the HTTP API instead (push mode / manual testing), override CMD with:
#   uvicorn app:app --host 0.0.0.0 --port 8080
CMD ["python", "worker_loop.py"]
