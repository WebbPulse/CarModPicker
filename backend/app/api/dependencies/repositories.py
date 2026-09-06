from dataclasses import dataclass

from app.db.dynamo.build_lists import (
    BuildListLaborEstimateRepository,
    BuildListPartRepository,
    BuildListPhaseRepository,
    BuildListRepository,
)
from app.db.dynamo.catalog import (
    CarGenerationRepository,
    CarMakeRepository,
    CarModelRepository,
    CategoryRepository,
    PartCarRepository,
    PartListingRepository,
    PartManufacturerRepository,
    PartPriceHistoryRepository,
    PartRepository,
    RetailerRepository,
)
from app.db.dynamo.users import OAuthAccountRepository, UserRepository, WebAuthnCredentialRepository


@dataclass(frozen=True)
class Repositories:
    users: UserRepository
    oauth_accounts: OAuthAccountRepository
    webauthn_credentials: WebAuthnCredentialRepository
    car_makes: CarMakeRepository
    car_models: CarModelRepository
    car_generations: CarGenerationRepository
    categories: CategoryRepository
    part_manufacturers: PartManufacturerRepository
    retailers: RetailerRepository
    parts: PartRepository
    part_cars: PartCarRepository
    part_listings: PartListingRepository
    part_price_history: PartPriceHistoryRepository
    build_lists: BuildListRepository
    build_list_parts: BuildListPartRepository
    build_list_phases: BuildListPhaseRepository
    build_list_labor_estimates: BuildListLaborEstimateRepository


_repositories = Repositories(
    users=UserRepository(),
    oauth_accounts=OAuthAccountRepository(),
    webauthn_credentials=WebAuthnCredentialRepository(),
    car_makes=CarMakeRepository(),
    car_models=CarModelRepository(),
    car_generations=CarGenerationRepository(),
    categories=CategoryRepository(),
    part_manufacturers=PartManufacturerRepository(),
    retailers=RetailerRepository(),
    parts=PartRepository(),
    part_cars=PartCarRepository(),
    part_listings=PartListingRepository(),
    part_price_history=PartPriceHistoryRepository(),
    build_lists=BuildListRepository(),
    build_list_parts=BuildListPartRepository(),
    build_list_phases=BuildListPhaseRepository(),
    build_list_labor_estimates=BuildListLaborEstimateRepository(),
)


def get_repositories() -> Repositories:
    return _repositories
