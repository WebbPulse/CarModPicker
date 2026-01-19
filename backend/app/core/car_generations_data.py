"""
Car generation data for popular modern cars since the 70s.

This module contains the canonical list of car generations that are available
in the application. The data is organized by make and model for easy maintenance.

To add a new car generation:
1. Find the make/model section (or create it if it doesn't exist)
2. Add a new generation entry with: generation_name, start_year, end_year
3. The initialization logic will automatically create it in the database
"""

from typing import TypedDict

from typing_extensions import NotRequired


class CarGenerationData(TypedDict):
    """Type definition for car generation data."""

    generation_name: str
    start_year: int
    end_year: int | None  # None for current/ongoing generations
    description: NotRequired[str]  # Optional field


class CarModelData(TypedDict):
    """Type definition for car model data."""

    model: str
    generations: list[CarGenerationData]


# Car generations organized by make and model
CAR_GENERATIONS: dict[str, list[CarModelData]] = {
    "Honda": [
        {
            "model": "Civic",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1972,
                    "end_year": 1979,
                    "description": "The original Civic introduced Honda's reputation for reliability and fuel efficiency. Featured CVCC engine technology and helped establish Honda in the US market.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1980,
                    "end_year": 1983,
                    "description": "Refined design with improved aerodynamics. Introduced the Civic Wagon and continued Honda's focus on fuel efficiency during the oil crisis era.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1984,
                    "end_year": 1987,
                    "description": "Notable for the introduction of the Si trim with sporty performance. Popular among tuners and featured in early import car culture.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1988,
                    "end_year": 1991,
                    "description": "Larger and more refined, with improved safety features. The CRX variant became a cult classic for its lightweight design and handling.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 1992,
                    "end_year": 1995,
                    "description": "Introduced VTEC technology to the Civic lineup. The Si model with B16 engine became legendary in the tuning community.",
                },
                {
                    "generation_name": "6th Gen",
                    "start_year": 1996,
                    "end_year": 2000,
                    "description": "Widely considered one of the best Civic generations. Featured the B16B and B18C engines in Type R variants, highly sought after by enthusiasts.",
                },
                {
                    "generation_name": "7th Gen",
                    "start_year": 2001,
                    "end_year": 2005,
                    "description": "Complete redesign with more modern styling. Introduced the K-series engine family, though some enthusiasts preferred the previous generation's character.",
                },
                {
                    "generation_name": "8th Gen",
                    "start_year": 2006,
                    "end_year": 2011,
                    "description": "Returned to double-wishbone front suspension. The Si model featured a high-revving K20Z3 engine and was praised for its driving dynamics.",
                },
                {
                    "generation_name": "9th Gen",
                    "start_year": 2012,
                    "end_year": 2015,
                    "description": "Refined styling and improved fuel economy. The Si model continued with K24 engine, offering more torque but lower redline than previous generation.",
                },
                {
                    "generation_name": "10th Gen",
                    "start_year": 2016,
                    "end_year": 2021,
                    "description": "First Civic generation with turbocharged engines in mainstream trims. Modern styling with hatchback, coupe, and sedan variants. Type R returned to US market.",
                },
                {
                    "generation_name": "11th Gen",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "More mature and refined design language. Improved technology and safety features while maintaining sporty character, especially in Si and Type R trims.",
                },
            ],
        },
        {
            "model": "Accord",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1976,
                    "end_year": 1981,
                    "description": "Honda's first mid-size sedan, establishing the Accord as a reliable family car. Featured CVCC technology and helped Honda compete in the American market.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1982,
                    "end_year": 1985,
                    "description": "Larger and more refined with improved fuel economy. Introduced the Accord hatchback and established the model as a best-seller.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1986,
                    "end_year": 1989,
                    "description": "First Accord built in the US. Introduced fuel injection and became one of the best-selling cars in America, known for reliability and quality.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1990,
                    "end_year": 1993,
                    "description": "Larger platform with improved safety features. The Accord Wagon was introduced, and the sedan became more upscale in its segment.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 1994,
                    "end_year": 1997,
                    "description": "Complete redesign with more rounded styling. V6 engine option introduced, and the Accord became known for its smooth ride and build quality.",
                },
                {
                    "generation_name": "6th Gen",
                    "start_year": 1998,
                    "end_year": 2002,
                    "description": "Larger and more spacious interior. The V6 model offered strong performance, and this generation maintained Honda's reputation for reliability.",
                },
                {
                    "generation_name": "7th Gen",
                    "start_year": 2003,
                    "end_year": 2007,
                    "description": "Two distinct body styles - sedan and coupe. Introduced i-VTEC technology and improved safety features. Hybrid version introduced.",
                },
                {
                    "generation_name": "8th Gen",
                    "start_year": 2008,
                    "end_year": 2012,
                    "description": "More aggressive styling with improved handling. The V6 coupe became a popular choice for enthusiasts seeking performance and reliability.",
                },
                {
                    "generation_name": "9th Gen",
                    "start_year": 2013,
                    "end_year": 2017,
                    "description": "Refined design with Earth Dreams engine technology. Improved fuel economy and introduced direct injection. Sport trim added for more engaging driving.",
                },
                {
                    "generation_name": "10th Gen",
                    "start_year": 2018,
                    "end_year": 2022,
                    "description": "Complete redesign with turbocharged engines. More dynamic styling and improved technology. The 2.0T engine in Sport and Touring trims offered strong performance.",
                },
                {
                    "generation_name": "11th Gen",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "More mature and sophisticated design. Hybrid powertrain became standard in many markets. Improved technology and safety features while maintaining driving dynamics.",
                },
            ],
        },
        {
            "model": "Integra",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1986,
                    "end_year": 1989,
                    "description": "Honda's sporty compact coupe and sedan. Featured advanced suspension and became popular in the tuning scene for its balance of performance and reliability.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1990,
                    "end_year": 1993,
                    "description": "Refined styling with improved aerodynamics. The GS-R trim introduced VTEC technology, making it a favorite among enthusiasts.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1994,
                    "end_year": 2001,
                    "description": "Widely considered the best Integra generation. Featured the legendary B18C engine in GS-R and Type R variants. Iconic in import tuning culture.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 2002,
                    "end_year": 2006,
                    "description": "Final generation with modern styling. Featured K-series engines and improved safety, though some enthusiasts preferred the previous generation's character.",
                },
            ],
        },
        {
            "model": "Integra Type R",
            "generations": [
                {
                    "generation_name": "DC2",
                    "start_year": 1995,
                    "end_year": 2001,
                    "description": "The legendary DC2 Type R featured a hand-built B18C5 engine, lightweight construction, and track-focused suspension. One of the most revered front-wheel-drive sports cars ever made.",
                },
                {
                    "generation_name": "DC5",
                    "start_year": 2001,
                    "end_year": 2006,
                    "description": "Final Type R generation with K20A engine. Featured improved technology and safety while maintaining the Type R's track-focused character and high-revving nature.",
                },
            ],
        },
        {
            "model": "Prelude",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1978,
                    "end_year": 1982,
                    "description": "Honda's sporty coupe with innovative features. Featured the first use of Honda's CVCC technology in a performance-oriented car.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1983,
                    "end_year": 1987,
                    "description": "More refined with improved handling. Introduced fuel injection and became popular among enthusiasts for its balance of sport and comfort.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1988,
                    "end_year": 1991,
                    "description": "Notable for the introduction of 4-wheel steering (4WS) option. Featured VTEC technology and became a technological showcase for Honda.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1992,
                    "end_year": 1996,
                    "description": "Widely considered the best Prelude generation. Featured H22A VTEC engine and excellent handling. The SH model with ATTS (Active Torque Transfer System) was highly advanced.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 1997,
                    "end_year": 2001,
                    "description": "Final generation with more modern styling. Featured improved H22A4 engine and continued the Prelude's reputation as a sophisticated sport coupe.",
                },
            ],
        },
        {
            "model": "S2000",
            "generations": [
                {
                    "generation_name": "AP1",
                    "start_year": 1999,
                    "end_year": 2003,
                    "description": "Honda's modern roadster celebrating 50 years of the company. Featured a high-revving F20C engine (9000 RPM redline), perfect 50/50 weight distribution, and exceptional handling. Pure driving experience.",
                },
                {
                    "generation_name": "AP2",
                    "start_year": 2004,
                    "end_year": 2009,
                    "description": "Refined version with F22C1 engine offering more torque. Improved suspension tuning and styling updates. Maintained the S2000's reputation as one of the best modern roadsters.",
                },
            ],
        },
        {
            "model": "Civic Type R",
            "generations": [
                {
                    "generation_name": "EK9",
                    "start_year": 1997,
                    "end_year": 2000,
                    "description": "The original Civic Type R, only available in Japan. Featured hand-built B16B engine, lightweight construction, and track-focused suspension. Highly sought after by collectors.",
                },
                {
                    "generation_name": "EP3",
                    "start_year": 2001,
                    "end_year": 2005,
                    "description": "First Type R sold in Europe. Featured K20A2 engine and hatchback body style. Popular among enthusiasts for its high-revving nature and practicality.",
                },
                {
                    "generation_name": "FD2/FN2",
                    "start_year": 2007,
                    "end_year": 2011,
                    "description": "FD2 sedan (Japan) and FN2 hatchback (Europe). Featured K20A engine with improved power. The FD2 is considered one of the best Type R generations.",
                },
                {
                    "generation_name": "FK2",
                    "start_year": 2015,
                    "end_year": 2017,
                    "description": "First turbocharged Type R with K20C1 engine. Produced 306 horsepower and featured aggressive styling. First Type R officially sold in the US market.",
                },
                {
                    "generation_name": "FK8",
                    "start_year": 2017,
                    "end_year": 2021,
                    "description": "Highly acclaimed Type R with 306 horsepower. Set multiple front-wheel-drive lap records at tracks worldwide. Featured advanced aerodynamics and track-focused technology.",
                },
                {
                    "generation_name": "FL5",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "Latest generation with more refined styling. Improved power delivery and handling. Continues the Type R legacy as the ultimate front-wheel-drive performance car.",
                },
            ],
        },
        {
            "model": "NSX",
            "generations": [
                {
                    "generation_name": "NA1/NA2",
                    "start_year": 1990,
                    "end_year": 2005,
                    "description": "The legendary first-generation NSX, co-developed with Ayrton Senna. Featured mid-engine layout, VTEC V6 engine, and all-aluminum construction. Revolutionized supercar expectations with Honda reliability and daily usability. One of the most iconic Japanese supercars ever made.",
                },
                {
                    "generation_name": "NC1",
                    "start_year": 2016,
                    "end_year": 2022,
                    "description": "Second-generation NSX with hybrid powertrain. Featured twin-turbo V6 with three electric motors, all-wheel drive, and advanced aerodynamics. Modern interpretation of the NSX legacy with cutting-edge technology.",
                },
            ],
        },
        {
            "model": "CRX",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1984,
                    "end_year": 1987,
                    "description": "The original CRX, a lightweight two-seater based on the Civic platform. Featured excellent fuel economy and nimble handling. The Si model with fuel injection became popular among early import tuners.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1988,
                    "end_year": 1991,
                    "description": "The legendary second-generation CRX. The Si model featured the B16A VTEC engine (in Japan) and became an icon in the tuning community. Lightweight, high-revving, and incredibly fun to drive. Highly sought after by collectors and enthusiasts.",
                },
            ],
        },
        {
            "model": "Del Sol",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1993,
                    "end_year": 1997,
                    "description": "The CRX successor, featuring a removable targa top. The Si model featured VTEC technology, and the VTEC trim (Japan) had the B16A engine. Popular among enthusiasts for its unique design and sporty character.",
                },
            ],
        },
        {
            "model": "CR-Z",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2011,
                    "end_year": 2016,
                    "description": "Modern hybrid sports coupe inspired by the CRX. Featured IMA hybrid system with manual transmission option. The Mugen and Supercharged variants offered enhanced performance. Has a dedicated enthusiast following despite being discontinued.",
                },
            ],
        },
        {
            "model": "Fit",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2001,
                    "end_year": 2007,
                    "description": "Honda's compact hatchback with innovative 'Magic Seat' system. The Sport trim featured sportier suspension and styling. Popular in autocross and track day communities for its excellent handling and reliability.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2008,
                    "end_year": 2013,
                    "description": "Second generation with improved styling and space efficiency. The Sport trim continued to be popular among enthusiasts. Known for excellent handling and aftermarket support in the tuning community.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 2015,
                    "end_year": 2020,
                    "description": "Third generation with more modern design and improved fuel economy. The Sport and Sport Touring trims offered enhanced performance. Remains popular in autocross and track communities.",
                },
            ],
        },
    ],
    "Toyota": [
        {
            "model": "Corolla",
            "generations": [
                {
                    "generation_name": "E70",
                    "start_year": 1974,
                    "end_year": 1979,
                    "description": "Established the Corolla as a reliable, fuel-efficient compact car. Helped Toyota gain market share during the oil crisis with its efficient engines.",
                },
                {
                    "generation_name": "E80",
                    "start_year": 1980,
                    "end_year": 1983,
                    "description": "Refined design with improved fuel economy. Continued Toyota's reputation for reliability and became one of the best-selling cars globally.",
                },
                {
                    "generation_name": "E90",
                    "start_year": 1984,
                    "end_year": 1987,
                    "description": "Front-wheel-drive platform introduced. More modern styling and improved interior space. The AE86 variant became legendary in drifting culture.",
                },
                {
                    "generation_name": "E100",
                    "start_year": 1988,
                    "end_year": 1992,
                    "description": "Larger and more refined with improved safety features. The Corolla became known for its build quality and reliability in this generation.",
                },
                {
                    "generation_name": "E110",
                    "start_year": 1993,
                    "end_year": 1997,
                    "description": "More rounded styling with improved aerodynamics. Featured updated engines and continued the Corolla's reputation for dependability.",
                },
                {
                    "generation_name": "E120",
                    "start_year": 1998,
                    "end_year": 2002,
                    "description": "Larger platform with more interior space. Improved safety and comfort features. The XRS trim with high-revving 2ZZ engine appealed to enthusiasts.",
                },
                {
                    "generation_name": "E140",
                    "start_year": 2003,
                    "end_year": 2008,
                    "description": "More modern styling with improved technology. Featured VVT-i engines and continued focus on reliability and fuel efficiency.",
                },
                {
                    "generation_name": "E150",
                    "start_year": 2009,
                    "end_year": 2013,
                    "description": "Complete redesign with more aggressive styling. Improved fuel economy and introduced more advanced safety features.",
                },
                {
                    "generation_name": "E170",
                    "start_year": 2014,
                    "end_year": 2018,
                    "description": "TNGA platform introduced. More dynamic styling and improved handling. The SE and XSE trims offered sportier character.",
                },
                {
                    "generation_name": "E210",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest generation with hybrid powertrain option. Improved technology, safety features, and fuel economy. SE and XSE trims offer sporty styling.",
                },
            ],
        },
        {
            "model": "Camry",
            "generations": [
                {
                    "generation_name": "V10",
                    "start_year": 1982,
                    "end_year": 1986,
                    "description": "First generation Camry, establishing it as a reliable mid-size sedan. Featured efficient engines and helped Toyota compete in the American market.",
                },
                {
                    "generation_name": "V20",
                    "start_year": 1987,
                    "end_year": 1991,
                    "description": "Larger platform with improved interior space. Introduced V6 engine option and became known for smooth ride and reliability.",
                },
                {
                    "generation_name": "XV10",
                    "start_year": 1992,
                    "end_year": 1996,
                    "description": "First US-built Camry. Larger and more refined, becoming one of the best-selling cars in America. Known for quality and dependability.",
                },
                {
                    "generation_name": "XV20",
                    "start_year": 1997,
                    "end_year": 2001,
                    "description": "More rounded styling with improved safety features. V6 models offered strong performance, and the Camry became the benchmark for reliability.",
                },
                {
                    "generation_name": "XV30",
                    "start_year": 2002,
                    "end_year": 2006,
                    "description": "Complete redesign with more modern styling. Improved engines and introduced hybrid powertrain option. Continued dominance in mid-size sedan segment.",
                },
                {
                    "generation_name": "XV40",
                    "start_year": 2007,
                    "end_year": 2011,
                    "description": "Larger and more spacious with improved technology. Hybrid version became more popular. Maintained Camry's reputation for quality and reliability.",
                },
                {
                    "generation_name": "XV50",
                    "start_year": 2012,
                    "end_year": 2017,
                    "description": "More aggressive styling with improved fuel economy. SE trim offered sportier character. Hybrid technology improved significantly.",
                },
                {
                    "generation_name": "XV70",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "TNGA platform with more dynamic styling. Improved handling and technology. TRD trim introduced for performance-oriented buyers. Hybrid powertrain refined.",
                },
            ],
        },
        {
            "model": "Supra",
            "generations": [
                {
                    "generation_name": "A40",
                    "start_year": 1978,
                    "end_year": 1981,
                    "description": "First generation Supra, based on Celica platform. Featured inline-6 engine and established Supra as Toyota's flagship sports car.",
                },
                {
                    "generation_name": "A60",
                    "start_year": 1982,
                    "end_year": 1986,
                    "description": "More distinct from Celica with unique styling. Featured improved engines and became popular among enthusiasts for its performance potential.",
                },
                {
                    "generation_name": "A70",
                    "start_year": 1987,
                    "end_year": 1992,
                    "description": "Standalone platform with turbocharged option. Featured advanced technology for its time and became a tuner favorite with strong aftermarket support.",
                },
                {
                    "generation_name": "A80",
                    "start_year": 1993,
                    "end_year": 2002,
                    "description": "The legendary MK4 Supra with 2JZ engine. Iconic in tuning culture, known for incredible power potential. Twin-turbo model produced 320 horsepower. Highly collectible.",
                },
                {
                    "generation_name": "A90",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Modern Supra revival co-developed with BMW. Features turbocharged inline-6 engine producing up to 382 horsepower. Excellent handling and modern technology while honoring Supra heritage.",
                },
            ],
        },
        {
            "model": "AE86",
            "generations": [
                {
                    "generation_name": "Zenki",
                    "start_year": 1983,
                    "end_year": 1985,
                    "description": "The legendary AE86 (Hachi-Roku) pre-facelift generation. Part of the E80 Corolla series but unique for retaining rear-wheel-drive. Available as Levin (fixed headlights) or Trueno (pop-up headlights). Features the 1.6L 4A-GE DOHC engine. Iconic in drifting culture and featured in Initial D. Highly sought after by enthusiasts for its lightweight, balanced chassis and tuning potential.",
                },
                {
                    "generation_name": "Kouki",
                    "start_year": 1986,
                    "end_year": 1987,
                    "description": "AE86 facelift generation with updated styling. Features revised bumpers, updated grille, new tail lights, and improved trim. The Black Limited special edition (400 units) featured unique styling. Remains one of the most iconic drift and tuner cars, with massive aftermarket support for engine swaps, suspension, and styling modifications.",
                },
            ],
        },
        {
            "model": "MR2",
            "generations": [
                {
                    "generation_name": "W10",
                    "start_year": 1984,
                    "end_year": 1989,
                    "description": "First generation MR2 (Mid-engine, Rear-wheel-drive, 2-seater). Lightweight mid-engine sports car with excellent handling. Featured 1.6L 4A-GE engine. Popular among enthusiasts for its unique layout and tunability. Supercharged variant available in later years.",
                },
                {
                    "generation_name": "W20",
                    "start_year": 1990,
                    "end_year": 1999,
                    "description": "Second generation MR2 with more aggressive styling. Featured turbocharged 2.0L 3S-GTE engine producing 200+ horsepower. Known for its sharp handling and mid-engine dynamics. Popular for engine swaps and turbo upgrades.",
                },
                {
                    "generation_name": "W30",
                    "start_year": 2000,
                    "end_year": 2007,
                    "description": "Third generation MR2 (MR-S/Spyder). Convertible roadster with 1.8L 1ZZ-FE engine. Lightweight and nimble, popular for track use and modifications. Less powerful but more refined than previous generations.",
                },
            ],
        },
        {
            "model": "Celica",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1970,
                    "end_year": 1977,
                    "description": "First generation Celica, Toyota's sporty coupe. Featured various engine options and established Celica as a popular sports car. Available in coupe and liftback variants.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1978,
                    "end_year": 1981,
                    "description": "Second generation with more modern styling. Featured improved engines and handling. The Supra was based on this platform initially.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1982,
                    "end_year": 1985,
                    "description": "Third generation with updated design. Featured front-wheel-drive platform. Popular among tuners for its sporty character and aftermarket support.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1986,
                    "end_year": 1989,
                    "description": "Fourth generation with more aggressive styling. Featured turbocharged All-Trac/GT-Four variant with all-wheel drive. Popular in rally and tuning communities.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 1990,
                    "end_year": 1993,
                    "description": "Fifth generation with pop-up headlights. Featured improved GT-Four with more power. Highly sought after for rally and track modifications.",
                },
                {
                    "generation_name": "6th Gen",
                    "start_year": 1994,
                    "end_year": 1999,
                    "description": "Sixth generation with fixed headlights. Featured the final GT-Four variant with 3S-GTE turbo engine. Popular for engine swaps and all-wheel-drive conversions.",
                },
                {
                    "generation_name": "7th Gen",
                    "start_year": 2000,
                    "end_year": 2005,
                    "description": "Final generation Celica with modern styling. Featured VVT-i engines and sporty handling. Popular among tuners despite front-wheel-drive only configuration.",
                },
            ],
        },
        {
            "model": "86",
            "generations": [
                {
                    "generation_name": "ZN6",
                    "start_year": 2012,
                    "end_year": 2020,
                    "description": "Toyota's modern rear-wheel-drive sports car co-developed with Subaru. Features boxer engine, perfect weight distribution, and exceptional handling. Revived affordable sports car segment. Note: Sold as Scion FR-S in North America from 2012-2016, then rebadged as Toyota 86.",
                },
                {
                    "generation_name": "ZN8",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Refined second generation with improved engine (2.4L), producing 228 horsepower. Better handling and technology while maintaining the 86's focus on driver engagement and affordability.",
                },
            ],
        },
        {
            "model": "Land Cruiser",
            "generations": [
                {
                    "generation_name": "J40",
                    "start_year": 1960,
                    "end_year": 1984,
                    "description": "Classic Land Cruiser with legendary off-road capability. Featured robust construction and various engine options. Highly popular for off-road modifications and overlanding builds.",
                },
                {
                    "generation_name": "J60",
                    "start_year": 1980,
                    "end_year": 1990,
                    "description": "More refined Land Cruiser with improved comfort. Featured larger engines and better on-road manners while maintaining off-road capability. Popular for lift kits and off-road modifications.",
                },
                {
                    "generation_name": "J80",
                    "start_year": 1990,
                    "end_year": 1997,
                    "description": "Iconic Land Cruiser generation with solid front and rear axles. Featured inline-6 engines and legendary reliability. Highly sought after for off-road builds and overlanding modifications.",
                },
                {
                    "generation_name": "J100",
                    "start_year": 1998,
                    "end_year": 2007,
                    "description": "More modern Land Cruiser with independent front suspension. Featured V8 engines and improved luxury. Popular for lift kits, bumpers, and off-road accessories.",
                },
                {
                    "generation_name": "J200",
                    "start_year": 2008,
                    "end_year": 2021,
                    "description": "Current generation Land Cruiser with advanced technology. Featured powerful V8 engines and sophisticated suspension. Popular for luxury off-road modifications and overlanding builds.",
                },
            ],
        },
        {
            "model": "4Runner",
            "generations": [
                {
                    "generation_name": "N60",
                    "start_year": 1984,
                    "end_year": 1989,
                    "description": "First generation 4Runner based on Hilux pickup. Featured removable top and various engines. Popular for off-road modifications and overlanding builds.",
                },
                {
                    "generation_name": "N120",
                    "start_year": 1990,
                    "end_year": 1995,
                    "description": "Second generation with more refined design. Featured improved engines and better interior. Popular for lift kits and off-road accessories.",
                },
                {
                    "generation_name": "N180",
                    "start_year": 1996,
                    "end_year": 2002,
                    "description": "Third generation with independent front suspension. Featured V6 engines and improved on-road comfort. Popular for suspension upgrades and off-road modifications.",
                },
                {
                    "generation_name": "N210",
                    "start_year": 2003,
                    "end_year": 2009,
                    "description": "Fourth generation with more modern styling. Featured V6 and V8 engine options. Popular for lift kits, bumpers, and overlanding modifications.",
                },
                {
                    "generation_name": "N280",
                    "start_year": 2010,
                    "end_year": 2024,
                    "description": "Fifth generation 4Runner with rugged design. Featured V6 engine and excellent off-road capability. Highly popular for off-road modifications, lift kits, bumpers, and overlanding builds.",
                },
            ],
        },
        {
            "model": "Tacoma",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1995,
                    "end_year": 2004,
                    "description": "First generation Tacoma compact pickup. Featured various engine options and excellent reliability. Popular for off-road modifications, lift kits, and overlanding builds.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2005,
                    "end_year": 2015,
                    "description": "Second generation with more modern design. Featured V6 engines and improved capability. Highly popular for off-road modifications, suspension upgrades, and truck bed accessories.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 2016,
                    "end_year": 2024,
                    "description": "Third generation with updated styling and technology. Featured improved engines and advanced safety features. Popular for off-road modifications, lift kits, and overlanding builds.",
                },
            ],
        },
        {
            "model": "GR Yaris",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Toyota's rally-inspired hot hatch co-developed with Gazoo Racing. Features turbocharged 1.6L 3-cylinder engine producing 257-268 horsepower, all-wheel drive, and lightweight construction. Limited production, highly sought after for track and rally modifications.",
                },
            ],
        },
        {
            "model": "Chaser",
            "generations": [
                {
                    "generation_name": "JZX90",
                    "start_year": 1992,
                    "end_year": 1996,
                    "description": "Fifth generation Chaser with JZX90 chassis code. Featured the Tourer V trim with twin-turbo 1JZ-GTE engine producing 280 PS. Popular JDM sedan highly sought after for drifting and modifications. Excellent aftermarket support for engine upgrades, suspension, and body kits.",
                },
                {
                    "generation_name": "JZX100",
                    "start_year": 1996,
                    "end_year": 2001,
                    "description": "Sixth and final generation Chaser with JZX100 chassis code. Featured single-turbo 1JZ-GTE with VVT-i in Tourer V trim. Iconic in JDM culture, extremely popular for drifting, engine swaps, and modifications. Massive aftermarket support for power upgrades, suspension, and styling.",
                },
            ],
        },
        {
            "model": "Soarer",
            "generations": [
                {
                    "generation_name": "Z30",
                    "start_year": 1991,
                    "end_year": 2000,
                    "description": "Third generation Soarer luxury coupe with Z30 chassis code. Available with 1JZ-GTE, 2JZ-GE, or 1UZ-FE V8 engines. Popular for engine swaps, turbo upgrades, and modifications. Known for advanced features like active suspension and luxury amenities. Sold as Lexus SC in export markets.",
                },
                {
                    "generation_name": "Z40",
                    "start_year": 2001,
                    "end_year": 2005,
                    "description": "Fourth and final generation Soarer with Z40 chassis code. Featured V8 engines and modern luxury features. Popular for modifications and engine swaps. Discontinued in 2005 when fully rebadged as Lexus SC 430 globally.",
                },
            ],
        },
        {
            "model": "Cressida",
            "generations": [
                {
                    "generation_name": "MX73",
                    "start_year": 1984,
                    "end_year": 1988,
                    "description": "Third generation Cressida with MX73 chassis code. Featured 5M-GE inline-6 engine and independent rear suspension. Popular in North America for modifications, especially 1UZ-FE V8 swaps. Known for reliability and comfortable ride.",
                },
                {
                    "generation_name": "MX83",
                    "start_year": 1988,
                    "end_year": 1992,
                    "description": "Fourth and final generation Cressida with MX83 chassis code. Featured 7M-GE 3.0L inline-6 engine producing 190 horsepower. Popular for modifications and engine swaps, especially 1UZ-FE and 2JZ swaps. Last Cressida generation before being replaced by Avalon in North America.",
                },
            ],
        },
        {
            "model": "Altezza",
            "generations": [
                {
                    "generation_name": "XE10",
                    "start_year": 1998,
                    "end_year": 2005,
                    "description": "First generation Altezza with XE10 chassis code. Available as AS200 (2.0L I6), RS200 (high-revving 2.0L I4 BEAMS engine), or AS300 (3.0L 2JZ-GE). Sold as Lexus IS200/IS300 in export markets. Popular for modifications, especially the RS200 with its 7,600 rpm redline. Excellent handling and aftermarket support.",
                },
            ],
        },
        {
            "model": "Aristo",
            "generations": [
                {
                    "generation_name": "S140",
                    "start_year": 1991,
                    "end_year": 1997,
                    "description": "First generation Aristo with S140 chassis code. Available with 2JZ-GE naturally aspirated or 2JZ-GTE twin-turbo engines. Sold as Lexus GS300 in export markets. Highly popular for modifications and engine swaps. The twin-turbo V300 variant is extremely sought after for its 2JZ-GTE engine.",
                },
                {
                    "generation_name": "S160",
                    "start_year": 1997,
                    "end_year": 2004,
                    "description": "Second generation Aristo with S160 chassis code. Featured updated styling and VVT-i technology on JZ engines. Available with 2JZ-GE, 2JZ-GTE, or V8 engines. Sold as Lexus GS300/GS400/GS430 in export markets. Popular for modifications, especially the twin-turbo variants. Discontinued in 2005 when fully rebadged as Lexus GS globally.",
                },
            ],
        },
        {
            "model": "FJ Cruiser",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2007,
                    "end_year": 2014,
                    "description": "Toyota's retro-styled off-road SUV inspired by the classic FJ40 Land Cruiser. Featured 4.0L V6 engine (239-260 hp depending on year). Highly popular for off-road modifications, lift kits, bumpers, rock sliders, and overlanding builds. Special Trail Teams and TRD editions available. Discontinued in US after 2014 but continued in other markets.",
                },
            ],
        },
        {
            "model": "Tundra",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2000,
                    "end_year": 2006,
                    "description": "First generation Tundra full-size pickup truck. Featured V6 and V8 engine options. Popular for modifications including lift kits, off-road accessories, performance upgrades, and towing modifications. Established Toyota in the full-size truck market.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2007,
                    "end_year": 2021,
                    "description": "Second generation Tundra with larger platform and more powerful engines. Featured 4.6L and 5.7L V8 engines. Highly popular for modifications including lift kits, off-road accessories, performance upgrades, superchargers, and overlanding builds. Mid-cycle refresh in 2014.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Third generation Tundra with complete redesign. Features new twin-turbo V6 engines and hybrid powertrain option. Modern technology and improved capability. Growing aftermarket support for modifications, lift kits, and off-road accessories.",
                },
            ],
        },
        {
            "model": "Sequoia",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2001,
                    "end_year": 2007,
                    "description": "First generation Sequoia full-size SUV based on Tundra platform. Featured V8 engines and three-row seating. Popular for modifications including lift kits, off-road accessories, and overlanding builds. Known for reliability and capability.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2008,
                    "end_year": 2022,
                    "description": "Second generation Sequoia with updated styling and improved features. Featured V8 engines and advanced safety technology. Popular for modifications including lift kits, suspension upgrades, off-road accessories, and overlanding modifications. Growing enthusiast community.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "Third generation Sequoia with complete redesign. Features new twin-turbo V6 hybrid powertrain (i-Force Max), modern technology, and improved capability. Growing aftermarket support for modifications and off-road accessories.",
                },
            ],
        },
    ],
    "Scion": [
        {
            "model": "xA",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2004,
                    "end_year": 2006,
                    "description": "Scion xA compact hatchback. Featured 1.5L engine and lightweight design. Developed a cult following among tuners for its affordability, compact size, and extensive aftermarket support. Popular for intake, exhaust, and suspension modifications.",
                },
            ],
        },
        {
            "model": "xB",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2004,
                    "end_year": 2007,
                    "description": "First generation Scion xB (boxy design). Featured compact dimensions and efficient engines. Popular for custom modifications and unique styling.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2008,
                    "end_year": 2015,
                    "description": "Second generation xB with larger, more rounded design. Featured improved engines and more space. Popular for modifications and custom builds.",
                },
            ],
        },
        {
            "model": "tC",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2005,
                    "end_year": 2010,
                    "description": "First generation Scion tC sport coupe. Featured 2.4L engine and sporty styling. Popular among young tuners for its affordability and aftermarket support.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2011,
                    "end_year": 2016,
                    "description": "Second generation tC with updated styling and improved engines. Featured 2.5L engine and continued popularity in the tuning community. Final model year before Scion brand discontinuation.",
                },
            ],
        },
        {
            "model": "xD",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2008,
                    "end_year": 2014,
                    "description": "Scion xD compact hatchback, successor to the xA. Featured 1.8L engine with improved power and more advanced engineering. Popular in the tuning community for intake, exhaust, header, and suspension modifications. Strong aftermarket support.",
                },
            ],
        },
        {
            "model": "FR-S",
            "generations": [
                {
                    "generation_name": "ZN6",
                    "start_year": 2012,
                    "end_year": 2016,
                    "description": "Scion FR-S, the North American market version of the Toyota 86/GT86. Co-developed with Subaru, featuring a 2.0L boxer engine, rear-wheel drive, and perfect weight distribution. Sold exclusively under the Scion brand in the US and Canada from 2012-2016, before being rebadged as the Toyota 86 in 2017. Highly popular for modifications, drifting, and track use.",
                },
            ],
        },
        {
            "model": "iA",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2016,
                    "end_year": 2016,
                    "description": "Scion iA sedan, based on the Mazda2 platform. Featured 1.5L Skyactiv engine and Mazda's sporty handling characteristics. Only sold for one year before Scion brand discontinuation. Attracted enthusiasts for its Mazda DNA and tuning potential.",
                },
            ],
        },
        {
            "model": "iM",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2016,
                    "end_year": 2016,
                    "description": "Scion iM hatchback, based on the Toyota Corolla iM platform. Featured 1.8L engine and practical hatchback design. Only sold for one year before Scion brand discontinuation. Popular among enthusiasts for its sporty styling and aftermarket potential.",
                },
            ],
        },
    ],
    "Subaru": [
        {
            "model": "WRX",
            "generations": [
                {
                    "generation_name": "GC",
                    "start_year": 1992,
                    "end_year": 2000,
                    "description": "The original WRX, legendary in rally and tuning culture. Featured turbocharged boxer engine and all-wheel drive. The STI variant with EJ20 engine became iconic.",
                },
                {
                    "generation_name": "GD",
                    "start_year": 2001,
                    "end_year": 2007,
                    "description": "First WRX sold in the US market. Featured 2.0L and 2.5L turbo engines. The STI model with 300+ horsepower became a tuner favorite and rally legend.",
                },
                {
                    "generation_name": "GR",
                    "start_year": 2008,
                    "end_year": 2014,
                    "description": "Wider body and improved handling. Featured EJ25 engine and continued the WRX's reputation for all-wheel-drive performance. STI model highly sought after.",
                },
                {
                    "generation_name": "VA",
                    "start_year": 2015,
                    "end_year": 2021,
                    "description": "Separated from Impreza platform. Featured FA20DIT engine producing 268 horsepower. Improved handling and technology while maintaining rally heritage.",
                },
                {
                    "generation_name": "VB",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Latest generation with FA24F engine producing 271 horsepower. Improved power delivery and handling. More refined while maintaining the WRX's character.",
                },
            ],
        },
        {
            "model": "BRZ",
            "generations": [
                {
                    "generation_name": "ZC6",
                    "start_year": 2012,
                    "end_year": 2020,
                    "description": "Subaru's rear-wheel-drive sports car co-developed with Toyota. Features naturally aspirated boxer engine, perfect weight distribution, and exceptional handling. Focus on driver engagement.",
                },
                {
                    "generation_name": "ZD8",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Refined second generation with improved 2.4L engine producing 228 horsepower. Better handling and technology while maintaining the BRZ's focus on pure driving experience.",
                },
            ],
        },
        {
            "model": "Impreza",
            "generations": [
                {
                    "generation_name": "GC/GF",
                    "start_year": 1992,
                    "end_year": 2000,
                    "description": "Subaru's compact car platform that spawned the WRX. Featured all-wheel drive and boxer engines. The base for the legendary WRX STI variants.",
                },
                {
                    "generation_name": "GD/GG",
                    "start_year": 2001,
                    "end_year": 2007,
                    "description": "Larger platform with improved safety and comfort. Featured updated engines and continued Subaru's focus on all-wheel drive and reliability.",
                },
                {
                    "generation_name": "GE/GH",
                    "start_year": 2008,
                    "end_year": 2014,
                    "description": "More refined design with improved fuel economy. Featured updated boxer engines and continued Subaru's reputation for all-weather capability.",
                },
                {
                    "generation_name": "GP/GJ",
                    "start_year": 2015,
                    "end_year": 2024,
                    "description": "Complete redesign with improved technology and fuel economy. WRX separated to its own model. Focus on safety, reliability, and all-wheel-drive capability.",
                },
            ],
        },
        {
            "model": "Legacy",
            "generations": [
                {
                    "generation_name": "BD/BG",
                    "start_year": 1995,
                    "end_year": 1999,
                    "description": "Subaru's mid-size sedan with all-wheel drive standard. Featured boxer engines and became known for reliability and all-weather capability.",
                },
                {
                    "generation_name": "BE/BH",
                    "start_year": 2000,
                    "end_year": 2004,
                    "description": "Larger platform with improved interior space. Featured updated engines and continued Subaru's focus on safety and all-wheel drive.",
                },
                {
                    "generation_name": "BL/BP",
                    "start_year": 2005,
                    "end_year": 2009,
                    "description": "More refined styling with improved technology. Featured updated boxer engines and introduced turbocharged option in GT trim.",
                },
                {
                    "generation_name": "BM/BR",
                    "start_year": 2010,
                    "end_year": 2014,
                    "description": "Larger and more spacious with improved fuel economy. Featured updated engines and continued Legacy's reputation for reliability and all-weather capability.",
                },
                {
                    "generation_name": "BN/BS",
                    "start_year": 2015,
                    "end_year": 2024,
                    "description": "Latest generation with improved technology and safety features. Featured updated boxer engines and continued Subaru's focus on all-wheel drive and reliability.",
                },
            ],
        },
        {
            "model": "Forester XT",
            "generations": [
                {
                    "generation_name": "SF",
                    "start_year": 1998,
                    "end_year": 2002,
                    "description": "First generation Forester XT with turbocharged EJ20 engine. Compact crossover with WRX-like performance. Popular in tuning community for its unique combination of utility and power.",
                },
                {
                    "generation_name": "SG",
                    "start_year": 2003,
                    "end_year": 2008,
                    "description": "Second generation with EJ25 turbo engine. Improved power and handling. STI variant available in some markets. Highly sought after by enthusiasts for its sleeper performance.",
                },
                {
                    "generation_name": "SH",
                    "start_year": 2009,
                    "end_year": 2013,
                    "description": "Third generation with EJ25 turbo producing 224-250 horsepower. More refined styling while maintaining performance. Popular platform for modifications and tuning.",
                },
                {
                    "generation_name": "SJ",
                    "start_year": 2014,
                    "end_year": 2018,
                    "description": "Fourth generation with FA20DIT turbo engine producing 250 horsepower. Modern technology and improved fuel economy. Last generation with turbocharged XT variant in North America.",
                },
            ],
        },
        {
            "model": "Legacy GT",
            "generations": [
                {
                    "generation_name": "BD/BG",
                    "start_year": 1995,
                    "end_year": 1999,
                    "description": "First generation Legacy GT with turbocharged EJ20 engine. Performance-oriented sedan and wagon variants. Established Legacy as a tuner-friendly platform.",
                },
                {
                    "generation_name": "BE/BH",
                    "start_year": 2000,
                    "end_year": 2004,
                    "description": "Second generation with updated turbo engines. GT and GT-B variants offered increased performance. Popular for modifications and tuning.",
                },
                {
                    "generation_name": "BL/BP",
                    "start_year": 2005,
                    "end_year": 2009,
                    "description": "Third generation Legacy GT with EJ255 turbo engine producing 243-265 horsepower. Spec.B variant with upgraded suspension and interior. Highly popular in tuning community for its balance of performance and practicality.",
                },
                {
                    "generation_name": "BM/BR",
                    "start_year": 2010,
                    "end_year": 2012,
                    "description": "Fourth generation Legacy GT with EJ255 engine. Last generation with manual transmission option in North America. Sought after by enthusiasts for its combination of power and refinement.",
                },
                {
                    "generation_name": "BN/BS",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Modern Legacy XT with FA24F turbo engine producing 260 horsepower. CVT-only transmission. Revived turbocharged Legacy for enthusiasts seeking performance in a refined package.",
                },
            ],
        },
        {
            "model": "Outback XT",
            "generations": [
                {
                    "generation_name": "BL/BP",
                    "start_year": 2005,
                    "end_year": 2009,
                    "description": "First generation Outback XT with EJ255 turbo engine producing 250 horsepower. Unique combination of crossover utility and turbocharged performance. Popular among enthusiasts for its versatility.",
                },
                {
                    "generation_name": "BM/BR",
                    "start_year": 2010,
                    "end_year": 2014,
                    "description": "Second generation with EJ255 turbo engine. Improved styling and technology. Last generation with manual transmission option. Sought after for its rare combination of off-road capability and turbo power.",
                },
                {
                    "generation_name": "BN/BS",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Modern Outback XT with FA24F turbo engine producing 260 horsepower and 277 lb-ft torque. CVT-only transmission. Revived turbocharged Outback offering performance in a practical crossover package.",
                },
            ],
        },
        {
            "model": "SVX",
            "generations": [
                {
                    "generation_name": "CXD",
                    "start_year": 1992,
                    "end_year": 1997,
                    "description": "Subaru's unique grand touring coupe with 3.3L flat-6 EG33 engine producing 230 horsepower. Distinctive styling with window-within-window design. Cult classic among enthusiasts for its rarity and character.",
                },
            ],
        },
        {
            "model": "XT",
            "generations": [
                {
                    "generation_name": "XT",
                    "start_year": 1985,
                    "end_year": 1991,
                    "description": "Subaru's futuristic coupe with wedge-shaped aerodynamic design. Featured EA82T turbo engine or ER27 flat-6 in XT6 variant. Unique pop-up headlights and advanced features. Rare enthusiast model with distinctive styling.",
                },
            ],
        },
    ],
    "Nissan": [
        {
            "model": "GT-R",
            "generations": [
                {
                    "generation_name": "PGC10",
                    "start_year": 1969,
                    "end_year": 1972,
                    "description": "The original Skyline GT-R, legendary in Japanese motorsport. Featured inline-6 engine and established GT-R as Nissan's ultimate performance car.",
                },
                {
                    "generation_name": "KPGC110",
                    "start_year": 1973,
                    "end_year": 1973,
                    "description": "Short-lived second generation due to fuel crisis. Featured updated styling and continued the GT-R legacy before hiatus.",
                },
                {
                    "generation_name": "R32",
                    "start_year": 1989,
                    "end_year": 1994,
                    "description": "The Godzilla - dominated Group A racing. Featured RB26DETT twin-turbo engine and ATTESA all-wheel drive. Iconic in tuning culture and motorsport history.",
                },
                {
                    "generation_name": "R33",
                    "start_year": 1995,
                    "end_year": 1998,
                    "description": "Larger and more refined GT-R. Featured improved RB26DETT engine and handling. Set Nürburgring record. Some enthusiasts prefer R32 or R34.",
                },
                {
                    "generation_name": "R34",
                    "start_year": 1999,
                    "end_year": 2002,
                    "description": "The ultimate Skyline GT-R. Featured refined RB26DETT engine, advanced technology, and aggressive styling. Highly collectible and iconic in car culture.",
                },
                {
                    "generation_name": "R35",
                    "start_year": 2007,
                    "end_year": 2024,
                    "description": "Modern GT-R with VR38DETT twin-turbo V6. Produces up to 600+ horsepower. Advanced all-wheel drive and technology. Set multiple production car lap records worldwide.",
                },
            ],
        },
        {
            "model": "350Z",
            "generations": [
                {
                    "generation_name": "Z33",
                    "start_year": 2002,
                    "end_year": 2009,
                    "description": "Nissan's modern Z car revival. Featured VQ35DE V6 engine producing up to 306 horsepower. Excellent handling and became popular among enthusiasts for its balance of performance and affordability.",
                },
            ],
        },
        {
            "model": "370Z",
            "generations": [
                {
                    "generation_name": "Z34",
                    "start_year": 2009,
                    "end_year": 2020,
                    "description": "Refined Z car with VQ37VHR engine producing 332 horsepower. Improved handling and technology. Nismo variant offered track-focused performance. Long production run showed its popularity.",
                },
            ],
        },
        {
            "model": "Z",
            "generations": [
                {
                    "generation_name": "RZ34",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "Latest Z car with twin-turbo V6 engine producing 400 horsepower. Modern technology while honoring Z car heritage. Performance and Nismo variants available.",
                },
            ],
        },
        {
            "model": "240SX",
            "generations": [
                {
                    "generation_name": "S13",
                    "start_year": 1989,
                    "end_year": 1994,
                    "description": "Nissan's rear-wheel-drive sports coupe. Featured KA24E/DE engines and became legendary in drifting culture. Popular platform for engine swaps, especially SR20DET.",
                },
                {
                    "generation_name": "S14",
                    "start_year": 1995,
                    "end_year": 1998,
                    "description": "Refined 240SX with improved styling. Featured updated KA24DE engine. Continued popularity in drifting and tuning scenes. Highly sought after for modification projects.",
                },
            ],
        },
        {
            "model": "Altima",
            "generations": [
                {
                    "generation_name": "L30",
                    "start_year": 2002,
                    "end_year": 2006,
                    "description": "Nissan's mid-size sedan with V6 engine option. Featured updated styling and improved technology. SE-R trim offered sportier character.",
                },
                {
                    "generation_name": "L31",
                    "start_year": 2007,
                    "end_year": 2012,
                    "description": "Larger platform with improved interior space. Featured updated V6 engines and improved fuel economy. Continued Altima's reputation for value and performance.",
                },
                {
                    "generation_name": "L32",
                    "start_year": 2013,
                    "end_year": 2018,
                    "description": "Complete redesign with more modern styling. Featured updated engines and introduced hybrid option. Improved technology and safety features.",
                },
                {
                    "generation_name": "L34",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest generation with turbocharged engine option. Improved technology, safety, and fuel economy. AWD option available. More refined and competitive in mid-size segment.",
                },
            ],
        },
        {
            "model": "Sentra",
            "generations": [
                {
                    "generation_name": "B15",
                    "start_year": 2000,
                    "end_year": 2006,
                    "description": "Nissan's compact sedan with efficient engines. Featured updated styling and became popular for its value and reliability.",
                },
                {
                    "generation_name": "B16",
                    "start_year": 2007,
                    "end_year": 2012,
                    "description": "Larger platform with improved interior space. Featured updated engines and improved fuel economy. SE-R trim offered sportier character.",
                },
                {
                    "generation_name": "B17",
                    "start_year": 2013,
                    "end_year": 2019,
                    "description": "Complete redesign with more modern styling. Featured updated engines and improved technology. Focus on fuel economy and value.",
                },
                {
                    "generation_name": "B18",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Latest generation with improved technology and safety features. Featured updated engines and continued Sentra's focus on value and efficiency.",
                },
            ],
        },
    ],
    "Mazda": [
        {
            "model": "Miata",
            "generations": [
                {
                    "generation_name": "NA",
                    "start_year": 1989,
                    "end_year": 1997,
                    "description": "The original Miata (MX-5) that revived the affordable roadster segment. Featured pop-up headlights, perfect 50/50 weight distribution, and exceptional handling. Pure driving joy.",
                },
                {
                    "generation_name": "NB",
                    "start_year": 1998,
                    "end_year": 2005,
                    "description": "Refined second generation with fixed headlights. Improved engines and handling. Maintained the Miata's focus on lightweight, driver-focused experience. Mazdaspeed variant offered turbocharged performance.",
                },
                {
                    "generation_name": "NC",
                    "start_year": 2006,
                    "end_year": 2015,
                    "description": "Larger platform with improved safety features. Featured MZR engines and retractable hardtop option. Some enthusiasts preferred previous generations, but still excellent handling.",
                },
                {
                    "generation_name": "ND",
                    "start_year": 2016,
                    "end_year": 2024,
                    "description": "Return to lightweight philosophy with Skyactiv technology. Featured improved fuel economy and handling. RF (retractable fastback) variant introduced. Maintains Miata's reputation as the best affordable sports car.",
                },
            ],
        },
        {
            "model": "RX-7",
            "generations": [
                {
                    "generation_name": "SA/FB",
                    "start_year": 1978,
                    "end_year": 1985,
                    "description": "Mazda's rotary-powered sports car. Featured Wankel rotary engine and established RX-7 as a unique sports car. Turbocharged variant introduced in later years.",
                },
                {
                    "generation_name": "FC",
                    "start_year": 1986,
                    "end_year": 1991,
                    "description": "Second generation with turbocharged 13B rotary engine. Featured improved handling and styling. Turbo II model produced 200 horsepower. Popular in tuning and racing scenes.",
                },
                {
                    "generation_name": "FD",
                    "start_year": 1992,
                    "end_year": 2002,
                    "description": "The ultimate RX-7 with sequential twin-turbo 13B-REW engine producing 255-280 horsepower. Iconic styling and exceptional handling. Highly sought after and collectible. Legendary in tuning culture.",
                },
            ],
        },
        {
            "model": "RX-3",
            "generations": [
                {
                    "generation_name": "S1",
                    "start_year": 1972,
                    "end_year": 1977,
                    "description": "Mazda's rotary-powered compact sports car (Savanna in Japan). Featured 10A and 12A twin-rotor engines producing 110-130 horsepower. Lightweight rear-wheel drive chassis with excellent handling. Popular in racing and established Mazda's rotary reputation before RX-7.",
                },
            ],
        },
        {
            "model": "Cosmo",
            "generations": [
                {
                    "generation_name": "110S",
                    "start_year": 1967,
                    "end_year": 1972,
                    "description": "Mazda's first production rotary-powered car (Cosmo Sport). Featured two-rotor Wankel engine producing 110 PS. Revolutionary design and technology that established Mazda's rotary heritage. Highly collectible and historically significant.",
                },
                {
                    "generation_name": "JC",
                    "start_year": 1990,
                    "end_year": 1995,
                    "description": "Eunos Cosmo - Mazda's flagship luxury grand tourer. Featured twin-turbo 13B-REW (230 PS) and legendary triple-rotor 20B-REW (276 PS) engines. First production car with built-in GPS navigation. Advanced technology and exclusive rotary power. Highly sought after JDM legend.",
                },
            ],
        },
        {
            "model": "323 GTX",
            "generations": [
                {
                    "generation_name": "BF",
                    "start_year": 1987,
                    "end_year": 1989,
                    "description": "Mazda's turbocharged all-wheel drive hot hatch. Featured 1.6L turbocharged engine producing 138 horsepower with full-time AWD system. Lightweight and capable, popular in rallying and early hot hatch culture. Rare and collectible performance variant of the 323/Familia.",
                },
            ],
        },
        {
            "model": "Mazdaspeed Protegé",
            "generations": [
                {
                    "generation_name": "BJ",
                    "start_year": 2003,
                    "end_year": 2004,
                    "description": "Mazda's factory-tuned performance sedan. Featured Garrett T25 turbocharged 2.0L engine producing 170 horsepower and 160 lb-ft torque. Racing-tuned suspension with Tokico dampers, limited-slip differential, and unique aero package. Limited production (~2,000 units) predecessor to Mazdaspeed3. Highly sought after by enthusiasts.",
                },
            ],
        },
        {
            "model": "Mazda3",
            "generations": [
                {
                    "generation_name": "BK",
                    "start_year": 2003,
                    "end_year": 2009,
                    "description": "Mazda's compact car with sporty character. Featured MZR engines and excellent handling. Mazdaspeed3 variant with turbocharged engine became a hot hatch legend.",
                },
                {
                    "generation_name": "BL",
                    "start_year": 2010,
                    "end_year": 2013,
                    "description": "Refined design with Skyactiv technology introduction. Improved fuel economy and handling. Mazdaspeed3 continued with 263 horsepower turbocharged engine.",
                },
                {
                    "generation_name": "BM",
                    "start_year": 2014,
                    "end_year": 2018,
                    "description": "Complete redesign with Skyactiv engines. Improved technology and fuel economy. More refined while maintaining sporty character. No Mazdaspeed variant this generation.",
                },
                {
                    "generation_name": "BP",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest generation with improved Skyactiv-X technology. More premium interior and improved technology. Turbocharged engine option available. Maintains Mazda3's sporty character.",
                },
            ],
        },
        {
            "model": "Mazda6",
            "generations": [
                {
                    "generation_name": "GG/GY",
                    "start_year": 2002,
                    "end_year": 2007,
                    "description": "Mazda's mid-size sedan with sporty character. Featured MZR engines and excellent handling. Mazdaspeed6 variant with turbocharged AWD was a performance sedan.",
                },
                {
                    "generation_name": "GH",
                    "start_year": 2008,
                    "end_year": 2012,
                    "description": "Refined design with improved technology. Featured updated engines and continued Mazda6's reputation for sporty handling in the mid-size segment.",
                },
                {
                    "generation_name": "GJ/GL",
                    "start_year": 2013,
                    "end_year": 2021,
                    "description": "Complete redesign with Skyactiv technology. Kodo design language introduced. Improved fuel economy and handling. More premium positioning in mid-size segment.",
                },
            ],
        },
        {
            "model": "MX-6",
            "generations": [
                {
                    "generation_name": "GD",
                    "start_year": 1987,
                    "end_year": 1992,
                    "description": "Mazda's sporty 2-door coupe. Featured 2.2L turbocharged engine in GT trim producing 145 horsepower. Stylish design with optional four-wheel steering. Platform shared with Ford Probe. Popular among enthusiasts for its turbocharged performance.",
                },
                {
                    "generation_name": "GE",
                    "start_year": 1993,
                    "end_year": 1997,
                    "description": "Second generation with refined styling. Featured 2.5L V6 engine in LS trim producing 164-165 horsepower. Improved handling and technology. Sporty coupe character with excellent driving dynamics.",
                },
            ],
        },
        {
            "model": "RX-8",
            "generations": [
                {
                    "generation_name": "SE3P",
                    "start_year": 2003,
                    "end_year": 2012,
                    "description": "Mazda's rotary-powered sports car with unique 4-door design. Featured naturally aspirated 13B-MSP Renesis engine producing 232-238 horsepower. High-revving character and excellent handling.",
                },
            ],
        },
    ],
    "Ford": [
        {
            "model": "Mustang",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1964,
                    "end_year": 1973,
                    "description": "The original Mustang that created the pony car segment. Featured V8 engines and iconic styling. Fastback, coupe, and convertible variants. Established Mustang as an American icon.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1974,
                    "end_year": 1978,
                    "description": "Smaller Mustang II due to fuel crisis. Featured smaller engines and compact design. Less powerful but maintained Mustang nameplate during challenging times.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1979,
                    "end_year": 1993,
                    "description": "Fox platform Mustang with improved performance. Featured V8 engines and became popular in drag racing. SVO turbocharged variant and 5.0L V8 became legendary.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1994,
                    "end_year": 2004,
                    "description": "SN95 platform with retro-inspired styling. Featured modular V8 engines and improved handling. SVT Cobra and Terminator variants were high-performance models.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 2005,
                    "end_year": 2014,
                    "description": "Retro-modern design honoring original Mustang. Featured updated V8 engines and improved technology. Shelby GT500 with supercharged V8 produced 500+ horsepower.",
                },
                {
                    "generation_name": "6th Gen",
                    "start_year": 2015,
                    "end_year": 2023,
                    "description": "Complete redesign with independent rear suspension. Featured EcoBoost turbo and V8 engines. GT350 and GT500 variants were track-focused. Improved handling and technology.",
                },
                {
                    "generation_name": "7th Gen",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Latest generation with updated styling and technology. Featured updated engines and improved performance. Dark Horse variant introduced. Continues Mustang legacy.",
                },
            ],
        },
        {
            "model": "Focus",
            "generations": [
                {
                    "generation_name": "Mk1",
                    "start_year": 1998,
                    "end_year": 2004,
                    "description": "Ford's compact car with European design. Featured efficient engines and good handling. SVT Focus variant offered sporty performance in North America.",
                },
                {
                    "generation_name": "Mk2",
                    "start_year": 2005,
                    "end_year": 2011,
                    "description": "Refined design with improved technology. Featured updated engines and continued Focus's reputation for handling and value.",
                },
                {
                    "generation_name": "Mk3",
                    "start_year": 2012,
                    "end_year": 2018,
                    "description": "Complete redesign with improved fuel economy. Featured EcoBoost engines and improved technology. ST and RS variants offered high-performance options.",
                },
            ],
        },
        {
            "model": "Fiesta",
            "generations": [
                {
                    "generation_name": "Mk6",
                    "start_year": 2008,
                    "end_year": 2012,
                    "description": "Ford's subcompact car with European design. Featured efficient engines and good handling. Popular for its value and fuel economy.",
                },
                {
                    "generation_name": "Mk7",
                    "start_year": 2013,
                    "end_year": 2019,
                    "description": "Refined design with improved technology. Featured EcoBoost engines and improved fuel economy. ST variant offered sporty performance.",
                },
            ],
        },
        {
            "model": "Focus RS",
            "generations": [
                {
                    "generation_name": "Mk2",
                    "start_year": 2009,
                    "end_year": 2011,
                    "description": "High-performance Focus with turbocharged engine and all-wheel drive. Produced 300+ horsepower. European hot hatch legend, not sold in US.",
                },
                {
                    "generation_name": "Mk3",
                    "start_year": 2016,
                    "end_year": 2018,
                    "description": "First RS sold in US market. Featured 2.3L EcoBoost engine producing 350 horsepower and advanced all-wheel drive. Drift mode feature. Highly sought after.",
                },
            ],
        },
        {
            "model": "Fiesta ST",
            "generations": [
                {
                    "generation_name": "Mk7",
                    "start_year": 2014,
                    "end_year": 2019,
                    "description": "Hot hatch variant with 1.6L EcoBoost engine producing 197 horsepower. Excellent handling and driver engagement. Popular among enthusiasts for its fun-to-drive character.",
                },
            ],
        },
        {
            "model": "GT",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2005,
                    "end_year": 2006,
                    "description": "Modern supercar inspired by GT40. Featured mid-engine layout with 5.4L supercharged V8 producing 550 horsepower. Carbon fiber body, advanced aerodynamics. Limited production American supercar.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2017,
                    "end_year": 2022,
                    "description": "Second generation supercar with advanced carbon fiber construction. Featured 3.5L twin-turbo EcoBoost V6 producing 647 horsepower. Race-derived aerodynamics and technology. Limited production, highly sought after.",
                },
            ],
        },
        {
            "model": "Bronco",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1966,
                    "end_year": 1977,
                    "description": "Original off-road SUV that created the segment. Featured removable doors and top, V8 engines, and legendary off-road capability. Iconic American 4x4 that competed with Jeep CJ.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1978,
                    "end_year": 1979,
                    "description": "Refined design with improved comfort. Featured updated styling and continued off-road capability. Maintained Bronco's reputation as capable off-roader.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1980,
                    "end_year": 1986,
                    "description": "Larger design with improved interior space. Featured V6 and V8 engines. Continued Bronco's off-road heritage with improved on-road comfort.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1987,
                    "end_year": 1991,
                    "description": "Aerodynamic redesign with improved fuel economy. Featured updated engines and technology. Last generation before full-size SUV transition.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 1992,
                    "end_year": 1996,
                    "description": "Full-size SUV based on F-Series platform. Featured V8 engines and improved towing capacity. Last generation before discontinuation.",
                },
                {
                    "generation_name": "6th Gen",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Bronco revival with modern off-road technology. Featured 2.3L EcoBoost and 2.7L twin-turbo V6 engines. Removable doors and top, advanced 4x4 systems. Raptor variant with 418 horsepower. Highly anticipated return of iconic off-roader.",
                },
            ],
        },
        {
            "model": "F-150 Raptor",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2010,
                    "end_year": 2014,
                    "description": "High-performance off-road truck based on F-150. Featured 6.2L V8 producing 411 horsepower. Fox Racing shocks, off-road tires, and enhanced suspension. Created the high-performance truck segment.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2017,
                    "end_year": 2020,
                    "description": "Second generation with 3.5L twin-turbo EcoBoost V6 producing 450 horsepower. Advanced off-road technology, improved suspension travel. More efficient while maintaining performance.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest generation with updated 3.5L twin-turbo EcoBoost V6 producing 450 horsepower (Raptor R with 5.2L supercharged V8 producing 700 horsepower). Advanced off-road systems, improved technology. Continues Raptor's dominance.",
                },
            ],
        },
        {
            "model": "SVT Lightning",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1993,
                    "end_year": 1995,
                    "description": "First high-performance F-150 from SVT. Featured 5.8L V8 producing 240 horsepower. Sport-tuned suspension and styling. Limited production performance truck.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1999,
                    "end_year": 2004,
                    "description": "Second generation with 5.4L supercharged V8 producing 360-380 horsepower. Improved performance and handling. 0-60 in 5.2 seconds. Iconic performance truck that established the segment.",
                },
            ],
        },
        {
            "model": "Taurus SHO",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1989,
                    "end_year": 1995,
                    "description": "Performance sedan with Yamaha-built 3.0L DOHC V6 producing 220 horsepower. Manual transmission available, sport-tuned suspension. Created the modern performance sedan segment.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1996,
                    "end_year": 1999,
                    "description": "Second generation with 3.4L V8 producing 235 horsepower. Updated styling and improved performance. Last generation before hiatus.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 2010,
                    "end_year": 2019,
                    "description": "SHO revival with 3.5L twin-turbo EcoBoost V6 producing 365 horsepower. All-wheel drive standard, sport-tuned suspension. Modern performance sedan with advanced technology.",
                },
            ],
        },
        {
            "model": "Focus ST",
            "generations": [
                {
                    "generation_name": "Mk3",
                    "start_year": 2013,
                    "end_year": 2018,
                    "description": "Hot hatch variant with 2.0L EcoBoost engine producing 252 horsepower. Front-wheel drive, sport-tuned suspension, and aggressive styling. Popular among enthusiasts for its balance of performance and practicality.",
                },
            ],
        },
        {
            "model": "Thunderbird",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1955,
                    "end_year": 1957,
                    "description": "Original two-seat personal luxury car. Featured V8 engines and iconic styling. Created the personal luxury car segment. Classic American design icon.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1958,
                    "end_year": 1960,
                    "description": "Larger four-seat design with distinctive styling. Featured V8 engines and continued Thunderbird's luxury focus. Squarebird design became iconic.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1961,
                    "end_year": 1963,
                    "description": "Bullet Bird design with sleeker styling. Featured V8 engines and improved performance. Popular among collectors and enthusiasts.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1964,
                    "end_year": 1966,
                    "description": "Flair Bird design with updated styling. Featured V8 engines and continued luxury focus. Last generation of classic Thunderbird design.",
                },
            ],
        },
        {
            "model": "Crown Victoria",
            "generations": [
                {
                    "generation_name": "Panther Platform",
                    "start_year": 1992,
                    "end_year": 2011,
                    "description": "Full-size rear-wheel-drive sedan. Featured 4.6L V8 engine, body-on-frame construction. Popular for police and taxi use. Large aftermarket support for modifications. Last American full-size sedan.",
                },
            ],
        },
    ],
    "Chevrolet": [
        {
            "model": "Camaro",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1967,
                    "end_year": 1969,
                    "description": "The original Camaro, Ford Mustang's competitor. Featured V8 engines and iconic styling. SS and Z/28 variants established Camaro as a performance car.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1970,
                    "end_year": 1981,
                    "description": "Larger second generation with improved styling. Featured big-block V8 engines. Z/28 and SS variants were high-performance models. Iconic in muscle car culture.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1982,
                    "end_year": 1992,
                    "description": "Smaller, more efficient Camaro. Featured V6 and V8 engines. IROC-Z variant became popular. Improved handling and fuel economy during fuel crisis era.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1993,
                    "end_year": 2002,
                    "description": "Final F-body Camaro. Featured LS1 V8 engine producing 305-320 horsepower. SS and Z28 variants were high-performance. Last generation before hiatus.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 2010,
                    "end_year": 2015,
                    "description": "Camaro revival with retro-modern design. Featured V6 and V8 engines. SS and ZL1 variants offered high performance. Z/28 was track-focused model.",
                },
                {
                    "generation_name": "6th Gen",
                    "start_year": 2016,
                    "end_year": 2024,
                    "description": "Alpha platform with improved handling. Featured updated V8 engines and improved technology. ZL1 with supercharged V8 produced 650 horsepower. 1LE track packages available.",
                },
            ],
        },
        {
            "model": "Corvette",
            "generations": [
                {
                    "generation_name": "C3",
                    "start_year": 1968,
                    "end_year": 1982,
                    "description": "Stingray design with iconic styling. Featured big-block and small-block V8 engines. Performance declined during fuel crisis but maintained Corvette's status as America's sports car.",
                },
                {
                    "generation_name": "C4",
                    "start_year": 1984,
                    "end_year": 1996,
                    "description": "Modern Corvette with improved technology. Featured updated V8 engines and improved handling. ZR-1 variant with DOHC V8 was a technological showcase.",
                },
                {
                    "generation_name": "C5",
                    "start_year": 1997,
                    "end_year": 2004,
                    "description": "Complete redesign with LS1 V8 engine. Featured improved handling and performance. Z06 variant was track-focused. Established modern Corvette performance.",
                },
                {
                    "generation_name": "C6",
                    "start_year": 2005,
                    "end_year": 2013,
                    "description": "Refined design with LS2/LS3 V8 engines. Z06 and ZR1 variants were high-performance. ZR1 with supercharged V8 produced 638 horsepower. Excellent value for performance.",
                },
                {
                    "generation_name": "C7",
                    "start_year": 2014,
                    "end_year": 2019,
                    "description": "Final front-engine Corvette. Featured LT1/LT4 V8 engines. Z06 and ZR1 variants were track-focused. ZR1 produced 755 horsepower. Advanced technology and aerodynamics.",
                },
                {
                    "generation_name": "C8",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "First mid-engine Corvette. Featured LT2 V8 engine producing 490-495 horsepower. Z06 variant with flat-plane crank V8. Revolutionary design maintaining Corvette's performance legacy.",
                },
            ],
        },
        {
            "model": "SS",
            "generations": [
                {
                    "generation_name": "VF Series",
                    "start_year": 2014,
                    "end_year": 2017,
                    "description": "Modern performance sedan based on Holden Commodore VF. Featured 6.2L LS3 V8 engine producing 415 horsepower. Rear-wheel drive with excellent handling. Popular among enthusiasts for modification potential and sleeper appeal.",
                },
            ],
        },
        {
            "model": "Chevelle SS",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1964,
                    "end_year": 1967,
                    "description": "Original Chevelle SS, initially as Malibu SS trim. Rare Z16 option introduced 396 big-block V8 in 1965. SS 396 became dedicated performance series from 1966-67. Established Chevelle as a muscle car icon.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1968,
                    "end_year": 1972,
                    "description": "Redesigned body style with SS as performance option/package. Peak performance in 1970 with SS 454 LS6 engine rated at ~450 gross horsepower. Iconic muscle car generation with big-block V8 engines.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1973,
                    "end_year": 1973,
                    "description": "Colonnade body style. SS badge offered as appearance and performance package on Malibu models. Power reduced due to emissions regulations and safety standards. Last year of true Chevelle SS.",
                },
            ],
        },
        {
            "model": "Nova SS",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1963,
                    "end_year": 1965,
                    "description": "Known as Chevy II with Nova designation. SS badge introduced in 1963 as trim/package on Nova 400 Sport Coupe and Convertible. Lightweight compact muscle car foundation.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1966,
                    "end_year": 1967,
                    "description": "Continued as Chevy II/Nova SS with styling revisions. SS remained performance-appearance package. Popular among enthusiasts for compact size and V8 power.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1968,
                    "end_year": 1974,
                    "description": "Nova name solidified. SS became its own series (1968-70) then reverted to option package. Engine power peaked early; SS identity shifted toward appearance in later years. Classic 'pocket rocket' muscle car.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1975,
                    "end_year": 1976,
                    "description": "Final Nova SS years. Performance edge lost due to emissions; emphasis shifted to appearance/luxury trims. SS discontinued after 1976. Last of the classic Nova SS models.",
                },
            ],
        },
        {
            "model": "El Camino SS",
            "generations": [
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1968,
                    "end_year": 1972,
                    "description": "A-body El Camino based on Chevelle platform. SS-396 introduced as separate model in 1968. Peak SS performance in 1970 with LS6 454 engine. Unique muscle car/pickup hybrid design.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1973,
                    "end_year": 1977,
                    "description": "Colonnade body style. SS offered primarily as trim/option level. Less potent than earlier SS big-block models due to stricter emissions and safety regulations. More cosmetic and handling features than pure performance.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 1978,
                    "end_year": 1987,
                    "description": "G-body downsized generation. SS returned as full trim and appearance package. By mid-1980s, SS often carried 5.0L V8, though power was much lower than earlier SS models. Final generation of El Camino.",
                },
            ],
        },
        {
            "model": "Cobalt SS",
            "generations": [
                {
                    "generation_name": "SS Supercharged",
                    "start_year": 2005,
                    "end_year": 2007,
                    "description": "First Cobalt SS with 2.0L LSJ Ecotec supercharged engine producing ~205 horsepower. Available only as coupe. Popular among tuners for lightweight design and modification potential. Discontinued due to emissions regulations.",
                },
                {
                    "generation_name": "SS Turbocharged",
                    "start_year": 2008,
                    "end_year": 2010,
                    "description": "Relaunched with 2.0L LNF Ecotec turbocharged engine producing ~260 horsepower and 260 lb-ft torque. Available as coupe (2008-2010) and sedan (2009 only). Featured Reconfigurable Performance Display. Highly tunable compact performance car.",
                },
            ],
        },
        {
            "model": "Monte Carlo SS",
            "generations": [
                {
                    "generation_name": "1st Gen SS",
                    "start_year": 1970,
                    "end_year": 1971,
                    "description": "First Monte Carlo SS package offered. Featured Turbo-Jet 454 big-block V8 engines. Luxury-muscle blend with emphasis on styling, suspension, and comfort as well as power.",
                },
                {
                    "generation_name": "4th Gen SS",
                    "start_year": 1983,
                    "end_year": 1988,
                    "description": "SS reintroduced after hiatus. Featured smaller V8 engines and sporty owner trims. Special 'Aerocoupe' versions in 1986-87. Emphasized styling, suspension, and comfort alongside performance.",
                },
                {
                    "generation_name": "6th Gen SS",
                    "start_year": 2000,
                    "end_year": 2007,
                    "description": "SS version revived for final Monte Carlo generation. Engines evolved from V6 to supercharged V6 to late 5.3L V8. Personal luxury coupe with performance focus. Final generation of Monte Carlo.",
                },
            ],
        },
        {
            "model": "Impala SS",
            "generations": [
                {
                    "generation_name": "7th Gen",
                    "start_year": 1994,
                    "end_year": 1996,
                    "description": "Impala SS reintroduced on rear-wheel-drive B-body platform with LT1 5.7L V8 producing 260-305 horsepower. SS was the only Impala version offered. Modern interpretation of classic full-size performance sedan.",
                },
                {
                    "generation_name": "9th Gen",
                    "start_year": 2004,
                    "end_year": 2009,
                    "description": "Impala SS on front-wheel-drive W-body platform. 2004-2005 featured supercharged 3.8L V6 (L67). 2006-2009 upgraded to 5.3L V8 (LS4) with Active Fuel Management. Full-size performance sedan with modern technology.",
                },
            ],
        },
        {
            "model": "TrailBlazer SS",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2006,
                    "end_year": 2009,
                    "description": "Performance SUV variant with LS2 6.0L V8 producing ~395 horsepower and 400 lb-ft torque. Fast for its class with V8 power in SUV chassis. Rare example of SS badge on large SUV. Popular among truck/SUV enthusiasts.",
                },
            ],
        },
    ],
    "BMW": [
        {
            "model": "M3",
            "generations": [
                {
                    "generation_name": "E30",
                    "start_year": 1986,
                    "end_year": 1991,
                    "description": "The original M3, built for homologation. Featured high-revving S14 inline-4 engine and exceptional handling. Iconic in motorsport and highly collectible.",
                },
                {
                    "generation_name": "E36",
                    "start_year": 1992,
                    "end_year": 1999,
                    "description": "First M3 with inline-6 engine (S50/S52). More refined and comfortable while maintaining performance. US model had different engine than European version.",
                },
                {
                    "generation_name": "E46",
                    "start_year": 2000,
                    "end_year": 2006,
                    "description": "Widely considered one of the best M3 generations. Featured S54 inline-6 engine producing 333 horsepower. Excellent balance of performance and daily usability.",
                },
                {
                    "generation_name": "E90/E92/E93",
                    "start_year": 2007,
                    "end_year": 2013,
                    "description": "First M3 with V8 engine (S65). Produced 414 horsepower with high-revving character. E92 coupe and E93 convertible variants. Last naturally aspirated M3.",
                },
                {
                    "generation_name": "F80",
                    "start_year": 2014,
                    "end_year": 2018,
                    "description": "First turbocharged M3 with S55 inline-6 engine producing 425 horsepower. Improved fuel economy and torque. M3 sedan and M4 coupe separated.",
                },
                {
                    "generation_name": "G80",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest M3 with S58 inline-6 engine producing 473-503 horsepower. Competition and CS variants available. More aggressive styling and advanced technology.",
                },
            ],
        },
        {
            "model": "330i",
            "generations": [
                {
                    "generation_name": "E30",
                    "start_year": 1975,
                    "end_year": 1990,
                    "description": "BMW's compact executive sedan with inline-6 engines. Featured excellent handling and build quality. Established 3 Series reputation for sporty luxury.",
                },
                {
                    "generation_name": "E36",
                    "start_year": 1991,
                    "end_year": 1998,
                    "description": "More refined 3 Series with improved technology. Featured updated inline-6 engines and better handling. Popular among enthusiasts for modification potential.",
                },
                {
                    "generation_name": "E46",
                    "start_year": 1999,
                    "end_year": 2005,
                    "description": "Widely considered one of the best 3 Series generations. Featured updated inline-6 engines and excellent handling. Balance of performance and daily usability.",
                },
                {
                    "generation_name": "E90/E91/E92/E93",
                    "start_year": 2006,
                    "end_year": 2011,
                    "description": "First 3 Series with turbocharged engines (335i). Featured updated inline-6 engines and improved technology. E92 coupe and E93 convertible variants.",
                },
                {
                    "generation_name": "F30/F31/F34",
                    "start_year": 2012,
                    "end_year": 2018,
                    "description": "Complete redesign with turbocharged engines standard. Featured improved fuel economy and technology. More refined while maintaining sporty character.",
                },
                {
                    "generation_name": "G20/G21",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest 3 Series with improved technology and handling. Featured updated turbocharged engines and advanced safety features. More premium positioning.",
                },
            ],
        },
        {
            "model": "M4",
            "generations": [
                {
                    "generation_name": "F82/F83",
                    "start_year": 2014,
                    "end_year": 2020,
                    "description": "M4 coupe and convertible with S55 inline-6 engine producing 425 horsepower. Separated from M3 sedan. Competition variant produced 444 horsepower.",
                },
                {
                    "generation_name": "G82/G83",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest M4 with S58 inline-6 engine producing 473-503 horsepower. Competition and CSL variants available. More aggressive styling and advanced technology.",
                },
            ],
        },
        {
            "model": "1 Series",
            "generations": [
                {
                    "generation_name": "E81/E82/E87/E88",
                    "start_year": 2004,
                    "end_year": 2013,
                    "description": "BMW's compact car with rear-wheel drive. Featured efficient engines and good handling. 135i variant with turbocharged inline-6 was a performance model.",
                },
                {
                    "generation_name": "F20/F21",
                    "start_year": 2011,
                    "end_year": 2019,
                    "description": "Refined 1 Series with front-wheel drive introduced. Featured updated engines and improved technology. M135i variant offered high performance.",
                },
                {
                    "generation_name": "F40",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest 1 Series with front-wheel drive platform. Featured updated engines and improved technology. M135i variant with all-wheel drive available.",
                },
            ],
        },
        {
            "model": "2 Series",
            "generations": [
                {
                    "generation_name": "F22/F23",
                    "start_year": 2014,
                    "end_year": 2021,
                    "description": "BMW's compact coupe and convertible with rear-wheel drive. Featured turbocharged engines and excellent handling. M2 variant was track-focused.",
                },
                {
                    "generation_name": "G42",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Latest 2 Series coupe with improved technology and handling. Featured updated turbocharged engines. M2 variant continued with high performance.",
                },
            ],
        },
        {
            "model": "5 Series",
            "generations": [
                {
                    "generation_name": "E39",
                    "start_year": 1995,
                    "end_year": 2003,
                    "description": "Widely considered one of the best 5 Series generations. Featured inline-6 and V8 engines. Excellent balance of luxury, performance, and build quality.",
                },
                {
                    "generation_name": "E60/E61",
                    "start_year": 2004,
                    "end_year": 2010,
                    "description": "Controversial styling with improved technology. Featured updated engines and introduced iDrive. More modern but some preferred previous generation.",
                },
                {
                    "generation_name": "F10/F11",
                    "start_year": 2011,
                    "end_year": 2016,
                    "description": "More refined design with improved technology. Featured turbocharged engines and better fuel economy. More comfortable and luxurious.",
                },
                {
                    "generation_name": "G30/G31",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "Latest 5 Series with improved technology and handling. Featured updated engines and advanced safety features. More premium and refined.",
                },
            ],
        },
        {
            "model": "M5",
            "generations": [
                {
                    "generation_name": "E28",
                    "start_year": 1984,
                    "end_year": 1988,
                    "description": "First generation M5. Hand-built with 3.5L inline-6 M88 engine derived from M1. Naturally aspirated, established M5 as the ultimate sport sedan.",
                },
                {
                    "generation_name": "E34",
                    "start_year": 1988,
                    "end_year": 1995,
                    "description": "Second generation M5 with updated 3.6L and later 3.8L inline-6 engines. Touring (wagon) variant introduced in limited numbers. Refined and more powerful than E28.",
                },
                {
                    "generation_name": "E39",
                    "start_year": 1998,
                    "end_year": 2003,
                    "description": "Widely considered one of the best M5 generations. Featured S62 V8 engine producing 394 horsepower. Perfect balance of luxury and performance.",
                },
                {
                    "generation_name": "E60",
                    "start_year": 2005,
                    "end_year": 2010,
                    "description": "M5 with S85 V10 engine producing 500 horsepower. High-revving character and exceptional performance. SMG transmission was controversial.",
                },
                {
                    "generation_name": "F10",
                    "start_year": 2011,
                    "end_year": 2016,
                    "description": "M5 with S63 twin-turbo V8 engine producing 560 horsepower. Improved torque and fuel economy. Competition variant produced 575 horsepower.",
                },
                {
                    "generation_name": "F90",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Latest M5 with S63 twin-turbo V8 engine producing 600-617 horsepower. All-wheel drive standard. Competition and CS variants available.",
                },
            ],
        },
        {
            "model": "M340i",
            "generations": [
                {
                    "generation_name": "F30/F31/F34",
                    "start_year": 2016,
                    "end_year": 2018,
                    "description": "High-performance 3 Series variant with B58 turbocharged inline-6 engine producing 320 horsepower. Excellent balance of performance and daily usability.",
                },
                {
                    "generation_name": "G20/G21",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest M340i with updated B58 engine producing 382 horsepower. Improved handling and technology. All-wheel drive available.",
                },
            ],
        },
        {
            "model": "335i",
            "generations": [
                {
                    "generation_name": "E90/E91/E92/E93",
                    "start_year": 2006,
                    "end_year": 2011,
                    "description": "High-performance 3 Series with N54/N55 turbocharged inline-6 engine producing 300-320 horsepower. Popular for tuning potential and performance.",
                },
                {
                    "generation_name": "F30/F31/F34",
                    "start_year": 2012,
                    "end_year": 2018,
                    "description": "335i with N55 turbocharged inline-6 engine producing 300-320 horsepower. Improved fuel economy and technology. M Performance variants available.",
                },
            ],
        },
        {
            "model": "328i",
            "generations": [
                {
                    "generation_name": "E90/E91/E92/E93",
                    "start_year": 2006,
                    "end_year": 2011,
                    "description": "3 Series with naturally aspirated inline-6 engines producing 230 horsepower. Good balance of performance and fuel economy. Popular daily driver.",
                },
                {
                    "generation_name": "F30/F31/F34",
                    "start_year": 2012,
                    "end_year": 2015,
                    "description": "328i with N20 turbocharged inline-4 engine producing 240 horsepower. Improved fuel economy and torque. More efficient than previous generation.",
                },
            ],
        },
        {
            "model": "4 Series",
            "generations": [
                {
                    "generation_name": "F32/F33/F36",
                    "start_year": 2014,
                    "end_year": 2020,
                    "description": "BMW's coupe, convertible, and Gran Coupe. Separated from 3 Series. Featured turbocharged engines and excellent handling. M4 was high-performance variant.",
                },
                {
                    "generation_name": "G22/G23/G26",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest 4 Series with updated styling and technology. Featured updated engines and improved handling. M4 continued as high-performance variant.",
                },
            ],
        },
        {
            "model": "M440i",
            "generations": [
                {
                    "generation_name": "F32/F33/F36",
                    "start_year": 2016,
                    "end_year": 2020,
                    "description": "High-performance 4 Series variant with B58 turbocharged inline-6 engine producing 320-355 horsepower. Excellent balance of performance and luxury.",
                },
                {
                    "generation_name": "G22/G23/G26",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest M440i with updated B58 engine producing 382 horsepower. Improved handling and technology. All-wheel drive available.",
                },
            ],
        },
        {
            "model": "M240i",
            "generations": [
                {
                    "generation_name": "F22/F23",
                    "start_year": 2016,
                    "end_year": 2021,
                    "description": "High-performance 2 Series variant with B58 turbocharged inline-6 engine producing 335 horsepower. Excellent handling and driver engagement.",
                },
                {
                    "generation_name": "G42",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Latest M240i with updated B58 engine producing 382 horsepower. Improved handling and technology. All-wheel drive available.",
                },
            ],
        },
        {
            "model": "M2",
            "generations": [
                {
                    "generation_name": "F87",
                    "start_year": 2016,
                    "end_year": 2021,
                    "description": "BMW's compact M car with N55/S55 engines producing 365-405 horsepower. Track-focused with excellent handling. Competition and CS variants available.",
                },
                {
                    "generation_name": "G87",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "Latest M2 with S58 inline-6 engine producing 453 horsepower. More powerful and aggressive styling. Competition variant available.",
                },
            ],
        },
        {
            "model": "135i",
            "generations": [
                {
                    "generation_name": "E82/E88",
                    "start_year": 2008,
                    "end_year": 2013,
                    "description": "High-performance 1 Series coupe and convertible with N54/N55 turbocharged inline-6 engine producing 300-320 horsepower. Popular for tuning potential.",
                },
                {
                    "generation_name": "F20/F21",
                    "start_year": 2012,
                    "end_year": 2019,
                    "description": "M135i with N55 turbocharged inline-6 engine producing 315-320 horsepower. Front-wheel drive platform but still offered good performance.",
                },
            ],
        },
        {
            "model": "M1",
            "generations": [
                {
                    "generation_name": "E26",
                    "start_year": 1978,
                    "end_year": 1981,
                    "description": "BMW's first supercar, developed in collaboration with Lamborghini. Mid-engined with M88/4 inline-6 engine producing 277-280 horsepower. Built for homologation and highly collectible.",
                },
            ],
        },
        {
            "model": "1M",
            "generations": [
                {
                    "generation_name": "E82",
                    "start_year": 2011,
                    "end_year": 2011,
                    "description": "Limited production high-performance 1 Series coupe. Twin-turbo N54 inline-6 producing 335-340 horsepower. Rear-wheel drive, 6-speed manual only. Only ~6,300 units produced globally.",
                },
            ],
        },
        {
            "model": "M6",
            "generations": [
                {
                    "generation_name": "E24",
                    "start_year": 1983,
                    "end_year": 1989,
                    "description": "First generation M6 (M635CSi). Featured M88/3 inline-6 engine related to M1, producing 286-340 horsepower depending on market. Naturally aspirated grand tourer.",
                },
                {
                    "generation_name": "E63/E64",
                    "start_year": 2005,
                    "end_year": 2010,
                    "description": "Second generation M6 with S85 V10 engine shared with E60 M5. High-revving character. Available as coupe (E63) and convertible (E64). Modern return of M6 after long hiatus.",
                },
                {
                    "generation_name": "F12/F13/F06",
                    "start_year": 2012,
                    "end_year": 2019,
                    "description": "Third generation M6 with S63 twin-turbo V8 engine. Available as coupe (F13), convertible (F12), and Gran Coupe (F06). More power and modern technology. Replaced by M8 in 2019.",
                },
            ],
        },
        {
            "model": "M8",
            "generations": [
                {
                    "generation_name": "F91/F92/F93",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "High-performance 8 Series with S63 twin-turbo V8 engine shared with F90 M5. Available as coupe (F92), convertible (F91), and Gran Coupe (F93). Competition variants available. Replaces M6.",
                },
            ],
        },
        {
            "model": "Z3 M",
            "generations": [
                {
                    "generation_name": "E36/7",
                    "start_year": 1997,
                    "end_year": 2002,
                    "description": "M Roadster - high-performance roadster variant of Z3. Featured S50/S52/S54 inline-6 engines depending on market and year. Excellent handling and driver engagement.",
                },
                {
                    "generation_name": "E36/8",
                    "start_year": 1998,
                    "end_year": 2002,
                    "description": "M Coupe - fixed-roof variant with 'Clown Shoe' body style. More rigid than roadster. Featured S50/S52/S54 inline-6 engines. Highly sought after by enthusiasts.",
                },
            ],
        },
        {
            "model": "Z4 M",
            "generations": [
                {
                    "generation_name": "E85/E86",
                    "start_year": 2006,
                    "end_year": 2008,
                    "description": "Z4 M Roadster (E85) and M Coupe (E86) with S54 inline-6 engine producing 330 horsepower. High-revving naturally aspirated engine. Excellent handling and driver engagement.",
                },
            ],
        },
        {
            "model": "Z8",
            "generations": [
                {
                    "generation_name": "E52",
                    "start_year": 2000,
                    "end_year": 2003,
                    "description": "Limited production roadster with aluminum space frame. Featured S62 V8 engine producing 400 horsepower. 6-speed manual transmission. Only ~5,703 units produced. Highly collectible.",
                },
            ],
        },
        {
            "model": "X5 M",
            "generations": [
                {
                    "generation_name": "E70",
                    "start_year": 2010,
                    "end_year": 2013,
                    "description": "First generation X5 M with S63 twin-turbo V8 engine producing 547 horsepower. Introduced M performance to SUV segment. All-wheel drive standard.",
                },
                {
                    "generation_name": "F85",
                    "start_year": 2015,
                    "end_year": 2018,
                    "description": "Second generation X5 M with updated S63 engine producing 575 horsepower. Improved styling and technology. Shares platform with F86 X6 M.",
                },
                {
                    "generation_name": "F95",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Third generation X5 M with Competition variant producing up to 616 horsepower. 2024 LCI update introduced mild-hybrid S68 V8. Standard X5 M dropped, Competition only.",
                },
            ],
        },
        {
            "model": "X6 M",
            "generations": [
                {
                    "generation_name": "E71",
                    "start_year": 2010,
                    "end_year": 2014,
                    "description": "First generation X6 M with S63 twin-turbo V8 engine producing 547-560 horsepower. Crossover coupe SUV with dramatic styling and strong performance.",
                },
                {
                    "generation_name": "F86",
                    "start_year": 2015,
                    "end_year": 2019,
                    "description": "Second generation X6 M with S63 engine producing 567 horsepower. Updated styling and technology. Shares platform with F85 X5 M.",
                },
                {
                    "generation_name": "F96",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Third generation X6 M producing 600-617 horsepower. Competition variants available. 2023 LCI update introduced mild-hybrid S68 V8. Improved power and efficiency.",
                },
            ],
        },
        {
            "model": "XM",
            "generations": [
                {
                    "generation_name": "F95",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "First electrified M Original since M1. Plug-in hybrid with V8 + electric motor producing 644 horsepower. Label Red variant produces 738 horsepower, making it the most powerful production BMW M model. Standalone performance SUV.",
                },
            ],
        },
        {
            "model": "i4 M50",
            "generations": [
                {
                    "generation_name": "G26",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Electric M Performance variant of i4 Gran Coupe. Dual-motor all-wheel drive producing 536 horsepower. 0-60 mph in 3.7 seconds. EPA range 227-269 miles. Features adaptive M suspension and M Sport Brakes.",
                },
            ],
        },
        {
            "model": "i5 M60",
            "generations": [
                {
                    "generation_name": "G60",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Electric M Performance variant of i5 sedan. Dual-motor xDrive producing 593 horsepower and 586 lb-ft torque. 0-60 mph in 3.7 seconds. EPA range 240-256 miles. 84.3 kWh usable battery.",
                },
            ],
        },
        {
            "model": "i7 M70",
            "generations": [
                {
                    "generation_name": "G70",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "Electric M Performance variant of i7 flagship sedan. Dual-motor all-wheel drive producing 650 horsepower, up to 811 lb-ft torque with M Sport Boost. 0-60 mph in 3.5 seconds. EPA range ~295 miles. 101.7 kWh usable battery.",
                },
            ],
        },
        {
            "model": "iX M60",
            "generations": [
                {
                    "generation_name": "I20",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Electric M Performance variant of iX SUV. Dual-motor all-wheel drive producing 610 horsepower and 749 lb-ft torque. 0-60 mph in 3.6 seconds. EPA range ~285 miles. 109.5 kWh battery with fast DC charging.",
                },
            ],
        },
    ],
    "Audi": [
        {
            "model": "A4",
            "generations": [
                {
                    "generation_name": "B5",
                    "start_year": 1994,
                    "end_year": 2001,
                    "description": "Audi's compact executive sedan with all-wheel drive. Featured turbocharged engines and established A4 as a premium compact car. S4 variant was high-performance.",
                },
                {
                    "generation_name": "B6",
                    "start_year": 2002,
                    "end_year": 2005,
                    "description": "Refined A4 with updated styling and technology. Featured updated engines and improved handling. Continued A4's reputation for all-wheel drive capability.",
                },
                {
                    "generation_name": "B7",
                    "start_year": 2006,
                    "end_year": 2008,
                    "description": "Facelifted A4 with updated styling and engines. Featured FSI direct injection technology. Improved fuel economy and performance.",
                },
                {
                    "generation_name": "B8",
                    "start_year": 2009,
                    "end_year": 2015,
                    "description": "Complete redesign with longitudinal engine layout. Featured updated engines and improved technology. More spacious and refined.",
                },
                {
                    "generation_name": "B9",
                    "start_year": 2016,
                    "end_year": 2023,
                    "description": "Latest A4 with updated styling and technology. Featured updated engines and advanced safety features. More premium positioning.",
                },
                {
                    "generation_name": "B10",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Newest A4 generation with updated design and technology. Featured updated engines and improved efficiency. More modern and refined.",
                },
            ],
        },
        {
            "model": "S4",
            "generations": [
                {
                    "generation_name": "B5",
                    "start_year": 1994,
                    "end_year": 2001,
                    "description": "High-performance A4 with twin-turbo V6 engine producing 250-265 horsepower. All-wheel drive standard. Popular among enthusiasts for tuning potential.",
                },
                {
                    "generation_name": "B6",
                    "start_year": 2002,
                    "end_year": 2005,
                    "description": "S4 with naturally aspirated V8 engine producing 339 horsepower. High-revving character and excellent performance. All-wheel drive standard.",
                },
                {
                    "generation_name": "B7",
                    "start_year": 2006,
                    "end_year": 2008,
                    "description": "S4 with updated V8 engine producing 344 horsepower. Improved technology and handling. All-wheel drive standard.",
                },
                {
                    "generation_name": "B8",
                    "start_year": 2009,
                    "end_year": 2015,
                    "description": "S4 with supercharged V6 engine producing 333 horsepower. Improved fuel economy and torque. All-wheel drive standard.",
                },
                {
                    "generation_name": "B9",
                    "start_year": 2016,
                    "end_year": 2023,
                    "description": "S4 with turbocharged V6 engine producing 349 horsepower. Improved technology and handling. All-wheel drive standard.",
                },
            ],
        },
        {
            "model": "TT",
            "generations": [
                {
                    "generation_name": "8N",
                    "start_year": 1998,
                    "end_year": 2006,
                    "description": "Audi's compact sports car with distinctive styling. Featured turbocharged engines and all-wheel drive. TT RS variant was high-performance.",
                },
                {
                    "generation_name": "8J",
                    "start_year": 2007,
                    "end_year": 2014,
                    "description": "Refined TT with updated styling and engines. Featured improved handling and technology. TT RS variant with 5-cylinder engine was powerful.",
                },
                {
                    "generation_name": "8S",
                    "start_year": 2015,
                    "end_year": 2023,
                    "description": "Latest TT with updated styling and technology. Featured updated engines and improved handling. TT RS variant was track-focused.",
                },
            ],
        },
        {
            "model": "A3",
            "generations": [
                {
                    "generation_name": "8L",
                    "start_year": 1996,
                    "end_year": 2003,
                    "description": "Audi's compact car with all-wheel drive option. Featured efficient engines and good handling. Established A3 as a premium compact car.",
                },
                {
                    "generation_name": "8P",
                    "start_year": 2004,
                    "end_year": 2013,
                    "description": "Refined A3 with updated styling and technology. Featured updated engines and improved handling. S3 variant was high-performance.",
                },
                {
                    "generation_name": "8V",
                    "start_year": 2013,
                    "end_year": 2020,
                    "description": "Complete redesign with updated styling and technology. Featured updated engines and improved fuel economy. S3 and RS3 variants available.",
                },
                {
                    "generation_name": "8Y",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest A3 with updated design and technology. Featured updated engines and advanced safety features. S3 and RS3 variants available.",
                },
            ],
        },
        {
            "model": "S3",
            "generations": [
                {
                    "generation_name": "8L",
                    "start_year": 1999,
                    "end_year": 2003,
                    "description": "High-performance A3 with turbocharged engine producing 210-225 horsepower. All-wheel drive standard. Hot hatch variant.",
                },
                {
                    "generation_name": "8P",
                    "start_year": 2006,
                    "end_year": 2013,
                    "description": "S3 with turbocharged engine producing 265 horsepower. All-wheel drive standard. Improved performance and handling.",
                },
                {
                    "generation_name": "8V",
                    "start_year": 2013,
                    "end_year": 2020,
                    "description": "S3 with turbocharged engine producing 292 horsepower. All-wheel drive standard. Improved technology and performance.",
                },
                {
                    "generation_name": "8Y",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest S3 with turbocharged engine producing 306 horsepower. All-wheel drive standard. Improved technology and handling.",
                },
            ],
        },
        {
            "model": "RS3",
            "generations": [
                {
                    "generation_name": "8P",
                    "start_year": 2011,
                    "end_year": 2012,
                    "description": "Ultra-high-performance A3 with 5-cylinder turbocharged engine producing 335-340 horsepower. All-wheel drive standard. Hot hatch variant.",
                },
                {
                    "generation_name": "8V",
                    "start_year": 2015,
                    "end_year": 2021,
                    "description": "RS3 with 5-cylinder turbocharged engine producing 394-400 horsepower. All-wheel drive standard. Exceptional performance and sound.",
                },
                {
                    "generation_name": "8Y",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest RS3 with 5-cylinder turbocharged engine producing 401 horsepower. All-wheel drive standard. Improved technology and performance.",
                },
            ],
        },
        {
            "model": "A5",
            "generations": [
                {
                    "generation_name": "8T",
                    "start_year": 2007,
                    "end_year": 2016,
                    "description": "Audi's coupe and convertible with elegant styling. Featured efficient engines and all-wheel drive option. S5 variant was high-performance.",
                },
                {
                    "generation_name": "F5",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "Latest A5 with updated styling and technology. Featured updated engines and improved handling. S5 and RS5 variants available.",
                },
            ],
        },
        {
            "model": "S5",
            "generations": [
                {
                    "generation_name": "8T",
                    "start_year": 2007,
                    "end_year": 2016,
                    "description": "High-performance A5 with V8 or supercharged V6 engine producing 333-354 horsepower. All-wheel drive standard. Coupe and convertible variants.",
                },
                {
                    "generation_name": "F5",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "S5 with turbocharged V6 engine producing 349 horsepower. All-wheel drive standard. Improved technology and performance.",
                },
            ],
        },
        {
            "model": "RS4",
            "generations": [
                {
                    "generation_name": "B5",
                    "start_year": 2000,
                    "end_year": 2001,
                    "description": "Ultra-high-performance A4 with naturally aspirated V6 engine producing 380 horsepower. All-wheel drive standard. Avant wagon variant.",
                },
                {
                    "generation_name": "B7",
                    "start_year": 2006,
                    "end_year": 2008,
                    "description": "RS4 with naturally aspirated V8 engine producing 420 horsepower. All-wheel drive standard. Avant wagon and sedan variants.",
                },
                {
                    "generation_name": "B8",
                    "start_year": 2012,
                    "end_year": 2015,
                    "description": "RS4 with naturally aspirated V8 engine producing 450 horsepower. All-wheel drive standard. Avant wagon variant only.",
                },
                {
                    "generation_name": "B9",
                    "start_year": 2017,
                    "end_year": 2023,
                    "description": "RS4 with twin-turbo V6 engine producing 450 horsepower. All-wheel drive standard. Avant wagon variant. Improved torque and efficiency.",
                },
            ],
        },
        {
            "model": "RS5",
            "generations": [
                {
                    "generation_name": "8T",
                    "start_year": 2010,
                    "end_year": 2016,
                    "description": "Ultra-high-performance A5 with naturally aspirated V8 engine producing 450 horsepower. All-wheel drive standard. Coupe variant.",
                },
                {
                    "generation_name": "F5",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "RS5 with twin-turbo V6 engine producing 444-450 horsepower. All-wheel drive standard. Coupe and Sportback variants. Improved torque.",
                },
            ],
        },
        {
            "model": "R8",
            "generations": [
                {
                    "generation_name": "42",
                    "start_year": 2007,
                    "end_year": 2015,
                    "description": "Audi's mid-engine supercar with 4.2L V8 or 5.2L V10 engines. Available as coupe and Spyder. Popular for exhaust upgrades, ECU tuning, aero modifications, and performance enhancements. Strong aftermarket support for modifications.",
                },
                {
                    "generation_name": "4S",
                    "start_year": 2016,
                    "end_year": 2024,
                    "description": "Second generation R8 with updated styling and technology. Featured 5.2L V10 producing 532-602 horsepower. Available as coupe and Spyder. Popular for exhaust upgrades, ECU tuning, aero modifications, and performance enhancements. Strong aftermarket support.",
                },
            ],
        },
        {
            "model": "RS2 Avant",
            "generations": [
                {
                    "generation_name": "B4",
                    "start_year": 1994,
                    "end_year": 1995,
                    "description": "First Audi RS model, co-developed with Porsche. Turbocharged 5-cylinder engine producing 315 horsepower. All-wheel drive standard. Limited production high-performance wagon. Highly sought after by enthusiasts.",
                },
            ],
        },
        {
            "model": "RS6 Avant",
            "generations": [
                {
                    "generation_name": "C5",
                    "start_year": 2002,
                    "end_year": 2004,
                    "description": "Ultra-high-performance A6 wagon with twin-turbo V8 engine producing 450 horsepower. All-wheel drive standard. Avant wagon variant only. Exceptional performance in a practical package.",
                },
                {
                    "generation_name": "C6",
                    "start_year": 2008,
                    "end_year": 2010,
                    "description": "RS6 Avant with twin-turbo V10 engine producing 580 horsepower. All-wheel drive standard. Avant wagon variant. Incredible power and performance.",
                },
                {
                    "generation_name": "C7",
                    "start_year": 2013,
                    "end_year": 2018,
                    "description": "RS6 Avant with twin-turbo V8 engine producing 560-605 horsepower. All-wheel drive standard. Avant wagon variant. Improved efficiency and technology.",
                },
                {
                    "generation_name": "C8",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest RS6 Avant with twin-turbo V8 engine producing 591-621 horsepower. All-wheel drive standard. Avant wagon variant. Performance variant available. Exceptional handling and power.",
                },
            ],
        },
        {
            "model": "RS7 Sportback",
            "generations": [
                {
                    "generation_name": "C7",
                    "start_year": 2013,
                    "end_year": 2019,
                    "description": "Ultra-high-performance A7 Sportback with twin-turbo V8 engine producing 560-605 horsepower. All-wheel drive standard. Sportback fastback design. Exceptional performance and styling.",
                },
                {
                    "generation_name": "C8",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest RS7 Sportback with twin-turbo V8 engine producing 591-621 horsepower. All-wheel drive standard. Performance variant available. Improved technology and handling.",
                },
            ],
        },
        {
            "model": "RS Q3",
            "generations": [
                {
                    "generation_name": "8U",
                    "start_year": 2013,
                    "end_year": 2018,
                    "description": "Ultra-high-performance Q3 compact SUV with turbocharged 5-cylinder engine producing 310-340 horsepower. All-wheel drive standard. Compact performance SUV.",
                },
                {
                    "generation_name": "F3",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Latest RS Q3 with turbocharged 5-cylinder engine producing 400 horsepower. All-wheel drive standard. Available as standard Q3 and Sportback variant. Improved power and technology.",
                },
            ],
        },
        {
            "model": "RS Q8",
            "generations": [
                {
                    "generation_name": "4M",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Ultra-high-performance Q8 SUV coupe with twin-turbo V8 engine producing 591-631 horsepower. All-wheel drive standard. Performance variant introduced in 2024. Flagship performance SUV.",
                },
            ],
        },
        {
            "model": "S1",
            "generations": [
                {
                    "generation_name": "8X",
                    "start_year": 2014,
                    "end_year": 2018,
                    "description": "High-performance A1 with turbocharged 4-cylinder engine producing 228 horsepower. All-wheel drive standard. Hot hatch variant. Compact performance car.",
                },
            ],
        },
        {
            "model": "S6",
            "generations": [
                {
                    "generation_name": "C4",
                    "start_year": 1994,
                    "end_year": 1997,
                    "description": "High-performance A6 with turbocharged inline-5 engine producing 227 horsepower. All-wheel drive standard. Sedan and Avant wagon variants.",
                },
                {
                    "generation_name": "C5",
                    "start_year": 1999,
                    "end_year": 2003,
                    "description": "S6 with twin-turbo V8 engine producing 335-340 horsepower. All-wheel drive standard. Sedan and Avant wagon variants. Improved performance.",
                },
                {
                    "generation_name": "C6",
                    "start_year": 2006,
                    "end_year": 2011,
                    "description": "S6 with naturally aspirated V10 engine producing 435 horsepower. All-wheel drive standard. Sedan and Avant wagon variants. High-revving character.",
                },
                {
                    "generation_name": "C7",
                    "start_year": 2012,
                    "end_year": 2018,
                    "description": "S6 with twin-turbo V8 engine producing 420 horsepower. All-wheel drive standard. Sedan and Avant wagon variants. Improved efficiency and torque.",
                },
                {
                    "generation_name": "C8",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest S6 with twin-turbo V8 engine producing 444 horsepower. All-wheel drive standard. Sedan and Avant wagon variants. Improved technology and performance.",
                },
            ],
        },
        {
            "model": "S7 Sportback",
            "generations": [
                {
                    "generation_name": "C7",
                    "start_year": 2012,
                    "end_year": 2018,
                    "description": "High-performance A7 Sportback with twin-turbo V8 engine producing 420 horsepower. All-wheel drive standard. Sportback fastback design. Powerful and elegant.",
                },
                {
                    "generation_name": "C8",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Latest S7 Sportback with twin-turbo V8 engine producing 444 horsepower. All-wheel drive standard. Improved technology and performance. More refined.",
                },
            ],
        },
        {
            "model": "S8",
            "generations": [
                {
                    "generation_name": "D2",
                    "start_year": 1996,
                    "end_year": 2003,
                    "description": "High-performance A8 with naturally aspirated V8 engine producing 360 horsepower. All-wheel drive standard. Flagship performance sedan. Featured in Transporter films.",
                },
                {
                    "generation_name": "D3",
                    "start_year": 2006,
                    "end_year": 2010,
                    "description": "S8 with naturally aspirated V10 engine producing 450 horsepower. All-wheel drive standard. Flagship performance sedan. High-revving V10 character.",
                },
                {
                    "generation_name": "D4",
                    "start_year": 2012,
                    "end_year": 2018,
                    "description": "S8 with twin-turbo V8 engine producing 520 horsepower. All-wheel drive standard. Flagship performance sedan. Plus variant produced 605 horsepower.",
                },
                {
                    "generation_name": "D5",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest S8 with twin-turbo V8 engine producing 563 horsepower. All-wheel drive standard. Flagship performance sedan. Improved technology and luxury.",
                },
            ],
        },
        {
            "model": "SQ5",
            "generations": [
                {
                    "generation_name": "8R",
                    "start_year": 2012,
                    "end_year": 2017,
                    "description": "High-performance Q5 compact SUV with supercharged V6 engine producing 354 horsepower. All-wheel drive standard. Performance-oriented SUV.",
                },
                {
                    "generation_name": "FY",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "SQ5 with turbocharged V6 engine producing 349-354 horsepower. All-wheel drive standard. Available as standard Q5 and Sportback variant. Improved technology.",
                },
                {
                    "generation_name": "FYS",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Latest SQ5 with updated powertrain and technology. All-wheel drive standard. Available as standard Q5 and Sportback variant. More refined and efficient.",
                },
            ],
        },
        {
            "model": "TT RS",
            "generations": [
                {
                    "generation_name": "8J",
                    "start_year": 2009,
                    "end_year": 2014,
                    "description": "Ultra-high-performance TT with turbocharged 5-cylinder engine producing 340-360 horsepower. All-wheel drive standard. Available as coupe and roadster. Exceptional performance and sound.",
                },
                {
                    "generation_name": "8S",
                    "start_year": 2014,
                    "end_year": 2023,
                    "description": "TT RS with turbocharged 5-cylinder engine producing 400 horsepower. All-wheel drive standard. Available as coupe and roadster. Track-focused performance.",
                },
            ],
        },
        {
            "model": "TTS",
            "generations": [
                {
                    "generation_name": "8J",
                    "start_year": 2008,
                    "end_year": 2014,
                    "description": "High-performance TT with turbocharged 4-cylinder engine producing 265-272 horsepower. All-wheel drive standard. Available as coupe and roadster. Sport-oriented variant.",
                },
                {
                    "generation_name": "8S",
                    "start_year": 2014,
                    "end_year": 2023,
                    "description": "TTS with turbocharged 4-cylinder engine producing 292-306 horsepower. All-wheel drive standard. Available as coupe and roadster. Improved performance and technology.",
                },
            ],
        },
    ],
    "Mercedes": [
        {
            "model": "C-Class",
            "generations": [
                {
                    "generation_name": "W202",
                    "start_year": 1993,
                    "end_year": 2000,
                    "description": "Mercedes' compact executive sedan. Featured efficient engines and good build quality. Established C-Class as a premium compact car.",
                },
                {
                    "generation_name": "W203",
                    "start_year": 2001,
                    "end_year": 2007,
                    "description": "Refined C-Class with updated styling and technology. Featured updated engines and improved handling. More modern and comfortable.",
                },
                {
                    "generation_name": "W204",
                    "start_year": 2008,
                    "end_year": 2014,
                    "description": "Complete redesign with updated styling and technology. Featured updated engines and improved fuel economy. More premium positioning.",
                },
                {
                    "generation_name": "W205",
                    "start_year": 2015,
                    "end_year": 2021,
                    "description": "Latest C-Class with updated styling and technology. Featured turbocharged engines and advanced safety features. More refined and efficient.",
                },
                {
                    "generation_name": "W206",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Newest C-Class with updated design and technology. Featured updated engines and improved efficiency. More modern and premium.",
                },
            ],
        },
        {
            "model": "E-Class",
            "generations": [
                {
                    "generation_name": "W210",
                    "start_year": 1995,
                    "end_year": 2002,
                    "description": "Mercedes' mid-size executive sedan. Featured efficient engines and good build quality. Established E-Class reputation for luxury and reliability.",
                },
                {
                    "generation_name": "W211",
                    "start_year": 2003,
                    "end_year": 2009,
                    "description": "Refined E-Class with updated styling and technology. Featured updated engines and improved handling. More modern and comfortable.",
                },
                {
                    "generation_name": "W212",
                    "start_year": 2010,
                    "end_year": 2016,
                    "description": "Complete redesign with updated styling and technology. Featured turbocharged engines and improved fuel economy. More premium positioning.",
                },
                {
                    "generation_name": "W213",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "Latest E-Class with updated styling and technology. Featured updated engines and advanced safety features. More refined and efficient.",
                },
            ],
        },
        {
            "model": "C63 AMG",
            "generations": [
                {
                    "generation_name": "W204",
                    "start_year": 2008,
                    "end_year": 2014,
                    "description": "High-performance C-Class with naturally aspirated V8 engine producing 451-487 horsepower. Rear-wheel drive. Popular for its V8 sound and performance.",
                },
                {
                    "generation_name": "W205",
                    "start_year": 2015,
                    "end_year": 2021,
                    "description": "C63 AMG with twin-turbo V8 engine producing 469-510 horsepower. All-wheel drive available. Improved torque and fuel economy.",
                },
                {
                    "generation_name": "W206",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Latest C63 AMG with hybrid powertrain. Featured updated technology and improved efficiency. More refined while maintaining performance.",
                },
            ],
        },
        {
            "model": "E63 AMG",
            "generations": [
                {
                    "generation_name": "W211",
                    "start_year": 2006,
                    "end_year": 2009,
                    "description": "High-performance E-Class with naturally aspirated V8 engine producing 507 horsepower. All-wheel drive available. Powerful sedan and wagon.",
                },
                {
                    "generation_name": "W212",
                    "start_year": 2010,
                    "end_year": 2016,
                    "description": "E63 AMG with twin-turbo V8 engine producing 518-577 horsepower. All-wheel drive standard. Improved torque and performance.",
                },
                {
                    "generation_name": "W213",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "Latest E63 AMG with twin-turbo V8 engine producing 603 horsepower. All-wheel drive standard. Improved technology and performance.",
                },
            ],
        },
        {
            "model": "S-Class",
            "generations": [
                {
                    "generation_name": "W140",
                    "start_year": 1991,
                    "end_year": 1998,
                    "description": "Flagship luxury sedan known for its build quality and innovations. Featured V8 and V12 engines. Over-engineered and highly sought after by enthusiasts.",
                },
                {
                    "generation_name": "W220",
                    "start_year": 1998,
                    "end_year": 2005,
                    "description": "Lighter and more modern S-Class with advanced technology. Featured AIRMATIC suspension and improved fuel economy. Still highly regarded.",
                },
                {
                    "generation_name": "W221",
                    "start_year": 2006,
                    "end_year": 2013,
                    "description": "Refined S-Class with updated styling and technology. Featured advanced safety systems and luxury features. Popular for modifications.",
                },
                {
                    "generation_name": "W222",
                    "start_year": 2014,
                    "end_year": 2020,
                    "description": "Modern S-Class with cutting-edge technology and luxury. Featured advanced driver assistance and premium interior. Highly customizable.",
                },
                {
                    "generation_name": "W223",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest S-Class with updated design and technology. Featured MBUX infotainment and advanced autonomous features. Most advanced generation.",
                },
            ],
        },
        {
            "model": "SL-Class",
            "generations": [
                {
                    "generation_name": "R129",
                    "start_year": 1989,
                    "end_year": 2001,
                    "description": "Classic roadster with retractable hardtop. Featured V6, V8, and V12 engines. SL500 and SL600 were popular. Iconic design.",
                },
                {
                    "generation_name": "R230",
                    "start_year": 2001,
                    "end_year": 2011,
                    "description": "Modern SL with retractable hardtop. Featured AMG variants (SL55, SL65). Popular for performance modifications and luxury upgrades.",
                },
                {
                    "generation_name": "R231",
                    "start_year": 2012,
                    "end_year": 2021,
                    "description": "Refined SL with updated styling and technology. Featured AMG variants with twin-turbo engines. Lighter and more efficient.",
                },
                {
                    "generation_name": "R232",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Latest SL-Class with updated design and technology. Featured AMG variants with hybrid powertrains. Most advanced roadster generation.",
                },
            ],
        },
        {
            "model": "SLK/SLC-Class",
            "generations": [
                {
                    "generation_name": "R170",
                    "start_year": 1996,
                    "end_year": 2004,
                    "description": "Compact roadster with Vario-Roof folding hardtop. Featured SLK32 AMG variant. Popular entry-level Mercedes roadster.",
                },
                {
                    "generation_name": "R171",
                    "start_year": 2004,
                    "end_year": 2011,
                    "description": "Refined SLK with updated styling. Featured SLK55 AMG with naturally aspirated V8. Popular for modifications and tuning.",
                },
                {
                    "generation_name": "R172",
                    "start_year": 2011,
                    "end_year": 2020,
                    "description": "Final SLK/SLC generation. Renamed to SLC in later years. Featured AMG variants and updated technology. Last compact roadster from Mercedes.",
                },
            ],
        },
        {
            "model": "CLK-Class",
            "generations": [
                {
                    "generation_name": "C208",
                    "start_year": 1997,
                    "end_year": 2002,
                    "description": "Coupe and convertible based on C-Class platform. Featured CLK55 AMG variant. Popular for styling and performance modifications.",
                },
                {
                    "generation_name": "C209",
                    "start_year": 2002,
                    "end_year": 2009,
                    "description": "Refined CLK with updated styling. Featured CLK55 and CLK63 AMG variants. Popular among enthusiasts for V8 performance.",
                },
                {
                    "generation_name": "C207",
                    "start_year": 2010,
                    "end_year": 2017,
                    "description": "Final CLK generation before being replaced by E-Class coupe. Featured AMG variants with twin-turbo engines. Last of the CLK line.",
                },
            ],
        },
        {
            "model": "CL-Class",
            "generations": [
                {
                    "generation_name": "C140",
                    "start_year": 1992,
                    "end_year": 1998,
                    "description": "Luxury coupe based on S-Class W140 platform. Featured V8 and V12 engines. Rare and highly sought after. Known for build quality.",
                },
                {
                    "generation_name": "C215",
                    "start_year": 1999,
                    "end_year": 2006,
                    "description": "Refined CL coupe based on S-Class W220. Featured CL55 and CL65 AMG variants. Popular for luxury and performance modifications.",
                },
                {
                    "generation_name": "C216",
                    "start_year": 2007,
                    "end_year": 2014,
                    "description": "Modern CL coupe based on S-Class W221. Featured AMG variants with twin-turbo engines. Last generation before being renamed S-Class Coupe.",
                },
            ],
        },
        {
            "model": "CLS-Class",
            "generations": [
                {
                    "generation_name": "W219",
                    "start_year": 2004,
                    "end_year": 2010,
                    "description": "First 4-door coupe from Mercedes. Created new segment. Featured CLS55 and CLS63 AMG variants. Highly sought after for styling.",
                },
                {
                    "generation_name": "C218",
                    "start_year": 2011,
                    "end_year": 2017,
                    "description": "Refined CLS with updated styling. Featured CLS63 AMG with twin-turbo V8. Popular for modifications and performance upgrades.",
                },
                {
                    "generation_name": "C257",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Latest CLS with modern design and technology. Featured AMG variants and updated powertrains. Most advanced 4-door coupe generation.",
                },
            ],
        },
        {
            "model": "A-Class",
            "generations": [
                {
                    "generation_name": "W176",
                    "start_year": 2013,
                    "end_year": 2018,
                    "description": "Compact hatchback and sedan. Featured A45 AMG with 2.0L turbo producing 355-381 horsepower. Popular hot hatch in Europe.",
                },
                {
                    "generation_name": "W177",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest A-Class with updated design and technology. Featured A35 and A45 AMG variants. Most powerful compact Mercedes.",
                },
            ],
        },
        {
            "model": "CLA-Class",
            "generations": [
                {
                    "generation_name": "C117",
                    "start_year": 2014,
                    "end_year": 2019,
                    "description": "Compact 4-door coupe based on A-Class. Featured CLA45 AMG with 2.0L turbo producing 355-381 horsepower. Popular entry-level AMG.",
                },
                {
                    "generation_name": "C118",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Latest CLA-Class with updated styling and technology. Featured CLA35 and CLA45 AMG variants. Most advanced compact 4-door coupe.",
                },
            ],
        },
        {
            "model": "G-Class",
            "generations": [
                {
                    "generation_name": "W463",
                    "start_year": 1990,
                    "end_year": 2018,
                    "description": "Iconic boxy off-road SUV. Featured G55 and G63 AMG variants. Highly sought after for off-road capability and luxury. Longest production run.",
                },
                {
                    "generation_name": "W463 (New)",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Modernized G-Class with updated technology while maintaining classic design. Featured G63 AMG with twin-turbo V8. Most advanced generation.",
                },
            ],
        },
        {
            "model": "GLC-Class",
            "generations": [
                {
                    "generation_name": "X253",
                    "start_year": 2016,
                    "end_year": 2022,
                    "description": "Compact luxury SUV. Featured GLC43 and GLC63 AMG variants. Popular for performance and luxury modifications.",
                },
                {
                    "generation_name": "X254",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "Latest GLC-Class with updated design and technology. Featured AMG variants with hybrid powertrains. Most advanced compact SUV.",
                },
            ],
        },
        {
            "model": "GLE-Class",
            "generations": [
                {
                    "generation_name": "W166",
                    "start_year": 2012,
                    "end_year": 2019,
                    "description": "Mid-size luxury SUV (formerly ML-Class). Featured GLE43 and GLE63 AMG variants. Popular for performance and luxury upgrades.",
                },
                {
                    "generation_name": "V167",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Latest GLE-Class with updated styling and technology. Featured AMG variants with hybrid powertrains. Most advanced mid-size SUV.",
                },
            ],
        },
        {
            "model": "GLS-Class",
            "generations": [
                {
                    "generation_name": "X166",
                    "start_year": 2013,
                    "end_year": 2019,
                    "description": "Full-size luxury SUV (formerly GL-Class). Featured GLS63 AMG with twin-turbo V8. Popular for luxury and performance modifications.",
                },
                {
                    "generation_name": "X167",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Latest GLS-Class with updated design and technology. Featured AMG variants with hybrid powertrains. Most advanced full-size SUV.",
                },
            ],
        },
        {
            "model": "SL63 AMG",
            "generations": [
                {
                    "generation_name": "R230",
                    "start_year": 2004,
                    "end_year": 2011,
                    "description": "High-performance SL roadster with naturally aspirated V8 producing 518 horsepower. Later twin-turbo variant. Popular for modifications.",
                },
                {
                    "generation_name": "R231",
                    "start_year": 2012,
                    "end_year": 2021,
                    "description": "SL63 AMG with twin-turbo V8 producing 577 horsepower. Improved torque and performance. Popular among enthusiasts.",
                },
                {
                    "generation_name": "R232",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Latest SL63 AMG with updated powertrain and technology. Featured hybrid assist. Most advanced performance roadster.",
                },
            ],
        },
        {
            "model": "SL65 AMG",
            "generations": [
                {
                    "generation_name": "R230",
                    "start_year": 2004,
                    "end_year": 2011,
                    "description": "Ultra-high-performance SL with twin-turbo V12 producing 604-670 horsepower. Extreme torque. Rare and highly sought after.",
                },
                {
                    "generation_name": "R231",
                    "start_year": 2012,
                    "end_year": 2021,
                    "description": "SL65 AMG with twin-turbo V12 producing 621 horsepower. Massive torque output. Ultimate performance roadster.",
                },
            ],
        },
        {
            "model": "G63 AMG",
            "generations": [
                {
                    "generation_name": "W463",
                    "start_year": 2012,
                    "end_year": 2018,
                    "description": "High-performance G-Class with twin-turbo V8 producing 536-563 horsepower. Iconic boxy design with extreme performance. Highly sought after.",
                },
                {
                    "generation_name": "W463 (New)",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest G63 AMG with updated powertrain producing 577 horsepower. Improved technology while maintaining classic design. Most advanced G-Class.",
                },
            ],
        },
        {
            "model": "GLE63 AMG",
            "generations": [
                {
                    "generation_name": "W166",
                    "start_year": 2015,
                    "end_year": 2019,
                    "description": "High-performance GLE with twin-turbo V8 producing 550-577 horsepower. All-wheel drive standard. Popular for performance modifications.",
                },
                {
                    "generation_name": "V167",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Latest GLE63 AMG with updated powertrain and hybrid assist. Featured improved technology and performance. Most advanced performance SUV.",
                },
            ],
        },
        {
            "model": "S63 AMG",
            "generations": [
                {
                    "generation_name": "W221",
                    "start_year": 2007,
                    "end_year": 2013,
                    "description": "High-performance S-Class with naturally aspirated and twin-turbo V8 engines producing 518-577 horsepower. Ultimate luxury performance sedan.",
                },
                {
                    "generation_name": "W222",
                    "start_year": 2014,
                    "end_year": 2020,
                    "description": "S63 AMG with twin-turbo V8 producing 577-603 horsepower. All-wheel drive available. Popular for luxury and performance modifications.",
                },
                {
                    "generation_name": "W223",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest S63 AMG with hybrid powertrain producing 791 horsepower. Featured advanced technology and efficiency. Most powerful S-Class.",
                },
            ],
        },
        {
            "model": "S65 AMG",
            "generations": [
                {
                    "generation_name": "W221",
                    "start_year": 2007,
                    "end_year": 2013,
                    "description": "Ultra-high-performance S-Class with twin-turbo V12 producing 604-621 horsepower. Extreme torque. Ultimate luxury performance flagship.",
                },
                {
                    "generation_name": "W222",
                    "start_year": 2014,
                    "end_year": 2020,
                    "description": "S65 AMG with twin-turbo V12 producing 621 horsepower. Massive torque output. Rare and highly sought after. Last V12 S-Class.",
                },
            ],
        },
        {
            "model": "CLS63 AMG",
            "generations": [
                {
                    "generation_name": "W219",
                    "start_year": 2006,
                    "end_year": 2010,
                    "description": "High-performance CLS with naturally aspirated V8 producing 507 horsepower. Later twin-turbo variant. Popular for modifications.",
                },
                {
                    "generation_name": "C218",
                    "start_year": 2011,
                    "end_year": 2017,
                    "description": "CLS63 AMG with twin-turbo V8 producing 518-577 horsepower. All-wheel drive available. Popular among enthusiasts.",
                },
                {
                    "generation_name": "C257",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Latest CLS63 AMG with updated powertrain and technology. Featured hybrid assist. Most advanced performance 4-door coupe.",
                },
            ],
        },
        {
            "model": "CLK63 AMG",
            "generations": [
                {
                    "generation_name": "C209",
                    "start_year": 2006,
                    "end_year": 2009,
                    "description": "High-performance CLK with naturally aspirated V8 producing 481 horsepower. Available in coupe and convertible. Popular for modifications.",
                },
            ],
        },
        {
            "model": "A45 AMG",
            "generations": [
                {
                    "generation_name": "W176",
                    "start_year": 2013,
                    "end_year": 2018,
                    "description": "High-performance compact hatchback with 2.0L turbo producing 355-381 horsepower. Most powerful 4-cylinder production engine at launch. Popular hot hatch.",
                },
                {
                    "generation_name": "W177",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest A45 AMG with 2.0L turbo producing 382-421 horsepower. Improved technology and performance. Most powerful compact Mercedes.",
                },
            ],
        },
        {
            "model": "CLA45 AMG",
            "generations": [
                {
                    "generation_name": "C117",
                    "start_year": 2014,
                    "end_year": 2019,
                    "description": "High-performance compact 4-door coupe with 2.0L turbo producing 355-381 horsepower. Popular entry-level AMG. Popular for modifications.",
                },
                {
                    "generation_name": "C118",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Latest CLA45 AMG with 2.0L turbo producing 382-421 horsepower. Improved technology and performance. Most powerful compact 4-door coupe.",
                },
            ],
        },
        {
            "model": "SLS AMG",
            "generations": [
                {
                    "generation_name": "C197",
                    "start_year": 2010,
                    "end_year": 2014,
                    "description": "Supercar with naturally aspirated 6.2L V8 producing 563-622 horsepower. Gullwing doors. Modern interpretation of classic 300SL. Highly sought after.",
                },
            ],
        },
        {
            "model": "AMG GT",
            "generations": [
                {
                    "generation_name": "C190",
                    "start_year": 2015,
                    "end_year": 2024,
                    "description": "Sports car with twin-turbo V8 producing 456-730 horsepower. Available in multiple variants (GT, GT S, GT C, GT R, GT Black Series). Popular for track use and modifications.",
                },
            ],
        },
        {
            "model": "SLR McLaren",
            "generations": [
                {
                    "generation_name": "R199",
                    "start_year": 2003,
                    "end_year": 2010,
                    "description": "Supercar collaboration with McLaren. Featured supercharged 5.4L V8 producing 617-650 horsepower. Gullwing doors available. Rare and highly collectible.",
                },
            ],
        },
    ],
    "Volkswagen": [
        {
            "model": "Golf",
            "generations": [
                {
                    "generation_name": "Mk1",
                    "start_year": 1974,
                    "end_year": 1983,
                    "description": "The original Golf that established the compact hatchback segment. Featured efficient engines and practical design. GTI variant created the hot hatch category.",
                },
                {
                    "generation_name": "Mk2",
                    "start_year": 1984,
                    "end_year": 1992,
                    "description": "Refined Golf with improved technology. Featured updated engines and better handling. GTI variant continued hot hatch legacy.",
                },
                {
                    "generation_name": "Mk3",
                    "start_year": 1993,
                    "end_year": 1998,
                    "description": "Larger Golf with improved safety and comfort. Featured updated engines and better handling. VR6 variant offered high performance.",
                },
                {
                    "generation_name": "Mk4",
                    "start_year": 1999,
                    "end_year": 2005,
                    "description": "More refined Golf with improved build quality. Featured updated engines and better technology. GTI and R32 variants were high-performance.",
                },
                {
                    "generation_name": "Mk5",
                    "start_year": 2006,
                    "end_year": 2009,
                    "description": "Complete redesign with updated styling and technology. Featured turbocharged engines and improved handling. GTI variant was highly praised.",
                },
                {
                    "generation_name": "Mk6",
                    "start_year": 2010,
                    "end_year": 2014,
                    "description": "Refined Golf with improved technology and fuel economy. Featured updated engines and better handling. GTI and R variants were high-performance.",
                },
                {
                    "generation_name": "Mk7",
                    "start_year": 2015,
                    "end_year": 2020,
                    "description": "Latest Golf with updated styling and technology. Featured updated engines and improved efficiency. GTI and R variants were highly praised.",
                },
                {
                    "generation_name": "Mk8",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Newest Golf with updated design and technology. Featured updated engines and advanced safety features. GTI and R variants available.",
                },
            ],
        },
        {
            "model": "Jetta",
            "generations": [
                {
                    "generation_name": "Mk4",
                    "start_year": 1999,
                    "end_year": 2005,
                    "description": "Volkswagen's compact sedan based on Golf platform. Featured efficient engines and practical design. GLI variant was sporty.",
                },
                {
                    "generation_name": "Mk5",
                    "start_year": 2006,
                    "end_year": 2010,
                    "description": "Refined Jetta with updated styling and technology. Featured updated engines and improved handling. GLI variant was high-performance.",
                },
                {
                    "generation_name": "Mk6",
                    "start_year": 2011,
                    "end_year": 2018,
                    "description": "Complete redesign with updated styling and technology. Featured updated engines and improved fuel economy. GLI variant was sporty.",
                },
                {
                    "generation_name": "Mk7",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Latest Jetta with updated design and technology. Featured updated engines and advanced safety features. GLI variant available.",
                },
            ],
        },
        {
            "model": "GTI",
            "generations": [
                {
                    "generation_name": "Mk5",
                    "start_year": 2006,
                    "end_year": 2009,
                    "description": "High-performance Golf with turbocharged engine producing 200 horsepower. Excellent handling and driver engagement. Widely praised hot hatch.",
                },
                {
                    "generation_name": "Mk6",
                    "start_year": 2010,
                    "end_year": 2014,
                    "description": "GTI with turbocharged engine producing 200-220 horsepower. Improved technology and handling. Continued hot hatch legacy.",
                },
                {
                    "generation_name": "Mk7",
                    "start_year": 2015,
                    "end_year": 2020,
                    "description": "GTI with turbocharged engine producing 220-245 horsepower. Improved technology and performance. Widely considered one of the best hot hatches.",
                },
                {
                    "generation_name": "Mk8",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest GTI with turbocharged engine producing 241-245 horsepower. Improved technology and handling. Continues hot hatch legacy.",
                },
            ],
        },
        {
            "model": "Golf R",
            "generations": [
                {
                    "generation_name": "Mk5",
                    "start_year": 2008,
                    "end_year": 2009,
                    "description": "All-wheel drive high-performance Golf with turbocharged 2.0L engine producing 256 horsepower. More powerful than GTI with superior traction. Limited US availability.",
                },
                {
                    "generation_name": "Mk6",
                    "start_year": 2012,
                    "end_year": 2014,
                    "description": "Golf R with turbocharged engine producing 256 horsepower and all-wheel drive. Improved technology and performance. Highly sought after by enthusiasts.",
                },
                {
                    "generation_name": "Mk7",
                    "start_year": 2015,
                    "end_year": 2020,
                    "description": "Golf R with turbocharged engine producing 292 horsepower and all-wheel drive. Torque-vectoring rear differential. Widely considered one of the best all-wheel drive hot hatches.",
                },
                {
                    "generation_name": "Mk8",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Latest Golf R with turbocharged engine producing 315-328 horsepower and all-wheel drive. Advanced torque-vectoring and performance features. Continues as VW's flagship hot hatch.",
                },
            ],
        },
        {
            "model": "R32",
            "generations": [
                {
                    "generation_name": "Mk4",
                    "start_year": 2004,
                    "end_year": 2004,
                    "description": "Limited production Golf with 3.2L VR6 engine producing 240 horsepower and all-wheel drive. Only 5,000 units imported to US. Highly collectible and sought after by enthusiasts.",
                },
                {
                    "generation_name": "Mk5",
                    "start_year": 2008,
                    "end_year": 2008,
                    "description": "Final R32 with 3.2L VR6 engine producing 250 horsepower and all-wheel drive. Only 5,000 units imported to US. Last naturally aspirated R model, highly collectible.",
                },
            ],
        },
        {
            "model": "Scirocco",
            "generations": [
                {
                    "generation_name": "Mk1",
                    "start_year": 1974,
                    "end_year": 1980,
                    "description": "Volkswagen's sporty 2+2 coupe based on Golf platform. Featured efficient engines and sporty styling. GTI variant introduced in 1976 with ~110 PS. Established Scirocco as a sporty coupe.",
                },
                {
                    "generation_name": "Mk2",
                    "start_year": 1981,
                    "end_year": 1992,
                    "description": "Refined Scirocco with updated styling. GTX and GT trims featured ~139 PS. Some variants exceeded 200 km/h. Popular with enthusiasts for modifications and sporty character.",
                },
                {
                    "generation_name": "Mk3",
                    "start_year": 2008,
                    "end_year": 2017,
                    "description": "Modern Scirocco revival with updated design. R variant featured turbocharged engine producing 265-280 PS. 0-100 km/h in ~5.7 seconds. Not sold in US market but popular in Europe.",
                },
            ],
        },
        {
            "model": "Corrado",
            "generations": [
                {
                    "generation_name": "G60",
                    "start_year": 1988,
                    "end_year": 1992,
                    "description": "Volkswagen's sporty coupe with G-Lader supercharged 1.8L engine producing ~160 PS. Featured active rear spoiler and sporty handling. Cult classic among enthusiasts. Popular for modifications and restoration.",
                },
                {
                    "generation_name": "VR6",
                    "start_year": 1992,
                    "end_year": 1995,
                    "description": "Corrado with 2.8L VR6 engine (US) or 2.9L VR6 (Europe) producing 187-190 PS. 0-60 mph in ~6.9 seconds. Last year of production. Highly sought after by enthusiasts for its unique VR6 engine and sporty character.",
                },
            ],
        },
        {
            "model": "Arteon",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Volkswagen's upscale grand tourer with sporty liftback design. Featured turbocharged 2.0L engines producing 268-300 horsepower. R-Line trims with sporty styling. R variant (2020+) with 320 PS, all-wheel drive, and torque-vectoring rear differential. 0-60 mph in ~4.9 seconds for R variant.",
                },
            ],
        },
        {
            "model": "Passat CC",
            "generations": [
                {
                    "generation_name": "B6/B7",
                    "start_year": 2008,
                    "end_year": 2017,
                    "description": "Volkswagen's 4-door coupe based on Passat platform. Featured 2.0L turbocharged and 3.6L VR6 engines. 3.6L V6 4Motion variant produced 296 horsepower, 0-60 mph in ~5.3-5.6 seconds. R-Line styling packages available. Upscale sporty sedan with coupe-like roofline.",
                },
            ],
        },
        {
            "model": "Beetle",
            "generations": [
                {
                    "generation_name": "Classic",
                    "start_year": 1938,
                    "end_year": 2003,
                    "description": "The original Volkswagen Beetle, one of the most iconic cars ever made. Air-cooled rear-engine design. Highly collectible, especially early models and special editions. Popular for restoration, customization, and classic car culture.",
                },
                {
                    "generation_name": "New Beetle",
                    "start_year": 1998,
                    "end_year": 2010,
                    "description": "Modern reinterpretation of the classic Beetle. Featured front-engine, front-wheel drive layout. Turbo S variant with 1.8L turbocharged engine producing 150-180 horsepower. Popular for styling modifications and customization.",
                },
                {
                    "generation_name": "A5",
                    "start_year": 2012,
                    "end_year": 2019,
                    "description": "Redesigned Beetle with more aggressive styling. Featured turbocharged 2.0L engines. R-Line variant with 210 horsepower, 0-60 mph in ~6.5-6.7 seconds. Turbo and R-Line trims popular with enthusiasts. Final generation before discontinuation.",
                },
            ],
        },
        {
            "model": "Rabbit",
            "generations": [
                {
                    "generation_name": "Mk1",
                    "start_year": 1975,
                    "end_year": 1984,
                    "description": "US-market name for the Golf Mk1. Featured efficient engines and practical design. Rabbit GTI introduced in 1983 with 1.8L engine and sport-tuned suspension. Established hot hatch category in America. Popular for modifications and restoration.",
                },
                {
                    "generation_name": "Mk5",
                    "start_year": 2006,
                    "end_year": 2009,
                    "description": "US-market revival of Rabbit name for Golf Mk5. Featured turbocharged engines and improved handling. Rabbit GTI variant was high-performance. Name reverted to Golf after 2009.",
                },
            ],
        },
        {
            "model": "Cabriolet",
            "generations": [
                {
                    "generation_name": "Mk1",
                    "start_year": 1980,
                    "end_year": 1993,
                    "description": "Convertible version of Golf Mk1/Rabbit. Featured soft-top convertible design. GTI variant available with sporty performance. Long production run spanning multiple Golf generations. Popular for open-top driving and modifications.",
                },
                {
                    "generation_name": "Mk3",
                    "start_year": 1995,
                    "end_year": 2002,
                    "description": "Convertible version of Golf Mk3. Featured updated styling and improved safety. VR6 variant available with high performance. Last generation before being replaced by Eos.",
                },
            ],
        },
    ],
    "Dodge": [
        {
            "model": "Challenger",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1970,
                    "end_year": 1974,
                    "description": "The original Challenger, competitor to Mustang and Camaro. Featured V8 engines and iconic styling. R/T and SRT variants were high-performance.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1978,
                    "end_year": 1983,
                    "description": "Smaller Challenger due to fuel crisis. Featured smaller engines and compact design. Less powerful but maintained Challenger nameplate.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 2008,
                    "end_year": 2023,
                    "description": "Challenger revival with retro-modern design. Featured V6 and V8 engines. SRT and Hellcat variants with supercharged V8 produced 700+ horsepower. Long production run.",
                },
            ],
        },
        {
            "model": "Charger",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1966,
                    "end_year": 1967,
                    "description": "The original Charger, introduced as a fastback specialty car. Featured V8 engines including the legendary 426 HEMI. Full-length center console and bucket seats. Only 468 Chargers had the 426 HEMI in 1966, making them extremely rare.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1968,
                    "end_year": 1970,
                    "description": "Iconic 'coke bottle' design with flying buttress roof. Featured the famous Charger Daytona (1969) for NASCAR homologation. Available with 318, 383, 440, and 426 HEMI engines. One of the most iconic muscle car designs.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1971,
                    "end_year": 1974,
                    "description": "Fuselage body style with smoother, rounded design. Featured 426 HEMI in 1971 only, plus 340, 360, 383, and 440 V8s. Peak production year was 1973. R/T and Super Bee variants available. Last of the true muscle car Chargers.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 1975,
                    "end_year": 1978,
                    "description": "Transitioned to personal luxury coupe, sharing body with Chrysler Cordoba. Featured smaller V8s (318, 360, 400). Less performance-focused, more comfort-oriented. SE and Daytona appearance packages available.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 1981,
                    "end_year": 1987,
                    "description": "Radical departure - front-wheel drive subcompact hatchback based on Omni platform. Featured 2.2L turbocharged engines. Shelby Charger variants (1983-1987) with up to 175 hp in GLHS trim. Very different from classic Chargers but popular with tuners.",
                },
                {
                    "generation_name": "LX",
                    "start_year": 2006,
                    "end_year": 2010,
                    "description": "Dodge's full-size sedan with V6 and V8 engines. Featured rear-wheel drive and good performance. SRT8 variant was high-performance.",
                },
                {
                    "generation_name": "LD",
                    "start_year": 2011,
                    "end_year": 2023,
                    "description": "Refined Charger with updated styling and technology. Featured updated V6 and V8 engines. SRT and Hellcat variants with supercharged V8 produced 700+ horsepower.",
                },
                {
                    "generation_name": "LB",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Latest Charger with updated design and technology. Featured updated engines and improved efficiency. SRT and Hellcat variants available.",
                },
            ],
        },
        {
            "model": "Viper",
            "generations": [
                {
                    "generation_name": "SR I",
                    "start_year": 1992,
                    "end_year": 1995,
                    "description": "First generation Viper, Dodge's flagship sports car. Featured 8.0L naturally aspirated V10 producing 400 hp and 465 lb-ft torque. Roadster only (RT/10). Minimal amenities - no exterior door handles initially, raw driving experience. Established Viper as American supercar.",
                },
                {
                    "generation_name": "SR II",
                    "start_year": 1996,
                    "end_year": 2002,
                    "description": "Second generation with roadster (RT/10) and GTS coupe introduced mid-1996. Featured 8.0L V10 with 415-460 hp depending on variant. Improved safety with airbags, better finish, and aluminum components. ACR track variant available. Top speed ~189 mph.",
                },
                {
                    "generation_name": "ZB I",
                    "start_year": 2003,
                    "end_year": 2006,
                    "description": "Third generation with major redesign. Featured 8.3L V10 producing 500-510 hp and 525 lb-ft torque. Available as convertible and coupe. Upgraded rigidity, lighter components, sharp bodywork. Improved handling and performance.",
                },
                {
                    "generation_name": "ZB II",
                    "start_year": 2008,
                    "end_year": 2010,
                    "description": "Fourth generation with increased displacement to 8.4L V10. Produced 600 hp and 560 lb-ft torque. Featured ACR track-focused variant and Final Edition to mark end of production. Peak power output before hiatus.",
                },
                {
                    "generation_name": "VX I",
                    "start_year": 2013,
                    "end_year": 2017,
                    "description": "Fifth and final generation, initially branded as SRT Viper. Featured 8.4L V10 producing 640-645 hp and 600 lb-ft torque. Modern safety equipment (ABS, traction/stability control), electronics, and aero. ACR and Time Attack variants available. Discontinued in 2017 due to low sales and safety regulations.",
                },
            ],
        },
        {
            "model": "Neon SRT-4",
            "generations": [
                {
                    "generation_name": "SRT-4",
                    "start_year": 2003,
                    "end_year": 2005,
                    "description": "High-performance turbocharged variant of the Neon, built by Dodge's Performance Vehicle Operations (PVO/SRT). Featured 2.4L turbocharged inline-4 producing 215 hp (2003) or 230 hp (2004-2005). 0-60 in 5.3-5.6 seconds. Popular in tuning community. 2005 ACR variant with track-focused upgrades. Front-wheel drive, 5-speed manual only.",
                },
            ],
        },
        {
            "model": "Caliber SRT-4",
            "generations": [
                {
                    "generation_name": "SRT-4",
                    "start_year": 2008,
                    "end_year": 2009,
                    "description": "Successor to Neon SRT-4. Featured turbocharged 4-cylinder engine with high output. Maintained SRT-4 concept of turbo 4-cyl performance. Compact crossover with sporty character.",
                },
            ],
        },
        {
            "model": "Stealth",
            "generations": [
                {
                    "generation_name": "R/T Turbo",
                    "start_year": 1990,
                    "end_year": 1996,
                    "description": "Dodge version of Mitsubishi 3000GT. Featured 3.0L twin-turbocharged V6 (Mitsubishi 6G72) producing 300-320 hp and 307-315 lb-ft torque. All-wheel drive with selectable driver settings. Available with 5-speed manual or 4-speed automatic. Featured four-wheel steering (some years), active aerodynamics, and advanced performance tuning. High-tech sports car with impressive capabilities.",
                },
            ],
        },
        {
            "model": "Magnum",
            "generations": [
                {
                    "generation_name": "SRT-8",
                    "start_year": 2005,
                    "end_year": 2008,
                    "description": 'Performance wagon variant of the Magnum. Featured 6.1L HEMI V8 producing 425 hp and 420 lb-ft torque. 0-60 in 5.0-5.4 seconds, quarter-mile in 13.1-13.7 seconds. Featured 20-inch wheels, Brembo brakes (14.2" front / 13.8" rear), stiffer suspension, and lower ride height. Unique SRT body styling. 5-speed automatic with AutoStick, rear-wheel drive.',
                },
            ],
        },
        {
            "model": "Durango",
            "generations": [
                {
                    "generation_name": "SRT 392",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Performance SUV variant with 6.4L (392 cu-in) HEMI V8 producing 475 hp and 470 lb-ft torque. High-performance SUV with track capability. Featured SRT-tuned suspension, brakes, and styling.",
                },
                {
                    "generation_name": "SRT Hellcat",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Most powerful SUV ever produced. Featured supercharged 6.2L HEMI Hellcat V8 producing 710 hp and 645 lb-ft torque. Initially planned as one-year model but revived due to strong demand. Available in 2021, 2023, 2024, and continuing into 2025-2026. Ultimate performance SUV.",
                },
            ],
        },
        {
            "model": "Daytona",
            "generations": [
                {
                    "generation_name": "Turbo/Shelby",
                    "start_year": 1984,
                    "end_year": 1993,
                    "description": "Performance coupe built on Chrysler K/G-platform. Featured turbocharged 2.2L engines producing 93-146 hp depending on year and trim. Turbo, Turbo Z, Shelby, and IROC variants available. Shelby trim introduced in 1987 with premium features and performance tuning. Popular in 1980s performance car scene. Front-wheel drive with sporty handling.",
                },
            ],
        },
        {
            "model": "Omni",
            "generations": [
                {
                    "generation_name": "GLH/GLHS",
                    "start_year": 1984,
                    "end_year": 1986,
                    "description": "Shelby-tuned hot hatch variants. GLH (Goes Like Hell) featured turbocharged 2.2L producing 146 hp. GLHS (1986) was Shelby's final Omni project with upgraded turbo, intercooler, and tuning producing ~175 hp and 175 lb-ft torque. Only ~500 GLHS units built, making them rare collectibles. 0-60 in ~6.5 seconds, quarter-mile ~14.8 seconds. Iconic American hot hatch from the 1980s.",
                },
            ],
        },
    ],
    "Acura": [
        {
            "model": "Integra",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1986,
                    "end_year": 1989,
                    "description": "Acura's sporty compact coupe and sedan. Featured advanced suspension and became popular in the tuning scene. Same as Honda Integra with Acura branding.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1990,
                    "end_year": 1993,
                    "description": "Refined Integra with improved styling. The GS-R trim introduced VTEC technology, making it a favorite among enthusiasts.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 1994,
                    "end_year": 2001,
                    "description": "Widely considered the best Integra generation. Featured the legendary B18C engine in GS-R and Type R variants. Iconic in import tuning culture.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 2002,
                    "end_year": 2006,
                    "description": "Final generation with modern styling. Featured K-series engines and improved safety. Some enthusiasts preferred previous generation's character.",
                },
                {
                    "generation_name": "5th Gen",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "Modern Integra revival as a liftback. Featured turbocharged 4-cylinder engines. Type S variant introduced in 2024 with 320 hp, 6-speed manual, and limited-slip differential. High-performance variant with Brembo brakes and sport-tuned suspension.",
                },
            ],
        },
        {
            "model": "CL",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 1997,
                    "end_year": 1999,
                    "description": "Acura's luxury coupe. Featured 2.2L and 2.3L 4-cylinder engines, or 3.0L V6. Premium coupe with good handling and luxury features.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2001,
                    "end_year": 2003,
                    "description": "Refined CL with updated styling. Featured 3.2L V6 engine. Type S variant introduced in 2001 as Acura's first Type S model in North America, producing 260 hp with sport-tuned suspension, larger brakes, and optional 6-speed manual with limited-slip differential.",
                },
            ],
        },
        {
            "model": "MDX",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2001,
                    "end_year": 2006,
                    "description": "Acura's mid-size luxury SUV. Featured V6 engines and all-wheel drive. Popular for its combination of luxury, performance, and practicality.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2007,
                    "end_year": 2013,
                    "description": "Refined MDX with updated styling and technology. Featured improved V6 engines and SH-AWD all-wheel drive. More refined and capable.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 2014,
                    "end_year": 2020,
                    "description": "Complete redesign with updated styling and technology. Featured updated V6 engines and improved fuel economy. More modern and efficient.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest MDX with updated design and technology. Featured updated engines and advanced safety features. Type S variant introduced in 2022 with 3.0L turbocharged V6 producing 355 hp, SH-AWD, Brembo brakes, and air suspension.",
                },
            ],
        },
        {
            "model": "NSX",
            "generations": [
                {
                    "generation_name": "NA1/NA2",
                    "start_year": 1990,
                    "end_year": 2005,
                    "description": "Acura's mid-engine supercar. Featured VTEC V6 engine and aluminum construction. Revolutionary design and exceptional handling. Highly collectible.",
                },
                {
                    "generation_name": "NC1",
                    "start_year": 2016,
                    "end_year": 2022,
                    "description": "Modern NSX revival with hybrid powertrain. Featured twin-turbo V6 with electric motors producing 573 horsepower (Type S variant in 2022 produced 600 hp). Advanced technology and all-wheel drive. Production ended in 2022.",
                },
            ],
        },
        {
            "model": "RSX",
            "generations": [
                {
                    "generation_name": "DC5",
                    "start_year": 2001,
                    "end_year": 2006,
                    "description": "Acura's sporty compact coupe. Featured K20A2 engine in Type-S variant. Popular among enthusiasts for its high-revving character and handling.",
                },
            ],
        },
        {
            "model": "TL",
            "generations": [
                {
                    "generation_name": "2nd Gen",
                    "start_year": 1999,
                    "end_year": 2003,
                    "description": "Acura's mid-size sedan with V6 engines. Featured good performance and reliability. Type S variant available in 2002-2003 with 260 hp. Popular for its value and sporty character.",
                },
                {
                    "generation_name": "3rd Gen",
                    "start_year": 2004,
                    "end_year": 2008,
                    "description": "Refined TL with updated styling and engines. Featured improved technology and handling. Type S variant (2007-2008) was high-performance with 3.5L V6 producing 286 hp, optional 6-speed manual, Brembo brakes, and limited-slip differential.",
                },
                {
                    "generation_name": "4th Gen",
                    "start_year": 2009,
                    "end_year": 2014,
                    "description": "Latest TL with updated styling and technology. Featured updated V6 engines and improved fuel economy. SH-AWD all-wheel drive available.",
                },
            ],
        },
        {
            "model": "TLX",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2015,
                    "end_year": 2020,
                    "description": "Acura's mid-size sedan replacing TL and TSX. Featured V6 and turbocharged 4-cylinder engines. SH-AWD all-wheel drive available.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest TLX with updated styling and technology. Featured updated engines and improved handling. Type S variant introduced in 2021 with 3.0L turbocharged V6 producing 355 hp, SH-AWD, Brembo brakes, and sport-tuned suspension.",
                },
            ],
        },
        {
            "model": "TSX",
            "generations": [
                {
                    "generation_name": "CL9",
                    "start_year": 2004,
                    "end_year": 2008,
                    "description": "Acura's compact sedan based on European Accord. Featured efficient 4-cylinder engines and good handling. Popular for its value and sporty character.",
                },
                {
                    "generation_name": "CU2",
                    "start_year": 2009,
                    "end_year": 2014,
                    "description": "Refined TSX with updated styling and engines. Featured V6 option and improved technology. Continued TSX's reputation for value and performance.",
                },
            ],
        },
        {
            "model": "ZDX",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2010,
                    "end_year": 2013,
                    "description": "Acura's luxury crossover coupe. Featured V6 engines and SH-AWD all-wheel drive. Unique styling with coupe-like roofline. Discontinued after 2013.",
                },
                {
                    "generation_name": "2nd Gen",
                    "start_year": 2024,
                    "end_year": 2025,
                    "description": "Electric ZDX revival built on GM's Ultium platform. Featured all-electric powertrain with dual motors and all-wheel drive. Type S variant introduced with nearly 500 hp, Brembo brakes, height-adjustable air suspension, and 22-inch wheels. Production ended in 2025.",
                },
            ],
        },
    ],
    "Lexus": [
        {
            "model": "IS",
            "generations": [
                {
                    "generation_name": "XE10",
                    "start_year": 1998,
                    "end_year": 2005,
                    "description": "Lexus' compact executive sedan. Featured inline-6 engines and excellent build quality. Established IS as a sporty luxury car.",
                },
                {
                    "generation_name": "XE20",
                    "start_year": 2006,
                    "end_year": 2013,
                    "description": "Refined IS with updated styling and engines. Featured V6 engines and improved technology. IS F variant with V8 was high-performance.",
                },
                {
                    "generation_name": "XE30",
                    "start_year": 2014,
                    "end_year": 2020,
                    "description": "Complete redesign with updated styling and technology. Featured updated V6 engines and improved handling. More modern and refined.",
                },
                {
                    "generation_name": "XE40",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Latest IS with updated design and technology. Featured updated engines and advanced safety features. More premium positioning.",
                },
            ],
        },
        {
            "model": "GS",
            "generations": [
                {
                    "generation_name": "JZS160",
                    "start_year": 1998,
                    "end_year": 2005,
                    "description": "Lexus' mid-size executive sedan. Featured inline-6 and V8 engines. Excellent balance of luxury and performance.",
                },
                {
                    "generation_name": "GRS190",
                    "start_year": 2006,
                    "end_year": 2011,
                    "description": "Refined GS with updated styling and engines. Featured V6 and V8 engines. Improved technology and handling.",
                },
                {
                    "generation_name": "GRL10",
                    "start_year": 2012,
                    "end_year": 2020,
                    "description": "Latest GS with updated styling and technology. Featured updated engines and improved fuel economy. More refined and efficient.",
                },
            ],
        },
        {
            "model": "GS F",
            "generations": [
                {
                    "generation_name": "URL10",
                    "start_year": 2016,
                    "end_year": 2020,
                    "description": "High-performance GS with naturally aspirated 5.0L V8 engine (2UR-GSE) producing 467 horsepower. Track-focused variant with excellent handling and build quality. Popular for exhaust upgrades, suspension modifications, and performance tuning.",
                },
            ],
        },
        {
            "model": "RC",
            "generations": [
                {
                    "generation_name": "ZRC",
                    "start_year": 2015,
                    "end_year": 2024,
                    "description": "Lexus' compact coupe with sporty styling. Featured V6 and V8 engines. RC F variant with V8 was high-performance.",
                },
            ],
        },
        {
            "model": "IS F",
            "generations": [
                {
                    "generation_name": "XE20",
                    "start_year": 2008,
                    "end_year": 2013,
                    "description": "High-performance IS with naturally aspirated V8 engine producing 416 horsepower. Excellent handling and build quality. Track-focused variant.",
                },
            ],
        },
        {
            "model": "RC F",
            "generations": [
                {
                    "generation_name": "ZRC",
                    "start_year": 2015,
                    "end_year": 2024,
                    "description": "High-performance RC with naturally aspirated V8 engine producing 467 horsepower. Track-focused with excellent handling and build quality.",
                },
            ],
        },
        {
            "model": "SC300",
            "generations": [
                {
                    "generation_name": "JZZ31",
                    "start_year": 1992,
                    "end_year": 2000,
                    "description": "First generation SC coupe with 3.0L inline-6 engine (2JZ-GE) producing 225 horsepower. Available with 5-speed manual (1992-1997) or automatic. Highly popular in enthusiast community for 2JZ-GTE swaps, NA-T conversions, and drift builds. VVT-i added in 1998. Popular for suspension upgrades, turbo conversions, and stance modifications.",
                },
            ],
        },
        {
            "model": "SC400",
            "generations": [
                {
                    "generation_name": "UZZ31",
                    "start_year": 1992,
                    "end_year": 2000,
                    "description": "First generation SC coupe with 4.0L V8 engine (1UZ-FE) producing 250-290 horsepower. Automatic transmission only. Smooth V8 power delivery. Popular for luxury modifications, V8 swaps into other platforms, and VIP/stance builds. VVT-i added in 1998. Known for reliability and smooth operation.",
                },
            ],
        },
        {
            "model": "SC430",
            "generations": [
                {
                    "generation_name": "UZZ40",
                    "start_year": 2002,
                    "end_year": 2010,
                    "description": "Second generation SC with retractable hardtop convertible. Features 4.3L V8 engine (3UZ-FE) producing 288-300 horsepower. Luxury-focused grand tourer. Popular for comfort modifications, suspension upgrades, and luxury customization. Less performance-focused than first generation but still has enthusiast following.",
                },
            ],
        },
        {
            "model": "LC",
            "generations": [
                {
                    "generation_name": "URZ100",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Lexus' flagship grand tourer with stunning design. Features 5.0L naturally aspirated V8 (LC500) producing 471 horsepower or 3.5L V6 hybrid (LC500h). Available as coupe and convertible. Built on GA-L platform with excellent handling. Popular for exhaust upgrades, aero modifications, and luxury customization. Convertible introduced in 2021, major interior/tech updates in 2024.",
                },
            ],
        },
        {
            "model": "LS",
            "generations": [
                {
                    "generation_name": "UCF10",
                    "start_year": 1990,
                    "end_year": 1994,
                    "description": "First generation LS, establishing Lexus as a luxury brand. Featured V8 engine and exceptional build quality. Popular for VIP/stance modifications and luxury customization.",
                },
                {
                    "generation_name": "UCF20",
                    "start_year": 1995,
                    "end_year": 2000,
                    "description": "Second generation LS with more refined design. Featured improved engines and technology. Highly popular in VIP/stance culture for modifications.",
                },
                {
                    "generation_name": "UCF30",
                    "start_year": 2001,
                    "end_year": 2006,
                    "description": "Third generation LS with updated styling and technology. Featured V8 engines and improved luxury features. Popular for VIP modifications and custom builds.",
                },
                {
                    "generation_name": "UCF40",
                    "start_year": 2007,
                    "end_year": 2017,
                    "description": "Fourth generation LS with more modern design. Featured V8 and hybrid powertrains. Popular for luxury modifications, VIP styling, and custom interiors.",
                },
                {
                    "generation_name": "URF50",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Fifth generation LS with bold new design language. Featured V6 twin-turbo and hybrid powertrains. Popular for luxury customization, VIP modifications, and high-end builds.",
                },
            ],
        },
        {
            "model": "LFA",
            "generations": [
                {
                    "generation_name": "LFA10",
                    "start_year": 2010,
                    "end_year": 2012,
                    "description": "Lexus' limited-production supercar with naturally aspirated 4.8L V10 engine producing 552 horsepower. Only 500 units produced. Features carbon fiber construction and Yamaha-tuned exhaust. Highly collectible, modifications typically focus on wheels, suspension, and subtle performance enhancements while preserving value.",
                },
            ],
        },
        {
            "model": "GX",
            "generations": [
                {
                    "generation_name": "J120",
                    "start_year": 2003,
                    "end_year": 2009,
                    "description": "First generation GX luxury SUV. Based on Land Cruiser Prado platform. Featured V8 engine and excellent off-road capability. Popular for off-road modifications, lift kits, and overlanding builds.",
                },
                {
                    "generation_name": "J150",
                    "start_year": 2010,
                    "end_year": 2023,
                    "description": "Second generation GX with updated styling. Featured V8 engine and improved technology. Popular for off-road modifications, luxury overlanding builds, and suspension upgrades.",
                },
                {
                    "generation_name": "J250",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Third generation GX with complete redesign. Features new platform, updated engines, and modern technology. Popular for off-road modifications and luxury overlanding builds.",
                },
            ],
        },
        {
            "model": "LX",
            "generations": [
                {
                    "generation_name": "J80",
                    "start_year": 1996,
                    "end_year": 1997,
                    "description": "First generation LX. Luxury version of Land Cruiser. Featured V8 engine and luxury appointments. Popular for luxury off-road modifications.",
                },
                {
                    "generation_name": "J100",
                    "start_year": 1998,
                    "end_year": 2007,
                    "description": "Second generation LX with more refined design. Featured V8 engines and improved luxury. Popular for luxury off-road modifications and overlanding builds.",
                },
                {
                    "generation_name": "J200",
                    "start_year": 2008,
                    "end_year": 2021,
                    "description": "Third generation LX with updated styling and technology. Featured powerful V8 engines and advanced suspension. Popular for luxury off-road modifications, lift kits, and high-end overlanding builds.",
                },
                {
                    "generation_name": "J310",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Fourth generation LX with complete redesign. Features new platform, updated engines, and modern technology. Popular for luxury off-road modifications and premium overlanding builds.",
                },
            ],
        },
        {
            "model": "CT200h",
            "generations": [
                {
                    "generation_name": "ZWA10",
                    "start_year": 2011,
                    "end_year": 2017,
                    "description": "Lexus' compact hybrid hatchback with 1.8L hybrid powertrain (2ZR-FXE) producing 134 combined horsepower. Popular in tuning scene despite hybrid limitations. Common modifications include suspension upgrades, brake improvements, F-Sport styling parts, and aesthetic modifications. Known for head gasket issues in some years, addressed with catch cans and EGR cleaning. Popular for stance builds and handling-focused modifications.",
                },
            ],
        },
        {
            "model": "ES",
            "generations": [
                {
                    "generation_name": "V20",
                    "start_year": 1990,
                    "end_year": 1996,
                    "description": "First generation ES luxury sedan. Based on Camry platform with luxury appointments. Popular for subtle modifications and luxury customization.",
                },
                {
                    "generation_name": "XV20",
                    "start_year": 1997,
                    "end_year": 2001,
                    "description": "Second generation ES with updated design. Featured V6 engines and improved luxury. Popular for modifications and custom builds.",
                },
                {
                    "generation_name": "XV30",
                    "start_year": 2002,
                    "end_year": 2006,
                    "description": "Third generation ES with more modern styling. Featured V6 engines and improved technology. Popular for modifications and luxury customization.",
                },
                {
                    "generation_name": "XV40",
                    "start_year": 2007,
                    "end_year": 2012,
                    "description": "Fourth generation ES with updated design. Featured V6 and hybrid powertrains. Popular for modifications and custom builds.",
                },
                {
                    "generation_name": "XV60",
                    "start_year": 2013,
                    "end_year": 2018,
                    "description": "Fifth generation ES with more aggressive styling. Featured V6 and hybrid powertrains. Popular for modifications and luxury customization.",
                },
                {
                    "generation_name": "XV70",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Sixth generation ES with complete redesign. Features new platform, updated engines, and modern technology. Popular for modifications and luxury customization.",
                },
            ],
        },
    ],
    "Mitsubishi": [
        {
            "model": "Lancer Evolution",
            "generations": [
                {
                    "generation_name": "I",
                    "start_year": 1992,
                    "end_year": 1995,
                    "description": "The original Lancer Evolution, built for rally homologation. Featured turbocharged engine and all-wheel drive. Established Evo as a rally legend.",
                },
                {
                    "generation_name": "II",
                    "start_year": 1996,
                    "end_year": 1998,
                    "description": "Refined Evolution with improved engine and handling. Featured updated turbocharged engine and better all-wheel drive system.",
                },
                {
                    "generation_name": "III",
                    "start_year": 1999,
                    "end_year": 2000,
                    "description": "Evolution with updated styling and improved performance. Featured updated turbocharged engine and better handling.",
                },
                {
                    "generation_name": "IV",
                    "start_year": 2001,
                    "end_year": 2002,
                    "description": "Evolution with significant updates. Featured improved turbocharged engine and all-wheel drive. Popular among enthusiasts.",
                },
                {
                    "generation_name": "V",
                    "start_year": 2003,
                    "end_year": 2005,
                    "description": "Evolution with updated styling and improved performance. Featured updated turbocharged engine and better handling. Popular in tuning scene.",
                },
                {
                    "generation_name": "VI",
                    "start_year": 2006,
                    "end_year": 2007,
                    "description": "Evolution with refined styling and improved technology. Featured updated turbocharged engine and better all-wheel drive system.",
                },
                {
                    "generation_name": "VII",
                    "start_year": 2008,
                    "end_year": 2010,
                    "description": "Evolution with updated styling and improved performance. Featured updated turbocharged engine and better handling. Popular among enthusiasts.",
                },
                {
                    "generation_name": "VIII",
                    "start_year": 2011,
                    "end_year": 2015,
                    "description": "Final Evolution generation sold in US. Featured turbocharged engine producing 291 horsepower. All-wheel drive standard. Highly sought after.",
                },
                {
                    "generation_name": "IX",
                    "start_year": 2016,
                    "end_year": 2016,
                    "description": "Final Evolution, limited production. Featured turbocharged engine and all-wheel drive. Marked the end of the Evolution line.",
                },
            ],
        },
        {
            "model": "3000GT",
            "generations": [
                {
                    "generation_name": "First Generation",
                    "start_year": 1991,
                    "end_year": 1993,
                    "description": "Mitsubishi's flagship sports car (GTO in Japan). VR-4 trim featured 3.0L twin-turbocharged V6 (6G72) producing 300 hp, all-wheel drive, four-wheel steering, active aerodynamics, and active exhaust. Base/SL models used naturally aspirated V6. High-tech sports car with impressive capabilities. Very popular with enthusiasts for modifications including turbo upgrades, ECU tuning, exhaust systems, and suspension work.",
                },
                {
                    "generation_name": "Second Generation",
                    "start_year": 1994,
                    "end_year": 1996,
                    "description": "Updated 3000GT with fixed headlights replacing pop-ups. VR-4 featured 6-speed manual transmission option. Some high-end features scaled back. Spyder convertible variant introduced in 1995-1996 with retractable hardtop. Popular for modifications and tuning. Strong aftermarket support.",
                },
                {
                    "generation_name": "Third Generation",
                    "start_year": 1997,
                    "end_year": 1999,
                    "description": "Final generation with further refinements. VR-4 featured updated styling including aggressive front bumper and distinctive 'Combat Wing' spoiler. Production ended in US after 1999. Highly sought after by collectors and enthusiasts. Popular for modifications including turbo upgrades, intercooler upgrades, ECU tuning, and performance enhancements.",
                },
            ],
        },
        {
            "model": "Eclipse",
            "generations": [
                {
                    "generation_name": "First Generation",
                    "start_year": 1990,
                    "end_year": 1994,
                    "description": "Mitsubishi's sporty compact coupe. GSX trim featured turbocharged 2.0L 4G63T engine with all-wheel drive producing 195 hp. GS-T trim featured same turbo engine with front-wheel drive. Base models used naturally aspirated engines. Very popular with enthusiasts for modifications including turbo upgrades, intercooler upgrades, ECU tuning, exhaust systems, and suspension work. Strong aftermarket support and tuning community.",
                },
                {
                    "generation_name": "Second Generation",
                    "start_year": 1995,
                    "end_year": 1999,
                    "description": "Redesigned Eclipse with updated styling. GSX (AWD) and GS-T (FWD) continued with upgraded 2.0L turbo 4G63T producing 210 hp. Convertible Spyder variant available. Highly popular in tuning scene with extensive aftermarket support. Engine swaps, turbo upgrades, and performance modifications are common. Iconic 90s tuner car.",
                },
                {
                    "generation_name": "Third Generation",
                    "start_year": 2000,
                    "end_year": 2005,
                    "description": "Redesigned Eclipse without turbo variants. Featured V6 engines in GT trim. Less popular with hardcore enthusiasts but still has following for modifications including intake/exhaust upgrades, suspension work, and styling modifications.",
                },
                {
                    "generation_name": "Fourth Generation",
                    "start_year": 2006,
                    "end_year": 2012,
                    "description": "Final Eclipse generation with updated styling. Featured V6 engines in GT trim. No turbo or AWD variants. Less enthusiast-focused than earlier generations but still has modification community for styling and performance upgrades.",
                },
            ],
        },
        {
            "model": "Galant VR-4",
            "generations": [
                {
                    "generation_name": "6th Generation",
                    "start_year": 1988,
                    "end_year": 1992,
                    "description": "Rally-bred performance sedan built for Group A homologation. Featured turbocharged 2.0L 4G63T engine, full-time all-wheel drive, four-wheel steering, and four-wheel independent suspension. Only 2,000 units imported to US in 1991, 1,000 in 1992. Highly sought after by enthusiasts and collectors. Popular for modifications including turbo upgrades, ECU tuning, suspension work, and rally-inspired builds. Rare and collectible.",
                },
            ],
        },
        {
            "model": "Starion",
            "generations": [
                {
                    "generation_name": "First Generation",
                    "start_year": 1983,
                    "end_year": 1986,
                    "description": "Mitsubishi's turbocharged rear-wheel-drive sports coupe. Featured 2.6L turbocharged inline-4 engine. Also sold as Dodge/Plymouth Conquest in North America. Popular with enthusiasts for modifications including turbo upgrades, intercooler upgrades, and performance tuning. Classic 80s sports car with strong following.",
                },
                {
                    "generation_name": "Second Generation",
                    "start_year": 1987,
                    "end_year": 1989,
                    "description": "Updated Starion with wide-body fenders ('fatty' models). ESI-R and TSi trims featured enhanced turbocharged engines, improved handling packages, and aggressive styling. Also sold as Chrysler Conquest. Highly popular with enthusiasts for modifications and tuning. Collectible 80s turbo sports car.",
                },
            ],
        },
        {
            "model": "Lancer Ralliart",
            "generations": [
                {
                    "generation_name": "9th Generation",
                    "start_year": 2009,
                    "end_year": 2015,
                    "description": "Performance variant of the Lancer positioned between GTS and Evolution. Featured turbocharged 2.0L MIVEC engine producing 237 hp and 253 lb-ft torque. Twin-clutch SST transmission with full-time all-wheel drive and Active Center Differential. Sport-tuned suspension and aggressive styling. Popular with enthusiasts for modifications including ECU tuning, exhaust upgrades, suspension work, and performance enhancements. Excellent value for turbo AWD performance sedan.",
                },
            ],
        },
    ],
    "Porsche": [
        {
            "model": "911",
            "generations": [
                {
                    "generation_name": "930",
                    "start_year": 1975,
                    "end_year": 1989,
                    "description": "Porsche 911 Turbo with iconic whale tail. Featured turbocharged flat-6 engine. Established 911 Turbo as a supercar. Highly collectible.",
                },
                {
                    "generation_name": "964",
                    "start_year": 1989,
                    "end_year": 1994,
                    "description": "Modernized 911 with updated technology. Featured updated engines and improved handling. Turbo variant was high-performance. Last air-cooled generation for some variants.",
                },
                {
                    "generation_name": "993",
                    "start_year": 1995,
                    "end_year": 1998,
                    "description": "Final air-cooled 911. Featured updated styling and improved handling. Turbo variant with twin-turbo engine. Highly collectible and sought after.",
                },
                {
                    "generation_name": "996",
                    "start_year": 1999,
                    "end_year": 2004,
                    "description": "First water-cooled 911. Featured updated engines and improved technology. Controversial styling but excellent performance. Turbo variant was powerful.",
                },
                {
                    "generation_name": "997",
                    "start_year": 2005,
                    "end_year": 2012,
                    "description": "Refined 911 with updated styling. Featured updated engines and improved handling. Turbo and GT3 variants were high-performance. Popular generation.",
                },
                {
                    "generation_name": "991",
                    "start_year": 2012,
                    "end_year": 2019,
                    "description": "Complete redesign with longer wheelbase. Featured updated engines and improved technology. Turbo, GT3, and GT2 RS variants were track-focused.",
                },
                {
                    "generation_name": "992",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Latest 911 with updated styling and technology. Featured updated engines and improved performance. Turbo, GT3, and GT2 RS variants available.",
                },
            ],
        },
        {
            "model": "356",
            "generations": [
                {
                    "generation_name": "356",
                    "start_year": 1948,
                    "end_year": 1965,
                    "description": "Porsche's first production model. Rear-engine, air-cooled, lightweight chassis with elegant lines. Multiple versions (356 A, B, C) with incremental improvements. Extensively used in motorsports. Highly collectible due to rarity, historic significance, and classic styling. Foundation of Porsche's sports car heritage.",
                },
            ],
        },
        {
            "model": "914",
            "generations": [
                {
                    "generation_name": "914",
                    "start_year": 1969,
                    "end_year": 1976,
                    "description": "Joint project between VW and Porsche to build a mid-engine entry-level sports car. Available as 914/4 (flat-4) and rare 914/6 (flat-6 from 911T). Mid-engine balance, lightweight feel, affordable restoration parts. Growing classic value, especially for factory 914/6s. Popular with enthusiasts for modifications and track use.",
                },
            ],
        },
        {
            "model": "924",
            "generations": [
                {
                    "generation_name": "924",
                    "start_year": 1976,
                    "end_year": 1988,
                    "description": "Entry-level Porsche replacing the 914. Front-engine, rear transaxle layout provided nearly balanced weight distribution. Shared components with VW/Audi but developed by Porsche. Modest power in base models, stronger performance in Turbo and S variants. Enthusiasts appreciate its value, tuning potential, and as a gateway into classic Porsche ownership.",
                },
            ],
        },
        {
            "model": "944",
            "generations": [
                {
                    "generation_name": "944",
                    "start_year": 1982,
                    "end_year": 1991,
                    "description": "Built on 924 foundation but significantly enhanced. Wider body, stronger engine options, more balanced handling, better refinement. Wide support in parts and community. Hits the sweet spot between affordability, driver engagement, and classic Porsche traits. Very popular with enthusiasts for modifications, track days, and daily driving.",
                },
            ],
        },
        {
            "model": "928",
            "generations": [
                {
                    "generation_name": "928",
                    "start_year": 1977,
                    "end_year": 1995,
                    "description": "Grand Tourer with front-engine V8. Ambitious design aimed to eventually succeed the 911 as Porsche's flagship. Innovative features: aluminum engine block, proprietary passive rear-wheel steering (Weissach Axle), constant updates through its long run. GTS version particularly desirable with more power, luxury, and refinement. Enthusiasts love its blend of comfort and performance.",
                },
            ],
        },
        {
            "model": "968",
            "generations": [
                {
                    "generation_name": "968",
                    "start_year": 1991,
                    "end_year": 1995,
                    "description": "Final evolution of the front-engine water-cooled transaxle Porsche line. Powered by 3.0L four-cylinder with DOHC and VarioCam. Available as 6-speed manual or Tiptronic automatic. Club Sport (CS) version especially prized: lighter, sharper handling, more stripped-out for track fun. Highly sought after by enthusiasts.",
                },
            ],
        },
        {
            "model": "Boxster",
            "generations": [
                {
                    "generation_name": "986",
                    "start_year": 1996,
                    "end_year": 2004,
                    "description": "Porsche's mid-engine roadster. More affordable entry into Porsche ownership. Featured flat-6 engines and excellent balance. S variant offered more power. Popular with enthusiasts for modifications, track use, and open-top driving experience.",
                },
                {
                    "generation_name": "987",
                    "start_year": 2005,
                    "end_year": 2012,
                    "description": "Refined Boxster with updated styling and engines. Featured improved handling and technology. S and Spyder variants were high-performance. Popular generation with strong enthusiast following.",
                },
                {
                    "generation_name": "981",
                    "start_year": 2013,
                    "end_year": 2016,
                    "description": "Complete redesign with updated styling and technology. Featured updated engines and improved performance. GTS and Spyder variants were track-focused. Last generation before 718 rebranding.",
                },
            ],
        },
        {
            "model": "Cayman",
            "generations": [
                {
                    "generation_name": "987",
                    "start_year": 2006,
                    "end_year": 2012,
                    "description": "Porsche's mid-engine coupe based on Boxster platform. Fixed roof provided better structural rigidity and handling. Featured flat-6 engines and excellent balance. S variant offered more power. Popular with enthusiasts for track use and modifications.",
                },
                {
                    "generation_name": "981",
                    "start_year": 2013,
                    "end_year": 2016,
                    "description": "Refined Cayman with updated styling and engines. Featured improved handling and technology. S, GTS, and GT4 variants were high-performance. Popular generation with strong enthusiast following. Last generation before 718 rebranding.",
                },
            ],
        },
        {
            "model": "718",
            "generations": [
                {
                    "generation_name": "982",
                    "start_year": 2016,
                    "end_year": 2024,
                    "description": "Rebranded Boxster and Cayman as 718 series. Initially featured turbocharged flat-4 engines (controversial among purists). Later reintroduced flat-6 in GTS 4.0, GT4, and Spyder variants. Excellent balance, modern safety and tech amenities. Boxster Spyder and Cayman GT4 deliver high-performance thrills. Record sales as buyers wanted last gas-powered versions before electrification.",
                },
            ],
        },
        {
            "model": "Cayenne",
            "generations": [
                {
                    "generation_name": "9PA",
                    "start_year": 2003,
                    "end_year": 2010,
                    "description": "Porsche's first SUV. Featured V6 and V8 engines. Turbo variant was high-performance. Combined practicality with Porsche performance. Popular with enthusiasts for modifications including ECU tuning, exhaust upgrades, and suspension work.",
                },
                {
                    "generation_name": "92A",
                    "start_year": 2011,
                    "end_year": 2017,
                    "description": "Refined Cayenne with updated styling and engines. Featured improved technology and performance. Turbo and Turbo S variants were extremely powerful. Popular with enthusiasts for modifications and performance upgrades.",
                },
                {
                    "generation_name": "PO536",
                    "start_year": 2018,
                    "end_year": 2023,
                    "description": "Complete redesign with updated styling and technology. Featured updated engines and improved performance. Turbo and Turbo S E-Hybrid variants were extremely powerful. Popular with enthusiasts for modifications and luxury features.",
                },
                {
                    "generation_name": "PO536 (Facelift)",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Updated Cayenne with refreshed styling and technology. Turbo E-Hybrid produces 729 hp and 700 lb-ft torque. 0-60 mph in 3.5 seconds. Top speed around 183 mph. Popular with enthusiasts for modifications and performance enhancements.",
                },
            ],
        },
        {
            "model": "Macan",
            "generations": [
                {
                    "generation_name": "95B",
                    "start_year": 2014,
                    "end_year": 2023,
                    "description": "Porsche's compact SUV. Featured turbocharged V6 engines. Turbo variant produced 434 hp with excellent performance. GTS variant was sporty. Popular with enthusiasts for modifications including ECU tuning, exhaust upgrades, and suspension work.",
                },
                {
                    "generation_name": "PO536 (Electric)",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Electric Macan with dual-motor all-wheel-drive. Turbo variant produces 630 hp with Launch Control and 833 lb-ft torque. 0-60 mph in 3.3 seconds. Top speed 162 mph. Popular for software tuning, suspension modifications, and performance enhancements.",
                },
            ],
        },
        {
            "model": "Panamera",
            "generations": [
                {
                    "generation_name": "970",
                    "start_year": 2010,
                    "end_year": 2016,
                    "description": "Porsche's luxury sedan. Featured V6 and V8 engines. Turbo and Turbo S variants were extremely powerful. Combined luxury with Porsche performance. Popular with enthusiasts for modifications and performance upgrades.",
                },
                {
                    "generation_name": "971",
                    "start_year": 2017,
                    "end_year": 2023,
                    "description": "Refined Panamera with updated styling and engines. Featured improved technology and performance. Turbo and Turbo S E-Hybrid variants were extremely powerful. Popular with enthusiasts for modifications and luxury features.",
                },
                {
                    "generation_name": "971 (Facelift)",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Updated Panamera with refreshed styling and technology. Turbo S E-Hybrid produces 771 hp. 0-60 mph in less than 3 seconds with Sport Chrono. Top speed 202 mph. Popular with enthusiasts for modifications and performance enhancements.",
                },
            ],
        },
        {
            "model": "Taycan",
            "generations": [
                {
                    "generation_name": "J1",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Porsche's first all-electric sedan. Featured dual-motor all-wheel-drive system. Turbo variant produces 871 hp, Turbo S produces 938 hp, Turbo GT produces 1,019 hp. 0-60 mph in 2.2-2.5 seconds. Top speed up to 190 mph with Weissach package. Popular for software tuning, suspension modifications, and performance enhancements. Represents the future of Porsche performance.",
                },
            ],
        },
        {
            "model": "959",
            "generations": [
                {
                    "generation_name": "959",
                    "start_year": 1986,
                    "end_year": 1993,
                    "description": "Porsche's legendary supercar. Featured twin-turbocharged flat-6 engine producing 450-530 hp. All-wheel drive with advanced technology. Built for Group B homologation. Extremely rare and highly collectible. Considered one of the greatest supercars of all time.",
                },
            ],
        },
        {
            "model": "Carrera GT",
            "generations": [
                {
                    "generation_name": "Carrera GT",
                    "start_year": 2004,
                    "end_year": 2007,
                    "description": "Porsche's mid-engine supercar. Featured 5.7L V10 engine producing 612 hp. Carbon fiber construction and advanced technology. Extremely rare and highly collectible. Considered one of the greatest supercars of the 2000s. Popular with collectors and enthusiasts.",
                },
            ],
        },
        {
            "model": "918 Spyder",
            "generations": [
                {
                    "generation_name": "918 Spyder",
                    "start_year": 2014,
                    "end_year": 2015,
                    "description": "Porsche's hybrid hypercar. Featured 4.6L V8 engine combined with electric motors producing 887 hp total. All-wheel drive with advanced hybrid technology. 0-60 mph in 2.5 seconds. Top speed 211 mph. Extremely rare and highly collectible. Part of the 'Holy Trinity' with McLaren P1 and Ferrari LaFerrari.",
                },
            ],
        },
    ],
    "Hyundai": [
        {
            "model": "Tiburon",
            "generations": [
                {
                    "generation_name": "RD1",
                    "start_year": 1997,
                    "end_year": 1999,
                    "description": "Hyundai's sporty front-wheel-drive coupe. Featured 1.6L, 1.8L, and 2.0L inline-4 engines. Popular for its affordable entry into the sport coupe segment. Good aftermarket support for modifications.",
                },
                {
                    "generation_name": "RD2",
                    "start_year": 2000,
                    "end_year": 2001,
                    "description": "Facelifted first generation Tiburon with updated styling. Featured improved engines and refreshed interior. Popular for modifications and affordable sporty driving.",
                },
                {
                    "generation_name": "GK",
                    "start_year": 2003,
                    "end_year": 2008,
                    "description": "Complete redesign with larger size and optional 2.7L V6 engine. Featured improved styling and performance. Popular for engine swaps, turbo kits, suspension upgrades, and body modifications. Strong enthusiast following.",
                },
            ],
        },
        {
            "model": "Genesis Coupe",
            "generations": [
                {
                    "generation_name": "BK",
                    "start_year": 2009,
                    "end_year": 2012,
                    "description": "Hyundai's rear-wheel-drive sports coupe. Featured turbocharged 4-cylinder and V6 engines. Popular for its value and performance potential.",
                },
                {
                    "generation_name": "BK2",
                    "start_year": 2013,
                    "end_year": 2016,
                    "description": "Refined Genesis Coupe with updated styling and engines. Featured improved turbocharged 4-cylinder and V6 engines. Better handling and performance.",
                },
            ],
        },
        {
            "model": "Elantra",
            "generations": [
                {
                    "generation_name": "XD",
                    "start_year": 2000,
                    "end_year": 2006,
                    "description": "Hyundai's compact sedan with efficient engines. Featured good value and reliability. Popular for its affordability.",
                },
                {
                    "generation_name": "HD",
                    "start_year": 2007,
                    "end_year": 2010,
                    "description": "Refined Elantra with updated styling and engines. Featured improved fuel economy and technology. Better value proposition.",
                },
                {
                    "generation_name": "MD",
                    "start_year": 2011,
                    "end_year": 2015,
                    "description": "Complete redesign with updated styling. Featured updated engines and improved fuel economy. More modern and refined.",
                },
                {
                    "generation_name": "AD",
                    "start_year": 2016,
                    "end_year": 2020,
                    "description": "Latest Elantra with updated styling and technology. Featured updated engines and improved fuel economy. More premium positioning.",
                },
                {
                    "generation_name": "CN7",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Newest Elantra with updated design and technology. Featured updated engines and advanced safety features. More modern and efficient.",
                },
            ],
        },
        {
            "model": "Elantra N",
            "generations": [
                {
                    "generation_name": "CN7",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Hyundai's high-performance sedan under the N sub-brand. Featured 2.0L turbocharged inline-4 producing 276 horsepower and 289 lb-ft torque. Available with 6-speed manual or 8-speed dual-clutch transmission. Includes electronic limited-slip differential, variable exhaust, and launch control. Popular for ECU tuning, exhaust upgrades, suspension modifications, and track-focused builds. Strong aftermarket support.",
                },
            ],
        },
        {
            "model": "Veloster",
            "generations": [
                {
                    "generation_name": "FS",
                    "start_year": 2011,
                    "end_year": 2017,
                    "description": "Hyundai's unique 3-door compact car. Featured efficient engines and distinctive styling. Turbo variant was sporty.",
                },
                {
                    "generation_name": "JS",
                    "start_year": 2018,
                    "end_year": 2022,
                    "description": "Refined Veloster with updated styling and engines. Featured turbocharged engine option. N variant was high-performance hot hatch.",
                },
            ],
        },
        {
            "model": "Kona N",
            "generations": [
                {
                    "generation_name": "OS",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Hyundai's high-performance compact SUV under the N sub-brand. Featured 2.0L turbocharged inline-4 producing 290 horsepower with N Grin Shift boost mode. 8-speed dual-clutch transmission with front-wheel drive. Popular for ECU tuning, exhaust upgrades, suspension modifications, and performance enhancements. Unique in being a performance-oriented SUV with strong enthusiast appeal.",
                },
            ],
        },
        {
            "model": "Ioniq 5 N",
            "generations": [
                {
                    "generation_name": "NE",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Hyundai's first electric performance vehicle under the N sub-brand. Featured dual-motor all-wheel-drive system producing 601 horsepower (641 hp with N Grin Boost). 84 kWh battery with 350 kW DC fast charging. 0-60 mph in 3.4 seconds. Popular for software tuning, suspension modifications, and performance enhancements. Represents the future of Hyundai N performance with electric powertrain.",
                },
            ],
        },
    ],
    "Kia": [
        {
            "model": "Stinger",
            "generations": [
                {
                    "generation_name": "CK",
                    "start_year": 2018,
                    "end_year": 2023,
                    "description": "Kia's flagship rear-wheel-drive sports sedan. Featured turbocharged 2.0L 4-cylinder and twin-turbo 3.3L V6 engines. GT trim produced up to 365-368 horsepower with optional all-wheel drive. 0-60 mph in 4.6-4.9 seconds. Featured Brembo brakes, performance tires, electronically-controlled suspension, and limited-slip differential. Excellent value and performance. Very popular with enthusiasts for modifications including ECU tuning, exhaust upgrades, suspension work, and forced induction enhancements.",
                },
            ],
        },
        {
            "model": "Forte GT",
            "generations": [
                {
                    "generation_name": "BD",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Performance variant of the Forte compact sedan. Featured 1.6L turbocharged 4-cylinder engine producing 201 horsepower and 195 lb-ft torque. Available with 6-speed manual or 7-speed dual-clutch automatic transmission. 0-60 mph in approximately 6.7 seconds. Sport-tuned suspension and aggressive styling. Popular with enthusiasts for modifications including ECU tuning, intake/exhaust upgrades, and suspension enhancements. Excellent value for performance-oriented compact sedan.",
                },
            ],
        },
        {
            "model": "Optima SX",
            "generations": [
                {
                    "generation_name": "TF",
                    "start_year": 2011,
                    "end_year": 2015,
                    "description": "High-performance trim of Kia's midsize sedan. Featured 2.0L turbocharged 4-cylinder engine producing 274 horsepower. Sport-tuned suspension and aggressive styling. Available with manual or automatic transmission. Popular with enthusiasts for modifications including ECU tuning, intake/exhaust upgrades, turbo upgrades, and suspension work. Excellent value for turbocharged midsize sedan performance.",
                },
                {
                    "generation_name": "JF",
                    "start_year": 2016,
                    "end_year": 2020,
                    "description": "Updated Optima SX with refined styling and improved technology. Featured 2.0L turbocharged 4-cylinder engine producing 245 horsepower. Sport-tuned suspension, premium interior features, and aggressive exterior styling. SXL trim added luxury features. Popular with enthusiasts for modifications including ECU tuning, exhaust upgrades, and suspension enhancements. Last generation before rebranding to K5.",
                },
            ],
        },
        {
            "model": "K5 GT",
            "generations": [
                {
                    "generation_name": "DL3",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Kia's midsize sports sedan, replacing the Optima. GT trim featured 2.5L turbocharged 4-cylinder engine producing 290 horsepower and 311 lb-ft torque. Front-wheel drive with 8-speed wet dual-clutch automatic transmission. 0-60 mph in approximately 5.7-5.8 seconds. Sport-tuned suspension, aggressive styling with fastback profile, and modern technology. Popular with enthusiasts for modifications including ECU tuning, exhaust upgrades, and suspension work. Excellent value and performance in midsize sedan segment.",
                },
            ],
        },
        {
            "model": "EV6 GT",
            "generations": [
                {
                    "generation_name": "CV",
                    "start_year": 2022,
                    "end_year": 2024,
                    "description": "Kia's flagship electric performance crossover. Featured dual-motor all-wheel-drive system producing 577 horsepower (576 hp in some markets). 77.4 kWh battery with 350 kW DC fast charging. 0-60 mph in 3.4 seconds. Featured GT mode, drift mode, performance tires, enhanced brakes, and electronic differential. Popular for software tuning, suspension modifications, and performance enhancements. Represents Kia's entry into high-performance electric vehicles.",
                },
                {
                    "generation_name": "CV1",
                    "start_year": 2024,
                    "end_year": 2025,
                    "description": "Facelifted EV6 GT with updated styling and enhanced performance. Featured dual-motor all-wheel-drive system producing 601 horsepower (641 hp with GT Boost mode). 84.0 kWh battery with improved range and 350 kW DC fast charging. 0-60 mph in 3.4 seconds. Added Virtual Gear Shift technology, updated interior, and refined exterior styling. Popular for software tuning, suspension modifications, and performance enhancements. Kia's most powerful production vehicle.",
                },
            ],
        },
    ],
    "Infiniti": [
        {
            "model": "FX35",
            "generations": [
                {
                    "generation_name": "S50",
                    "start_year": 2003,
                    "end_year": 2008,
                    "description": "Infiniti's sporty crossover SUV. Featured V6 engines and available all-wheel drive. Popular for its car-like handling and performance. Strong enthusiast following for modifications including ECU tuning, exhaust upgrades, and suspension enhancements.",
                },
            ],
        },
        {
            "model": "FX45",
            "generations": [
                {
                    "generation_name": "S50",
                    "start_year": 2003,
                    "end_year": 2008,
                    "description": "High-performance variant of FX35 with 4.5L V8 engine producing 315 horsepower. Sporty crossover with excellent acceleration and handling. Very popular with enthusiasts for modifications including ECU tuning, exhaust, and brake upgrades.",
                },
            ],
        },
        {
            "model": "FX50",
            "generations": [
                {
                    "generation_name": "S51",
                    "start_year": 2009,
                    "end_year": 2013,
                    "description": "Updated FX with 5.0L V8 engine producing 390 horsepower. Featured improved styling and technology. Sporty crossover with excellent performance. Popular for modifications including ECU tuning, exhaust upgrades, and suspension work.",
                },
            ],
        },
        {
            "model": "G20",
            "generations": [
                {
                    "generation_name": "P10",
                    "start_year": 1991,
                    "end_year": 1996,
                    "description": "Infiniti's compact sedan based on Nissan Primera. Featured SR20DE 4-cylinder engine. Popular with tuners for modifications including ECU tuning, intake/exhaust upgrades, and suspension work. Manual transmission available.",
                },
                {
                    "generation_name": "P11",
                    "start_year": 1997,
                    "end_year": 2002,
                    "description": "Updated G20 with refined styling and improved engines. Featured SR20DE engine with better power output. Continued popularity with enthusiasts for modifications. Manual transmission available.",
                },
            ],
        },
        {
            "model": "G35",
            "generations": [
                {
                    "generation_name": "V35",
                    "start_year": 2002,
                    "end_year": 2007,
                    "description": "Infiniti's compact executive sedan and coupe. Featured V6 engines and rear-wheel drive. Popular for its value and performance. G35 coupe was sporty.",
                },
            ],
        },
        {
            "model": "G37",
            "generations": [
                {
                    "generation_name": "V36",
                    "start_year": 2007,
                    "end_year": 2013,
                    "description": "Refined G35 successor with updated styling and engines. Featured V6 engines producing up to 330 horsepower. Coupe and sedan variants. Popular among enthusiasts.",
                },
            ],
        },
        {
            "model": "I30",
            "generations": [
                {
                    "generation_name": "A32",
                    "start_year": 1996,
                    "end_year": 2001,
                    "description": "Infiniti's compact sedan based on Nissan Maxima. Featured VG30DE V6 engine producing 190-227 horsepower. Popular for modifications including suspension upgrades, exhaust, and ECU tuning. Good value for performance.",
                },
            ],
        },
        {
            "model": "I35",
            "generations": [
                {
                    "generation_name": "A33",
                    "start_year": 2002,
                    "end_year": 2004,
                    "description": "Updated I30 with refined styling and improved V6 engine producing 255 horsepower. Based on Nissan Maxima platform. Popular for modifications and good value proposition.",
                },
            ],
        },
        {
            "model": "J30",
            "generations": [
                {
                    "generation_name": "J30",
                    "start_year": 1993,
                    "end_year": 1997,
                    "description": "Infiniti's mid-size luxury sedan. Featured VG30DE V6 engine. Unique styling and luxury features. Less common but has enthusiast following for modifications.",
                },
            ],
        },
        {
            "model": "M30",
            "generations": [
                {
                    "generation_name": "M30",
                    "start_year": 1990,
                    "end_year": 1992,
                    "description": "Infiniti's luxury coupe and convertible. Featured VG30DE V6 engine. Rare and collectible, especially the convertible variant. Enthusiast-focused model.",
                },
            ],
        },
        {
            "model": "M35",
            "generations": [
                {
                    "generation_name": "Y50",
                    "start_year": 2006,
                    "end_year": 2010,
                    "description": "Infiniti's mid-size luxury sedan with V6 engine. Featured 3.5L V6 producing 275-303 horsepower. Popular for modifications including ECU tuning, exhaust upgrades, and suspension work. Good balance of luxury and performance.",
                },
            ],
        },
        {
            "model": "M37",
            "generations": [
                {
                    "generation_name": "Y51",
                    "start_year": 2011,
                    "end_year": 2013,
                    "description": "Updated M35 with 3.7L V6 engine producing 330 horsepower. Refined styling and improved technology. Popular with enthusiasts for modifications and performance upgrades.",
                },
            ],
        },
        {
            "model": "M45",
            "generations": [
                {
                    "generation_name": "Y34",
                    "start_year": 2003,
                    "end_year": 2004,
                    "description": "High-performance M sedan with 4.5L V8 engine producing 340 horsepower. Sporty variant with excellent acceleration. Popular with enthusiasts for modifications including ECU tuning and exhaust upgrades.",
                },
                {
                    "generation_name": "Y50",
                    "start_year": 2006,
                    "end_year": 2010,
                    "description": "Updated M45 with 4.5L V8 engine producing 325 horsepower. Featured improved styling and technology. Very popular with enthusiasts for V8 performance and modification potential.",
                },
            ],
        },
        {
            "model": "M56",
            "generations": [
                {
                    "generation_name": "Y51",
                    "start_year": 2011,
                    "end_year": 2013,
                    "description": "High-performance M sedan with 5.6L V8 engine producing 420 horsepower. Ultimate performance variant with excellent acceleration. Very popular with enthusiasts for modifications and track use.",
                },
            ],
        },
        {
            "model": "Q45",
            "generations": [
                {
                    "generation_name": "FY33",
                    "start_year": 1990,
                    "end_year": 1996,
                    "description": "Infiniti's original flagship sedan. Featured 4.5L V8 engine (VH45DE) producing 278 horsepower. Highly popular with enthusiasts for modifications including ECU tuning, supercharger kits, suspension upgrades, and brake improvements. Strong aftermarket support.",
                },
                {
                    "generation_name": "Y33",
                    "start_year": 1997,
                    "end_year": 2001,
                    "description": "Updated Q45 with refined styling and improved V8 engine. Featured 4.1L V8 producing 266 horsepower. Continued popularity with enthusiasts for modifications and luxury features.",
                },
                {
                    "generation_name": "F50",
                    "start_year": 2002,
                    "end_year": 2006,
                    "description": "Final Q45 generation with updated styling and 4.5L V8 engine producing 340 horsepower. Featured improved technology and performance. Popular with enthusiasts for modifications.",
                },
            ],
        },
        {
            "model": "Q50",
            "generations": [
                {
                    "generation_name": "V37",
                    "start_year": 2014,
                    "end_year": 2020,
                    "description": "Infiniti's compact executive sedan replacing G37. Featured V6 engines and improved technology. Red Sport variant was high-performance.",
                },
                {
                    "generation_name": "V37 (Facelift)",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Updated Q50 with refreshed styling and technology. Featured updated engines and improved fuel economy. More refined and efficient.",
                },
            ],
        },
        {
            "model": "Q60",
            "generations": [
                {
                    "generation_name": "V37",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "Infiniti's compact coupe replacing G37 coupe. Featured V6 engines and updated styling. Red Sport variant was high-performance.",
                },
            ],
        },
        {
            "model": "Q70",
            "generations": [
                {
                    "generation_name": "Y51",
                    "start_year": 2014,
                    "end_year": 2019,
                    "description": "Infiniti's full-size luxury sedan (renamed from M series). Featured V6 and V8 engines. Q70L was long-wheelbase variant. Popular with enthusiasts for modifications including ECU tuning, exhaust upgrades, and suspension work.",
                },
            ],
        },
        {
            "model": "QX70",
            "generations": [
                {
                    "generation_name": "S51",
                    "start_year": 2014,
                    "end_year": 2017,
                    "description": "Renamed FX series sporty crossover. Featured V6 and V8 engines. Maintained sporty character and performance. Popular with enthusiasts for modifications including ECU tuning, exhaust, and suspension upgrades.",
                },
            ],
        },
    ],
    "Genesis": [
        {
            "model": "G70",
            "generations": [
                {
                    "generation_name": "RG",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "Genesis' compact executive sedan. Featured turbocharged 4-cylinder (2.5T) and twin-turbo V6 (3.3T) engines producing up to 365 horsepower. Excellent value and performance with Brembo brakes and sport-tuned suspension. Competes with BMW 3 Series and Mercedes C-Class. Popular for modifications including exhaust upgrades, ECU tuning, and suspension enhancements.",
                },
            ],
        },
        {
            "model": "G80",
            "generations": [
                {
                    "generation_name": "DH",
                    "start_year": 2017,
                    "end_year": 2020,
                    "description": "Genesis' mid-size executive sedan. Featured V6 and V8 engines. Excellent value and luxury. Competes with BMW 5 Series and Mercedes E-Class.",
                },
                {
                    "generation_name": "RG3",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Redesigned G80 with updated styling and technology. Featured 2.5T turbo four-cylinder and 3.5T twin-turbo V6 engines producing up to 375 horsepower. Available in gas and electrified variants. Enhanced luxury and performance features.",
                },
            ],
        },
        {
            "model": "G90",
            "generations": [
                {
                    "generation_name": "HI",
                    "start_year": 2017,
                    "end_year": 2020,
                    "description": "Genesis' flagship luxury sedan. Featured 3.3L twin-turbo V6 and 5.0L V8 engines. Ultimate luxury and refinement. Competes with Mercedes S-Class and BMW 7 Series.",
                },
                {
                    "generation_name": "RS4",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Redesigned G90 flagship sedan with advanced technology and luxury. Featured 3.5T twin-turbo V6 and e-Supercharger hybrid variant producing up to 409 horsepower. Ultimate luxury with cutting-edge features and exceptional performance.",
                },
            ],
        },
        {
            "model": "GV70",
            "generations": [
                {
                    "generation_name": "JK1",
                    "start_year": 2020,
                    "end_year": 2024,
                    "description": "Genesis' compact luxury SUV. Featured 2.5T turbo four-cylinder and 3.5T twin-turbo V6 engines producing up to 375 horsepower. Sporty handling and performance in a luxury SUV package. Popular for enthusiasts seeking SUV practicality with sedan-like dynamics.",
                },
            ],
        },
        {
            "model": "GV80",
            "generations": [
                {
                    "generation_name": "JX1",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Genesis' mid-size luxury SUV. Featured 2.5T turbo four-cylinder and 3.5T twin-turbo V6 engines producing up to 375 horsepower. Available as standard SUV and coupe variant (JX1C). Excellent performance and luxury. Popular for modifications and enthusiast appeal.",
                },
            ],
        },
        {
            "model": "GV60",
            "generations": [
                {
                    "generation_name": "JW1",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Genesis' compact luxury electric SUV. Featured dual-motor AWD setup with Performance variant producing up to 483 horsepower and 516 lb-ft torque. Boost Mode enables 0-60 mph in 3.6 seconds. ~77-84 kWh battery with ~235-294 mile range. Fast charging capability. Popular among EV enthusiasts for performance and luxury.",
                },
            ],
        },
    ],
    "Lamborghini": [
        {
            "model": "Countach",
            "generations": [
                {
                    "generation_name": "LP400",
                    "start_year": 1974,
                    "end_year": 1978,
                    "description": "Iconic wedge-shaped supercar that defined Lamborghini design language. Featured 3.9L V12 producing 375 horsepower. Extremely low production numbers. Popular for restoration, period-correct modifications, exhaust upgrades, and maintaining classic aesthetics. Highly collectible and sought after by enthusiasts.",
                },
                {
                    "generation_name": "LP400S",
                    "start_year": 1978,
                    "end_year": 1982,
                    "description": "Updated Countach with wider tires and optional spoiler. Featured 3.9L V12 with improved handling. Popular for restoration projects, exhaust modifications, and period-correct styling. Iconic design with pop-up headlights and scissor doors.",
                },
                {
                    "generation_name": "LP500S / 5000QV",
                    "start_year": 1982,
                    "end_year": 1990,
                    "description": "Countach with 4.8L V12 (later 5.2L in QV) producing 455-455 horsepower. 25th Anniversary edition featured updated styling. Popular for exhaust upgrades, restoration, body kit modifications, and maintaining the iconic wedge design. Strong enthusiast community and moderate aftermarket support.",
                },
            ],
        },
        {
            "model": "Diablo",
            "generations": [
                {
                    "generation_name": "Diablo",
                    "start_year": 1990,
                    "end_year": 1999,
                    "description": "Countach successor with 5.7L V12 producing 492-530 horsepower. Available as coupe and Roadster. Popular for exhaust upgrades, intake modifications, carbon fiber trim, body kits, and performance tuning. Strong aftermarket support with specialist vendors offering restoration and upgrade parts.",
                },
                {
                    "generation_name": "VT / SV / SE30",
                    "start_year": 1993,
                    "end_year": 2001,
                    "description": "Diablo variants including VT (all-wheel drive), SV (sport version), and SE30 (limited edition). Featured 5.7L V12 with power ranging from 492-595 horsepower. Popular for exhaust systems, performance upgrades, carbon fiber components, and custom bodywork. Strong enthusiast following and aftermarket support.",
                },
            ],
        },
        {
            "model": "Murciélago",
            "generations": [
                {
                    "generation_name": "Murciélago",
                    "start_year": 2001,
                    "end_year": 2006,
                    "description": "Diablo successor with 6.2L V12 producing 580 horsepower. Available as coupe and Roadster. Popular for exhaust upgrades, intake modifications, aero body kits, carbon fiber components, and performance tuning. Good aftermarket support with custom shops offering specialized modifications.",
                },
                {
                    "generation_name": "LP640",
                    "start_year": 2006,
                    "end_year": 2010,
                    "description": "Updated Murciélago with 6.5L V12 producing 640 horsepower. SV (SuperVeloce) variant was track-focused with increased power. Popular for exhaust systems, performance upgrades, widebody conversions, and aero modifications. Strong enthusiast community and good aftermarket support.",
                },
            ],
        },
        {
            "model": "Gallardo",
            "generations": [
                {
                    "generation_name": "1st Gen",
                    "start_year": 2003,
                    "end_year": 2008,
                    "description": "Lamborghini's entry-level supercar with 5.0L V10 engine producing 493-520 horsepower. Over 14,000 units produced, making it highly accessible for modifications. Available as coupe and Spyder. Popular for exhaust upgrades, ECU tuning, aero modifications, and performance enhancements. Massive aftermarket support.",
                },
                {
                    "generation_name": "LP 560-4",
                    "start_year": 2008,
                    "end_year": 2013,
                    "description": "Updated Gallardo with LP 560-4 designation. Featured 5.2L V10 producing 552 horsepower. Improved performance and technology. Popular for modifications including exhaust, tuning, and aero upgrades. Superleggera variant was lightweight track-focused model.",
                },
            ],
        },
        {
            "model": "Huracán",
            "generations": [
                {
                    "generation_name": "LP 610-4",
                    "start_year": 2014,
                    "end_year": 2019,
                    "description": "Gallardo successor with 5.2L V10 producing 602 horsepower. Over 26,000 units produced, making it one of the most mod-friendly modern supercars. Available as coupe and Spyder. Popular for exhaust systems, ECU tuning, turbo upgrades, aero modifications, and widebody conversions. Extensive aftermarket support.",
                },
                {
                    "generation_name": "EVO",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Updated Huracán with improved technology and performance. Featured updated V10 engine and advanced all-wheel drive system. Performante variant with track-focused upgrades. Popular for modifications including exhaust, tuning, and performance enhancements.",
                },
            ],
        },
        {
            "model": "Aventador",
            "generations": [
                {
                    "generation_name": "LP 700-4",
                    "start_year": 2011,
                    "end_year": 2016,
                    "description": "Lamborghini's flagship V12 supercar with 6.5L engine producing 691 horsepower. Over 11,000 units produced. Available as coupe and Roadster. Popular for exhaust upgrades, ECU tuning, aero modifications, and performance enhancements. SV variant was track-focused with increased power.",
                },
                {
                    "generation_name": "S",
                    "start_year": 2017,
                    "end_year": 2022,
                    "description": "Updated Aventador with improved performance. Featured 6.5L V12 producing 730 horsepower. SVJ variant was extreme track-focused model. Popular for modifications including exhaust, tuning, and aero upgrades. Final naturally aspirated V12 Lamborghini before hybrid era.",
                },
            ],
        },
        {
            "model": "Urus",
            "generations": [
                {
                    "generation_name": "Urus",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Lamborghini's first SUV with 4.0L twin-turbo V8 producing 641-666 horsepower. Over 20,000 units produced, making it highly accessible for modifications. Popular for widebody kits, exhaust upgrades, ECU tuning (Stage 1/2), intake systems, aero modifications, and aggressive styling. Very high aftermarket support with numerous tuners offering comprehensive upgrade packages.",
                },
                {
                    "generation_name": "Performante",
                    "start_year": 2023,
                    "end_year": None,
                    "description": "Track-focused Urus variant with enhanced performance and aerodynamics. Featured improved V8 engine and advanced suspension. Popular for performance upgrades, exhaust systems, and further aero enhancements. Strong aftermarket support continues to grow.",
                },
            ],
        },
        {
            "model": "Revuelto",
            "generations": [
                {
                    "generation_name": "Revuelto",
                    "start_year": 2023,
                    "end_year": None,
                    "description": "Aventador successor with hybrid powertrain combining 6.5L V12 and three electric motors producing 1,001 horsepower. Flagship supercar representing Lamborghini's future. Aftermarket support emerging with OEM accessories, wheels, and trim options. Performance modifications limited due to hybrid complexity and warranty considerations, but growing enthusiast interest.",
                },
            ],
        },
    ],
    "Ferrari": [
        {
            "model": "308",
            "generations": [
                {
                    "generation_name": "308",
                    "start_year": 1975,
                    "end_year": 1985,
                    "description": "Iconic mid-engine V8 Ferrari that became a cultural symbol. Featured 2.9L V8 producing 240-255 horsepower. Available as GTB (coupe) and GTS (targa). Popular for exhaust upgrades, period-correct wheel modifications, interior refurbishment, and maintaining classic aesthetics. Strong enthusiast community and parts availability.",
                },
            ],
        },
        {
            "model": "328",
            "generations": [
                {
                    "generation_name": "328",
                    "start_year": 1985,
                    "end_year": 1989,
                    "description": "Evolution of the 308 with 3.2L V8 producing 270 horsepower. Available as GTB and GTS. Popular for exhaust upgrades, modern wheel fitments, suspension improvements, and interior modernization while preserving classic character. Beloved by enthusiasts for its analog driving experience.",
                },
            ],
        },
        {
            "model": "Testarossa",
            "generations": [
                {
                    "generation_name": "Testarossa",
                    "start_year": 1984,
                    "end_year": 1991,
                    "description": "Iconic flat-12 mid-engine supercar with 4.9L engine producing 390 horsepower. Famous for side strakes and pop-up headlights. Popular for exhaust upgrades, wheel modifications, interior refurbishment, and maintaining period-correct styling. Highly sought after by collectors and enthusiasts.",
                },
                {
                    "generation_name": "512 TR",
                    "start_year": 1991,
                    "end_year": 1994,
                    "description": "Updated Testarossa with improved 4.9L flat-12 producing 428 horsepower. Enhanced performance and refined styling. Popular for exhaust systems, suspension upgrades, and modern wheel fitments while preserving iconic design elements.",
                },
                {
                    "generation_name": "512M",
                    "start_year": 1994,
                    "end_year": 1996,
                    "description": "Final evolution of Testarossa with 4.9L flat-12 producing 440 horsepower. Featured fixed headlights and refined aerodynamics. Popular for exhaust upgrades, suspension improvements, and maintaining the classic Testarossa aesthetic with modern touches.",
                },
            ],
        },
        {
            "model": "348",
            "generations": [
                {
                    "generation_name": "348",
                    "start_year": 1989,
                    "end_year": 1995,
                    "description": "Entry-level mid-engine V8 Ferrari with 3.4L engine producing 300-320 horsepower. Available as TB (coupe), TS (targa), and Challenge track variant. Popular for exhaust upgrades, HID light conversions, suspension improvements, and twin-turbo kits for significant power gains. Strong aftermarket support.",
                },
            ],
        },
        {
            "model": "F355",
            "generations": [
                {
                    "generation_name": "F355",
                    "start_year": 1994,
                    "end_year": 1999,
                    "description": "Highly regarded mid-engine V8 with 3.5L engine producing 375-380 horsepower. Available as Berlinetta, GTS (targa), Spider, and Challenge Stradale. Famous for its exhaust note and F1 paddle-shift transmission. Popular for exhaust upgrades, intake modifications, suspension improvements, and Challenge Stradale-inspired styling. Strong enthusiast following.",
                },
            ],
        },
        {
            "model": "360",
            "generations": [
                {
                    "generation_name": "Modena",
                    "start_year": 1999,
                    "end_year": 2005,
                    "description": "Modern mid-engine V8 with 3.6L engine producing 400 horsepower. Available as coupe and Spider. Popular for twin-turbo kits (significant power gains), exhaust systems (Capristo, Fabspeed), ECU tuning, suspension upgrades, and carbon fiber aero. Strong aftermarket support with extensive modification options.",
                },
                {
                    "generation_name": "Challenge Stradale",
                    "start_year": 2003,
                    "end_year": 2005,
                    "description": "Track-focused variant of 360 with 3.6L V8 producing 425 horsepower. Lightweight construction with enhanced aerodynamics. Popular for exhaust upgrades, suspension tuning, and maintaining the Challenge Stradale's track-focused character.",
                },
            ],
        },
        {
            "model": "F430",
            "generations": [
                {
                    "generation_name": "F430",
                    "start_year": 2004,
                    "end_year": 2009,
                    "description": "Ferrari's V8 supercar with 4.3L naturally aspirated engine producing 483 horsepower. Available as coupe and Spider. Popular for exhaust upgrades, supercharger kits (Novitec Rosso), ECU tuning, aero modifications, and carbon fiber bodywork. Strong aftermarket support for modifications.",
                },
            ],
        },
        {
            "model": "458",
            "generations": [
                {
                    "generation_name": "Italia",
                    "start_year": 2009,
                    "end_year": 2015,
                    "description": "Ferrari's V8 supercar with 4.5L naturally aspirated engine producing 562 horsepower. Available as coupe, Spider, and Speciale track variant. Popular for exhaust upgrades, ECU tuning, aero modifications (including CTR-style kits), carbon fiber bodywork, and suspension upgrades. Highly mod-friendly with extensive aftermarket support.",
                },
            ],
        },
        {
            "model": "488",
            "generations": [
                {
                    "generation_name": "GTB",
                    "start_year": 2015,
                    "end_year": 2019,
                    "description": "Ferrari's turbocharged V8 supercar with 3.9L twin-turbo engine producing 661 horsepower. Available as coupe and Spider. Popular for turbo upgrades (Pure800, etc.), exhaust systems, ECU tuning, intake modifications, and aero enhancements. Pista variant was track-focused. Strong aftermarket support for forced induction modifications.",
                },
            ],
        },
        {
            "model": "F8",
            "generations": [
                {
                    "generation_name": "Tributo",
                    "start_year": 2019,
                    "end_year": 2023,
                    "description": "Ferrari's final V8 supercar before hybrid era. Featured 3.9L twin-turbo V8 producing 710 horsepower. Available as coupe and Spider. Popular for turbo upgrades, exhaust systems, ECU tuning, and aero modifications. Tributo and Pista variants offered increased performance. Strong aftermarket support for modifications.",
                },
            ],
        },
        {
            "model": "550",
            "generations": [
                {
                    "generation_name": "Maranello",
                    "start_year": 1996,
                    "end_year": 2001,
                    "description": "Front-engine V12 grand tourer with 5.5L engine producing 485 horsepower. Classic GT layout with excellent long-distance capability. Popular for ECU tuning (15-25 HP gains), exhaust upgrades (headers, H-pipes, Tubi mufflers), suspension improvements, and modern wheel fitments. Strong enthusiast community.",
                },
            ],
        },
        {
            "model": "575",
            "generations": [
                {
                    "generation_name": "Maranello",
                    "start_year": 2002,
                    "end_year": 2006,
                    "description": "Evolution of 550 with 5.7L V12 producing 515 horsepower. Featured F1 transmission option. Popular for ECU tuning, exhaust systems, suspension upgrades, brake improvements, and restomod projects. V12 heat management and cooling upgrades are essential for modifications.",
                },
            ],
        },
        {
            "model": "599",
            "generations": [
                {
                    "generation_name": "GTB Fiorano",
                    "start_year": 2006,
                    "end_year": 2012,
                    "description": "Front-engine V12 supercar with 6.0L engine producing 612-670 horsepower. Available as GTB and GTO track variant. Popular for exhaust upgrades, ECU tuning, intake modifications, suspension refinement, and aero enhancements. Strong aftermarket support from Novitec and others.",
                },
            ],
        },
        {
            "model": "F12",
            "generations": [
                {
                    "generation_name": "Berlinetta",
                    "start_year": 2012,
                    "end_year": 2017,
                    "description": "Front-engine V12 supercar with 6.3L engine producing 730 horsepower. Modern GT with exceptional performance. Popular for carbon aero kits, exhaust systems, ECU tuning (Novitec has 774 HP builds), suspension upgrades, and forged wheels. Strong aftermarket support.",
                },
            ],
        },
        {
            "model": "812",
            "generations": [
                {
                    "generation_name": "Superfast",
                    "start_year": 2017,
                    "end_year": 2023,
                    "description": "Front-engine V12 supercar with 6.5L naturally aspirated engine producing 789-830 horsepower. Final naturally aspirated V12 Ferrari. Popular for exhaust upgrades, ECU tuning, carbon aero enhancements, suspension improvements, and maintaining the V12's character. Strong enthusiast following.",
                },
            ],
        },
        {
            "model": "California",
            "generations": [
                {
                    "generation_name": "California",
                    "start_year": 2008,
                    "end_year": 2014,
                    "description": "Front-engine V8 grand tourer with 4.3L engine producing 453-483 horsepower. Retractable hardtop convertible. Popular for exhaust upgrades, ECU tuning, suspension improvements, and subtle aero modifications. Good aftermarket support for GT-focused modifications.",
                },
                {
                    "generation_name": "California T",
                    "start_year": 2014,
                    "end_year": 2017,
                    "description": "Turbocharged evolution with 3.9L twin-turbo V8 producing 552-560 horsepower. Improved performance and efficiency. Popular for turbo upgrades, exhaust systems, ECU tuning, and suspension modifications. Strong aftermarket support for forced induction tuning.",
                },
            ],
        },
        {
            "model": "Portofino",
            "generations": [
                {
                    "generation_name": "Portofino",
                    "start_year": 2017,
                    "end_year": 2021,
                    "description": "Front-engine V8 grand tourer with 3.9L twin-turbo engine producing 592 horsepower. Retractable hardtop convertible. Popular for exhaust upgrades (valved systems), ECU tuning, subtle aero enhancements, and interior luxury modifications. Modern tech with good modification potential.",
                },
                {
                    "generation_name": "Portofino M",
                    "start_year": 2021,
                    "end_year": 2023,
                    "description": "Updated Portofino with 3.9L twin-turbo V8 producing 612 horsepower. Enhanced performance and refined styling. Popular for exhaust systems, ECU tuning, and aero modifications. Warranty considerations apply to modifications.",
                },
            ],
        },
        {
            "model": "Roma",
            "generations": [
                {
                    "generation_name": "Roma",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Front-engine V8 grand tourer with 3.9L twin-turbo engine producing 612 horsepower. Elegant coupe design. Popular for exhaust upgrades, ECU tuning, subtle aero enhancements, and interior customization. Modern platform with good aftermarket support.",
                },
            ],
        },
        {
            "model": "FF",
            "generations": [
                {
                    "generation_name": "FF",
                    "start_year": 2011,
                    "end_year": 2016,
                    "description": "Front-engine V12 shooting brake with 6.3L engine producing 651 horsepower. Unique four-seat layout with all-wheel drive. Popular for exhaust upgrades, ECU tuning, and subtle modifications while preserving the FF's unique character. Niche but enthusiastic owner community.",
                },
            ],
        },
        {
            "model": "GTC4Lusso",
            "generations": [
                {
                    "generation_name": "GTC4Lusso",
                    "start_year": 2016,
                    "end_year": 2020,
                    "description": "Evolution of FF with 6.3L V12 producing 681 horsepower. Available as V12 and V8 turbo variants. Four-seat shooting brake with all-wheel drive. Popular for exhaust upgrades, ECU tuning, and maintaining the practical supercar character. Unique in the Ferrari lineup.",
                },
            ],
        },
        {
            "model": "296",
            "generations": [
                {
                    "generation_name": "GTB",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "Mid-engine V6 hybrid supercar with 3.0L twin-turbo V6 and electric motor producing 818-830 horsepower. Represents Ferrari's hybrid future. Popular for exhaust upgrades, ECU tuning (hybrid system considerations), and aero modifications. Growing aftermarket support as platform matures.",
                },
            ],
        },
        {
            "model": "SF90",
            "generations": [
                {
                    "generation_name": "Stradale",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Mid-engine V8 hybrid hypercar with 4.0L twin-turbo V8 and three electric motors producing 986-1000 horsepower. Extreme performance with hybrid technology. Popular for exhaust upgrades, ECU tuning (Novitec has 1100+ HP builds), aero modifications, and appearance packages. Strong aftermarket support from premium tuners.",
                },
            ],
        },
        {
            "model": "F40",
            "generations": [
                {
                    "generation_name": "F40",
                    "start_year": 1987,
                    "end_year": 1992,
                    "description": "Legendary mid-engine twin-turbo V8 hypercar with 2.9L engine producing 471-478 horsepower. Built to celebrate Ferrari's 40th anniversary. Iconic design and extreme performance. Modifications are rare due to collector value, but exhaust upgrades and suspension improvements are available. Highly sought after by collectors.",
                },
            ],
        },
        {
            "model": "F50",
            "generations": [
                {
                    "generation_name": "F50",
                    "start_year": 1995,
                    "end_year": 1997,
                    "description": "Mid-engine V12 hypercar with 4.7L naturally aspirated engine producing 513 horsepower. Limited production track-focused supercar. Modifications are extremely rare due to collector value and limited numbers. Exhaust upgrades and suspension tuning available from specialist tuners. Iconic collector's item.",
                },
            ],
        },
        {
            "model": "Enzo",
            "generations": [
                {
                    "generation_name": "Enzo",
                    "start_year": 2002,
                    "end_year": 2004,
                    "description": "Mid-engine V12 hypercar with 6.0L naturally aspirated engine producing 651 horsepower. Named after company founder. Limited production with extreme performance. Modifications are rare due to collector value, but exhaust upgrades and suspension improvements available from specialist tuners. Highly collectible.",
                },
            ],
        },
        {
            "model": "LaFerrari",
            "generations": [
                {
                    "generation_name": "LaFerrari",
                    "start_year": 2013,
                    "end_year": 2018,
                    "description": "Mid-engine V12 hybrid hypercar with 6.3L naturally aspirated V12 and electric motor producing 949-963 horsepower. Limited production hybrid hypercar. Modifications are extremely rare due to collector value and limited numbers. Exhaust upgrades and suspension tuning available from specialist tuners. Ultimate collector's Ferrari.",
                },
            ],
        },
    ],
    "McLaren": [
        {
            "model": "MP4-12C",
            "generations": [
                {
                    "generation_name": "MP4-12C / 12C",
                    "start_year": 2011,
                    "end_year": 2014,
                    "description": "McLaren's first modern road car with 3.8L twin-turbo V8 producing 592-616 horsepower. Available as coupe and Spider. Foundation for all modern McLarens. Popular for exhaust upgrades, ECU tuning, aero modifications, carbon fiber bodywork, and suspension upgrades. Good aftermarket support from specialist tuners.",
                },
            ],
        },
        {
            "model": "540C",
            "generations": [
                {
                    "generation_name": "540C",
                    "start_year": 2015,
                    "end_year": 2021,
                    "description": "McLaren's most affordable entry-level supercar with 3.8L twin-turbo V8 producing 533 horsepower. Part of Sports Series lineup. Popular for exhaust upgrades, ECU tuning, aero modifications, carbon fiber bodywork, and suspension upgrades. Good aftermarket support, though warranty concerns exist for modifications.",
                },
            ],
        },
        {
            "model": "570S",
            "generations": [
                {
                    "generation_name": "570S",
                    "start_year": 2015,
                    "end_year": 2021,
                    "description": "McLaren's entry-level supercar with 3.8L twin-turbo V8 producing 562 horsepower. Part of Sports Series lineup. Available as coupe and Spider. Popular for exhaust upgrades (NOVITEC), ECU tuning, aero modifications, carbon fiber bodywork, and suspension upgrades. Good aftermarket support, though warranty concerns exist for modifications.",
                },
            ],
        },
        {
            "model": "570GT",
            "generations": [
                {
                    "generation_name": "570GT",
                    "start_year": 2016,
                    "end_year": 2021,
                    "description": "McLaren's grand touring variant with 3.8L twin-turbo V8 producing 562 horsepower. Part of Sports Series. More comfort-oriented than 570S with softer suspension and better insulation. Popular for exhaust upgrades, ECU tuning, aero modifications, and carbon fiber bodywork. Good aftermarket support.",
                },
            ],
        },
        {
            "model": "600LT",
            "generations": [
                {
                    "generation_name": "600LT",
                    "start_year": 2018,
                    "end_year": 2020,
                    "description": "McLaren's Longtail track-focused variant with 3.8L twin-turbo V8 producing 592 horsepower. Part of Sports Series. Available as coupe and Spider. Lighter, more aggressive aero, and track-focused suspension. Popular for exhaust upgrades, ECU tuning, aero modifications, and weight reduction. Strong enthusiast following.",
                },
            ],
        },
        {
            "model": "620R",
            "generations": [
                {
                    "generation_name": "620R",
                    "start_year": 2019,
                    "end_year": 2020,
                    "description": "McLaren's highly track-focused, road-legal version with 3.8L twin-turbo V8 producing 610 horsepower. Part of Sports Series. Most extreme Sports Series variant with race car-derived components. Limited production. Modifications are rare but exhaust and suspension tuning available from specialist tuners.",
                },
            ],
        },
        {
            "model": "650S",
            "generations": [
                {
                    "generation_name": "650S",
                    "start_year": 2014,
                    "end_year": 2017,
                    "description": "McLaren's mid-range supercar with 3.8L twin-turbo V8 producing 641 horsepower. Part of Super Series. Available as coupe and Spider. Popular for exhaust upgrades, ECU tuning (FAB Design), aero modifications, carbon fiber bodywork, and performance enhancements. Good aftermarket support for modifications.",
                },
            ],
        },
        {
            "model": "675LT",
            "generations": [
                {
                    "generation_name": "675LT",
                    "start_year": 2015,
                    "end_year": 2017,
                    "description": "McLaren's Longtail limited-production variant with 3.8L twin-turbo V8 producing 666 horsepower. Part of Super Series. Available as coupe and Spider. Track-focused with aggressive aero, lighter weight, and enhanced performance. Popular for exhaust upgrades, ECU tuning, and aero modifications. Highly sought after by enthusiasts.",
                },
            ],
        },
        {
            "model": "720S",
            "generations": [
                {
                    "generation_name": "720S",
                    "start_year": 2017,
                    "end_year": 2024,
                    "description": "McLaren's flagship supercar with 4.0L twin-turbo V8 producing 710 horsepower. Part of Super Series. Available as coupe and Spider. Popular for exhaust upgrades, ECU tuning, aero modifications, carbon fiber bodywork (including full panel replacements for weight reduction), and performance enhancements. Extensive aftermarket support, though warranty concerns exist.",
                },
            ],
        },
        {
            "model": "765LT",
            "generations": [
                {
                    "generation_name": "765LT",
                    "start_year": 2020,
                    "end_year": 2022,
                    "description": "McLaren's Longtail limited-production variant with 4.0L twin-turbo V8 producing 755 horsepower. Part of Super Series. Available as coupe and Spider. Extremely track-focused with aggressive aero, lighter weight, and enhanced performance. Popular for exhaust upgrades, ECU tuning, and aero modifications. Highly sought after by enthusiasts.",
                },
            ],
        },
        {
            "model": "750S",
            "generations": [
                {
                    "generation_name": "750S",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "McLaren's evolution of the 720S with 4.0L twin-turbo V8 producing 740 horsepower. Part of Super Series. Available as coupe and Spider. Higher power, improved performance, and refined aerodynamics. Popular for exhaust upgrades, ECU tuning, aero modifications, and performance enhancements. Extensive aftermarket support.",
                },
            ],
        },
        {
            "model": "Artura",
            "generations": [
                {
                    "generation_name": "Artura",
                    "start_year": 2021,
                    "end_year": 2024,
                    "description": "McLaren's hybrid supercar with 3.0L twin-turbo V6 and electric motor producing 671 horsepower. First McLaren with V6 engine. Combines Sports and Super Series characteristics. Popular for exhaust upgrades, ECU tuning, aero modifications, and hybrid system optimization. Growing aftermarket support.",
                },
            ],
        },
        {
            "model": "P1",
            "generations": [
                {
                    "generation_name": "P1",
                    "start_year": 2013,
                    "end_year": 2015,
                    "description": "McLaren's hybrid hypercar with 3.8L twin-turbo V8 and electric motor producing 903 horsepower. Part of Ultimate Series. Limited production extreme performance machine. Modifications are extremely rare due to collector value and limited numbers. Exhaust upgrades and suspension tuning available from specialist tuners. Highly collectible.",
                },
            ],
        },
        {
            "model": "Senna",
            "generations": [
                {
                    "generation_name": "Senna",
                    "start_year": 2018,
                    "end_year": 2020,
                    "description": "McLaren's track-focused hypercar with 4.0L twin-turbo V8 producing 789 horsepower. Part of Ultimate Series. Named after Ayrton Senna. Limited production extreme track machine. Modifications are rare due to collector value, but exhaust upgrades and suspension tuning available from specialist tuners. Highly sought after by enthusiasts.",
                },
            ],
        },
        {
            "model": "Speedtail",
            "generations": [
                {
                    "generation_name": "Speedtail",
                    "start_year": 2018,
                    "end_year": 2020,
                    "description": "McLaren's hybrid hyper-GT with 4.0L twin-turbo V8 and electric motor producing 1035 horsepower. Part of Ultimate Series. Limited production extreme grand tourer focused on high-speed performance. Modifications are extremely rare due to collector value and limited numbers. Highly collectible.",
                },
            ],
        },
        {
            "model": "Elva",
            "generations": [
                {
                    "generation_name": "Elva",
                    "start_year": 2019,
                    "end_year": 2021,
                    "description": "McLaren's open-cockpit hypercar with 4.0L twin-turbo V8 producing 804 horsepower. Part of Ultimate Series. No windshield, focused on pure driving experience. Limited production. Modifications are extremely rare due to collector value and limited numbers. Highly collectible.",
                },
            ],
        },
    ],
    "Aston Martin": [
        {
            "model": "Vantage",
            "generations": [
                {
                    "generation_name": "V8 Vantage (Classic)",
                    "start_year": 1977,
                    "end_year": 1989,
                    "description": "Classic standalone V8 Vantage flagship with 5.3L naturally aspirated V8. Iconic William Towns design. Popular for engine rebuilds, suspension upgrades, and restoration modifications.",
                },
                {
                    "generation_name": "V8 Vantage",
                    "start_year": 2005,
                    "end_year": 2017,
                    "description": "Aston Martin's compact sports car with 4.3L-4.7L V8 engines. Available as coupe and Roadster. Popular for exhaust upgrades, ECU tuning (Monte Tuning), intake modifications, aero enhancements, and carbon fiber bodywork. Strong aftermarket support for modifications.",
                },
                {
                    "generation_name": "V12 Vantage",
                    "start_year": 2009,
                    "end_year": 2018,
                    "description": "High-performance Vantage with 5.9L naturally aspirated V12 producing 510-565 horsepower. Available as coupe and Roadster. Popular for exhaust upgrades, ECU tuning, intake modifications, aero enhancements, and performance modifications. Highly sought after by enthusiasts.",
                },
                {
                    "generation_name": "Vantage",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "New generation Vantage with 4.0L twin-turbo V8 producing 503-535 horsepower. Available as coupe and Roadster. V12 version available in limited production (2022-2023). Popular for exhaust upgrades, ECU tuning, aero modifications, and performance enhancements. Good aftermarket support.",
                },
            ],
        },
        {
            "model": "DB5",
            "generations": [
                {
                    "generation_name": "DB5",
                    "start_year": 1963,
                    "end_year": 1965,
                    "description": "Iconic grand tourer with 4.0L inline-6 engine. Made famous by James Bond films. Available as coupe, convertible (Volante), and shooting brake. Highly collectible with strong restoration and modification community.",
                },
            ],
        },
        {
            "model": "DB6",
            "generations": [
                {
                    "generation_name": "DB6",
                    "start_year": 1965,
                    "end_year": 1970,
                    "description": "Evolution of the DB5 with improved aerodynamics and longer wheelbase. 4.0L inline-6 engine. Available as coupe, Volante, and shooting brake. Classic collector car with restoration and modification support.",
                },
            ],
        },
        {
            "model": "DB7",
            "generations": [
                {
                    "generation_name": "DB7",
                    "start_year": 1994,
                    "end_year": 2004,
                    "description": "Modern grand tourer with supercharged 3.2L inline-6 (Vantage) or 5.9L V12 engines. Available as coupe and Volante. Popular for exhaust upgrades, supercharger modifications, ECU tuning, and suspension improvements. Strong aftermarket support.",
                },
            ],
        },
        {
            "model": "DB9",
            "generations": [
                {
                    "generation_name": "DB9",
                    "start_year": 2004,
                    "end_year": 2016,
                    "description": "Aston Martin's grand tourer with 5.9L V12 engine producing 470-510 horsepower. Available as coupe and Volante. Popular for exhaust upgrades, ECU tuning, intake modifications, aero enhancements (V-Collection, Mansory), carbon fiber bodywork, and luxury customization. Strong aftermarket support for modifications.",
                },
            ],
        },
        {
            "model": "DB11",
            "generations": [
                {
                    "generation_name": "DB11",
                    "start_year": 2016,
                    "end_year": 2023,
                    "description": "Grand tourer with 5.2L twin-turbo V12 (600-630 hp) or 4.0L twin-turbo V8 (510 hp) engines. Available as coupe and Volante. Popular for exhaust upgrades, ECU tuning, intake modifications, aero enhancements, and luxury customization. Good aftermarket support.",
                },
            ],
        },
        {
            "model": "DB12",
            "generations": [
                {
                    "generation_name": "DB12",
                    "start_year": 2023,
                    "end_year": 2024,
                    "description": "Current flagship 'Super Tourer' with 5.2L twin-turbo V12 producing 671 horsepower. Available as coupe and Volante. DB12 S offers higher performance. Popular for exhaust upgrades, ECU tuning, and luxury customization. Growing aftermarket support.",
                },
            ],
        },
        {
            "model": "DBS",
            "generations": [
                {
                    "generation_name": "DBS (Classic)",
                    "start_year": 1967,
                    "end_year": 1972,
                    "description": "Original DBS fastback GT with 4.0L inline-6 or 5.3L V8 engines. Iconic William Towns design. Available as coupe. Classic collector car with restoration and modification support.",
                },
                {
                    "generation_name": "DBS",
                    "start_year": 2007,
                    "end_year": 2012,
                    "description": "Flagship grand tourer with 5.9L V12 producing 510-517 horsepower. Available as coupe and Volante. Popular for exhaust upgrades, ECU tuning, intake modifications, aero enhancements, and luxury customization. Strong aftermarket support.",
                },
                {
                    "generation_name": "DBS Superleggera",
                    "start_year": 2018,
                    "end_year": 2024,
                    "description": "Flagship super GT with 5.2L twin-turbo V12 producing 715 horsepower. Available as coupe and Volante. Advanced aerodynamics and carbon fiber construction. Popular for exhaust upgrades, ECU tuning, and performance modifications. Good aftermarket support.",
                },
            ],
        },
        {
            "model": "Vanquish",
            "generations": [
                {
                    "generation_name": "Vanquish",
                    "start_year": 2001,
                    "end_year": 2007,
                    "description": "Original flagship with 5.9L V12 producing 460-520 horsepower. Available as coupe. Popular for exhaust upgrades, ECU tuning, intake modifications, and suspension improvements. Strong aftermarket support.",
                },
                {
                    "generation_name": "Vanquish",
                    "start_year": 2012,
                    "end_year": 2018,
                    "description": "VH-platform Vanquish with 5.9L V12 producing 565-600 horsepower. Available as coupe and Volante. Vanquish S variant available. Popular for exhaust upgrades, ECU tuning, aero enhancements, and luxury customization. Strong aftermarket support.",
                },
                {
                    "generation_name": "Vanquish",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Revived flagship with new twin-turbo V12 engine. Replaces DBS Superleggera as top model. Available as coupe and Volante. Popular for exhaust upgrades, ECU tuning, and performance modifications. Growing aftermarket support.",
                },
            ],
        },
        {
            "model": "Rapide",
            "generations": [
                {
                    "generation_name": "Rapide",
                    "start_year": 2010,
                    "end_year": 2020,
                    "description": "Four-door sport sedan grand tourer with 5.9L V12 producing 470-552 horsepower. Available as Rapide and Rapide S. Popular for exhaust upgrades, ECU tuning, intake modifications, and luxury customization. Moderate aftermarket support.",
                },
            ],
        },
        {
            "model": "One-77",
            "generations": [
                {
                    "generation_name": "One-77",
                    "start_year": 2009,
                    "end_year": 2012,
                    "description": "Ultra-exclusive limited production (77 units) hypercar with 7.3L naturally aspirated V12 producing 750 horsepower. Hand-built, extremely rare. Minimal aftermarket modifications due to exclusivity and value.",
                },
            ],
        },
        {
            "model": "Valkyrie",
            "generations": [
                {
                    "generation_name": "Valkyrie",
                    "start_year": 2019,
                    "end_year": 2024,
                    "description": "Ultra-exclusive hypercar with 6.5L naturally aspirated V12 hybrid powertrain producing over 1,000 horsepower. Available as Coupe, Spider, AMR Pro, and LM racing variants. Extremely limited production. Minimal aftermarket modifications due to exclusivity.",
                },
            ],
        },
        {
            "model": "Valhalla",
            "generations": [
                {
                    "generation_name": "Valhalla",
                    "start_year": 2024,
                    "end_year": 2024,
                    "description": "Hybrid supercar with 4.0L twin-turbo V8 hybrid powertrain producing 998 horsepower. Mid-engine layout. Limited production. Popular for exhaust upgrades and performance modifications. Growing aftermarket support.",
                },
            ],
        },
    ],
}


def get_all_car_generations() -> list[dict[str, str | int | None]]:
    """
    Flatten the nested car generations structure into a flat list.

    Returns:
        List of dictionaries with make, model, generation_name, start_year, end_year, and optionally description
    """
    generations: list[dict[str, str | int | None]] = []
    for make, models in CAR_GENERATIONS.items():
        for model_data in models:
            model = model_data["model"]
            for gen in model_data["generations"]:
                gen_dict = {
                    "make": make,
                    "model": model,
                    "generation_name": gen["generation_name"],
                    "start_year": gen["start_year"],
                    "end_year": gen["end_year"],
                }
                if "description" in gen:
                    gen_dict["description"] = gen["description"]
                generations.append(gen_dict)
    return generations
