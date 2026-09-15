"""Non-domain logic every domain may depend on.

Nothing here imports `app.domains` at module level, so importing `app.common`
costs no domain package. The lazy per-domain loaders are the one exception, and
`tests/common/test_domain_boundaries.py` holds them to it.
"""
