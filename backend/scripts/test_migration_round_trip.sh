#!/usr/bin/env bash
# Phase 4 DATA-09 / D-31: Alembic upgrade -> downgrade -> upgrade round-trip.
#
# Usage:
#   ./scripts/test_migration_round_trip.sh <revision_id|head>
#
# REVISION is REQUIRED (INFO 13). Pass a specific revision hash or literal
# `head`. Silent defaulting is disabled to force explicit intent.
#
# Prerequisites:
#   - A local test Postgres is running. Two common options:
#       (a) docker compose -f docker-compose.test.yml up -d postgres-test
#           (port 5433, added by plan 04-05 — per-worker test DB)
#       (b) backend/docker-compose.yml (dev Postgres at 5432)
#   - DATABASE_URL points at the local test Postgres for alembic.
#   - Run from the backend/ directory (alembic.ini lives there).
#
# Exits non-zero if any alembic step fails. The reviewer-gated convention is
# documented in .planning/codebase/CONVENTIONS.md ("Alembic downgrade testing").
#
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <revision_id|head>" >&2
  echo "" >&2
  echo "REVISION is REQUIRED. Examples:" >&2
  echo "  $0 head" >&2
  echo "  $0 274bde4f4654" >&2
  echo "" >&2
  echo "Prerequisites:" >&2
  echo "  - DATABASE_URL env var points at a LOCAL test Postgres." >&2
  echo "  - Run from backend/ (alembic.ini lives there)." >&2
  exit 1
fi

REVISION="$1"

echo "==> Running migration round-trip test"
echo "    DATABASE_URL: ${DATABASE_URL:-<DATABASE_URL not set>}"
echo "    Revision:     $REVISION"

echo
echo "Step 1: alembic upgrade $REVISION"
alembic upgrade "$REVISION"

echo
echo "Step 2: alembic downgrade -1"
alembic downgrade -1

echo
echo "Step 3: alembic upgrade head"
alembic upgrade head

echo
echo "==> Round-trip successful."
