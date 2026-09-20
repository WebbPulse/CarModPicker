"""The identity domain's entrypoint, run as `python -m app.domains.identity.entrypoint`.

Login, refresh, email verification, password reset, TOTP, WebAuthn and Google
OAuth under `/api/auth`, all served by the `webbpulse.identity` package. Tokens
are RS256 signed in KMS, so it holds no `SECRET_KEY`.
"""

from webbpulse.composition import domain_entrypoint

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import build_domain_app, start_domain

DOMAIN = DOMAINS["identity"]

build_app, main = domain_entrypoint(
    DOMAIN,
    build=lambda domain: build_domain_app(domain, title=domain.title),
    check=start_domain,
)


if __name__ == "__main__":
    main()
