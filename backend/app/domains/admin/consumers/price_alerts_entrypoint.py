"""The admin domain's `part_listings` stream consumer for price drop alerts.

Sends alert mail through SES and signs the unsubscribe link, so unlike the votes
consumer it needs `SECRET_KEY`.
"""

from typing import Any, Dict, List, Mapping

from fastapi import FastAPI

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import check_signing_key, configure_logging, configure_tracing

DOMAIN = DOMAINS["admin"]

SERVICE_NAME = f"{DOMAIN.service_name}-price-alerts-consumer"

_repos: Any = None


def repositories() -> Any:
    """The `admin` bundle, memoised for the life of the execution environment."""
    global _repos
    if _repos is None:
        from app.common.composition.wiring import bundle_for

        _repos = bundle_for([DOMAIN])
    return _repos


def handle_batch(event: Mapping[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """Evaluate price alerts for every record this batch touched."""
    from app.domains.admin.consumers.price_alerts import handle

    return handle(event, repositories())


def build_app() -> FastAPI:
    """The consumer's application: shared consumer scaffolding over the batch handler."""
    from webbpulse.events import stream_consumer_app

    return stream_consumer_app(
        handle_batch,
        title=f"{DOMAIN.title} price alerts stream consumer",
        per_record=False,
        service_name=SERVICE_NAME,
    )


def main() -> None:
    """Process-wide setup, then serve. Not run by importing this module."""
    from webbpulse.lambda_entry import run_uvicorn

    configure_logging(service=SERVICE_NAME)

    check_signing_key([DOMAIN])

    configure_tracing(DOMAIN)

    run_uvicorn(build_app())


app = build_app()


if __name__ == "__main__":
    main()
