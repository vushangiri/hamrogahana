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

`seed` prompts for initial pure gold and silver rates; these are operator-supplied values, not downloaded market data. `create-admin` prompts for phone/name and a password twice. There are no default login credentials. Open http://localhost:8082 . Register a merchant at `/register`, then use `/admin/login` to verify it. Create a product, upload an image, publish it and inspect it publicly. Upgrade requests need payment evidence and admin review. Free stores have no reel or featured entitlement.

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

The suite targets http://localhost:8082 by default, at 390×844 and 360×800. To target a staging HTTPS host, set BASE_URL in your shell (`$env:BASE_URL='https://your-domain'` in PowerShell; `export BASE_URL=https://your-domain` on Ubuntu). The supplied browser suite covers public navigation, theme persistence, manual location, access gates and PWA assets. Use `docs/ACCEPTANCE.md` for the remaining authenticated/browser/device checks; they are not implied by that small suite.

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

The app now uses **127.0.0.1:8082** by default, leaving ports 8080 and 8081 available for your other apps. Set `APP_PORT` in `.env` to change it. For **hamrogahana.com**, follow the [VPS domain and HTTPS setup](docs/DEPLOYMENT.md); the ready-to-install host Nginx configuration is [deploy/hamrogahana.com.conf](deploy/hamrogahana.com.conf).

See `docs/DEPLOYMENT.md` for Ubuntu HTTPS, storage, backup/restore and troubleshooting. See `docs/ARCHITECTURE.md` for service boundaries, quota/ranking policies, maps and extension guidance. `docs/ENDPOINTS.md` lists routes. `docs/schema.sql` is the frozen initial DDL; migrations are authoritative. `docs/IMPLEMENTATION_PLAN.md` maps requirements to components.

## Daily rates, installation and notifications

Run the new migration before starting the updated app:

```sh
docker compose build app worker rates
docker compose run --rm app python -m flask --app wsgi db upgrade
docker compose up -d app worker rates
```

The `rates` service checks FENEGOSIDA every minute during 10:45–11:15 Asia/Kathmandu. It imports once per Nepal calendar day, retrying unavailable, incomplete or stale responses throughout that window. Keep this service running independently of media processing. Outside Docker, run `python -m flask --app wsgi rate-scheduler`. A stopped scheduler does not catch up outside the window; existing rates remain available. Errors are recorded in scheduler logs.

FENEGOSIDA's `todayBaseRatePerGram` field contains the labelled unit total. Only the Tola rows are imported. Internal gram pricing is derived from the Tola total using 1 Tola = 11.6638 grams; 10-gram rows are ignored. The feed's `todayDate` supplies the effective Nepal date. Manual admin publications take effect immediately with today's Nepal date and clear the imported unit totals. A later daily import can replace a manual publication; a later manual publication replaces the import. A manual publication made during an HTTP fetch wins over that fetch. Repeated checks after a successful import do not overwrite subsequent manual changes. Public rates and product estimates show the effective date and source; failed imports leave both unchanged.

Install the PWA from the production HTTPS origin. Android: use Chrome's **Install app** prompt/menu, rather than creating a browser shortcut. iPhone: Share → Add to Home Screen, keeping **Open as Web App** enabled where offered. Existing shortcuts may need to be removed and the app reinstalled. Standalone metadata cannot force a browser to create a WebAPK or remove its shortcut badge. The top banner offers the browser's installation prompt where supported and platform instructions otherwise. Installed launches hide the banner; browsers cannot reliably detect or launch an installed iPhone PWA, so the banner directs users to its home screen icon.

Authenticated users have a notification inbox at `/notifications`, with an unread count and per-message read actions. Admins receive new-store and upgrade-request notifications. Merchants receive store status, product moderation, subscription and upgrade-review updates. Notifications are account-specific and persist from the time of this update; they are in-app messages, not operating-system push notifications.

Merchants can set optional public email and WhatsApp numbers in Workspace → Store. Public store pages offer call, SMS, optional WhatsApp/email, and map directions.

## Passwords and manual recovery

Passwords must contain 6–128 characters, including administrator passwords created through the CLI. Users select **Forgot password?** on sign-in and submit their full name, store name, registered phone number (username), and address. Repeated submissions for the same normalized phone number create only one pending request; the original details remain available for review.

Admins receive an inbox notification and can open **Administration → Password reset requests** to compare submitted and registered details, then reject or approve. Approval replaces the account password with a randomly generated 10-character password shown once to the reviewing admin. The admin must copy it and manually text it to the account's registered phone number. No SMS is sent automatically, and plaintext passwords are never stored in notifications, sessions, or audit history. If the admin leaves without copying, a new request and approval is needed. Rejection leaves the existing password intact. A new request can be submitted after an earlier one is reviewed.

Apply the latest database migration before running this version (`docker compose build`, then `docker compose run --rm app python -m flask --app wsgi db upgrade`, then `docker compose up -d`).

## Display units and loading feedback

Admin → Units lets an administrator choose Gram or any active custom unit as the platform default. Public pages include a display-unit selector with an option to follow the platform default. Explicit visitor choices persist in a cookie. Product weights and per-unit metal rates use the selected unit; item totals, price filters, making charges and canonical gram calculations stay unchanged. Administrative input fields explicitly labelled per gram remain in grams. A unit must be replaced as the default before it can be disabled; visitors with a disabled or missing selection fall back to the current default.

Navigation begins immediately, without page fade transitions. Slower requests show a progress bar, followed by skeletons; images, searches, media buffering and additional list pages have their own loading feedback. Reduced-motion preferences disable decorative movement. Map scripts load only on pages with a map. Apply the latest migration before starting this version and keep the service worker version current when updating cached assets. Real-device performance still depends on network, media size and VPS response time.


## Client feedback update

Apply migration `0005` before starting this version. It preserves existing gram weights and copies each store’s existing surplus to its new silver surplus field. Gold and silver surplus can then be edited independently, per gram or per Tola. Imported rates are recalculated from their retained Tola totals, and Tola becomes the initial platform display default; administrators and visitors can still change display units.

Products accept Gram or Tola weights and remember the input unit for editing. **Other** requires a description and fixed NPR price; metal weight, purity and making charges are omitted. Photos and videos use the same upload and publication rules as jewellery.

Workspace → Products now includes each product’s photos and videos. **Take photo** and **Record video** open native camera capture on supported mobile browsers; ordinary file uploads remain available. Photo adjustments include quarter-turn rotation, centre square crop and brightness. Video adjustments include start/end trim (at least 5 seconds) and audio removal. The existing worker applies video edits and converts clips to MP4; original video limits (5–60 seconds, 100 MB) and plan allowances remain in effect. Native camera behaviour varies by device, and desktop browsers may show a file chooser instead. This is a small upload editor, without music, overlays or timeline effects.

Dashboard tabs load their main content through HTMX, with full navigation for the map-based Store settings. Public navigation prefetches only links the visitor points at, focuses or touches, keeping at most three responses in service-worker memory for eight seconds. Responses are consumed once and invalidated by form submissions and save changes; private dashboards are excluded. Lists automatically load only the first three pages, then offer Load more to keep the document bounded. No framework or editing bundle is added.

### Follow-up UI fixes (asset version 1.3.1)

Card artwork has a fixed, clipped row above its text. Password fields render a Show/Hide text button, and Other product fields initialize independently of maps and other page scripts, including after partial navigation. Media previews fit within the viewport. Saved links carry the visitor’s selected coordinates; without a selected location, saved cards omit distance rather than assuming Kathmandu. Saved products are not limited by discovery radius.

Versioned CSS/JavaScript URLs and immediate service-worker activation prevent an older asset cache from masking this update after refresh. Public media metadata loads in one query; published images/videos may be reused by the same browser for 60 seconds. Private uploads retain no-store responses. Page fades and the unused Alpine page script have been removed. This update introduces no new migration beyond 0005.

With the updated files on the server, run from the project directory:

```sh
docker compose build app worker rates
docker compose stop app worker rates
docker compose up -d db
docker compose run --rm app python -m flask --app wsgi db upgrade
# Continue only if the migration command succeeds.
docker compose up -d --force-recreate app worker rates nginx
docker compose ps
docker compose logs --tail=50 app worker rates
```

Recreating Nginx refreshes its upstream connection after the app container is replaced. Refresh the browser/PWA after restart to load asset version 1.3.1. `db upgrade` is safe when 0005 is already applied.

### Upgrade to 1.3.2

Back up PostgreSQL, then build the new images and apply migration 0006 before starting the updated services.

```sh
docker compose build app worker rates
docker compose stop app worker rates
docker compose run --rm app python -m flask --app wsgi db upgrade
# Continue only if the migration succeeds.
docker compose up -d --force-recreate app worker rates nginx
docker compose ps
```

Refresh the browser or installed app. In **Merchant → Products**, choose a standard purity or **Custom percentage** for gold and silver. Enter a making percentage from 0 to 100. For example, 10% on 100 g adds 10 g of making weight, priced at the current metal rate per gram. Existing NPR making charges stay in place until you enter a percentage.

To enable reel bonuses, set `REEL_VIEWS_PER_BONUS_HOUR` in `.env` before recreating the app. The default is `0` (disabled). Each signed-in account can count once per reel per Nepal calendar week after watching three seconds in the Reels feed. Store owners’ own views are excluded. Every full threshold earns one extra featured hour for the following week on Standard and Premium, up to three extra hours. The bonus appears in **Merchant → Featured** when that week begins and can be booked during that week.
