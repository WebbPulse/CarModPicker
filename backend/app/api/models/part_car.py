"""
Association table for many-to-many between Part and Car.
A part can be associated with multiple cars, or marked as universal (fits all cars).
"""

from sqlalchemy import Column, ForeignKey, Table, Uuid

from app.db.base_class import Base

part_cars = Table(
    "part_cars",
    Base.metadata,
    Column("part_id", Uuid(as_uuid=True), ForeignKey("parts.id", ondelete="CASCADE"), primary_key=True),
    Column("car_id", Uuid(as_uuid=True), ForeignKey("car_generations.id", ondelete="CASCADE"), primary_key=True),
)
