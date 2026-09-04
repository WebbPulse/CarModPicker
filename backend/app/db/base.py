# Registers all ORM models for Alembic; Base is defined in base_class.
# Import all models here so they are attached to Base before Alembic loads env.
# pyright: reportUnusedImport=false
from app.api.models.app_settings import AppSettings  # noqa: F401
from app.api.models.associations.part_car import part_cars  # noqa: F401
from app.api.models.build_list import BuildList  # noqa: F401
from app.api.models.build_list_part import BuildListPart  # noqa: F401
from app.api.models.car_generation import CarGeneration  # noqa: F401
from app.api.models.car_make import CarMake  # noqa: F401
from app.api.models.car_model import CarModel  # noqa: F401
from app.api.models.category import Category  # noqa: F401
from app.api.models.image_source_mapping import ImageSourceMapping  # noqa: F401
from app.api.models.part import Part  # noqa: F401
from app.api.models.part_listing import PartListing  # noqa: F401
from app.api.models.part_price_history import PartPriceHistory  # noqa: F401
from app.api.models.report import Report  # noqa: F401
from app.api.models.retailer import Retailer  # noqa: F401
from app.api.models.vote import Vote  # noqa: F401
from app.db.base_class import Base  # noqa: F401
