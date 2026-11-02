# HAMRO GAHANA — COMPLETE MOBILE-FIRST PWA ENGINEERING PROMPT

## ROLE AND MISSION

You are the Principal Full-Stack Engineer, UI Engineer, Database Architect, Security Engineer, Performance Engineer, QA Engineer and Technical Documentation Lead responsible for building **Hamro Gahana**, a mobile-first jewellery discovery Progressive Web Application for Nepal.

Your assignment is to build, run, test, audit, repair and deliver the complete functional application based on the approved HTML prototype attached to this request.

**Do not stop at scaffolding, placeholder endpoints, simulated dashboards, static UI pages or untested functionality.**

The finished product must be a functioning, self-hostable web application that looks and feels like a polished native mobile application.

Work autonomously when requirements are sufficiently clear. Ask for clarification only when an ambiguity materially affects security, financial calculations or fundamental product behaviour.

---

## 1. VISUAL SOURCE OF TRUTH

The attached file `hamro_gahana_v9_interactive.html` is the approved UI reference.

Study the entire HTML, CSS and JavaScript carefully before implementation.

Preserve:

- Overall ivory, champagne, gold and dark-mode aesthetics.
- Typography, visual hierarchy, component proportions, cards, spacing and borders.
- Mobile-first layout and fixed bottom navigation.
- Discover, Reels, Stores and Saved navigation.
- Dedicated merchant login and registration pages.
- Merchant and administrator dashboards.
- Product detail presentation, tags and pricing breakdown.
- Animated banners, transitions and reel interactions.
- Skeleton loading patterns.
- Twelve-phase adaptive appearance system.
- The featured jewellery heading **“The Spotlight”**, including its visual treatment.

Do not replace the approved interface with a generic Bootstrap, Material Design, Tailwind component-library or admin-dashboard template.

Refactor the prototype into maintainable templates, components, styles and JavaScript modules. Remove simulated data and replace it with real backend functionality.

Make minor visual refinements only when they improve accessibility, consistency, responsiveness or interaction quality without changing the approved design language.

**Mobile view is the primary and only required application layout.** On desktop, display the mobile interface in a centered, appropriately sized app shell. Do not build a separate desktop experience.

---

## 2. MINIMAL TECHNOLOGY STACK

Use the following architecture:

**Backend**
- Python 3.12+
- Flask
- SQLAlchemy 2
- Alembic via Flask-Migrate
- PostgreSQL with PostGIS
- Flask-Login or an equally small, well-maintained session-authentication solution
- Werkzeug or Argon2 password hashing
- Gunicorn for deployment

**Frontend**
- Server-rendered Jinja2
- HTMX for partial updates
- Alpine.js for lightweight reactive interactions
- Modern CSS with design tokens and custom properties
- Small, purpose-built JavaScript modules where required
- Native browser APIs for gestures, uploads, geolocation, caching and PWA functionality

**Mapping and location**
- Leaflet
- OpenStreetMap-compatible map tiles
- Nominatim-compatible geocoding
- PostgreSQL/PostGIS for spatial queries

**Media**
- Pillow for image optimization
- FFmpeg/ffprobe for video inspection, thumbnails and transcoding
- Local filesystem media storage for the MVP, structured so S3-compatible storage can be introduced later

**Infrastructure**
- Docker Compose
- PostgreSQL/PostGIS container
- Flask application container
- Nginx reverse proxy
- HTTPS configuration
- Pytest
- Ruff
- GitHub Actions for automated tests

Use one application and one database as the primary deployment architecture.

Do not introduce React, Next.js, Kubernetes, Kafka, Elasticsearch, Typesense, Ory, separate microservices or distributed infrastructure unless a specific requirement demonstrably cannot be met with this stack.

A lightweight separate background worker process using the same Python codebase is permitted for video processing. Prefer a PostgreSQL-backed job queue if it is reliable for the intended workload; otherwise justify the smallest additional dependency necessary.

Avoid synchronous video transcoding in web requests.

---

## 3. MOBILE-FIRST NATIVE-LIKE EXPERIENCE

Implement a complete installable PWA.

Requirements:

- Valid web app manifest.
- Proper icons and splash-screen assets.
- Standalone display mode.
- Service worker with versioned asset caching.
- Offline fallback page.
- Correct cache invalidation after deployments.
- Mobile safe-area support.
- Appropriate status-bar and theme colors.
- Responsive touch targets.
- Smooth scrolling and gestures.
- Fixed bottom navigation.
- Smooth transitions between application views.
- Scroll-position restoration where appropriate.
- Native-feeling forms, dialogs, sheets and notifications.
- Install prompt where supported.
- Accessible focus management and reduced-motion support.

The logo must always navigate to Discover.

Navigation should feel immediate, including on slower connections.

Use skeleton previews for product grids, store lists, dashboards and media loading. Show progress indicators for uploads and meaningful feedback for mutations.

Do not add artificial delays to create the impression of loading.

Avoid heavy animation frameworks. Use efficient CSS transforms, opacity transitions and requestAnimationFrame only where needed.

Respect `prefers-reduced-motion`.

---

## 4. THEME ENGINE

Implement three selectable appearance modes:

1. Light
2. Dark
3. Adaptive

Adaptive must use the actual current time in **Asia/Kathmandu**, not the device's local timezone.

Create twelve visual phases covering the twenty-four-hour day in two-hour intervals.

The phases must remain within the approved design language, using coordinated variations in surface colors, background warmth, text contrast, accent intensity and atmosphere.

Use six daytime variants and six nighttime variants.

Theme transitions must be subtle, smooth and free of flashing.

Persist the selected appearance preference per device.

Recalculate the adaptive phase on application startup, visibility restoration and relevant time boundaries.

All phases must meet reasonable WCAG contrast standards.

---

## 5. PUBLIC JEWELLERY DISCOVERY

Visitors must be able to browse without creating an account.

Implement:

- Discover homepage.
- Six configurable promotional banners.
- “The Spotlight” featured jewellery section.
- Product catalogue.
- Categories.
- Search.
- Advanced filters.
- Product details.
- Saved products.
- Nearby stores.
- Reels.

Each product has:

- Name.
- Description.
- One category.
- Multiple tags.
- Metal type.
- Metal purity.
- Metal weight in grams.
- Making charge.
- Fixed charge.
- Store association.
- Optimized images.
- Publication status.
- Optional reels.
- Dynamic price.

Product details must display descriptions, relevant tags, weight, applicable custom units, price breakdown and store information.

Saved products should work for anonymous visitors using local browser storage and should not require authentication.

---

## 6. LOCATION AND REAL OPEN-SOURCE MAPS

Implement genuine interactive 2D maps, not CSS illustrations.

Use Leaflet with OpenStreetMap-compatible tiles.

Provide three ways to choose a discovery location:

- **Use my current location** using browser geolocation, after user permission.
- **Search for a location** by typing an address, landmark, city or area.
- **Choose a location manually** by tapping or dragging a marker on the map.

Show the currently selected location clearly in the public header.

Allow users to change it at any time.

Store the selected discovery location locally so it persists across visits.

For store registration and store profile editing:

- Display an interactive map.
- Allow searching for an address.
- Allow selecting and dragging a marker.
- Populate latitude and longitude.
- Allow direct coordinate editing.
- Validate geographic coordinates.
- Save coordinates to PostGIS.
- Show the selected address and location preview.

Use a geocoding abstraction so the application can initially use a responsibly configured public provider and later switch to a self-hosted geocoder.

Do not assume the public Nominatim endpoint can support unrestricted production autocomplete. Respect provider usage policies, rate limits, caching requirements and attribution. Prefer search-on-submit rather than making a geocoding request for every keystroke.

Likewise, use an appropriate tile provider or self-hosted tiles if public OpenStreetMap infrastructure is unsuitable for production traffic.

Location search failures must not prevent manual marker placement.

---

## 7. GEOSPATIAL PRODUCT DISCOVERY

Store coordinates in PostGIS geography or geometry columns with appropriate SRID and indexes.

Implement nearby-store discovery using spatial database queries rather than calculating distances for every store in Python.

Product discovery must support:

- Search text.
- Category.
- Multiple tags.
- Metal.
- Purity.
- Price range.
- Weight range.
- Distance radius.
- Store.
- Nearest-first sorting.
- Price sorting.
- Recent products.
- Featured products.

Index searchable and filterable columns appropriately.

Use PostgreSQL full-text search and/or trigram indexes where justified.

Use a GiST index for geospatial queries.

Avoid N+1 database queries.

Use pagination or cursor-based loading where appropriate.

Only show products from verified, active stores.

Prevent a single store from monopolizing the first page of nearby results through a documented, deterministic ranking policy.

Benchmark representative catalogue queries and document the results.

---

## 8. DYNAMIC METAL PRICING

Administrators control pure gold and pure silver rates.

All monetary calculations must use Python Decimal and PostgreSQL NUMERIC, never floating-point arithmetic.

The formula is:

metal_value = pure_metal_rate_per_gram × purity_fraction × weight_grams

surplus_value = store_surplus_per_gram × weight_grams

final_price = metal_value + surplus_value + making_charge + fixed_charge

All prices are in NPR.

Store owners control their own per-gram surplus.

Admin metal-rate updates must immediately affect displayed prices after appropriate cache invalidation.

Retain rate history, including administrator, timestamp, previous value, new value and reason.

Retain store-surplus change history.

Display a transparent price breakdown on product detail pages.

---

## 9. CUSTOM WEIGHT UNITS

Administrators must be able to define custom jewellery weight units.

Example:

1 xyz = 0.5 grams

A silver product weighing 2 grams must therefore display:

2 g = 4 xyz

Each unit requires:

- Name.
- Symbol.
- Grams-per-unit conversion factor.
- Active/inactive status.
- Optional description.
- Creation and update timestamps.

Use precise Decimal arithmetic.

Validate that conversion factors are greater than zero.

Allow administrators to create, edit, activate and deactivate units.

Display applicable units in product details.

The canonical stored metal weight must always remain grams.

Do not allow a custom unit to change the underlying product weight or price calculation.

---

## 10. STORE REGISTRATION AND AUTHENTICATION

Store owners register using:

- Owner name.
- Unique phone number.
- Password.
- Optional email.
- Store name.
- Store phone.
- Store address.
- Store location coordinates.
- Per-gram surplus.
- Optional verification documents.

Registration creates an unverified store.

Administrators manually verify new stores.

No WhatsApp integration or SMS OTP is required for the MVP.

Store owners cannot publish products until verified.

Use secure password hashing, CSRF protection, session-cookie security, rate limiting, login throttling and server-side authorization checks.

Separate merchant and administrator access.

Never implement demo bypasses in production authentication.

---

## 11. STORE OWNER DASHBOARD

Implement fully functional pages for:

- Overview.
- Products.
- Images and Reels.
- Featured placement.
- Store profile.
- Subscription.

Verified store owners can create, edit, publish and unpublish their own products.

**Products do not require routine administrator approval.**

Administrators retain the ability to archive or suspend any product.

An owner must not be able to republish an administratively archived or suspended product.

Validate all permissions on the backend.

Implement meaningful status history and audit events.

---

## 12. SUBSCRIPTION TIERS

Implement these limits:

| Entitlement | Free | Standard | Premium |
|---|---:|---:|---:|
| Products | 20 | 80 | 300 |
| Reels per product | 0 | 1 | 5 |
| Featured hours per week | 0 | 20 | 50 |

Store owners can request plan upgrades and attach payment evidence.

Administrators review and approve upgrades manually.

Enforce entitlements server-side.

Define and test downgrade behaviour so existing excess products and reels cannot be used to bypass limits.

---

## 13. REELS

Reels are associated with products.

Requirements:

- MP4.
- H.264.
- Vertical 9:16.
- Target 1080 × 1920.
- Duration 5–60 seconds.
- Maximum upload size 100 MB.
- Generated thumbnail.
- Appropriate moderation controls.

Validate actual media properties using ffprobe rather than trusting filename extensions or browser-provided metadata.

Process videos asynchronously.

Generate web-compatible outputs and thumbnails.

Prevent unsafe file paths and unauthorized media access.

Reels must have a fluid vertical browsing experience with swipe gestures, smooth transitions, pause/play, progress indication, product links and graceful loading states.

Preload only nearby reels in the feed.

Do not download the entire reel catalogue.

Pause playback when the view is hidden.

Avoid excessive CPU, memory and network consumption.

Administrators can suspend or remove reels.

---

## 14. FEATURED PLACEMENTS

Implement scheduled featured placements using Asia/Kathmandu time.

Track weekly entitlement usage Monday through Sunday.

Validate:

- Product eligibility.
- Store verification.
- Subscription entitlement.
- Weekly hour limits.
- Requested time windows.
- Slot overlap.
- Capacity.
- Store suspension.
- Product archival.
- Plan changes.

Maintain allocation, scheduling and delivery history.

Do not implement featured placement merely as a permanent boolean flag.

---

## 15. ADMINISTRATION

Provide a complete mobile-optimized administrator workspace.

Administrators must be able to:

- Verify or reject newly registered stores.
- Suspend and reactivate stores.
- Archive or suspend products.
- Manage reels.
- Update daily gold and silver rates.
- Review rate history.
- Create and manage custom weight units.
- Manage subscription plans and upgrade requests.
- Manage featured scheduling.
- View relevant audit logs.
- Manage promotional banners and applicable settings.

The admin interface must be functional, not a visual mockup.

All mutations require server-side permission checks.

---

## 16. PERFORMANCE AND INDEXING

Optimize perceived speed and actual performance.

Implement:

- Database indexes based on real query patterns.
- Eager loading where appropriate.
- Efficient joins.
- Pagination.
- Responsive image variants.
- WebP or AVIF where supported.
- Lazy image loading.
- Explicit image dimensions to prevent layout shift.
- HTTP caching.
- Asset compression.
- Appropriate cache headers.
- Skeleton previews.
- Optimistic UI only when rollback and error handling are correct.
- Debounced search inputs.
- Request cancellation or stale-response protection.
- Minimal JavaScript bundles.
- Deferred noncritical scripts.
- Lightweight transitions.

Avoid unnecessary requests and duplicate database queries.

Do not claim that a particular latency target has been achieved without measuring it.

---

## 17. APPLICATION STRUCTURE

Use a maintainable modular monolith.

Suggested modules:

- Identity and authentication.
- Stores.
- Catalogue and categories.
- Tags and search.
- Metal rates and pricing.
- Custom weight units.
- Media and reels.
- Featured scheduling.
- Subscriptions.
- Administration and auditing.
- Public pages and PWA assets.

Separate database models, domain services, authorization rules, routes, templates and background jobs.

Keep business logic out of Jinja templates and browser JavaScript.

Use database migrations for schema changes.

Provide configuration through environment variables and documented defaults.

---

## 18. SECURITY AND DATA INTEGRITY

Implement and test:

- CSRF protection.
- Secure sessions.
- Password hashing.
- Authentication and authorization.
- Role-based permissions.
- Ownership enforcement.
- Input validation.
- File upload validation.
- Rate limiting.
- SQL injection prevention.
- XSS prevention.
- Safe redirects.
- Audit logging.
- Transaction handling.
- Idempotency for relevant mutations.
- Concurrency-safe subscription and featured allocation checks.

Never rely on hidden UI controls for authorization.

---

## 19. TESTING AND QUALITY ASSURANCE

Build automated tests for:

**Public application**
- All navigation routes.
- Location selection.
- Geospatial filtering.
- Search and filters.
- Product details.
- Saved products.
- Responsive mobile layouts.
- Theme switching.
- PWA installation assets.

**Merchant**
- Registration.
- Login and logout.
- Pending verification.
- Product creation.
- Self-publishing.
- Image uploads.
- Reel limits.
- Profile editing.
- Plan upgrades.
- Featured requests.

**Administrator**
- Store verification.
- Store suspension.
- Product archival.
- Product suspension.
- Metal-rate updates.
- Custom-unit conversions.
- Subscription approvals.
- Featured scheduling.
- Audit history.

**Technical**
- Decimal pricing accuracy.
- Database constraints.
- Concurrent quota enforcement.
- File validation.
- Security boundaries.
- Pagination.
- Geospatial query correctness.
- Media processing failures.
- Migration integrity.

Use Playwright or an equivalent browser-testing tool for real end-to-end UI interactions.

Test at representative mobile viewport sizes.

Verify that every visible button, link, navigation element, input and modal action performs its intended function.

Capture screenshots and compare them against the approved V9 design.

Perform multiple rounds of testing and correction.

A test that has not run must never be reported as passing.

---

## 20. DEPLOYMENT AND DOCUMENTATION

Deliver a complete repository containing:

- Working application code.
- Database models.
- Alembic migrations.
- Docker Compose configuration.
- Nginx configuration.
- Environment example.
- PWA manifest and service worker.
- Media processing implementation.
- Test suite.
- CI configuration.
- Seed data.
- Development commands.
- Production deployment instructions.
- Database backup and restore instructions.
- Troubleshooting guide.
- Architecture documentation.
- Feature-extension guide.
- Security notes.

Target self-hosting on an Ubuntu VPS.

Include exact commands for local development, Docker deployment, migrations, tests and production startup.

Document how to replace public map/geocoding providers with self-hosted services later.

---

## 21. EXECUTION STRATEGY

First inspect the attached approved UI and inventory every existing interaction.

Then produce a concise implementation plan and requirements-to-component matrix.

Proceed with implementation rather than waiting for additional approval when requirements are clear.

Build the database, domain services, server routes, templates, media pipeline and PWA functionality.

Integrate the approved visual design.

Execute automated tests.

Run the application and inspect it in a real browser.

Fix all identified failures.

Repeat the audit until the application meets the requirements or a genuine environmental limitation prevents verification.

Do not silently remove features to make tests pass.

---

## 22. FINAL ACCEPTANCE CRITERIA

The project is complete only when:

1. The approved mobile visual design is faithfully reproduced.
2. All public navigation and interactions work.
3. Merchant registration and authentication work.
4. Store verification is enforced.
5. Verified owners can publish without administrator approval.
6. Administrator suspension and archival restrictions work.
7. Location selection and real map interactions work.
8. Nearby catalogue queries use PostGIS.
9. Dynamic pricing and custom units calculate correctly.
10. Image uploads and reel processing work.
11. Subscription and featured limits are enforced.
12. Light, Dark and 12-phase Adaptive modes work.
13. The PWA can be installed and launched in standalone mode.
14. Loading states and animations are smooth and accessible.
15. Database migrations and deployment instructions work.
16. All critical automated tests pass.
17. Browser tests verify the intended mobile experience.
18. Documentation explains how to run, maintain and extend the application.

Provide the complete source repository and a final report distinguishing implemented features, verified tests, known limitations and deployment requirements.

**Your responsibility is to deliver a working application, not merely to generate code.**