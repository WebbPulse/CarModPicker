"""The build-logs domain's entrypoint, run as `python -m app.domains.build_logs.entrypoint`.

Forum-style build log threads and their posts: 5 routes under
`/api/build-logs`. Verifies identity access tokens, so it needs no
application secret.
"""

from webbpulse.composition import domain_entrypoint

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import build_domain_app, start_domain

DOMAIN = DOMAINS["build-logs"]

build_app, main = domain_entrypoint(
    DOMAIN,
    build=lambda domain: build_domain_app(domain, title=domain.title),
    check=start_domain,
)


if __name__ == "__main__":
    main()
