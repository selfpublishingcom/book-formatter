# Deploy the Book Formatter worker on your Hostinger VPS

One-time setup. After this, the worker runs continuously (restarts on crash and on
reboot) and processes every import/render job — nothing to start each session.

It only makes **outbound** calls to Supabase, so no ports or firewall changes are
needed.

## 0. What you need
- SSH access to the VPS (Hostinger hPanel → VPS → "SSH access" shows host/IP, user, password — or use the browser terminal).
- Your Supabase **service_role key**: Supabase → Project Settings → API → `service_role`. Keep it private; it goes only in the VPS `.env` file (never in chat or git).

## 1. Get the worker folder onto the VPS
Pick whichever is easiest:

**A. Upload via Hostinger File Manager** — zip the `book-formatter-worker` folder on your PC, upload it through hPanel's file manager, and unzip it (e.g. into `/opt/book-formatter-worker`).

**B. Copy with scp from your PC** (PowerShell):
```
scp -r "D:\Apps\Agent Dev\projects\hub\book-formatter-worker" root@YOUR_VPS_IP:/opt/
```

Either way you should end up with `/opt/book-formatter-worker` containing `Dockerfile`, `docker-compose.yml`, `engine/`, `worker_loop.py`, `fonts/`, etc.

## 2. Install Docker (skip if already installed)
SSH in, then:
```
docker --version || curl -fsSL https://get.docker.com | sh
```

## 3. Add your settings
```
cd /opt/book-formatter-worker
cp .env.example .env
nano .env          # paste your service_role key into SUPABASE_SERVICE_KEY, save (Ctrl+O, Enter, Ctrl+X)
```

## 4. Build and start it
```
docker compose up -d --build
```
First build takes a few minutes (it installs pandoc + WeasyPrint + fonts once).

## 5. Confirm it's working
```
docker compose logs -f
```
You should see `book-formatter worker polling https://...supabase.co every 4s ...`,
then within seconds a line like `[import] <id> -> ready (N blocks)` as it picks up
your queued "Claw and Steel" job. Press Ctrl+C to stop watching logs (the worker
keeps running).

## Done
The worker now runs forever. Re-uploading the folder + `docker compose up -d --build`
redeploys after any code change. To stop: `docker compose down`.

## Updating the service key or settings
Edit `.env`, then `docker compose up -d` (no rebuild needed).
