# Deployment

Production runs on a single Ubuntu VM:

```
internet ──▶ nginx (:80/:443, TLS)  ──▶ gunicorn (127.0.0.1:8000) ──▶ Django
                    │
                    └─ /media/ served directly from /var/www/poseidon/media
```

- **gunicorn** runs the WSGI app (`config.wsgi:application`), managed by systemd.
- **nginx** terminates TLS and reverse-proxies everything to gunicorn.
- **WhiteNoise** serves `/static/` from within Django; **nginx** serves `/media/`
  (user uploads) directly from disk.

Files in this directory:

- `poseidon.service` — systemd unit for gunicorn
- `nginx-poseidon.conf` — nginx site config

Paths/users below assume the VM account `rooty` and project at
`/home/rooty/poseidon_anpassungs_katalog`. Adjust if yours differ.

---

## Configuration (`.env`)

Settings are env-driven (`config/settings.py` loads `.env`). Production `.env`:

```ini
DEBUG=False
SECRET_KEY=<generate one>            # uv run python -c "import secrets; print(secrets.token_urlsafe(50))"
ALLOWED_HOSTS=localhost,127.0.0.1,<VM_IP>,app.poseidon-klimaanpassung.de
CSRF_TRUSTED_ORIGINS=https://app.poseidon-klimaanpassung.de
# HTTPS=True                         # enable only AFTER TLS is set up (Phase 2)
MEDIA_ROOT=/var/www/poseidon/media   # uploads, served directly by nginx
# DATABASE_URL=postgres://user:pass@localhost:5432/poseidon   # omit to use SQLite
```

`HTTPS=True` turns on SSL redirect, secure cookies and HSTS. Leave it off until
certbot has installed a certificate, otherwise plain-HTTP access loops forever.

---

## Phase 1 — live over HTTP (by IP)

On the VM, from the project directory:

```bash
git pull
uv sync

# media lives outside the home dir so nginx can read it without home-dir perms
sudo mkdir -p /var/www/poseidon/media
sudo chown -R rooty:www-data /var/www/poseidon/media
sudo chmod 755 /var/www/poseidon
cp -a media/. /var/www/poseidon/media/ 2>/dev/null || true   # move existing uploads

uv run python manage.py collectstatic --noinput
uv run python manage.py migrate --noinput

# gunicorn service
sudo cp deploy/poseidon.service /etc/systemd/system/poseidon.service
sudo systemctl daemon-reload
sudo systemctl enable --now poseidon
sudo systemctl status poseidon          # expect "active (running)"

# nginx
sudo apt update && sudo apt install -y nginx
sudo cp deploy/nginx-poseidon.conf /etc/nginx/sites-available/poseidon
sudo ln -sf /etc/nginx/sites-available/poseidon /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Open inbound **TCP 80 and 443** in the cloud provider's firewall / security group
(the OS `ufw` is inactive, but the provider may still block them).

The site is now reachable at `http://<VM_IP>`. (Add the IP to `server_name` in the
nginx config during early testing.)

---

## Phase 2 — TLS / custom domain

1. Point DNS: add an **A record** `app.poseidon-klimaanpassung.de → <VM_IP>` and
   wait for it to resolve.
2. Issue a certificate (certbot rewrites the nginx config for 443 + auto-renew):
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d app.poseidon-klimaanpassung.de
   ```
3. Enable hardening: set `HTTPS=True` in `.env`, then `sudo systemctl restart poseidon`.

Live at `https://app.poseidon-klimaanpassung.de`.

---

## Updating a running deployment

```bash
cd ~/poseidon_anpassungs_katalog
git pull
uv sync
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput
sudo systemctl restart poseidon
```

## Operating

```bash
sudo systemctl status poseidon      # service state
sudo journalctl -u poseidon -f      # gunicorn / app logs
sudo systemctl reload nginx         # after editing nginx config
sudo tail -f /var/log/nginx/error.log
```

## Verifying media

```bash
curl -I http://<VM_IP>/media/<existing-file>   # 200 + "Server: nginx" = OK
```
