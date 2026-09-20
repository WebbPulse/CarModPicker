"""The vehicles domain's entrypoint, run as `python -m app.domains.vehicles.entrypoint`.

Car makes, models and generations plus the unified search: 11 routes. Every
route is a public read, so this is the one domain that needs no secret.
"""

from webbpulse.composition import domain_entrypoint

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import build_domain_app, start_domain

DOMAIN = DOMAINS["vehicles"]

build_app, main = domain_entrypoint(
    DOMAIN,
    build=lambda domain: build_domain_app(domain, title=domain.title),
    check=start_domain,
)


if __name__ == "__main__":
    main()
