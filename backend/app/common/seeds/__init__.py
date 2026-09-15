"""Seed data and the reconcilers that load it into DynamoDB.

The car generation seeding is shared: the vehicles domain runs it on startup,
the admin domain exposes it as a db-ops endpoint, and `composition.wiring` runs
it for the composed app. It depends on `app.common` alone, so it lives here
rather than in any one domain.
"""
