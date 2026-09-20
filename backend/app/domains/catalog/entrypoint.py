"""The catalog domain's entrypoint, run as `python -m app.domains.catalog.entrypoint`.

Parts, manufacturers, categories and retailers: 43 routes, the largest
domain. Verifies identity access tokens, and keeps the app secret only for
the `EXTENSION_API_KEY` that `POST /api/parts/price-history` checks.
"""

from webbpulse.composition import domain_entrypoint

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import build_domain_app, start_domain

DOMAIN = DOMAINS["catalog"]

build_app, main = domain_entrypoint(
    DOMAIN,
    build=lambda domain: build_domain_app(domain, title=domain.title),
    check=start_domain,
)


if __name__ == "__main__":
    main()
