"""The users domain's entrypoint, run as `python -m app.domains.users.entrypoint`.

User accounts, the app settings singleton and Stripe billing: routes under
`/api/users`, `/api/app-settings` and `/api/billing`. Verifies identity access
tokens, and reads the Stripe keys from the application secret.
"""

from webbpulse.composition import domain_entrypoint

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import build_domain_app, start_domain

DOMAIN = DOMAINS["users"]

build_app, main = domain_entrypoint(
    DOMAIN,
    build=lambda domain: build_domain_app(domain, title=domain.title),
    check=start_domain,
)


if __name__ == "__main__":
    main()
