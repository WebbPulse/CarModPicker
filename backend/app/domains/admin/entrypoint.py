"""The admin domain's entrypoint, run as `python -m app.domains.admin.entrypoint`.

Price-drop alerts, the Chrome extension page parser and the two admin
modules: 12 routes. Keeps `SECRET_KEY` for the one route that reads an
emailed HS256 unsubscribe token.
"""

from webbpulse.composition import domain_entrypoint

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import build_domain_app, start_domain

DOMAIN = DOMAINS["admin"]

build_app, main = domain_entrypoint(
    DOMAIN,
    build=lambda domain: build_domain_app(domain, title=domain.title),
    check=start_domain,
)


if __name__ == "__main__":
    main()
