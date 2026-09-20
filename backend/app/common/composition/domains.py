"""The nine domains of the split, as descriptors carrying their routers.

Importing this module imports no endpoint module: each loader does its own
imports in its body, which is what keeps one domain's image free of the rest.

The descriptor and the registry are `webbpulse.composition`'s; the rows, the
loaders and the repository lists are this product's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Sequence, Tuple

from webbpulse.composition import Domain, DomainRegistry

from app.common.composition.service import SERVICE_NAME_TEMPLATE
from app.common.core.config import settings

API_PREFIX = settings.API_STR
"""Every domain row mounts its routers under this, which the package does not default."""

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import APIRouter

RouterSpec = Tuple["APIRouter", str, Tuple[str, ...]]


def _identity_routers() -> "Sequence[RouterSpec]":
    """No routers of its own since row 13. The package's router is all of `/api/auth`."""
    return []


def _identity_unprefixed_routers(settings: "Any") -> "Sequence[APIRouter]":
    """The shared package's identity router and the extension handoff router.

    Both carry the issuer's own path, so they mount with no prefix; a prefix
    would double every path to `/api/auth/api/auth/...`. Empty when
    `IDENTITY_ISSUER` is unset, so a deployment without an issuer builds none
    of the glue's AWS clients.
    """
    if not settings.IDENTITY_ISSUER:
        return []

    from app.domains.identity.extension import build_router as build_extension_router
    from app.domains.identity.package_glue import build_router as build_identity_router

    return [build_identity_router(settings), build_extension_router(settings)]


def _users_routers() -> "Sequence[RouterSpec]":
    """The user account router and the app settings singleton router."""
    from app.domains.users.endpoints import app_settings, users

    return [
        (users.router, "/users", ("users",)),
        (app_settings.router, "/app-settings", ("app-settings",)),
    ]


def _catalog_routers() -> "Sequence[RouterSpec]":
    """Parts, categories, manufacturers and retailers."""
    from app.domains.catalog.endpoints import categories, part_manufacturers, parts, retailers

    return [
        (parts.router, "/parts", ("parts",)),
        (categories.router, "/categories", ("categories",)),
        (part_manufacturers.router, "/part-manufacturers", ("part_manufacturers",)),
        (retailers.router, "/retailers", ("retailers",)),
    ]


def _vehicles_routers() -> "Sequence[RouterSpec]":
    """Car generations and the unified search."""
    from app.domains.vehicles.endpoints import car_generations, search

    return [
        (car_generations.router, "/car-generations", ("car-generations",)),
        (search.router, "/search", ("search",)),
    ]


def _build_lists_routers() -> "Sequence[RouterSpec]":
    """Build lists and their parts, phases and labor estimates."""
    from app.domains.build_lists.endpoints import (
        build_list_labor_estimates,
        build_list_parts,
        build_list_phases,
        build_lists,
    )

    return [
        (build_lists.router, "/build-lists", ("build-lists",)),
        (build_list_parts.router, "/build-list-parts", ("build-list-parts",)),
        (build_list_phases.router, "/build-list-phases", ("build-list-phases",)),
        (
            build_list_labor_estimates.router,
            "/build-list-labor-estimates",
            ("build-list-labor-estimates",),
        ),
    ]


def _build_logs_routers() -> "Sequence[RouterSpec]":
    """The build log threads and posts router."""
    from app.domains.build_logs.endpoints import build_logs

    return [(build_logs.router, "/build-logs", ("build-logs",))]


def _moderation_routers() -> "Sequence[RouterSpec]":
    """Votes, reports and bug reports."""
    from app.domains.moderation.endpoints import bug_reports, reports, votes

    return [
        (votes.router, "/votes", ("votes",)),
        (reports.router, "/reports", ("reports",)),
        (bug_reports.router, "/bug-reports", ("bug-reports",)),
    ]


def _media_routers() -> "Sequence[RouterSpec]":
    """The image upload and serving router."""
    from app.domains.media.endpoints import images

    return [(images.router, "/images", ("images",))]


def _admin_routers() -> "Sequence[RouterSpec]":
    """Price alerts, crawled pages and the two admin routers."""
    from app.domains.admin.endpoints import crawled_pages, part_price_alerts
    from app.domains.admin.endpoints import db_ops as admin_db_ops
    from app.domains.admin.endpoints import stats as admin_stats

    return [
        (part_price_alerts.router, "/part-price-alerts", ("part-price-alerts",)),
        (crawled_pages.router, "/crawled-pages", ("crawled-pages",)),
        (admin_stats.router, "/admin/stats", ("admin",)),
        (admin_db_ops.router, "/admin/db-ops", ("admin",)),
    ]


_IDENTITY_REPOSITORIES = ("users", "oauth_accounts", "webauthn_credentials")

_USERS_REPOSITORIES = (
    "users",
    "app_settings",
    "oauth_accounts",
)

_CATALOG_REPOSITORIES = (
    "users",
    "car_makes",
    "car_models",
    "car_generations",
    "categories",
    "part_manufacturers",
    "retailers",
    "parts",
    "part_cars",
    "part_listings",
    "part_price_history",
    "votes",
)

_VEHICLES_REPOSITORIES = _CATALOG_REPOSITORIES + ("build_lists",)

_BUILD_LISTS_REPOSITORIES = (
    "users",
    "car_makes",
    "car_models",
    "car_generations",
    "categories",
    "part_manufacturers",
    "retailers",
    "parts",
    "part_cars",
    "part_listings",
    "part_price_history",
    "build_lists",
    "build_list_parts",
    "build_list_phases",
    "build_list_labor_estimates",
    "build_logs",
    "build_log_posts",
    "votes",
)

_BUILD_LOGS_REPOSITORIES = ("users", "build_lists", "build_logs", "build_log_posts")

_MODERATION_REPOSITORIES = (
    "users",
    "car_makes",
    "car_models",
    "car_generations",
    "parts",
    "build_lists",
    "votes",
    "reports",
    "bug_reports",
)

_MEDIA_REPOSITORIES = (
    "users",
    "car_generations",
    "parts",
    "build_lists",
    "image_source_mappings",
)

_ADMIN_REPOSITORIES = (
    "users",
    "oauth_accounts",
    "webauthn_credentials",
    "car_makes",
    "car_models",
    "car_generations",
    "categories",
    "part_manufacturers",
    "retailers",
    "parts",
    "part_cars",
    "part_listings",
    "part_price_history",
    "part_price_alerts",
    "build_lists",
    "build_list_phases",
    "build_logs",
    "votes",
    "reports",
    "image_source_mappings",
)


_ROWS: Dict[str, Domain] = {
    "identity": Domain(
        name="identity",
        service_name_template=SERVICE_NAME_TEMPLATE,
        router_prefix=API_PREFIX,
        title="CarModPicker identity",
        load_routers=_identity_routers,
        load_unprefixed_routers=_identity_unprefixed_routers,
        repositories=_IDENTITY_REPOSITORIES,
    ),
    "users": Domain(
        name="users",
        service_name_template=SERVICE_NAME_TEMPLATE,
        router_prefix=API_PREFIX,
        title="CarModPicker users",
        load_routers=_users_routers,
        repositories=_USERS_REPOSITORIES,
    ),
    "catalog": Domain(
        name="catalog",
        service_name_template=SERVICE_NAME_TEMPLATE,
        router_prefix=API_PREFIX,
        title="CarModPicker catalog",
        load_routers=_catalog_routers,
        repositories=_CATALOG_REPOSITORIES,
    ),
    "vehicles": Domain(
        name="vehicles",
        service_name_template=SERVICE_NAME_TEMPLATE,
        router_prefix=API_PREFIX,
        title="CarModPicker vehicles",
        load_routers=_vehicles_routers,
        repositories=_VEHICLES_REPOSITORIES,
    ),
    "build-lists": Domain(
        name="build-lists",
        service_name_template=SERVICE_NAME_TEMPLATE,
        router_prefix=API_PREFIX,
        title="CarModPicker build lists",
        load_routers=_build_lists_routers,
        repositories=_BUILD_LISTS_REPOSITORIES,
    ),
    "build-logs": Domain(
        name="build-logs",
        service_name_template=SERVICE_NAME_TEMPLATE,
        router_prefix=API_PREFIX,
        title="CarModPicker build logs",
        load_routers=_build_logs_routers,
        repositories=_BUILD_LOGS_REPOSITORIES,
    ),
    "moderation": Domain(
        name="moderation",
        service_name_template=SERVICE_NAME_TEMPLATE,
        router_prefix=API_PREFIX,
        title="CarModPicker moderation",
        load_routers=_moderation_routers,
        repositories=_MODERATION_REPOSITORIES,
    ),
    "media": Domain(
        name="media",
        service_name_template=SERVICE_NAME_TEMPLATE,
        router_prefix=API_PREFIX,
        title="CarModPicker media",
        load_routers=_media_routers,
        repositories=_MEDIA_REPOSITORIES,
    ),
    "admin": Domain(
        name="admin",
        service_name_template=SERVICE_NAME_TEMPLATE,
        router_prefix=API_PREFIX,
        title="CarModPicker admin",
        load_routers=_admin_routers,
        repositories=_ADMIN_REPOSITORIES,
        requires_secrets=("SECRET_KEY",),
    ),
}

DOMAINS = DomainRegistry(_ROWS)
"""The ordered, immutable registry both composition roots and every entrypoint read."""

DOMAIN_NAMES: Tuple[str, ...] = DOMAINS.names

ENTRYPOINT_MODULES: Dict[str, str] = DOMAINS.entrypoint_modules

SEEDING_DOMAINS: FrozenSet[str] = frozenset({"vehicles"})
"""Domains whose application runs the car generation seeder on first request.

A product concern rather than a registry field: only a root serving one of these
wires the lifespan hook, so a function with read-only IAM on the car tables never
attempts the write.
"""
