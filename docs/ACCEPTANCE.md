# Release acceptance checklist

Run on a disposable staging deployment first. Record actual outcomes and failures; this file is not a claim that checks passed.

1. Apply migration to empty PostgreSQL/PostGIS, inspect indexes, seed operator rates and create an admin. Downgrade/upgrade only on a disposable database; verify immutable audit trigger exists afterward.
2. Register two merchants, one with a valid image and one with PDF evidence. Duplicate normalized phone must fail. Wrong password, CSRF-free forms and merchant access to admin mutations must fail.
3. Create drafts while pending; publication must fail. Admin verifies one store. Upload an actual image, inspect WebP sizes and stripped metadata, publish and inspect price breakdown/custom units.
4. Change rates and surplus; catalogue/detail price must change immediately and before/after history must remain. Create 0.5 g unit; 2 g must show 4 units. Invalid/zero/NaN amounts must fail.
5. Edit another merchant's IDs in product/media/profile URLs and POST data; every operation must be denied. Suspend/archive a product; owner edit/publish must fail. Suspend store; public product/media routes must become unavailable.
6. Exhaust Free/Standard product and reel allowances, including two simultaneous requests for the final slot. Exactly one should succeed. Downgrade from Premium with excess records and scheduled placements; verify hidden excess items and cancelled unused hours.
7. Upload valid/invalid MP4 files: 4 seconds, 5 seconds, 60 seconds, 61 seconds, >100 MB, supported MOV/WebM codecs, landscape aspect ratios, malformed bytes and rotation metadata. Supported codecs/aspects/orientations should convert to upright padded H.264/AAC MP4; invalid durations and malformed bytes should fail. Inspect queued/processing/ready/failed states and thumbnails. Kill/restart worker during a transcode and confirm lease recovery without publishing a duplicate.
8. Schedule placements across Nepal Sunday/Monday, overlap windows, exhaust six slots, and race two bookings for the same product. Cancel midway; consumed hours must still count. Verify suspension and plan changes cancel remaining time. Inspect delivery and audit history.
9. Test every filter and all pages with at least 5,000 products across 100 stores. Verify GiST use and collect EXPLAIN ANALYZE and timing distributions. Include empty/no-rate/invalid-ID cases. Verify store interleaving on default order and stable explicit price order.
10. On physical Android and iPhone, test geolocation allowed/denied/unavailable, address search, manual marker and coordinates, registration/profile maps and persisted discovery location. Test the configured provider; preview-environment tile access was blocked.
11. Run Playwright at 360/390 widths. Also inspect 320/430, safe areas and large desktop centred shell. Exercise every merchant/admin form and every visible control with keyboard and touch. Compare against reference/approved-v9.html; include empty/loading/error/success states and dark mode.
12. Install PWA over HTTPS, launch standalone, go offline and verify fallback. Ensure no account pages/evidence or tile cache is available offline. Deploy an asset-version bump and test old-tab/new-launch behavior. Real-device installation remains a release gate.
13. Scroll reels rapidly; only visible and next metadata should load, hidden playback must pause, native controls must work. Confirm smoothness and network use on a low-end device; do not infer it from desktop screenshots.
14. Test all 12 adaptive phases with controlled clock in Asia/Kathmandu; reload/restore visibility at boundaries. Measure text/accent contrast and reduced-motion behavior. Adaptive phase tests on real devices are not covered by a single dark-mode screenshot.
15. Test backup/restore on a separate VPS/volume, verify TLS renewal, secure cookies, logs, retention and disk exhaustion recovery.

## Store browsing and detail previews

- Open a verified store as a guest, search by name/description/category/tag, sort by price/newest and navigate all pages. Draft, archived, suspended and excess products must remain hidden. Changing the device location must not exclude that store’s published range.
- As admin, click store/product names in listings. Inspect owner/contact/location/plan/evidence data and products across every status. Guests and merchants must receive 403 for these detail pages.
- Open product images, merchant previews and admin reel/evidence previews. Images/videos should open inside the app without a download; Close/Escape should stop playback and return focus. Check dark mode, narrow screens and portrait/landscape media. PDF evidence retains its explicit download action.
- Upload PNG/JPEG/TIFF images and supported MOV/WebM reels. Confirm WebP output sizes/transparency and 720×1280 H.264 MP4 output, poster images and seek/range playback after background processing.
