# Hamro Gahana

Mobile jewellery discovery PWA for Nepal, implemented with Flask, SQLAlchemy, PostgreSQL/PostGIS, Jinja, HTMX, Alpine CSP, Leaflet and FFmpeg. The approved V9 prototype is preserved in `reference/approved-v9.html`; production pages use server-rendered templates and persisted domain models.

**Release status: source implementation delivered; not certified production-ready.** Read `docs/VERIFICATION.md` before deployment. PostgreSQL integration, Docker startup and live end-to-end workflows could not run in the authoring environment. Do not treat skipped tests as passing.

## Windows Docker Desktop or Ubuntu Docker Compose

Use Docker Desktop in Linux-container mode on Windows. On Ubuntu, install Docker Engine and the Compose plugin from Docker's official packages first.

From the extracted repository directory:

```sh
cp .env.example .env
```

PowerShell equivalent:

```powershell
Copy-Item .env.example .env
```

Edit `.env`: replace SECRET_KEY and POSTGRES_PASSWORD with separate random hex values. Generate each with `python -c "import secrets; print(secrets.token_hex(32))"`. Keep `COOKIE_SECURE=0` only for local HTTP. Set a real contact email in GEOCODER_AGENT, or leave it blank to disable address search while retaining manual coordinates/maps.

```sh
docker compose build
docker compose up -d db
docker compose run --rm app python -m flask --app wsgi db upgrade
docker compose run --rm app python -m flask --app wsgi seed
docker compose run --rm app python -m flask --app wsgi create-admin
docker compose up -d
```

`seed` prompts for initial pure gold and silver rates; these are operator-supplied values, not downloaded market data. `create-admin` prompts for phone/name and a password twice. There are no default login credentials. Open http://localhost:8080 . Register a merchant at `/register`, then use `/admin/login` to verify it. Create a product, upload an image, publish it and inspect it publicly. Upgrade requests need payment evidence and admin review. Free stores have no reel or featured entitlement.

## Store browsing and media

Open a store to search its published jewellery, sort by price or newest and browse every page. Admins can click store and product names in their workspace to inspect details across all statuses. Image and reel previews open inside the app.

Images convert automatically to resized WebP variants. Supported reels (including MOV and WebM) convert in the worker to compressed 720×1280 H.264/AAC MP4 with a thumbnail; orientation is applied and landscape clips are padded. Limits: 10 MB images, 100 MB reels, 5–60 second videos. A running worker is required for reel processing. Format support depends on the bundled Pillow/FFmpeg decoders.

## Run the remaining tests

Create a separate test database once (do not point tests at your application database):

```sh
docker compose exec db createdb -U hamro hamro_test
docker compose -f compose.yaml -f compose.test.yaml run --rm tests
```

The integration fixture creates a uniquely named schema per test and drops that test schema afterward. It requires permission to install PostGIS, pg_trgm and btree_gist. Concurrent tests use separate connections against the same test schema. The CI workflow uses the same PostgreSQL/PostGIS family.

For browser checks, with the application running:

```sh
npm install
npx playwright install chromium
npm run test:e2e
```

The suite targets http://localhost:8080 by default, at 390×844 and 360×800. To target a staging HTTPS host, set BASE_URL in your shell (`$env:BASE_URL='https://your-domain'` in PowerShell; `export BASE_URL=https://your-domain` on Ubuntu). The supplied browser suite covers public navigation, theme persistence, manual location, access gates and PWA assets. Use `docs/ACCEPTANCE.md` for the remaining authenticated/browser/device checks; they are not implied by that small suite.

## Python development without Docker

Install Python 3.12+, PostgreSQL 16 with PostGIS and FFmpeg on your machine. Create a database and user; the first migration needs permission to create extensions.

```sh
python -m venv .venv
# Ubuntu: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set environment variables: `SECRET_KEY`, `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/hamro`, `COOKIE_SECURE=0`. The app does not silently load `.env` outside Compose; export values in your shell. Then:

```sh
python -m flask --app wsgi db upgrade
python -m flask --app wsgi seed
python -m flask --app wsgi create-admin
python -m flask --app wsgi run --host 127.0.0.1 --port 8000
```

Run `python -m flask --app wsgi worker` in a second terminal. Without the worker, reels remain queued. `python -m pytest -q` runs unit checks and explicitly skips database tests unless TEST_DATABASE_URL is set. `python -m ruff check app tests` runs lint checks.

## Production and maintenance

See `docs/DEPLOYMENT.md` for Ubuntu HTTPS, storage, backup/restore and troubleshooting. See `docs/ARCHITECTURE.md` for service boundaries, quota/ranking policies, maps and extension guidance. `docs/ENDPOINTS.md` lists routes. `docs/schema.sql` is the frozen initial DDL; migrations are authoritative. `docs/IMPLEMENTATION_PLAN.md` maps requirements to components.
