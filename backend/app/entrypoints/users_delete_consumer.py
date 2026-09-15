"""Terraform-pinned module path for the users domain's account delete cascade consumer.

The implementation is `app.domains.users.consumers.delete_entrypoint`. This shim exists because
`terraform/lambda_stream_consumers.tf` pins the container command to
`python -m app.entrypoints.users_delete_consumer`, and Terraform is out of scope here.
"""

from app.domains.users.consumers.delete_entrypoint import (
    app,
    build_app,
    handle_batch,
    main,
    repositories,
)

__all__ = ["app", "build_app", "handle_batch", "main", "repositories"]


if __name__ == "__main__":
    main()
