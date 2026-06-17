# Book Formatter worker — run it locally (free, no host, no tunnel)

The worker **polls** Supabase for work and writes results back. It only needs
*outbound* internet, so there is **no tunnel and no public URL** to set up. Run it
on your machine while you test; close it when you're done. Reps can't use it until
it lives on an always-on host, but for prototyping this is all you need.

## What it does

While running, it watches the Hub Supabase project and:
- picks up book projects marked **importing** → parses the uploaded manuscript into
  the editable block model → marks them **ready**;
- picks up render jobs marked **queued** → builds the PDF + EPUB → uploads them to
  the `formatted` storage bucket → marks the job **done**.

That's the whole loop. The Hub UI just creates the projects/jobs; this does the work.

## One secret you need

The worker uses your Supabase **service role key**. Get it at:
Supabase Dashboard → your project → **Project Settings → API → `service_role`**.

Keep it private — it bypasses row security. Do not paste it into chat or commit it.
Set it as an environment variable only.

## Run it (Python)

```bash
cd book-formatter-worker
pip install -r requirements.txt          # needs system pandoc + WeasyPrint libs (see Docker option if missing)

export SUPABASE_URL="https://tgfoylcsdxqfmyfcnrkc.supabase.co"
export SUPABASE_SERVICE_KEY="paste-your-service-role-key"
python worker_loop.py
```

You'll see `book-formatter worker polling ... every 4s`. Leave it running and use
the Hub UI in your browser. Each import/render prints a line here.

## Run it (Docker — easiest, no local pandoc/WeasyPrint needed)

```bash
cd book-formatter-worker
docker build -t book-formatter-worker .
docker run --rm \
  -e SUPABASE_URL="https://tgfoylcsdxqfmyfcnrkc.supabase.co" \
  -e SUPABASE_SERVICE_KEY="paste-your-service-role-key" \
  book-formatter-worker
```

The image bundles pandoc, WeasyPrint, and the book fonts, so it "just runs."

## When you want reps to use it

Run the *same* image on any small always-on host (Render / Railway / Fly / an SPS
box) with the same two env vars. Nothing else changes — same polling worker.

## Optional: HTTP mode

`app.py` exposes `/import`, `/render`, `/themes`, `/health` for manual testing or a
future push-based deployment. Run it with:
`uvicorn app:app --host 0.0.0.0 --port 8080`. Not needed for the polling loop.
