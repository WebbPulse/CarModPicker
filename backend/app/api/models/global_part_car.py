"""
Association table for many-to-many between GlobalPart and Car.
A part can be associated with multiple cars, or marked as universal (fits all cars).
"""

from sqlalchemy import ForeignKey, Table, Column

from app.db.base_class import Base

global_part_cars = Table(
    "global_part_cars",
    Base.metadata,
    Column("global_part_id", ForeignKey("global_parts.id", ondelete="CASCADE"), primary_key=True),
    Column("car_id", ForeignKey("cars.id", ondelete="CASCADE"), primary_key=True),
)
