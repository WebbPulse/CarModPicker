"""Terraform-pinned module path for the admin domain's price alerts consumer.

The implementation is `app.domains.admin.consumers.price_alerts_entrypoint`. This shim exists because
`terraform/lambda_stream_consumers.tf` pins the container command to
`python -m app.entrypoints.admin_price_alerts_consumer`, and Terraform is out of scope here.
"""

from app.domains.admin.consumers.price_alerts_entrypoint import (
    app,
    build_app,
    handle_batch,
    main,
    repositories,
)

__all__ = ["app", "build_app", "handle_batch", "main", "repositories"]


if __name__ == "__main__":
    main()
