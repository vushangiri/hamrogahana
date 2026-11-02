# Ubuntu VPS deployment

## Before public launch

Run the full PostgreSQL and browser acceptance checks first. Configure a real domain and DNS A record pointing at the VPS. Keep PostgreSQL internal to the Compose network. Keep `.env` out of source control, mode 600 on Ubuntu. Back up both the database and the media volume; neither is recoverable from the source archive.

The default Compose publishes Nginx only on `127.0.0.1:8080`. For direct TLS in its Nginx container:

1. Stop any other service using ports 80/443, or integrate with your existing reverse proxy rather than conflicting with it.
2. Obtain a certificate using your ACME client, e.g. `sudo certbot certonly --standalone -d jewellery.example.com` when port 80 is free. Replace the example domain.
3. Copy `deploy/https.conf.example` to `deploy/nginx.conf`, replace all domain/certificate paths, and mount `/etc/letsencrypt:/etc/letsencrypt:ro` into the nginx service. Change its published ports to `80:80` and `443:443`.
4. Set `COOKIE_SECURE=1` in `.env`. Recreate app/worker/nginx with `docker compose up -d --build`.
5. Configure certificate renewal. For standalone renewal stop the TLS container only for the renewal challenge, renew, then restart it. Prefer a webroot challenge in ongoing production and mount the same webroot into Nginx. Reload Nginx after renewal: `docker compose exec nginx nginx -s reload`.
6. Verify HTTPS, HSTS, cookie flags, `/health`, installability and a full merchant/admin workflow before sending traffic.

If retaining an existing host Nginx/Certbot setup, use the default loopback port, add a TLS virtual host on the host proxy and explicitly propagate trusted HTTPS/client-IP headers through the internal Nginx. Do not blindly trust headers from public clients. The bundled configuration is for one trusted Nginx hop; adapt/test ProxyFix counts for any additional proxy.

## Routine deployment

```sh
docker compose build
docker compose run --rm app python -m flask --app wsgi db upgrade
docker compose up -d
docker compose logs --tail=100 app worker nginx
```

Take a backup before migrations. Bump `app/static/js/sw.js` VERSION when changing cached assets. No automatic down-migration on failure: inspect migration output, restore backups if necessary, and do not repeatedly restart against a broken schema.

## Backups (works without shell binary redirection in PowerShell)

```sh
docker compose exec db pg_dump -U hamro -d hamro -Fc -f /tmp/hamro.dump
docker compose cp db:/tmp/hamro.dump ./hamro.dump
docker compose exec app tar -czf /tmp/media.tar.gz -C /data media
docker compose cp app:/tmp/media.tar.gz ./media.tar.gz
```

For a consistent snapshot, stop app and worker writes first, or use a maintenance window and database/filesystem snapshot strategy. Encrypt backups and move them off the VPS. Test restoration periodically. Evidence files may contain private business information.

Restore into a fresh database and media volume during a maintenance window. The following destroys existing database objects: use only on the intended restore target after taking a backup.

```sh
docker compose stop app worker
docker compose cp ./hamro.dump db:/tmp/hamro.dump
docker compose exec db pg_restore -U hamro -d hamro --clean --if-exists --no-owner /tmp/hamro.dump
docker compose cp ./media.tar.gz app:/tmp/media.tar.gz
```

Because `docker compose cp` targets an existing stopped container, it can copy the archive while app is stopped. Restore the archive using a one-off app container sharing the media volume; a direct mount is portable:

```sh
docker compose run --rm -v ./media.tar.gz:/tmp/restore.tar.gz:ro app tar -xzf /tmp/restore.tar.gz -C /data
docker compose up -d app worker
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
