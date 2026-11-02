# Verification report — 2 November 2026

## Local update verification — 2 November 2026

Store catalogues, admin detail pages, in-app previews and automatic media conversion were verified on the local Docker/PostGIS environment:

- Full test suite: **73 passed, none skipped**, including isolated PostgreSQL/PostGIS integration tests.
- Actual PNG/JPEG/TIFF-to-WebP and MOV/WebM-to-H.264 MP4 conversions passed, including dimensions, transparency and generated thumbnails.
- Queued reel upload → worker processing → ready state → inline preview and HTTP range playback passed.
- Store search/pagination and public visibility, admin detail access controls, private image evidence and inline media MIME/disposition passed.
- JavaScript syntax and Python compilation passed. Browser interaction/visual checks for this update were not run; use the added acceptance checklist for modal keyboard behavior and device playback.

The original delivery report below is historical; its database/runtime availability limitations no longer describe this local test run. This update does not certify the remaining production/device criteria.

## Result

Source implementation is delivered. **The full acceptance criteria are not yet verified; this is not a production-ready certification.** Backend, migrations, worker, templates, browser modules, deployment configuration and documentation are present. No SQLite fallback, fake production accounts, simulated production uploads or hardcoded catalogue are used.

## Executed successfully

- `python -m pytest -q --junitxml=docs/test-results.xml`: **39 passed, 11 skipped**. See the machine-readable report.
- `python -m ruff check app tests scripts`: passed.
- Python module compilation: passed.
- All Jinja templates parsed; populated public, merchant and admin views rendered in test request contexts.
- Catalogue SQL compiled for nearby/price/recent sorting, text, tags and featured filters against the PostgreSQL dialect. Compilation does not prove database execution or query performance.
- `python -m flask --app wsgi db upgrade --sql`: emitted 293 lines of migration SQL successfully. It was not applied to a running database here.
- Node syntax checks for app.js, theme.js and sw.js: passed.
- FFmpeg generated actual temporary H.264 MP4 files; ffprobe validation accepted 5 seconds and rejected 4 seconds, 61 seconds and fake MP4 bytes.
- Browser visual inspection of Jinja-rendered fixture pages confirmed the centred mobile shell, Spotlight styling, appearance controls and dark-mode persistence after reload.
- Leaflet map/marker controls loaded; manual coordinates could be edited. Public OpenStreetMap tiles returned an access-blocked tile image in this environment. Tile delivery and geocoder responses are therefore not verified.

## Blocked or not executed

- **11 PostgreSQL integration tests skipped.** No PostgreSQL/Docker runtime was initially installed. System package installation was restricted, and running PostgreSQL under a non-root account was unavailable (`setresuid` failed). Tests retain a real PostgreSQL/PostGIS dependency; they were not substituted with SQLite or mocked transactions.
- Database migration application, GiST/exclusion/immutable-audit constraint behavior, registration persistence, publishing/moderation, live pricing updates, ownership checks involving stored data, concurrent featured allocation and downgrade flows require those tests on the target host.
- The full Flask browser preview could not start through the managed preview launcher because its runtime could not find Python. A separate static rendering of real templates with explicit QA fixtures was used solely for visual inspection. Those fixtures are not included in production data or presented as a working backend.
- The Playwright target suite is supplied but was not executed against a running database-backed app here. Authenticated browser flows need the manual acceptance checklist in addition to the supplied public suite.
- No Docker Compose build/start, Nginx TLS termination, backup/restore, real-device standalone installation, physical geolocation permission or mobile video playback benchmark was executed.
- No representative 5,000-product query benchmark was possible. `scripts/benchmark.py` is supplied for a seeded staging database. No latency target is claimed.
- All twelve adaptive phases are implemented, but comprehensive contrast measurement and controlled-clock/device testing remain open. The visual comparison was manual and partial, not a pixel-difference certification at every requested viewport.

## Corrections made during audit

- Preserved already-consumed featured hours when cancelling a placement; only future time can be released.
- Refresh product/store state under quota locks to avoid stale state after concurrent restrictions.
- Added an explicit published-product quota check to prevent admin release of excess records bypassing a lower plan.
- Prevented an incomplete new product from autoflushing before all required fields are validated.
- Kept private evidence and dynamic media out of service-worker caching, and made the offline document independent of sessions/CSRF tokens.
- Added eager relationships for administrator listings and a shared current-rate lookup for Spotlight rendering.
- Preserved the V9 horizontal category chips and changed the prototype's old featured heading to the requested “The Spotlight”.

## Deliberate MVP policies and limitations

- Configurable defaults: 20/80/300 products, 0/1/5 reels per product, 0/20/50 featured hours. Admins can change these explicitly with an audit record.
- Six featured slots; current-week usage counts allocated elapsed time, not unique viewer attention. Delivery counts are aggregate response impressions.
- One catalogue category/product; twenty tags maximum; eight product images maximum. Anonymous saves are local to the device and limited to 100 IDs.
- Store listing is capped at the nearest 50 stores. Catalogue and admin lists paginate; very large/deep catalogues may need cursor pagination after measurement.
- Archived products still consume slots; upgrades do not automatically republish previously hidden excess records. Admin release returns products to draft; publication quotas still apply.
- Product/media privacy takes precedence over aggressive long-lived media caching. Media responses use range support but are private/no-store so suspended content is not knowingly served from an application cache.
- Public-user accounts, checkout/payments, OTP and WhatsApp are outside the requested discovery MVP. Payment evidence is reviewed manually.
- PWA icon/splash metadata is provided; device-specific install/splash behavior depends on the browser and must be tested on target devices.

## Next release gate

Follow README.md to run the source on Docker Desktop or Ubuntu. Run all PostgreSQL tests, the Playwright suite and docs/ACCEPTANCE.md. Fix any observed failures before public launch. Keep the checks above separated from checks run later on the target infrastructure.
