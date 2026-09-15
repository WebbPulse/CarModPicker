"""Compatibility shims for the four stream consumer module paths Terraform pins.

`terraform/lambda_stream_consumers.tf` sets each consumer's container command to
`python -m app.entrypoints.<name>`. Those four names live on here so the move to
`app/domains/<name>/consumers/` needs no Terraform change. Each shim re-exports
its domain module's `app` and `main` and holds no logic of its own.
"""
