"""
One-shot rename script. Delete after use.

Renames:
  Make entity        -> CarMake
  Car entity         -> CarGeneration  (Car was always a generation, not a vehicle)
  entity_type 'car'  -> 'car_generation'  (Vote/Report discriminator)
  Car.make property  -> Car.car_make_name
  Car.model property -> Car.car_model_name
  URL /cars          -> /car-generations  (backend + frontend)

Uses Option 2 (enumerate exact strings) to avoid corrupting CarModel/CarMake,
which contain the substring 'Car' or 'Make'.

Exclusions (files skipped):
  - alembic/versions/*  (historical migrations must not change)
  - node_modules, .git, __pycache__, dist, build, coverage, .venv
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "coverage",
    ".venv",
    "venv",
    ".pytest_cache",
    ".mypy_cache",
    ".next",
    "htmlcov",
}

EXCLUDE_PATH_SUBSTRINGS = [
    "backend/alembic/versions/",
]

INCLUDE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json"}

# Order matters WITHIN a category (longest/most-specific first), but categories
# are independent. We apply all replacements to each file in one pass.
REPLACEMENTS: List[Tuple[str, str]] = [
    # ---- Make -> CarMake (Python imports / identifiers) ----
    ("from app.api.models.make import Make", "from app.api.models.car_make import CarMake"),
    ("from app.api.models.make", "from app.api.models.car_make"),
    ("from .make import Make", "from .car_make import CarMake"),
    # CarModel.make relationship attribute rename (atomic: left-hand + type)
    ('make: Mapped["Make"] = relationship("Make",', 'car_make: Mapped["CarMake"] = relationship("CarMake",'),
    ('Mapped[List["Make"]]', 'Mapped[List["CarMake"]]'),
    ('Mapped["Make"]', 'Mapped["CarMake"]'),
    ('relationship("Make"', 'relationship("CarMake"'),
    ('ForeignKey("makes.id"', 'ForeignKey("car_makes.id"'),
    ('__tablename__ = "makes"', '__tablename__ = "car_makes"'),
    ("class Make(Base):", "class CarMake(Base):"),
    # Unique constraint name
    ("uq_car_models_make_id_name", "uq_car_models_car_make_id_name"),
    # Column/attribute names on CarModel (make_id -> car_make_id)
    ("CarModel.make_id", "CarModel.car_make_id"),
    ("CarModel(make_id=", "CarModel(car_make_id="),
    ('"make_id"', '"car_make_id"'),  # within ORM string args
    (".make_id ==", ".car_make_id =="),
    (" make_id ", " car_make_id "),  # prose in comments
    # relationship name: CarModel.make (ORM relation attr) -> CarModel.car_make
    ("CarModel.make ==", "CarModel.car_make =="),
    (".join(CarModel.make)", ".join(CarModel.car_make)"),
    ("joinedload(CarModel.make)", "joinedload(CarModel.car_make)"),
    # car_model.make -> car_model.car_make (attribute access, Python)
    (".car_model.make.name", ".car_model.car_make.name"),
    ("car_model.make.name", "car_model.car_make.name"),
    # back_populates inside Make.car_models relationship
    ('back_populates="make"', 'back_populates="car_make"'),

    # ---- Car -> CarGeneration (Python imports / identifiers) ----
    ("from app.api.models.car import Car as DBCar", "from app.api.models.car_generation import CarGeneration as DBCar"),
    ("from app.api.models.car import Car", "from app.api.models.car_generation import CarGeneration"),
    ("from app.api.models.car ", "from app.api.models.car_generation "),
    ("from app.api.schemas.car import", "from app.api.schemas.car_generation import"),
    ("from app.api.services.car_service import", "from app.api.services.car_generation_service import"),
    ("from .car import Car", "from .car_generation import CarGeneration"),
    # Atomic: rename 'cars' attribute on Part/CarModel (with type) -> 'car_generations'
    ('cars: Mapped[List["Car"]] = relationship(', 'car_generations: Mapped[List["CarGeneration"]] = relationship('),
    # SQLAlchemy quoted class refs
    ('Mapped[List["Car"]]', 'Mapped[List["CarGeneration"]]'),
    ('Mapped["Car"]', 'Mapped["CarGeneration"]'),
    ('relationship("Car"', 'relationship("CarGeneration"'),
    # .cars attribute accesses (on Part instances) -> .car_generations
    ("self.cars", "self.car_generations"),
    (".cars = [", ".car_generations = ["),
    (".cars = []", ".car_generations = []"),
    (".cars or [])", ".car_generations or [])"),
    ("if p.cars", "if p.car_generations"),
    ("len(p.cars)", "len(p.car_generations)"),
    ("for c in p.cars]", "for c in p.car_generations]"),
    ("GlobalPart.cars", "GlobalPart.car_generations"),
    # back_populates="cars" -> "car_generations"
    ('back_populates="cars"', 'back_populates="car_generations"'),
    # Primary join strings embed Car.id
    ("Vote.entity_id == Car.id", "Vote.entity_id == CarGeneration.id"),
    ("Report.entity_id == Car.id", "Report.entity_id == CarGeneration.id"),
    # Vote/Report discriminator string 'car' -> 'car_generation'
    ("Vote.entity_type == 'car'", "Vote.entity_type == 'car_generation'"),
    ("Report.entity_type == 'car'", "Report.entity_type == 'car_generation'"),
    # Table name
    ('__tablename__ = "cars"', '__tablename__ = "car_generations"'),
    # Foreign key references to cars table
    ('ForeignKey("cars.id"', 'ForeignKey("car_generations.id"'),
    # Class def
    ("class Car(Base):", "class CarGeneration(Base):"),
    # back_populates="car" -> "car_generation" (on BuildList.car FK)
    ('back_populates="car"', 'back_populates="car_generation"'),
    # Association table ref in part.py: secondary="part_cars"
    # (leave - secondary table stays part_cars; only change if we decide to rename)
    # Schema classes
    ("class CarCreate(BaseModel):", "class CarGenerationCreate(BaseModel):"),
    ("class CarUpdate(BaseModel):", "class CarGenerationUpdate(BaseModel):"),
    ("class CarRead(BaseModel):", "class CarGenerationRead(BaseModel):"),
    # Schema/service class refs in type hints and calls
    ("BaseCRUDService[DBCar, CarCreate, CarRead, CarUpdate]", "BaseCRUDService[DBCar, CarGenerationCreate, CarGenerationRead, CarGenerationUpdate]"),
    ("CarCreate,", "CarGenerationCreate,"),
    ("CarRead,", "CarGenerationRead,"),
    ("CarUpdate,", "CarGenerationUpdate,"),
    ("CarCreate)", "CarGenerationCreate)"),
    ("CarRead)", "CarGenerationRead)"),
    ("CarUpdate)", "CarGenerationUpdate)"),
    ("CarRead]", "CarGenerationRead]"),
    ("CarCreate]", "CarGenerationCreate]"),
    ("CarUpdate]", "CarGenerationUpdate]"),
    ("CarRead.model_validate", "CarGenerationRead.model_validate"),
    ("[CarRead]", "[CarGenerationRead]"),
    ("-> List[CarRead]", "-> List[CarGenerationRead]"),
    ("-> CarRead", "-> CarGenerationRead"),
    ("response_model=List[CarRead]", "response_model=List[CarGenerationRead]"),
    ("response_model=CarRead", "response_model=CarGenerationRead"),
    # Service class rename
    ("class CarService(BaseCRUDService", "class CarGenerationService(BaseCRUDService"),
    ("CarService()", "CarGenerationService()"),
    ("CarService(", "CarGenerationService("),
    ("car_service = ", "car_generation_service = "),
    ("car_service.", "car_generation_service."),
    ("car_service,", "car_generation_service,"),
    ("car_service=", "car_generation_service="),

    # ---- URL paths: /cars -> /car-generations ----
    ('"/cars/"', '"/car-generations/"'),
    ("'/cars/'", "'/car-generations/'"),
    ('"/cars/by-ids"', '"/car-generations/by-ids"'),
    ('"/cars/search"', '"/car-generations/search"'),
    ('"/cars/count"', '"/car-generations/count"'),
    ('"/cars/makes/count"', '"/car-generations/car-makes/count"'),
    ('"/cars/stats/makes"', '"/car-generations/stats/car-makes"'),
    ('"/cars/car-models/count"', '"/car-generations/car-models/count"'),
    ("'/cars/by-ids'", "'/car-generations/by-ids'"),
    ("'/cars/search'", "'/car-generations/search'"),
    ("'/cars/count'", "'/car-generations/count'"),
    ("'/cars/makes/count'", "'/car-generations/car-makes/count'"),
    ("'/cars/stats/makes'", "'/car-generations/stats/car-makes'"),
    ("'/cars/car-models/count'", "'/car-generations/car-models/count'"),
    # URL template literals with interpolation (backticks)
    ("`/cars/${", "`/car-generations/${"),
    ("/cars/make/", "/car-generations/car-makes/"),  # backend route & frontend paths
    # Registry pattern strings (backend main.py)
    ('router_prefix="/cars"', 'router_prefix="/car-generations"'),
    ('prefix="/cars"', 'prefix="/car-generations"'),
    ("prefix='/cars'", "prefix='/car-generations'"),

    # ---- entity_type string 'car' ----
    # enum and dispatcher references
    ('CAR = "car"', 'CAR_GENERATION = "car_generation"'),
    ("EntityType.CAR ", "EntityType.CAR_GENERATION "),
    ("EntityType.CAR,", "EntityType.CAR_GENERATION,"),
    ("EntityType.CAR)", "EntityType.CAR_GENERATION)"),
    ("EntityType.CAR:", "EntityType.CAR_GENERATION:"),
    # "car" as entity type in lists
    ('"build_list", "part", "user", "car"', '"build_list", "part", "user", "car_generation"'),
    ('"build_list", "part", "user", "car", "build_log_post"', '"build_list", "part", "user", "car_generation", "build_log_post"'),
    # Comparisons
    ('DBVote.entity_type == "car"', 'DBVote.entity_type == "car_generation"'),
    ('entity_type == "car"', 'entity_type == "car_generation"'),
    # Test assertions
    ('vote.entity_type == "car"', 'vote.entity_type == "car_generation"'),
    ('data["entity_type"] == "car"', 'data["entity_type"] == "car_generation"'),
    ('summary["entity_type"] == "car"', 'summary["entity_type"] == "car_generation"'),
    # Test dict access for by_entity_type summary
    ('by_entity_type"]["car"]', 'by_entity_type"]["car_generation"]'),

    # ---- images.py specific ----
    ('elif entity_type == "car":', 'elif entity_type == "car_generation":'),

    # ---- entity_name constructor args ----
    ('entity_name="car"', 'entity_name="car_generation"'),
    ("entity_name='car'", "entity_name='car_generation'"),

    # ---- BuildList.car attribute (left-hand side) ----
    ('    car: Mapped["Car"]', '    car_generation: Mapped["CarGeneration"]'),
    ('    car: Mapped[Optional["Car"]]', '    car_generation: Mapped[Optional["CarGeneration"]]'),

    # ---- EntityType.CAR with additional suffixes ----
    ("EntityType.CAR}", "EntityType.CAR_GENERATION}"),
    ("EntityType.CAR.", "EntityType.CAR_GENERATION."),
    ("EntityType.CAR]", "EntityType.CAR_GENERATION]"),
    ("EntityType.CAR ==", "EntityType.CAR_GENERATION =="),
    ("EntityType.CAR !=", "EntityType.CAR_GENERATION !="),
    ("EntityType.CAR\n", "EntityType.CAR_GENERATION\n"),

    # ---- Python .make / .model attribute renames on Car (via @property) ----
    # These access patterns change from car.make -> car.car_make_name, car.model -> car.car_model_name
    # Very targeted: only match explicit car-variable field accesses
    ("car.make", "car.car_make_name"),
    ("car.model,", "car.car_model_name,"),
    ("car.model)", "car.car_model_name)"),
    ("car.model}", "car.car_model_name}"),
    # NOTE: "car.model" without trailing char is risky since car.model_validate is Pydantic.
    # We rely on specific suffix chars above.

    # ---- Frontend types (TypeScript interfaces) ----
    ("export interface CarCreate ", "export interface CarGenerationCreate "),
    ("export interface CarRead ", "export interface CarGenerationRead "),
    ("export interface CarUpdate ", "export interface CarGenerationUpdate "),
    ("export interface CarCreate {", "export interface CarGenerationCreate {"),
    ("export interface CarRead {", "export interface CarGenerationRead {"),
    ("export interface CarUpdate {", "export interface CarGenerationUpdate {"),
    # Frontend usages (types)
    (": CarRead ", ": CarGenerationRead "),
    (": CarRead;", ": CarGenerationRead;"),
    (": CarRead,", ": CarGenerationRead,"),
    (": CarRead\n", ": CarGenerationRead\n"),
    (": CarRead)", ": CarGenerationRead)"),
    (": CarRead | ", ": CarGenerationRead | "),
    ("<CarRead>", "<CarGenerationRead>"),
    ("<CarRead[]>", "<CarGenerationRead[]>"),
    ("<CarCreate>", "<CarGenerationCreate>"),
    ("<CarUpdate>", "<CarGenerationUpdate>"),
    ("CarRead[]", "CarGenerationRead[]"),
    (" CarRead,", " CarGenerationRead,"),
    (" CarRead;", " CarGenerationRead;"),
    (" CarRead\n", " CarGenerationRead\n"),
    (" CarCreate,", " CarGenerationCreate,"),
    (" CarUpdate,", " CarGenerationUpdate,"),
    (" CarCreate;", " CarGenerationCreate;"),
    (" CarUpdate;", " CarGenerationUpdate;"),
    # API object rename
    ("export const carsApi", "export const carGenerationsApi"),
    ("carsApi.", "carGenerationsApi."),
    (" carsApi,", " carGenerationsApi,"),
    (" carsApi }", " carGenerationsApi }"),
    ("{ carsApi", "{ carGenerationsApi"),
    ("carsApi,\n", "carGenerationsApi,\n"),
]


def should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    rel = path.relative_to(ROOT).as_posix()
    for ex in EXCLUDE_PATH_SUBSTRINGS:
        if rel.startswith(ex):
            return True
    # skip this script itself
    if path.resolve() == Path(__file__).resolve():
        return True
    return False


def main() -> None:
    changed_files: List[str] = []
    total_replacements = 0

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in INCLUDE_EXTS:
            continue
        if should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        new_text = text
        file_replacements = 0
        for old, new in REPLACEMENTS:
            if old in new_text:
                count = new_text.count(old)
                new_text = new_text.replace(old, new)
                file_replacements += count

        if file_replacements > 0:
            path.write_text(new_text, encoding="utf-8")
            changed_files.append(f"{path.relative_to(ROOT).as_posix()} ({file_replacements})")
            total_replacements += file_replacements

    print(f"Changed {len(changed_files)} files, {total_replacements} total replacements.")
    for f in changed_files:
        print(f"  {f}")


if __name__ == "__main__":
    main()
