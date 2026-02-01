"""
Part category data for the global parts catalog.

This module contains the canonical list of part categories that are available
in the application. Categories are seeded into the database on startup via
init_categories.py.

To add a new part category:
1. Add a new entry to PART_CATEGORIES with: name, display_name, description, icon, sort_order
2. The initialization logic will automatically create it in the database
"""

from typing import TypedDict, cast

from typing_extensions import NotRequired


class PartCategoryData(TypedDict):
    """Type definition for part category data."""

    name: str
    display_name: str
    description: NotRequired[str]
    icon: NotRequired[str]
    sort_order: int


# Part categories - source of truth for the application
PART_CATEGORIES: list[PartCategoryData] = [
    {
        "name": "exhaust",
        "display_name": "Exhaust Systems",
        "description": "Exhaust systems, mufflers, headers, and related components",
        "icon": "🔧",
        "sort_order": 1,
    },
    {
        "name": "suspension",
        "display_name": "Suspension",
        "description": "Coilovers, springs, struts, and suspension components",
        "icon": "📐",
        "sort_order": 2,
    },
    {
        "name": "engine",
        "display_name": "Engine Performance",
        "description": "Turbochargers, superchargers, intakes, and engine mods",
        "icon": "⚙️",
        "sort_order": 3,
    },
    {
        "name": "wheels",
        "display_name": "Wheels & Tires",
        "description": "Wheels, rims, tires, and wheel accessories",
        "icon": "🛞",
        "sort_order": 4,
    },
    {
        "name": "body",
        "display_name": "Body & Aero",
        "description": "Body kits, spoilers, splitters, and aerodynamic components",
        "icon": "🚗",
        "sort_order": 5,
    },
    {
        "name": "interior",
        "display_name": "Interior",
        "description": "Seats, steering wheels, shift knobs, and interior mods",
        "icon": "🪑",
        "sort_order": 6,
    },
    {
        "name": "brakes",
        "display_name": "Brakes",
        "description": "Brake pads, rotors, calipers, and brake systems",
        "icon": "🛑",
        "sort_order": 7,
    },
]


def get_all_part_categories() -> list[PartCategoryData]:
    """
    Return all part category definitions for seeding the database.

    Returns:
        List of dictionaries with name, display_name, description, icon, sort_order
    """
    return cast(list[PartCategoryData], [dict(cat) for cat in PART_CATEGORIES])
