"""The build-lists domain's entrypoint, run as `python -m app.domains.build_lists.entrypoint`.

Build lists and their parts, phases and labor estimates: 34 routes.
Verifies identity access tokens, so it needs no application secret.
"""

from webbpulse.composition import domain_entrypoint

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import build_domain_app, start_domain

DOMAIN = DOMAINS["build-lists"]

build_app, main = domain_entrypoint(
    DOMAIN,
    build=lambda domain: build_domain_app(domain, title=domain.title),
    check=start_domain,
)


if __name__ == "__main__":
    main()
