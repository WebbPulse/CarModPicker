"""The media domain's entrypoint, run as `python -m app.domains.media.entrypoint`.

Image upload and serving through S3: 9 routes under `/api/images`. Every
route verifies a token, so the domain needs `SECRET_KEY`.
"""

from webbpulse.composition import domain_entrypoint

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import build_domain_app, start_domain

DOMAIN = DOMAINS["media"]

build_app, main = domain_entrypoint(
    DOMAIN,
    build=lambda domain: build_domain_app(domain, title=domain.title),
    check=start_domain,
)


if __name__ == "__main__":
    main()
