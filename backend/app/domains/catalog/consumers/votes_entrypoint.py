"""The catalog domain's `votes` stream consumer.

A FastAPI app because the base image's Lambda Web Adapter is the runtime and POSTs
non-HTTP events to `AWS_LWA_PASS_THROUGH_PATH`.
"""

from typing import Any, Dict, List, Mapping

from fastapi import FastAPI

from app.common.composition.domains import DOMAINS
from app.common.composition.wiring import configure_logging, configure_tracing

DOMAIN = DOMAINS["catalog"]

SERVICE_NAME = f"{DOMAIN.service_name}-votes-consumer"

_repos: Any = None


def repositories() -> Any:
    """The `catalog` bundle, memoised for the life of the execution environment."""
    global _repos
    if _repos is None:
        from app.common.composition.wiring import bundle_for

        _repos = bundle_for([DOMAIN])
    return _repos


def handle_batch(event: Mapping[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """Recompute `parts.net_votes` for every record this batch touched."""
    from app.domains.catalog.consumers.votes import handle

    return handle(event, repositories())


def build_app() -> FastAPI:
    """The consumer's application: shared consumer scaffolding over the batch handler."""
    from webbpulse.events import stream_consumer_app

    return stream_consumer_app(
        handle_batch,
        title=f"{DOMAIN.title} votes stream consumer",
        per_record=False,
        service_name=SERVICE_NAME,
    )


def main() -> None:
    """Process-wide setup, then serve. Not run by importing this module."""
    from webbpulse.lambda_entry import run_uvicorn

    configure_logging(service=SERVICE_NAME)
    configure_tracing(DOMAIN)

    run_uvicorn(build_app())


app = build_app()


if __name__ == "__main__":
    main()
