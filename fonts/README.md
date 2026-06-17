# Book fonts

The Dockerfile bundles these into the image (`COPY fonts/`). All are free/OFL and
embeddable in KDP/IngramSpark PDFs.

- **Body:** EB Garamond, Lora, Merriweather, Libre Baskerville, Source Serif 4
- **Headings (sans):** Montserrat, Lato

The `.ttf` files are **not committed** (binary). Populate this folder once on the
build machine before `docker compose up -d --build`:

```bash
cd book-formatter-worker/fonts && bash fetch_fonts.sh
```

If no TTFs are present at build time, the image still builds and renders — it just
falls back to the system serif/sans (DejaVu). Output is valid; typography is
slightly off until the real faces are added.
