# Chrome Extension API Contract

Every HTTP call the extension makes. All are issued by the MV3 service worker
in `src/background.ts`; no content script, popup or options page calls the API.

## Base URL

`chrome.storage.sync.apiUrl`, defaulting to `https://api.carmodpicker.com/api`.
Every path below is relative to that base. Local development points at port 8000
directly: the port 4000 frontend proxy sends no CORS headers for
`chrome-extension://` origins.

## Auth and headers

The extension authenticates with a **bearer token, not cookies**. `apiRequest`
sets on every call:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `Authorization` | `Bearer <token>` when `chrome.storage.local.authToken` is set |
| `X-API-Key` | value of `chrome.storage.local.apiKey` when set |

CORS is granted by **explicit origin**: the backend builds
`chrome-extension://<id>` origins from `CHROME_EXTENSION_IDS`. There is no
`chrome-extension://.*` regex and no `null` origin, so an id outside that list is
refused at the preflight.

Sign in exchanges a short lived handoff code for an access token. That one call
carries no `Authorization` header, since it is what a signed out extension uses
to sign in. No refresh token comes back: an expired token means signing in again.

## Endpoints

The extension sends a trailing slash on `/categories/`, `/car-generations/`,
`/part-manufacturers/`, `/retailers/` and `/parts/`; the backend registers those
routes without one and FastAPI's slash redirect answers a `307` to the canonical
path. The redirect preserves the method and body, so writes are unaffected.

| Method | Path | Auth | Called by |
| --- | --- | --- | --- |
| POST | `/auth/extension/token` | none | `exchangeHandoffCode` |
| GET | `/users/me` | bearer | `getCurrentUser` |
| GET | `/categories/` | bearer | `getCategories` |
| GET | `/car-generations/?limit=` | bearer | `getCars` |
| GET | `/car-generations/search?q=&limit=` | bearer | `searchCars` |
| GET | `/part-manufacturers/?active_only=` | bearer | `getPartManufacturers` |
| GET | `/part-manufacturers/search?q=&limit=` | bearer | `searchPartManufacturers` |
| POST | `/part-manufacturers/` | bearer | `createPartManufacturer` |
| GET | `/retailers/?active_only=` | bearer | `getRetailers` |
| POST | `/retailers/get-or-create` | bearer | `getOrCreateRetailerByDomain` |
| GET | `/parts/check-url?product_url=` | bearer | `checkProductUrl` |
| GET | `/parts/{part_id}` | bearer | `getPart` |
| GET | `/parts/find-by-part-manufacturer-and-part-number?part_manufacturer_id=&part_number=` | bearer | `findExistingPartByPartManufacturerAndPartNumber` |
| POST | `/parts/` | bearer | `createPart` |
| POST | `/parts/{part_id}/listings` | bearer | `addPartListing` |
| POST | `/parts/{part_id}/append-images` | bearer | `appendImagesToPart` |
| GET | `/images/by-source-url?source_url=` | bearer | `getImageBySourceUrl` |
| POST | `/images/fetch-from-url` | bearer | `uploadImage` |
| POST | `/crawled-pages/scrape` | bearer | `scrapeAndParsePage` |

---

### POST `/auth/extension/token`

Spends a handoff code for an access token.

Request:

```json
{ "code": "<handoff code>" }
```

Response `200`:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

`401` with `detail.error_code` of `HANDOFF_CODE_INVALID` when the code is
expired, forged, or is an access token rather than a handoff code.

---

### GET `/users/me`

Response `200` (`UserRead`):

```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "disabled": false,
  "email_verified": true,
  "image_urls": ["string"] ,
  "is_superuser": false,
  "is_admin": false,
  "is_service_account": false,
  "subscription_tier": "string",
  "subscription_status": "string",
  "subscription_expires_at": "datetime | null",
  "totp_enabled": false,
  "instagram_url": null,
  "facebook_url": null,
  "reddit_url": null,
  "youtube_url": null,
  "tiktok_url": null,
  "session_expire_minutes": null,
  "oauth_accounts": []
}
```

`image_urls` come back as presigned URLs, not file keys. There are no
`created_at` or `updated_at` fields on this response.

---

### GET `/categories/`

Response `200`: a bare array of `CategoryResponse`.

```json
[
  {
    "id": "uuid",
    "name": "exhaust",
    "display_name": "Exhaust Systems",
    "description": "string | null",
    "icon": "string | null",
    "is_active": true,
    "sort_order": 0,
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

`display_name` is required on the response, not nullable.

---

### GET `/car-generations/`

Query: `limit` (1 to 1000, default 100), `cursor`.

Response `200`: a **`CursorPage`**, not a bare array.

```json
{
  "items": [
    {
      "id": "uuid",
      "car_make_name": "string",
      "car_model_name": "string",
      "car_model_display_name": "string | null",
      "generation_name": "string",
      "display_name": "string | null",
      "start_year": 2020,
      "end_year": null,
      "description": "string | null",
      "image_urls": ["string"],
      "display_label": "string"
    }
  ],
  "next_cursor": "string | null",
  "has_next": false
}
```

### GET `/car-generations/search`

Query: `q` (required), `limit`, `cursor`. Same `CursorPage[CarGenerationRead]`
body as the list route.

---

### GET `/part-manufacturers/`

Query: `active_only` (default `true`).

Response `200`: a bare array of `PartManufacturerResponse`.

```json
[
  {
    "id": "uuid",
    "name": "string",
    "description": "string | null",
    "is_active": true,
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

### GET `/part-manufacturers/search`

Query: `q` (required), `limit`, `cursor`. Response `200`: a
**`CursorPage[PartManufacturerResponse]`**, unlike the plain list route.

### POST `/part-manufacturers/`

Request (`PartManufacturerCreate`):

```json
{ "name": "string", "description": "string | null", "is_active": true }
```

Response `200`: one `PartManufacturerResponse`. The route dedupes on a case
insensitive name match and returns the existing manufacturer, so a create on an
existing brand is not a `409`.

---

### GET `/retailers/`

Query: `active_only` (default `true`). Response `200`: a bare array of
`RetailerRead`.

```json
[
  {
    "id": "uuid",
    "name": "string",
    "domain": "string | null",
    "base_url": "string | null",
    "is_active": true,
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

### POST `/retailers/get-or-create`

Request:

```json
{
  "domain": "a90shop.com",
  "name": "string (optional, derived from the domain when omitted)",
  "base_url": "string (optional)"
}
```

Response `200`: one `RetailerRead`. `400` when `domain` is blank.

---

### GET `/parts/check-url`

Query: `product_url`.

Response `200`:

```json
{ "existing_part_id": "uuid | null" }
```

The route swallows its own errors and answers `200` with a null id rather than
raising, so a null result does not prove the catalog was reachable.

### GET `/parts/{part_id}`

Response `200`: one `PartRead`. This is the generic CRUD read route, so it
carries **no `listings` and no `best_listing`**; those belong to
`/parts/{part_id}/with-listings`, which the extension does not call.

```json
{
  "id": "uuid",
  "name": "string",
  "description": "string | null",
  "best_price_cents": null,
  "image_urls": ["presigned url"],
  "category_id": "uuid",
  "user_id": "uuid",
  "car_ids": ["uuid"],
  "is_universal": false,
  "part_manufacturer_id": "uuid | null",
  "part_number": "string | null",
  "gtin": "string | null",
  "canonical_part_id": "uuid | null",
  "edit_count": 0,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

`PartRead` has no `is_verified` and no `source` field.

### GET `/parts/find-by-part-manufacturer-and-part-number`

Query: `part_manufacturer_id` (uuid, required), `part_number` (required, min
length 1).

Response `200`: one `PartRead`. `404` when nothing matches, which is how the
scraper tells an update from a create.

### POST `/parts/`

Request (`PartCreate`):

```json
{
  "name": "string",
  "description": "string | null",
  "image_urls": ["file key or external url"],
  "product_url": "string | null",
  "category_id": "uuid",
  "car_ids": ["uuid"],
  "is_universal": false,
  "part_manufacturer_id": "uuid | null",
  "part_number": "string | null",
  "gtin": "string | null",
  "retailer_id": "uuid | null",
  "price_cents": 0
}
```

`image_urls` is capped at 12 entries; the first is the primary image.
`part_manufacturer_id` is **optional**: a scrape that cannot determine the brand
leaves it null. `price_cents` must be 0 to 2147483647. There is no top level
`price` field on the request.

Response `200`: one `PartRead`. `409` when the part already exists.

### POST `/parts/{part_id}/listings`

Request (`PartListingCreate`):

```json
{
  "part_id": "uuid",
  "retailer_id": "uuid",
  "product_url": "string | null",
  "price_cents": 0
}
```

The body `part_id` must equal the path `part_id`, or the route answers `409`
with error code `PART_ID_MISMATCH`. `404` when the part or retailer is unknown.

Response `200` (`PartListingReadWithRetailer`):

```json
{
  "id": "uuid",
  "part_id": "uuid",
  "retailer_id": "uuid",
  "product_url": "string | null",
  "last_known_price_cents": 0,
  "last_price_updated_at": "datetime | null",
  "created_at": "datetime",
  "updated_at": "datetime",
  "retailer": { "...RetailerRead": "" }
}
```

### POST `/parts/{part_id}/append-images`

Request:

```json
{ "file_keys": ["string"] }
```

Response `200`: the updated `PartRead`. `400` when the gallery already holds 12
images; the extension's `MAX_IMAGES_PER_GLOBAL_PART` must equal the backend's
`MAX_IMAGES_PER_PART`, which is 12.

---

### GET `/images/by-source-url`

Query: `source_url`. The backend canonicalizes the URL before looking it up.

Response `200`:

```json
{ "file_key": "string" }
```

`404` when nothing is cached for that source URL, which is the normal signal that
an image still needs fetching.

### POST `/images/fetch-from-url`

Request:

```json
{
  "source_url": "https://...",
  "entity_type": "part",
  "entity_id": "uuid (optional)"
}
```

The extension always sends `entity_type: "part"`, plus `entity_id` when it
already has a part, which lets the backend refuse an upload onto a full gallery.

Response `200`:

```json
{
  "file_key": "string",
  "presigned_url": "string",
  "message": "string"
}
```

The server fetches the bytes, not the extension: a service worker fetch to a
retailer image CDN is an ordinary cross origin request, most of those CDNs send
no `Access-Control-Allow-Origin`, and the hosts are whatever page the user
scraped, so `host_permissions` cannot cover them.

---

### POST `/crawled-pages/scrape`

Request:

```json
{ "url": "https://...", "html": "<!doctype html>..." }
```

Response `200` (`ScrapeResponse`):

```json
{
  "name": "string | null",
  "description": "string | null",
  "price": 0,
  "image_urls": ["string"],
  "product_url": "string",
  "part_manufacturer": "string | null",
  "part_number": "string | null",
  "adapter_used": "generic",
  "inferred_category": "string | null",
  "html_size_bytes": 0,
  "html_sha256": "string"
}
```

`price` is in **cents**, from the parser's `price_cents`. There is no `archived`
and no `archive_skipped_duplicate` field. A page the parser cannot read still
answers `200`, with every parsed field null or empty.

`400` when `url` or `html` is blank. `413` when the HTML exceeds
`CRAWLED_PAGE_MAX_HTML_BYTES`.

## Error envelope

A non-2xx body carries `detail`, either a plain string or an object with
`error_code` and `message`. `apiRequest` reads `detail.message` when `detail` is
an object and falls back to `HTTP <status>: <statusText>`.
