"""Pydantic schemas more than one domain reads or returns.

Deliberately re-exports nothing: importing one schema must not import the rest,
which is what keeps a domain's import closure proportional to its routes.
"""
