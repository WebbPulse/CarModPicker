"""The moderation domain's entrypoint, run as `python -m app.domains.moderation.entrypoint`.

Votes, reports and bug reports: 20 routes, polymorphic over `entity_type` so
this one domain serves moderation for every other. Needs `SECRET_KEY`.
"""

from webbpulse.composition import domain_entrypoint

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import build_domain_app, start_domain

DOMAIN = DOMAINS["moderation"]

build_app, main = domain_entrypoint(
    DOMAIN,
    build=lambda domain: build_domain_app(domain, title=domain.title),
    check=start_domain,
)


if __name__ == "__main__":
    main()
