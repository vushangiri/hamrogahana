# Implementation plan and component matrix

Execution order: inspect V9 → model domain and permissions → implement services and routes → integrate Jinja/CSS and browser modules → implement media worker and deployment → run tests and visual review → report verification limits.

| Requirement | Implementation | Verification route |
|---|---|---|
| V9 mobile shell, Spotlight, banners | extracted design.css, base/discover/macros templates | rendered fixture visual review, browser suite |
| Public catalogue, search, filters, nearby mix | services/catalogue.py, routes.py | PostgreSQL integration tests; compiled SQL test |
| Exact pricing and local units | core.breakdown, Rate/Unit models, product.html | Decimal unit tests + DB rate update test |
| Location picker and provider search | Leaflet, app.js, /api/geocode, GeoCache | rendered map controls; provider and geolocation checks on target |
| Identity and manual verification | Flask-Login, register/login routes, admin store mutations | CSRF/access tests + integration flows |
| Ownership and publication | merchant.py, locked_store, audit | integration tests for publishing and cross-owner denial |
| Media upload and reel pipeline | services/media.py, Media/Job, worker CLI | real ffprobe tests; queue integration on Postgres |
| Subscription enforcement | Plan, Upgrade, core.set_plan | integration downgrade and quota tests |
| Featured scheduling | Feature, advisory lock + exclusion constraint, Nepal week slicing | week-boundary unit test + concurrent integration test |
| Administration and audit | admin.py, admin.html, immutable Audit trigger | template tests + all dashboard tab integration test |
| Saved products and adaptive theme | app.js and theme.js | rendered browser interaction; Playwright target suite |
| PWA | manifest, sw.js, icons, offline fallback | asset/cache tests; target install test remains |
| Self hosting | Dockerfile, compose, Nginx, migration snapshot | target Docker execution required |

V9 interaction inventory: logo, appearance chooser, merchant/admin login, registration; location switch, rate display, six-banner arrows/dots/CTA, Spotlight cards, search, category/filter/reset/pagination, save/detail/store links; nearby store map/list; vertical reels and video controls; owner overview/products/editor/publish/media/profile/subscription/featured; admin verification/suspension/product restrictions/rates/history/units/plans/featured/audit. Simulated media, fake authentication and decorative maps were removed from the application. The original prototype is retained only in reference/.

New required controls added beyond V9: real geocoding and geolocation, coordinate picker, additional filters, document/evidence uploads, sign-out, featured start/end times, moderation reasons, editable unit symbols and activation, configurable banners and plan entitlements.
