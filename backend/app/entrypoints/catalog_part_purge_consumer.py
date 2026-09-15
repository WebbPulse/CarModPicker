"""Terraform-pinned module path for the catalog domain's part purge consumer.

The implementation is `app.domains.catalog.consumers.part_purge_entrypoint`. This shim exists because
`terraform/lambda_stream_consumers.tf` pins the container command to
`python -m app.entrypoints.catalog_part_purge_consumer`, and Terraform is out of scope here.
"""

from app.domains.catalog.consumers.part_purge_entrypoint import (
    app,
    build_app,
    handle_batch,
    main,
    repositories,
)

__all__ = ["app", "build_app", "handle_batch", "main", "repositories"]


if __name__ == "__main__":
    main()
