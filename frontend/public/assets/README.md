# Static UI assets

This folder holds images used in the UI: manufacturer logos, part category icons, and optional generation images. Files here are served at `/assets/` (Vite `public` folder).

## Folder structure

```
assets/
├── manufacturers/   # Car make/manufacturer logos (e.g. Honda, BMW, Aston Martin)
├── categories/      # Part category icons (exhaust, suspension, engine, etc.)
├── generations/     # Optional: per-generation images (make/model/generation)
└── README.md
```

## Naming conventions

### Manufacturers (`manufacturers/`)

- **Filename**: lowercase slug of the make name.
  - One word: `Honda` → `honda.svg`
  - Multiple words: `Aston Martin` → `aston-martin.svg`
- **Formats**: `.svg` (preferred), `.png`, or `.webp`.
- **Usage**: Build Lists Catalog “Select Manufacturer” grid, car selection UI, etc.

Current makes in the app (from car generations data):  
Acura, Aston Martin, Audi, BMW, Chevrolet, Dodge, Ferrari, Ford, Genesis, Honda, Hyundai, Infiniti, Kia, Lamborghini, Lexus, Mazda, McLaren, Mercedes, Mitsubishi, Nissan, Porsche, Scion, Subaru, Toyota, Volkswagen.

### Part categories (`categories/`)

- **Filename**: exact category `name` from backend `part_categories_data.py` (lowercase).
- **Formats**: `.svg` (preferred), `.png`, or `.webp`.
- **Usage**: Parts catalog filters, category chips, part cards.

Category names:  
`exhaust`, `suspension`, `engine`, `wheels`, `body`, `interior`, `brakes`.

### Generations (`generations/`) — optional

- **Structure**: `generations/<make-slug>/<model-slug>/<generation-slug>.(svg|png|webp)`  
  Example: `generations/honda/civic/10th-gen.png`
- Generation imagery can also come from the API (`car.image_url`). Use this folder for static fallbacks or when you don’t store images in the DB.

## Frontend usage

Use the helpers in `src/utils/assetPaths.ts`:

- **Manufacturer logo**: `getManufacturerLogoUrl(make)` → e.g. `/assets/manufacturers/honda.svg`
- **Part category icon**: `getPartCategoryAssetUrl(category.name)` → e.g. `/assets/categories/exhaust.svg`

Handle missing files in the UI (e.g. `onError` fallback to text or placeholder).
