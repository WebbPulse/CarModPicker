#!/usr/bin/env python3
"""
Script to populate cars (car generations) for popular modern cars since the 70s.

Usage:
    cd backend
    python ../scripts/populate_car_generations.py
"""

import sys
from pathlib import Path

# Add backend directory to path so we can import app modules
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Load .env file from backend directory before importing app modules
from dotenv import load_dotenv

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"Loaded .env file from: {env_path}")
else:
    print(f"Warning: .env file not found at {env_path}")

from sqlalchemy.orm import Session

from app.api.models.car import (
    Car,
)  # pyright: ignore[reportMissingImports]
from app.db.session import SessionLocal  # pyright: ignore[reportMissingImports]


def create_car_generations(db: Session) -> list[Car]:
    """Create car generations for popular modern cars since the 70s."""
    print("Creating car generations...")

    # Define car generations with make, model, generation name, start year, end year, and optional description
    # Focus on date ranges that represent what is commonly referred to as the generation
    generations_data = [
        # Honda Civic (1972-present)
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "1st Gen",
            "start_year": 1972,
            "end_year": 1979,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "2nd Gen",
            "start_year": 1980,
            "end_year": 1983,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "3rd Gen",
            "start_year": 1984,
            "end_year": 1987,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "4th Gen",
            "start_year": 1988,
            "end_year": 1991,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "5th Gen",
            "start_year": 1992,
            "end_year": 1995,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "6th Gen",
            "start_year": 1996,
            "end_year": 2000,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "7th Gen",
            "start_year": 2001,
            "end_year": 2005,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "8th Gen",
            "start_year": 2006,
            "end_year": 2011,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "9th Gen",
            "start_year": 2012,
            "end_year": 2015,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "10th Gen",
            "start_year": 2016,
            "end_year": 2021,
        },
        {
            "make": "Honda",
            "model": "Civic",
            "generation_name": "11th Gen",
            "start_year": 2022,
            "end_year": 2024,
        },
        # Honda Accord (1976-present)
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "1st Gen",
            "start_year": 1976,
            "end_year": 1981,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "2nd Gen",
            "start_year": 1982,
            "end_year": 1985,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "3rd Gen",
            "start_year": 1986,
            "end_year": 1989,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "4th Gen",
            "start_year": 1990,
            "end_year": 1993,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "5th Gen",
            "start_year": 1994,
            "end_year": 1997,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "6th Gen",
            "start_year": 1998,
            "end_year": 2002,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "7th Gen",
            "start_year": 2003,
            "end_year": 2007,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "8th Gen",
            "start_year": 2008,
            "end_year": 2012,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "9th Gen",
            "start_year": 2013,
            "end_year": 2017,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "10th Gen",
            "start_year": 2018,
            "end_year": 2022,
        },
        {
            "make": "Honda",
            "model": "Accord",
            "generation_name": "11th Gen",
            "start_year": 2023,
            "end_year": 2024,
        },
        # Honda Integra (1986-2006)
        {
            "make": "Honda",
            "model": "Integra",
            "generation_name": "1st Gen",
            "start_year": 1986,
            "end_year": 1989,
        },
        {
            "make": "Honda",
            "model": "Integra",
            "generation_name": "2nd Gen",
            "start_year": 1990,
            "end_year": 1993,
        },
        {
            "make": "Honda",
            "model": "Integra",
            "generation_name": "3rd Gen",
            "start_year": 1994,
            "end_year": 2001,
        },
        {
            "make": "Honda",
            "model": "Integra",
            "generation_name": "4th Gen",
            "start_year": 2002,
            "end_year": 2006,
        },
        # Honda Prelude (1978-2001)
        {
            "make": "Honda",
            "model": "Prelude",
            "generation_name": "1st Gen",
            "start_year": 1978,
            "end_year": 1982,
        },
        {
            "make": "Honda",
            "model": "Prelude",
            "generation_name": "2nd Gen",
            "start_year": 1983,
            "end_year": 1987,
        },
        {
            "make": "Honda",
            "model": "Prelude",
            "generation_name": "3rd Gen",
            "start_year": 1988,
            "end_year": 1991,
        },
        {
            "make": "Honda",
            "model": "Prelude",
            "generation_name": "4th Gen",
            "start_year": 1992,
            "end_year": 1996,
        },
        {
            "make": "Honda",
            "model": "Prelude",
            "generation_name": "5th Gen",
            "start_year": 1997,
            "end_year": 2001,
        },
        # Honda S2000 (1999-2009)
        {
            "make": "Honda",
            "model": "S2000",
            "generation_name": "AP1",
            "start_year": 1999,
            "end_year": 2003,
        },
        {
            "make": "Honda",
            "model": "S2000",
            "generation_name": "AP2",
            "start_year": 2004,
            "end_year": 2009,
        },
        # Toyota Corolla (1966-present, focusing on modern generations)
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E70",
            "start_year": 1974,
            "end_year": 1979,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E80",
            "start_year": 1980,
            "end_year": 1983,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E90",
            "start_year": 1984,
            "end_year": 1987,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E100",
            "start_year": 1988,
            "end_year": 1992,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E110",
            "start_year": 1993,
            "end_year": 1997,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E120",
            "start_year": 1998,
            "end_year": 2002,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E140",
            "start_year": 2003,
            "end_year": 2008,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E150",
            "start_year": 2009,
            "end_year": 2013,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E170",
            "start_year": 2014,
            "end_year": 2018,
        },
        {
            "make": "Toyota",
            "model": "Corolla",
            "generation_name": "E210",
            "start_year": 2019,
            "end_year": 2024,
        },
        # Toyota Camry (1982-present)
        {
            "make": "Toyota",
            "model": "Camry",
            "generation_name": "V10",
            "start_year": 1982,
            "end_year": 1986,
        },
        {
            "make": "Toyota",
            "model": "Camry",
            "generation_name": "V20",
            "start_year": 1987,
            "end_year": 1991,
        },
        {
            "make": "Toyota",
            "model": "Camry",
            "generation_name": "XV10",
            "start_year": 1992,
            "end_year": 1996,
        },
        {
            "make": "Toyota",
            "model": "Camry",
            "generation_name": "XV20",
            "start_year": 1997,
            "end_year": 2001,
        },
        {
            "make": "Toyota",
            "model": "Camry",
            "generation_name": "XV30",
            "start_year": 2002,
            "end_year": 2006,
        },
        {
            "make": "Toyota",
            "model": "Camry",
            "generation_name": "XV40",
            "start_year": 2007,
            "end_year": 2011,
        },
        {
            "make": "Toyota",
            "model": "Camry",
            "generation_name": "XV50",
            "start_year": 2012,
            "end_year": 2017,
        },
        {
            "make": "Toyota",
            "model": "Camry",
            "generation_name": "XV70",
            "start_year": 2018,
            "end_year": 2024,
        },
        # Toyota Supra (1978-present)
        {
            "make": "Toyota",
            "model": "Supra",
            "generation_name": "A40",
            "start_year": 1978,
            "end_year": 1981,
        },
        {
            "make": "Toyota",
            "model": "Supra",
            "generation_name": "A60",
            "start_year": 1982,
            "end_year": 1986,
        },
        {
            "make": "Toyota",
            "model": "Supra",
            "generation_name": "A70",
            "start_year": 1987,
            "end_year": 1992,
        },
        {
            "make": "Toyota",
            "model": "Supra",
            "generation_name": "A80",
            "start_year": 1993,
            "end_year": 2002,
        },
        {
            "make": "Toyota",
            "model": "Supra",
            "generation_name": "A90",
            "start_year": 2019,
            "end_year": 2024,
        },
        # Toyota 86 / GT86 / FR-S (2012-present)
        {
            "make": "Toyota",
            "model": "86",
            "generation_name": "ZN6",
            "start_year": 2012,
            "end_year": 2020,
        },
        {
            "make": "Toyota",
            "model": "86",
            "generation_name": "ZN8",
            "start_year": 2021,
            "end_year": 2024,
        },
        # Subaru WRX / Impreza WRX (1992-present)
        {
            "make": "Subaru",
            "model": "WRX",
            "generation_name": "GC",
            "start_year": 1992,
            "end_year": 2000,
        },
        {
            "make": "Subaru",
            "model": "WRX",
            "generation_name": "GD",
            "start_year": 2001,
            "end_year": 2007,
        },
        {
            "make": "Subaru",
            "model": "WRX",
            "generation_name": "GR",
            "start_year": 2008,
            "end_year": 2014,
        },
        {
            "make": "Subaru",
            "model": "WRX",
            "generation_name": "VA",
            "start_year": 2015,
            "end_year": 2021,
        },
        {
            "make": "Subaru",
            "model": "WRX",
            "generation_name": "VB",
            "start_year": 2022,
            "end_year": 2024,
        },
        # Subaru BRZ (2012-present)
        {
            "make": "Subaru",
            "model": "BRZ",
            "generation_name": "ZC6",
            "start_year": 2012,
            "end_year": 2020,
        },
        {
            "make": "Subaru",
            "model": "BRZ",
            "generation_name": "ZD8",
            "start_year": 2021,
            "end_year": 2024,
        },
        # Nissan GT-R / Skyline GT-R (1969-present)
        {
            "make": "Nissan",
            "model": "GT-R",
            "generation_name": "PGC10",
            "start_year": 1969,
            "end_year": 1972,
        },
        {
            "make": "Nissan",
            "model": "GT-R",
            "generation_name": "KPGC110",
            "start_year": 1973,
            "end_year": 1973,
        },
        {
            "make": "Nissan",
            "model": "GT-R",
            "generation_name": "R32",
            "start_year": 1989,
            "end_year": 1994,
        },
        {
            "make": "Nissan",
            "model": "GT-R",
            "generation_name": "R33",
            "start_year": 1995,
            "end_year": 1998,
        },
        {
            "make": "Nissan",
            "model": "GT-R",
            "generation_name": "R34",
            "start_year": 1999,
            "end_year": 2002,
        },
        {
            "make": "Nissan",
            "model": "GT-R",
            "generation_name": "R35",
            "start_year": 2007,
            "end_year": 2024,
        },
        # Nissan 350Z (2002-2009)
        {
            "make": "Nissan",
            "model": "350Z",
            "generation_name": "Z33",
            "start_year": 2002,
            "end_year": 2009,
        },
        # Nissan 370Z (2009-2020)
        {
            "make": "Nissan",
            "model": "370Z",
            "generation_name": "Z34",
            "start_year": 2009,
            "end_year": 2020,
        },
        # Nissan 240SX / Silvia (1989-1998)
        {
            "make": "Nissan",
            "model": "240SX",
            "generation_name": "S13",
            "start_year": 1989,
            "end_year": 1994,
        },
        {
            "make": "Nissan",
            "model": "240SX",
            "generation_name": "S14",
            "start_year": 1995,
            "end_year": 1998,
        },
        # Mazda Miata / MX-5 (1989-present)
        {
            "make": "Mazda",
            "model": "Miata",
            "generation_name": "NA",
            "start_year": 1989,
            "end_year": 1997,
        },
        {
            "make": "Mazda",
            "model": "Miata",
            "generation_name": "NB",
            "start_year": 1998,
            "end_year": 2005,
        },
        {
            "make": "Mazda",
            "model": "Miata",
            "generation_name": "NC",
            "start_year": 2006,
            "end_year": 2015,
        },
        {
            "make": "Mazda",
            "model": "Miata",
            "generation_name": "ND",
            "start_year": 2016,
            "end_year": 2024,
        },
        # Mazda RX-7 (1978-2002)
        {
            "make": "Mazda",
            "model": "RX-7",
            "generation_name": "SA/FB",
            "start_year": 1978,
            "end_year": 1985,
        },
        {
            "make": "Mazda",
            "model": "RX-7",
            "generation_name": "FC",
            "start_year": 1986,
            "end_year": 1991,
        },
        {
            "make": "Mazda",
            "model": "RX-7",
            "generation_name": "FD",
            "start_year": 1992,
            "end_year": 2002,
        },
        # Ford Mustang (1964-present)
        {
            "make": "Ford",
            "model": "Mustang",
            "generation_name": "1st Gen",
            "start_year": 1964,
            "end_year": 1973,
        },
        {
            "make": "Ford",
            "model": "Mustang",
            "generation_name": "2nd Gen",
            "start_year": 1974,
            "end_year": 1978,
        },
        {
            "make": "Ford",
            "model": "Mustang",
            "generation_name": "3rd Gen",
            "start_year": 1979,
            "end_year": 1993,
        },
        {
            "make": "Ford",
            "model": "Mustang",
            "generation_name": "4th Gen",
            "start_year": 1994,
            "end_year": 2004,
        },
        {
            "make": "Ford",
            "model": "Mustang",
            "generation_name": "5th Gen",
            "start_year": 2005,
            "end_year": 2014,
        },
        {
            "make": "Ford",
            "model": "Mustang",
            "generation_name": "6th Gen",
            "start_year": 2015,
            "end_year": 2023,
        },
        {
            "make": "Ford",
            "model": "Mustang",
            "generation_name": "7th Gen",
            "start_year": 2024,
            "end_year": 2024,
        },
        # Chevrolet Camaro (1967-present)
        {
            "make": "Chevrolet",
            "model": "Camaro",
            "generation_name": "1st Gen",
            "start_year": 1967,
            "end_year": 1969,
        },
        {
            "make": "Chevrolet",
            "model": "Camaro",
            "generation_name": "2nd Gen",
            "start_year": 1970,
            "end_year": 1981,
        },
        {
            "make": "Chevrolet",
            "model": "Camaro",
            "generation_name": "3rd Gen",
            "start_year": 1982,
            "end_year": 1992,
        },
        {
            "make": "Chevrolet",
            "model": "Camaro",
            "generation_name": "4th Gen",
            "start_year": 1993,
            "end_year": 2002,
        },
        {
            "make": "Chevrolet",
            "model": "Camaro",
            "generation_name": "5th Gen",
            "start_year": 2010,
            "end_year": 2015,
        },
        {
            "make": "Chevrolet",
            "model": "Camaro",
            "generation_name": "6th Gen",
            "start_year": 2016,
            "end_year": 2024,
        },
        # Chevrolet Corvette (1953-present, focusing on modern)
        {
            "make": "Chevrolet",
            "model": "Corvette",
            "generation_name": "C3",
            "start_year": 1968,
            "end_year": 1982,
        },
        {
            "make": "Chevrolet",
            "model": "Corvette",
            "generation_name": "C4",
            "start_year": 1984,
            "end_year": 1996,
        },
        {
            "make": "Chevrolet",
            "model": "Corvette",
            "generation_name": "C5",
            "start_year": 1997,
            "end_year": 2004,
        },
        {
            "make": "Chevrolet",
            "model": "Corvette",
            "generation_name": "C6",
            "start_year": 2005,
            "end_year": 2013,
        },
        {
            "make": "Chevrolet",
            "model": "Corvette",
            "generation_name": "C7",
            "start_year": 2014,
            "end_year": 2019,
        },
        {
            "make": "Chevrolet",
            "model": "Corvette",
            "generation_name": "C8",
            "start_year": 2020,
            "end_year": 2024,
        },
        # BMW 3 Series (1975-present)
        {
            "make": "BMW",
            "model": "M3",
            "generation_name": "E30",
            "start_year": 1986,
            "end_year": 1991,
        },
        {
            "make": "BMW",
            "model": "M3",
            "generation_name": "E36",
            "start_year": 1992,
            "end_year": 1999,
        },
        {
            "make": "BMW",
            "model": "M3",
            "generation_name": "E46",
            "start_year": 2000,
            "end_year": 2006,
        },
        {
            "make": "BMW",
            "model": "M3",
            "generation_name": "E90/E92/E93",
            "start_year": 2007,
            "end_year": 2013,
        },
        {
            "make": "BMW",
            "model": "M3",
            "generation_name": "F80",
            "start_year": 2014,
            "end_year": 2018,
        },
        {
            "make": "BMW",
            "model": "M3",
            "generation_name": "G80",
            "start_year": 2021,
            "end_year": 2024,
        },
        # BMW 3 Series (non-M)
        {
            "make": "BMW",
            "model": "330i",
            "generation_name": "E30",
            "start_year": 1975,
            "end_year": 1990,
        },
        {
            "make": "BMW",
            "model": "330i",
            "generation_name": "E36",
            "start_year": 1991,
            "end_year": 1998,
        },
        {
            "make": "BMW",
            "model": "330i",
            "generation_name": "E46",
            "start_year": 1999,
            "end_year": 2005,
        },
        {
            "make": "BMW",
            "model": "330i",
            "generation_name": "E90/E91/E92/E93",
            "start_year": 2006,
            "end_year": 2011,
        },
        {
            "make": "BMW",
            "model": "330i",
            "generation_name": "F30/F31/F34",
            "start_year": 2012,
            "end_year": 2018,
        },
        {
            "make": "BMW",
            "model": "330i",
            "generation_name": "G20/G21",
            "start_year": 2019,
            "end_year": 2024,
        },
        # BMW M4 (2014-present)
        {
            "make": "BMW",
            "model": "M4",
            "generation_name": "F82/F83",
            "start_year": 2014,
            "end_year": 2020,
        },
        {
            "make": "BMW",
            "model": "M4",
            "generation_name": "G82/G83",
            "start_year": 2021,
            "end_year": 2024,
        },
        # Audi A4 (1994-present)
        {
            "make": "Audi",
            "model": "A4",
            "generation_name": "B5",
            "start_year": 1994,
            "end_year": 2001,
        },
        {
            "make": "Audi",
            "model": "A4",
            "generation_name": "B6",
            "start_year": 2002,
            "end_year": 2005,
        },
        {
            "make": "Audi",
            "model": "A4",
            "generation_name": "B7",
            "start_year": 2006,
            "end_year": 2008,
        },
        {
            "make": "Audi",
            "model": "A4",
            "generation_name": "B8",
            "start_year": 2009,
            "end_year": 2015,
        },
        {
            "make": "Audi",
            "model": "A4",
            "generation_name": "B9",
            "start_year": 2016,
            "end_year": 2023,
        },
        {
            "make": "Audi",
            "model": "A4",
            "generation_name": "B10",
            "start_year": 2024,
            "end_year": 2024,
        },
        # Audi S4
        {
            "make": "Audi",
            "model": "S4",
            "generation_name": "B5",
            "start_year": 1994,
            "end_year": 2001,
        },
        {
            "make": "Audi",
            "model": "S4",
            "generation_name": "B6",
            "start_year": 2002,
            "end_year": 2005,
        },
        {
            "make": "Audi",
            "model": "S4",
            "generation_name": "B7",
            "start_year": 2006,
            "end_year": 2008,
        },
        {
            "make": "Audi",
            "model": "S4",
            "generation_name": "B8",
            "start_year": 2009,
            "end_year": 2015,
        },
        {
            "make": "Audi",
            "model": "S4",
            "generation_name": "B9",
            "start_year": 2016,
            "end_year": 2023,
        },
        # Audi TT (1998-present)
        {
            "make": "Audi",
            "model": "TT",
            "generation_name": "8N",
            "start_year": 1998,
            "end_year": 2006,
        },
        {
            "make": "Audi",
            "model": "TT",
            "generation_name": "8J",
            "start_year": 2007,
            "end_year": 2014,
        },
        {
            "make": "Audi",
            "model": "TT",
            "generation_name": "8S",
            "start_year": 2015,
            "end_year": 2023,
        },
        # Mercedes-Benz C-Class (1993-present)
        {
            "make": "Mercedes",
            "model": "C-Class",
            "generation_name": "W202",
            "start_year": 1993,
            "end_year": 2000,
        },
        {
            "make": "Mercedes",
            "model": "C-Class",
            "generation_name": "W203",
            "start_year": 2001,
            "end_year": 2007,
        },
        {
            "make": "Mercedes",
            "model": "C-Class",
            "generation_name": "W204",
            "start_year": 2008,
            "end_year": 2014,
        },
        {
            "make": "Mercedes",
            "model": "C-Class",
            "generation_name": "W205",
            "start_year": 2015,
            "end_year": 2021,
        },
        {
            "make": "Mercedes",
            "model": "C-Class",
            "generation_name": "W206",
            "start_year": 2022,
            "end_year": 2024,
        },
        # Dodge Challenger (1970-present)
        {
            "make": "Dodge",
            "model": "Challenger",
            "generation_name": "1st Gen",
            "start_year": 1970,
            "end_year": 1974,
        },
        {
            "make": "Dodge",
            "model": "Challenger",
            "generation_name": "2nd Gen",
            "start_year": 1978,
            "end_year": 1983,
        },
        {
            "make": "Dodge",
            "model": "Challenger",
            "generation_name": "3rd Gen",
            "start_year": 2008,
            "end_year": 2023,
        },
        # Dodge Charger (1966-present, modern)
        {
            "make": "Dodge",
            "model": "Charger",
            "generation_name": "LX",
            "start_year": 2006,
            "end_year": 2010,
        },
        {
            "make": "Dodge",
            "model": "Charger",
            "generation_name": "LD",
            "start_year": 2011,
            "end_year": 2023,
        },
        {
            "make": "Dodge",
            "model": "Charger",
            "generation_name": "LB",
            "start_year": 2024,
            "end_year": 2024,
        },
        # Volkswagen Golf / GTI (1974-present)
        {
            "make": "Volkswagen",
            "model": "Golf",
            "generation_name": "Mk1",
            "start_year": 1974,
            "end_year": 1983,
        },
        {
            "make": "Volkswagen",
            "model": "Golf",
            "generation_name": "Mk2",
            "start_year": 1984,
            "end_year": 1992,
        },
        {
            "make": "Volkswagen",
            "model": "Golf",
            "generation_name": "Mk3",
            "start_year": 1993,
            "end_year": 1998,
        },
        {
            "make": "Volkswagen",
            "model": "Golf",
            "generation_name": "Mk4",
            "start_year": 1999,
            "end_year": 2005,
        },
        {
            "make": "Volkswagen",
            "model": "Golf",
            "generation_name": "Mk5",
            "start_year": 2006,
            "end_year": 2009,
        },
        {
            "make": "Volkswagen",
            "model": "Golf",
            "generation_name": "Mk6",
            "start_year": 2010,
            "end_year": 2014,
        },
        {
            "make": "Volkswagen",
            "model": "Golf",
            "generation_name": "Mk7",
            "start_year": 2015,
            "end_year": 2020,
        },
        {
            "make": "Volkswagen",
            "model": "Golf",
            "generation_name": "Mk8",
            "start_year": 2021,
            "end_year": 2024,
        },
        # Acura Integra (1986-2006)
        {
            "make": "Acura",
            "model": "Integra",
            "generation_name": "1st Gen",
            "start_year": 1986,
            "end_year": 1989,
        },
        {
            "make": "Acura",
            "model": "Integra",
            "generation_name": "2nd Gen",
            "start_year": 1990,
            "end_year": 1993,
        },
        {
            "make": "Acura",
            "model": "Integra",
            "generation_name": "3rd Gen",
            "start_year": 1994,
            "end_year": 2001,
        },
        {
            "make": "Acura",
            "model": "Integra",
            "generation_name": "4th Gen",
            "start_year": 2002,
            "end_year": 2006,
        },
        # Acura NSX (1990-present)
        {
            "make": "Acura",
            "model": "NSX",
            "generation_name": "NA1/NA2",
            "start_year": 1990,
            "end_year": 2005,
        },
        {
            "make": "Acura",
            "model": "NSX",
            "generation_name": "NC1",
            "start_year": 2016,
            "end_year": 2022,
        },
        # Lexus IS (1998-present)
        {
            "make": "Lexus",
            "model": "IS",
            "generation_name": "XE10",
            "start_year": 1998,
            "end_year": 2005,
        },
        {
            "make": "Lexus",
            "model": "IS",
            "generation_name": "XE20",
            "start_year": 2006,
            "end_year": 2013,
        },
        {
            "make": "Lexus",
            "model": "IS",
            "generation_name": "XE30",
            "start_year": 2014,
            "end_year": 2020,
        },
        {
            "make": "Lexus",
            "model": "IS",
            "generation_name": "XE40",
            "start_year": 2021,
            "end_year": 2024,
        },
        # Mitsubishi Lancer Evolution (1992-2016)
        {
            "make": "Mitsubishi",
            "model": "Lancer Evolution",
            "generation_name": "I",
            "start_year": 1992,
            "end_year": 1995,
        },
        {
            "make": "Mitsubishi",
            "model": "Lancer Evolution",
            "generation_name": "II",
            "start_year": 1996,
            "end_year": 1998,
        },
        {
            "make": "Mitsubishi",
            "model": "Lancer Evolution",
            "generation_name": "III",
            "start_year": 1999,
            "end_year": 2000,
        },
        {
            "make": "Mitsubishi",
            "model": "Lancer Evolution",
            "generation_name": "IV",
            "start_year": 2001,
            "end_year": 2002,
        },
        {
            "make": "Mitsubishi",
            "model": "Lancer Evolution",
            "generation_name": "V",
            "start_year": 2003,
            "end_year": 2005,
        },
        {
            "make": "Mitsubishi",
            "model": "Lancer Evolution",
            "generation_name": "VI",
            "start_year": 2006,
            "end_year": 2007,
        },
        {
            "make": "Mitsubishi",
            "model": "Lancer Evolution",
            "generation_name": "VII",
            "start_year": 2008,
            "end_year": 2010,
        },
        {
            "make": "Mitsubishi",
            "model": "Lancer Evolution",
            "generation_name": "VIII",
            "start_year": 2011,
            "end_year": 2015,
        },
        {
            "make": "Mitsubishi",
            "model": "Lancer Evolution",
            "generation_name": "IX",
            "start_year": 2016,
            "end_year": 2016,
        },
        # Porsche 911 (1963-present, modern focus)
        {
            "make": "Porsche",
            "model": "911",
            "generation_name": "930",
            "start_year": 1975,
            "end_year": 1989,
        },
        {
            "make": "Porsche",
            "model": "911",
            "generation_name": "964",
            "start_year": 1989,
            "end_year": 1994,
        },
        {
            "make": "Porsche",
            "model": "911",
            "generation_name": "993",
            "start_year": 1995,
            "end_year": 1998,
        },
        {
            "make": "Porsche",
            "model": "911",
            "generation_name": "996",
            "start_year": 1999,
            "end_year": 2004,
        },
        {
            "make": "Porsche",
            "model": "911",
            "generation_name": "997",
            "start_year": 2005,
            "end_year": 2012,
        },
        {
            "make": "Porsche",
            "model": "911",
            "generation_name": "991",
            "start_year": 2012,
            "end_year": 2019,
        },
        {
            "make": "Porsche",
            "model": "911",
            "generation_name": "992",
            "start_year": 2020,
            "end_year": 2024,
        },
    ]

    generations = []
    created_count = 0
    skipped_count = 0

    for gen_data in generations_data:
        # Check if car (generation) already exists
        existing = (
            db.query(Car)
            .filter(
                Car.make == gen_data["make"],
                Car.model == gen_data["model"],
                Car.generation_name == gen_data["generation_name"],
            )
            .first()
        )

        if existing:
            print(
                f"Skipping {gen_data['make']} {gen_data['model']} {gen_data['generation_name']} (already exists)"
            )
            skipped_count += 1
            continue

        car = Car(**gen_data)
        db.add(car)
        generations.append(car)
        created_count += 1

    db.commit()
    for gen in generations:
        db.refresh(gen)

    print(f"Created {created_count} cars (generations)")
    if skipped_count > 0:
        print(f"Skipped {skipped_count} cars (generations) (already exist)")
    return generations


def main() -> None:
    """Main function to populate cars (car generations)."""
    print("=" * 60)
    print("Populating cars (generations) for popular modern cars...")
    print("=" * 60)

    db: Session = SessionLocal()

    try:
        generations = create_car_generations(db)

        print("=" * 60)
        print("Car (generation) population complete!")
        print("=" * 60)
        print(f"\nTotal cars (generations) created: {len(generations)}")

    except Exception as e:
        db.rollback()
        print(f"Error populating car generations: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
