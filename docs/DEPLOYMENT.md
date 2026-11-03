# Ubuntu VPS deployment

## Before public launch

Run the full PostgreSQL and browser acceptance checks first. Configure a real domain and DNS A record pointing at the VPS. Keep PostgreSQL internal to the Compose network. Keep `.env` out of source control, mode 600 on Ubuntu. Back up both the database and the media volume; neither is recoverable from the source archive.

## Domain and HTTPS: hamrogahana.com

This setup assumes an Ubuntu VPS with Docker Compose and **host Nginx** handling public ports 80/443. Hamro Gahana listens only on **127.0.0.1:8082**, leaving your apps on 8080 and 8081 alone. Traffic flows from HTTPS on the host Nginx to the loopback port, through container Nginx to Flask. TLS certificates live on the host.

If an existing host Nginx already serves your other apps, add this virtual host to it. If Apache, Caddy, Traefik or a container proxy already owns 80/443, integrate this domain with that proxy instead of starting another listener. A container proxy cannot reach the host using its own `127.0.0.1`; the supplied configuration is for host Nginx.

### 1. Point the domain at the VPS

In your DNS provider's dashboard, create:

| Type | Name | Value |
| --- | --- | --- |
| A | @ | Your VPS public IPv4 address |
| CNAME | www | hamrogahana.com |

Only add an AAAA record if IPv6 actually reaches this VPS and its firewall allows HTTP/HTTPS over IPv6. Remove incorrect or stale AAAA records. Wait for DNS propagation, then check from your computer:

```sh
dig +short hamrogahana.com A
dig +short hamrogahana.com AAAA
dig +short www.hamrogahana.com
```

Both names must resolve correctly before requesting a certificate for both. If you do not want `www`, omit its DNS record, remove it from `server_name` in the supplied config and omit its `-d` certificate argument. When using Cloudflare, use DNS-only mode during initial setup; after certification, use Full (strict) if enabling its proxy.

### 2. Configure and start the app

From your project directory on the VPS, create `.env` from `.env.example` only if it does not already exist. Preserve existing secrets and database passwords when upgrading. Set:

```dotenv
APP_PORT=8082
COOKIE_SECURE=1
```

Set real SECRET_KEY, POSTGRES_PASSWORD and GEOCODER_AGENT values as described in README. Check that 8082 is free with `sudo ss -ltnp 'sport = :8082'`. If occupied, choose another port in `.env` and change `proxy_pass` in `deploy/hamrogahana.com.conf` to match. Keep the Compose binding on `127.0.0.1`.

```sh
chmod 600 .env
docker compose build
docker compose up -d db
docker compose run --rm app python -m flask --app wsgi db upgrade
```

On a **new installation only**, run the configuration seed and create your administrator:

```sh
docker compose run --rm app python -m flask --app wsgi seed
docker compose run --rm app python -m flask --app wsgi create-admin
```

Then start the services and check the internal endpoint:

```sh
docker compose up -d
curl --fail http://127.0.0.1:8082/health
```

A successful health response is JSON with `status: ok`. The rate scheduler is included in Compose. Secure cookies require the final HTTPS address for login; do not log in through the internal HTTP port in production.

### 3. Add the host Nginx virtual host

Install Nginx if it is not already present:

```sh
sudo apt update
sudo apt install nginx
```

Copy the supplied configuration from the project directory, enable it, validate all host configs, and reload:

```sh
sudo cp deploy/hamrogahana.com.conf /etc/nginx/sites-available/hamrogahana.com
sudo ln -s /etc/nginx/sites-available/hamrogahana.com /etc/nginx/sites-enabled/hamrogahana.com
sudo nginx -t
sudo systemctl reload nginx
```

If `sudo nginx -t` reports `could not build server_names_hash ... server_names_hash_bucket_size: 32`, edit the host's main configuration:

```sh
sudo nano /etc/nginx/nginx.conf
```

Inside the existing `http { ... }` block, add or uncomment this directive (replace an existing value rather than adding a duplicate):

```nginx
server_names_hash_bucket_size 64;
```

This is an `http`-level setting, not a directive for the domain's `server` block. If the same error remains at 64, increase it to 128. Save and validate before reloading:

```sh
sudo nginx -t && sudo systemctl reload nginx
```

Do not reload if validation fails. See [Nginx server name hash guidance](https://nginx.org/en/docs/http/server_names.html#optimization).

Create the symlink only once. If this domain already has a virtual host, update that configuration instead of creating a duplicate. Keep other apps' virtual hosts and listeners in place.

Allow inbound TCP **80 and 443** in your VPS provider's firewall. If UFW is already enabled, allow Nginx with `sudo ufw allow 'Nginx Full'`. Preserve your SSH rule; do not enable a new firewall blindly on a remote server. Do not open 8082 or PostgreSQL publicly.

```sh
curl --fail http://hamrogahana.com/health
```

The internal Nginx config preserves the trusted host proxy's HTTPS and client-IP headers. The host proxy overwrites headers supplied by public visitors. Flask's existing ProxyFix trusts the resulting single value. Keep this trust boundary if adapting the setup to another proxy.

### 4. Issue and install the HTTPS certificate

If Certbot is already installed, keep your existing installation method. Otherwise install the recommended snap version (install `snapd` first if missing):

```sh
sudo snap install --classic certbot
sudo /snap/bin/certbot --nginx --redirect -d hamrogahana.com -d www.hamrogahana.com
```

Enter your certificate contact email and accept the terms when prompted. Certbot verifies the domain over port 80, installs the certificate in the matching Nginx virtual host, configures HTTPS and redirects HTTP traffic to HTTPS. Both hostnames serve the app. Certificates do not need to be mounted into Docker.

```sh
sudo nginx -t
curl --fail https://hamrogahana.com/health
curl -I http://hamrogahana.com
curl -I https://hamrogahana.com
sudo /snap/bin/certbot renew --dry-run
systemctl list-timers --all | rg certbot
```

Use `grep certbot` instead of `rg certbot` if ripgrep is not installed. For an existing package-based Certbot, use `sudo certbot` instead of `/snap/bin/certbot`. The snap sets up automatic renewal; confirm its timer and the dry-run result. Keep port 80 reachable for later HTTP validation. Check the domain, certificate expiry, HTTPS login, uploads, maps, notification inbox and Android/iPhone installation before launch.

If issuance fails, check DNS (including AAAA), both firewall layers, port 80 reachability, and `sudo nginx -t`. If other applications redirect this domain, check for duplicate server names. For HTTPS login/CSRF problems, verify `COOKIE_SECURE=1`, recreate the app after changing `.env`, and ensure both proxies use the supplied forwarding headers.

Official references: [Certbot Nginx instructions](https://certbot.eff.org/instructions?os=snap&ws=nginx), [Nginx reverse proxy documentation](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).

## Routine deployment

```sh
docker compose build
docker compose run --rm app python -m flask --app wsgi db upgrade
docker compose up -d
docker compose logs --tail=100 app worker rates nginx
```

Take a backup before migrations. Bump `app/static/js/sw.js` VERSION when changing cached assets. No automatic down-migration on failure: inspect migration output, restore backups if necessary, and do not repeatedly restart against a broken schema.

## Backups (works without shell binary redirection in PowerShell)

```sh
docker compose exec db pg_dump -U hamro -d hamro -Fc -f /tmp/hamro.dump
docker compose cp db:/tmp/hamro.dump ./hamro.dump
docker compose exec app tar -czf /tmp/media.tar.gz -C /data media
docker compose cp app:/tmp/media.tar.gz ./media.tar.gz
```

For a consistent snapshot, stop app, worker and rates writes first, or use a maintenance window and database/filesystem snapshot strategy. Encrypt backups and move them off the VPS. Test restoration periodically. Evidence files may contain private business information.

Restore into a fresh database and media volume during a maintenance window. The following destroys existing database objects: use only on the intended restore target after taking a backup.

```sh
docker compose stop app worker rates
docker compose cp ./hamro.dump db:/tmp/hamro.dump
docker compose exec db pg_restore -U hamro -d hamro --clean --if-exists --no-owner /tmp/hamro.dump
docker compose cp ./media.tar.gz app:/tmp/media.tar.gz
```

Because `docker compose cp` targets an existing stopped container, it can copy the archive while app is stopped. Restore the archive using a one-off app container sharing the media volume; a direct mount is portable:

```sh
docker compose run --rm -v ./media.tar.gz:/tmp/restore.tar.gz:ro app tar -xzf /tmp/restore.tar.gz -C /data
docker compose up -d app worker rates
```

On Windows replace the bind source with an absolute Docker Desktop-accessible path if needed. Keep the original application SECRET_KEY if preserving active sessions is intended; rotate it to revoke all sessions after a security incident.

## Worker and cleanup

Run one worker initially. PostgreSQL SKIP LOCKED supports more workers, but each video can use substantial RAM/CPU. The Compose worker is limited to two CPUs and 1.5 GB RAM. Benchmark on your actual VPS before increasing concurrency. Maximum transcode timeout is ten minutes; lease expiry is fifteen minutes. Crashed jobs are reclaimed. Failed jobs report their error; a merchant can re-upload a corrected video. Schedule `docker compose run --rm app python -m flask --app wsgi cleanup` daily using cron/systemd. This removes only old unreferenced files and expired counters/tokens, not audit records or referenced evidence.

## Troubleshooting

- `SECRET_KEY` startup error: supply a random key of at least 32 characters; do not use an example in production.
- Login succeeds but does not persist on localhost: local HTTP needs COOKIE_SECURE=0. Production HTTPS needs 1.
- `relation does not exist`: apply migrations before starting web/worker.
- Extension permission error: have the database administrator install PostGIS, pg_trgm and btree_gist or temporarily run the migration with the appropriate role.
- Reels stay queued: inspect worker logs; confirm shared media volume, ffmpeg availability and database connectivity.
- Reel fails validation: export upright H.264 MP4 in 9:16 without rotation metadata, 5–60 seconds, max 100 MB. 2160×3840 is the maximum accepted source resolution.
- Upload 413: both Flask and Nginx cap requests; individual videos cap at 100 MB, images/evidence at 10 MB.
- Address search 503: GEOCODER_AGENT is unset, provider failed, or contact details are invalid. Manual coordinates remain available.
- Geocoding 429: public service is globally limited; retry later or use a self-hosted geocoder. Do not add autocomplete.
- Map shows a blocked tile: verify provider eligibility, attribution/referrer policies and network environment; configure an appropriate TILE_URL. Do not bypass provider restrictions.
- Product not public: verify store status, product status, image state and plan allowance. Saved products hide unavailable listings.
- Install button absent: browser support varies; use the browser's install/Add to Home Screen flow. PWA installation needs HTTPS or localhost.
