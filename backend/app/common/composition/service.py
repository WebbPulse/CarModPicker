"""The service name template every domain row renders, and the OpenAPI version.

Its own module because `domains.py` stamps the template onto each row and
`wiring.py` reads both, and importing either from the other would be a cycle.
This module imports nothing of the product, so a registry import stays free.
"""

from __future__ import annotations

SERVICE_NAME_TEMPLATE = "carmodpicker-{domain}"
"""What each row renders its `service_name` with, and what Terraform sets as `SERVICE_NAME`."""

OPENAPI_VERSION = "0.1.0"
"""Pinned so `create_app` publishes the version the OpenAPI snapshot records."""
