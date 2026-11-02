# Architecture and maintenance

A Flask modular monolith renders Jinja templates. HTMX updates catalogue results; browser JavaScript handles maps, saved products, theme, upload progress and viewport-limited video playback. Dependencies are vendored for startup without CDN access. PostgreSQL/PostGIS is mandatory. A second process from the same application runs PostgreSQL-backed media jobs. Nginx terminates/proxies HTTP; FFmpeg is installed in the image. No Redis, external search service, React or microservices.

## Structure

- app/__init__.py: application factory, configuration, headers, errors.
- app/models.py: 19 domain tables plus the product-tag association (19 total including association). UUID identities; numeric money; geography and foreign keys. See schema.sql for actual definitions.
- app/security.py: admin guard, database-wide throttles and atomic form mutation tokens.
- app/services/core.py: validation, Decimal pricing, verification, quotas, scheduling and audit services.
- app/services/catalogue.py: SQL queries, spatial filtering and ranking.
- app/services/media.py: storage adapter, bounded uploads, image conversion, ffprobe and worker leases.
- app/routes.py: public catalogue, identity, maps and PWA endpoints.
- app/merchant.py and admin.py: authorized forms and mutations.
- app/templates/: reusable Jinja views and macros; no business calculations except display-only unit conversion.
- app/static/: extracted V9 CSS, small application scripts, icons and vendored dependencies.
- migrations/: frozen initial schema; does not import current models during upgrade.
- tests/: Python unit/integration tests and Playwright target-browser suite.

## Important policies

Discovery is guest-accessible. Phones normalize to international form; Nepal mobile numbers accept a local form. Administrator and merchant logins use distinct paths and role checks. Production ships without demo users or bypasses. An operator creates the first admin from the CLI. Passwords use Werkzeug scrypt. No SMS or WhatsApp.

All non-GET forms require CSRF. Authenticated domain forms have unique mutation tokens; a replay returns HTTP 409. Domain mutation and token insertion commit together. Login throttles are per normalized phone and IP, registration per IP; counters are shared across workers. Session cookies are signed, HttpOnly and SameSite=Lax. Enable Secure cookies under HTTPS. Proxy trust is exactly one Nginx hop; don't expose the app port.

Uploads are private by default. Even processed product media is served through an authorization/visibility check and conditional range responses; it is deliberately not exposed via an unrestricted Nginx media alias. Images and reels preview in an accessible in-app dialog, with a dedicated preview page as fallback. Image evidence is inline; PDF evidence remains an attachment. Explicit WebP/MP4/PDF MIME types avoid platform-dependent download behavior. Originals are randomly named, path checked and never executed. Images strip metadata and produce 320/640/1280 maximum-edge WebP variants; smaller source files are not upscaled. At most eight images/product. Video properties are validated in the worker to avoid long web-request processing. A queued upload reserves a reel slot before processing. Invalid or failed media does not appear publicly. Video output is H.264/AAC, yuv420p, faststart, 720×1280 at 30 fps; audio is optional. Supported FFmpeg-decodable video formats (including MOV and WebM) are converted automatically. Videos must be 5–60 seconds and at most 4096 pixels per side; orientation metadata is applied and other aspect ratios are fitted with padding rather than stretched. Images retain transparency and use WebP quality 80. The existing upload caps remain 10 MB for images/evidence and 100 MB for reels. Worker timeout is shorter than its lease. Lost leases are reclaimable; three failed attempts end in failed state. Source files and unreferenced failed outputs need periodic cleanup. Files are not a separate service; replace path_for/root with an object-storage adapter if needed.

Current rates are joined into every catalogue price query, with Decimal/NUMERIC arithmetic and half-up rounding to two decimals. There is no stale product-price cache. Rates and surplus changes retain before/after values, actor and timestamp in immutable Audit events. Audit database triggers prohibit UPDATE/DELETE; application permissions prohibit bypass. A superuser can still alter database schema: use restricted operational credentials and backups when hardening production.

One product has one category and multiple normalized tags. Text search covers product name, description, category, purity, metal and tags, plus current store name. GIN trigram indexes support substring search. Geography GiST supports ST_DWithin radius filtering. Default nearby ranking interleaves store turns (first result from each matching store before a second), then sorts by distance and UUID; explicit price/newest sorts follow the user's chosen order. This intentionally trades strict nearest order for store diversity. Pagination is offset-based (12 results), bounded at 10,000 pages; benchmark before adopting much larger catalogues. Dynamic price sorting is calculated, not indexed: see benchmark instructions and don't claim measured production latency.

Creation quotas serialize through SELECT FOR UPDATE on the store. Archived records still consume product slots; deletion is not an escape hatch. Downgrades mark newest excess products/reels `excess` and cancel unused featured time. Existing records remain for audit. Upgrades do not silently republish excess content; an admin can release products to draft, subject to publication quota, and merchants may re-upload reels within the new allowance. Suspended/archived products cannot be edited or republished by owners. Removal of an image unpublishes its product conservatively until the owner reviews and republishes it.

Featured windows are interpreted in Asia/Kathmandu, split against Monday 00:00 weekly boundaries. Six concurrent slots; exclusive range end. Scheduling uses a global transaction advisory lock followed by the store lock, with a database exclusion constraint as a second barrier. Same-product overlap is prohibited. Cancellation releases future time only; elapsed time remains in quota usage. Changing plans, store suspension or product restrictions cancels remaining time and audits it. Page responses record aggregate daily Spotlight delivery counts, not unique viewers. No personal analytics identifiers are used.

## Extending features

1. Add fields/models with explicit constraints and indexes for the intended query.
2. Generate a new migration using `python -m flask --app wsgi db migrate -m "description"`; inspect PostGIS changes manually. Never edit an applied migration.
3. Put state-changing rules in services, then call them from an ownership/admin-guarded route. Acquire store locks before quota counts. Preserve existing lock order.
4. Add Jinja components using design tokens. Keep user content escaped; never inject untrusted HTML into JavaScript.
5. Add relevant unit, real PostgreSQL and browser tests. Run upgrade/downgrade on a disposable database before deployment.
6. Bump the service-worker VERSION on every static-asset deployment. New workers activate after existing controlled tabs close; reopening the app adopts the update without discarding an in-progress form.

## Open map services

Nominatim search is submit-only, globally throttled to one uncached request/second across workers and cached for 30 days; address queries are limited to Nepal. Set a meaningful GEOCODER_AGENT with operator contact details. Switch GEOCODER_URL to a compatible self-hosted service without changing clients. Map tile URL is configurable. For traffic beyond public provider allowances, configure a licensed provider or self-host OSM tiles. Tile policy: https://operations.osmfoundation.org/policies/tiles/ ; geocoding policy: https://operations.osmfoundation.org/policies/nominatim/ . Never enable offline tile prefetch or cache public map tiles in the service worker. Manual coordinates remain available if either external provider fails.

Store pages expose searchable, paginated published products with price/recent sorting, scoped to that store without a geographic radius. Administrator-only store/product detail pages include nonpublic statuses, owner/contact/subscription data and protected media/evidence previews.
