# Endpoint contract

Forms are application/x-www-form-urlencoded, except uploads (multipart/form-data). All mutation forms require csrf_token; authenticated domain mutations also require a UUID mutation token. HTML responses use 303/302 redirects after success; validation is 400, forbidden 403, missing/hidden records 404, replay/conflict 409, throttled 429. This MVP exposes server-rendered workflows rather than duplicating every form as a JSON API.

| Method / route | Access | Inputs / result |
|---|---|---|
| GET / | Guest | q, category UUID, tags comma list (AND), metal, purity fraction, price_min/max, weight_min/max, lat/lon, radius km, store UUID, sort near/low/high/new, featured, page; HTMX returns catalogue partial |
| GET /products/{uuid} | Guest | Visible published detail with pricing and units |
| GET /stores | Guest | lat/lon/radius; up to 50 nearest verified active stores |
| GET /stores/{uuid} | Guest | Store profile and catalogue link |
| GET /saved | Guest | ids comma-separated UUIDs, page; device-local saved selection |
| GET /reels | Guest | page; five ready public reels at a time |
| GET /location, /appearance | Guest | Device preferences and map picker |
| GET /api/geocode | Guest, throttled | q, JSON [{label,lat,lon}] or {error} |
| GET/POST /register | Guest, throttled | owner_name, phone, password, email?, name, store_phone, address, latitude, longitude, surplus, document? |
| GET/POST /login, /admin/login | Guest, throttled | phone, password; role-specific session |
| POST /logout | Session | Invalidate current browser session |
| GET /merchant | Merchant | tab Overview/Products/Media/Featured/Store/Subscription |
| GET/POST /merchant/products/new | Merchant | name, category_id, metal, purity code, weight, making, fixed, tags, description |
| GET/POST /merchant/products/{uuid}/edit | Owner | Same fields; restricted states reject edits |
| POST /merchant/products/{uuid}/publish | Owner | Toggle draft/publication subject to verification/media/quota |
| POST /merchant/products/{uuid}/media | Owner | kind image/reel, file |
| POST /merchant/media/{uuid}/remove | Owner | Hide media; image removal unpublishes for review |
| POST /merchant/profile | Owner | name, phone, address, latitude, longitude, surplus |
| POST /merchant/upgrade | Owner | plan, evidence file |
| POST /merchant/featured | Owner | product_id, start/end datetime-local in Nepal |
| POST /merchant/featured/{uuid}/cancel | Owner | Cancel unused allocation |
| GET /admin | Admin | tab Overview/Stores/Products/Reels/Rates/Units/Plans/Featured/Banners/Audit, page |
| POST /admin/stores/{uuid} | Admin | action verified/rejected/pending/suspend/reactivate, reason |
| GET /admin/stores/{uuid}/documents | Admin | Private verification evidence list |
| POST /admin/products/{uuid} | Admin | status archived/suspended/draft, reason |
| POST /admin/rates | Admin | Gold, Silver, reason |
| POST /admin/units[/{uuid}] | Admin | name, symbol, grams, description, active checkbox |
| POST /admin/plans/{name} | Admin | products, reels, hours; applies quota transitions to affected stores |
| POST /admin/subscriptions/{uuid} | Admin | plan for store |
| POST /admin/upgrades/{uuid} | Admin | action approved/rejected |
| POST /admin/featured | Admin | product_id, start/end in Nepal; same quota/capacity rules |
| POST /admin/featured/{uuid}/cancel | Admin | Cancel unused allocation |
| POST /admin/reels/{uuid} | Admin | reason; suspend |
| POST /admin/banners/{uuid} | Admin | eyebrow, title, art, href (local path), active |
| GET /media/{uuid}/{variant} | Visibility/ownership checked | file/thumb/320/640/1280; explicit inline image/video MIME types; PDFs download as attachments |
| GET /health | Public | Database/PostGIS health and application version |
| GET /manifest.webmanifest, /sw.js, /offline | Public | PWA assets |

Administrative and owner mutations create immutable audit entries. Role and ownership checks occur server-side, independent of visible controls. Store suspension affects public visibility immediately. No checkout/payments, OTP, WhatsApp or public-user account API is included because this is a discovery MVP.

| Additional route | Access | Purpose |
| --- | --- | --- |
| GET /stores/{uuid}?q=&sort=new&page=1 | Public, active verified stores | Search and browse the full published store catalogue; no distance filter |
| GET /admin/stores/{uuid}?q=&page=1 | Admin | Store, owner, subscription, evidence and products across all statuses |
| GET /admin/products/{uuid} | Admin | Product data, current pricing and media across all statuses |
| GET /media/{uuid}/preview | Same visibility/ownership checks as media files | In-app image/reel preview fallback page |
