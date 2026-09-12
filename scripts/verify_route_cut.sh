#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/verify_route_cut.sh <env> <domain>

  env      staging | production
  domain   media | build-logs | moderation | vehicles | admin
           | build-lists | identity | catalog | users

Environment:
  CARMODPICKER_ORIGIN_VERIFY   origin-verify header value for the staging gate
  CARMODPICKER_GATE_COOKIE     Cookie header value, as an alternative
  CARMODPICKER_INVOKE_FALLBACK set to 1 to skip HTTP and invoke the function
  CARMODPICKER_API_BASE_URL    override the API base URL entirely
  CARMODPICKER_CURL_TIMEOUT    per request timeout in seconds (default 20)
  CARMODPICKER_RETRIES         attempts per path (default 5)
  CARMODPICKER_LOG_WAIT        seconds to wait for the access log (default 120)
USAGE
  exit 2
}

[ $# -eq 2 ] || usage

ENV_NAME=$1
DOMAIN=$2

case "$ENV_NAME" in
staging | production) ;;
*)
  echo "Unknown environment: $ENV_NAME" >&2
  usage
  ;;
esac

case "$DOMAIN" in
media)
  PREFIXES=(/api/images)
  ;;
build-logs)
  PREFIXES=(/api/build-logs)
  ;;
moderation)
  PREFIXES=(/api/votes /api/reports /api/bug-reports)
  ;;
vehicles)
  PREFIXES=(/api/car-generations /api/search)
  ;;
admin)
  PREFIXES=(/api/crawled-pages /api/part-price-alerts /api/admin/db-ops /api/admin/stats)
  ;;
build-lists)
  PREFIXES=(/api/build-lists /api/build-list-parts /api/build-list-phases /api/build-list-labor-estimates)
  ;;
identity)
  PREFIXES=(/api/auth)
  ;;
catalog)
  PREFIXES=(/api/parts /api/part-manufacturers /api/categories /api/retailers)
  ;;
users)
  PREFIXES=(/api/users /api/app-settings)
  ;;
*)
  echo "Unknown domain: $DOMAIN" >&2
  usage
  ;;
esac

if [ ${#PREFIXES[@]} -eq 0 ]; then
  echo "No path prefixes are defined for domain '$DOMAIN' yet." >&2
  echo "That cut has not landed; add its prefixes here when it does." >&2
  exit 2
fi

PREFIX_NAME=carmodpicker-${ENV_NAME}
ACCESS_LOG_GROUP=/aws/apigateway/${PREFIX_NAME}-api
FUNCTION_NAME=${PREFIX_NAME}-${DOMAIN}

if [ -n "${CARMODPICKER_API_BASE_URL:-}" ]; then
  BASE_URL=${CARMODPICKER_API_BASE_URL%/}
elif [ "$ENV_NAME" = "production" ]; then
  BASE_URL=https://api.carmodpicker.com
else
  BASE_URL=https://api.staging.carmodpicker.com
fi

TIMEOUT=${CARMODPICKER_CURL_TIMEOUT:-20}
RETRIES=${CARMODPICKER_RETRIES:-5}
LOG_WAIT=${CARMODPICKER_LOG_WAIT:-120}
AWS_REGION_ARG=${AWS_REGION:-us-west-2}

FAILURES=0
NOT_CUT=0

invoke_fallback() {
  echo "Direct invoke fallback: probing ${FUNCTION_NAME} without the gateway."
  echo

  local event response status failed=0
  event=$(mktemp)
  response=$(mktemp)
  trap 'rm -f "$event" "$response"' RETURN

  for prefix in "${PREFIXES[@]}"; do
    cat >"$event" <<JSON
{
  "version": "2.0",
  "routeKey": "ANY ${prefix}",
  "rawPath": "${prefix}",
  "rawQueryString": "",
  "headers": {
    "accept": "application/json",
    "host": "verify.invoke.local",
    "user-agent": "carmodpicker-verify-route-cut"
  },
  "requestContext": {
    "accountId": "anonymous",
    "apiId": "verify",
    "domainName": "verify.invoke.local",
    "http": {
      "method": "GET",
      "path": "${prefix}",
      "protocol": "HTTP/1.1",
      "sourceIp": "127.0.0.1",
      "userAgent": "carmodpicker-verify-route-cut"
    },
    "requestId": "verify",
    "routeKey": "ANY ${prefix}",
    "stage": "\$default",
    "time": "01/Jan/2026:00:00:00 +0000",
    "timeEpoch": 1767225600000
  },
  "isBase64Encoded": false
}
JSON

    aws lambda invoke \
      --function-name "$FUNCTION_NAME" \
      --region "$AWS_REGION_ARG" \
      --cli-binary-format raw-in-base64-out \
      --payload "file://$event" \
      --cli-read-timeout 60 \
      "$response" >/dev/null

    status=$(python3 -c '
import json, sys
try:
    payload = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    print("unparseable")
    sys.exit(0)
print(payload.get("statusCode", "missing") if isinstance(payload, dict) else "not-an-object")
' "$response")

    case "$status" in
    404 | missing | unparseable | not-an-object)
      echo "  ${prefix} -> ${FUNCTION_NAME} answered ${status}  FAIL"
      echo "        The function does not serve this path. The routes map"
      echo "        cannot fix that; the image or the entrypoint is wrong."
      failed=1
      ;;
    *)
      echo "  ${prefix} -> ${FUNCTION_NAME} answered ${status}  OK"
      ;;
    esac
  done

  echo
  if [ "$failed" -ne 0 ]; then
    echo "FAILED: ${FUNCTION_NAME} does not serve every '${DOMAIN}' prefix."
    return 1
  fi
  echo "WARNING: this ran without the gateway, so it did NOT verify the cut."
  echo "It proves ${FUNCTION_NAME} serves the '${DOMAIN}' prefixes and nothing"
  echo "more. Supply CARMODPICKER_ORIGIN_VERIFY or CARMODPICKER_GATE_COOKIE and"
  echo "run again to verify the routing."
  return 0
}

if [ "${CARMODPICKER_INVOKE_FALLBACK:-}" = "1" ]; then
  invoke_fallback
  exit $?
fi

GATE_ARGS=()
if [ -n "${CARMODPICKER_ORIGIN_VERIFY:-}" ]; then
  GATE_ARGS=(-H "x-origin-verify: ${CARMODPICKER_ORIGIN_VERIFY}")
  echo "Using the origin-verify header for the access gate."
elif [ -n "${CARMODPICKER_GATE_COOKIE:-}" ]; then
  GATE_ARGS=(-H "cookie: ${CARMODPICKER_GATE_COOKIE}")
  echo "Using the supplied gate cookie."
elif [ "$ENV_NAME" = "staging" ]; then
  echo "No CARMODPICKER_ORIGIN_VERIFY and no CARMODPICKER_GATE_COOKIE." >&2
  echo "Staging is behind the access gate, so every request below would be" >&2
  echo "answered by the gate with a 401 rather than by the API, and would" >&2
  echo "report as a failed cut that is really a missing credential." >&2
  echo "Falling back to a direct invoke of ${FUNCTION_NAME}." >&2
  echo >&2
  invoke_fallback
  exit $?
fi

echo "Verifying the '$DOMAIN' cut against $BASE_URL"
echo

MARKER="verify-${DOMAIN}-$(date +%s)-$$"

declare -a PROBE_PATHS=()
for prefix in "${PREFIXES[@]}"; do
  PROBE_PATHS+=("$prefix")
  PROBE_PATHS+=("${prefix}/verify-route-cut-probe")
done

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
APIGATEWAY_TF=${CARMODPICKER_APIGATEWAY_TF:-${REPO_ROOT}/terraform/apigateway.tf}
RESOLVER=${REPO_ROOT}/scripts/expected_route_key.py

expected_key() {
  local path=$1 resolved
  resolved=$(python3 "$RESOLVER" "$APIGATEWAY_TF" GET "$path" "${PREFIXES[@]}" 2>/dev/null) || resolved=""
  printf '%s' "$resolved"
}

if [ ! -r "$APIGATEWAY_TF" ]; then
  echo "Cannot read ${APIGATEWAY_TF}." >&2
  echo "The expected route key is derived from the declared route map, so a" >&2
  echo "missing file would silently weaken every assertion below." >&2
  exit 1
fi

START_EPOCH_MS=$(($(date +%s) * 1000 - 60000))

for path in "${PROBE_PATHS[@]}"; do
  url="${BASE_URL}${path}"
  code=000
  for attempt in $(seq 1 "$RETRIES"); do
    code=$(curl -sS --max-time "$TIMEOUT" -o /dev/null -w '%{http_code}' \
      -A "$MARKER" "${GATE_ARGS[@]}" "$url" 2>/dev/null || echo 000)
    case "$code" in
    5* | 000)
      [ "$attempt" -lt "$RETRIES" ] && sleep 5
      ;;
    *)
      break
      ;;
    esac
  done

  case "$code" in
  5* | 000)
    echo "  ${path} -> HTTP ${code}  FAIL"
    echo "        The API did not answer. A cut cannot be verified against a"
    echo "        gateway that is erroring; fix that first."
    FAILURES=$((FAILURES + 1))
    ;;
  *)
    echo "  ${path} -> HTTP ${code}, reached the API"
    ;;
  esac
done

echo
echo "Waiting up to ${LOG_WAIT}s for ${ACCESS_LOG_GROUP} to catch up."

FOUND_PATHS=$(mktemp)
trap 'rm -f "$FOUND_PATHS"' EXIT

DEADLINE=$(($(date +%s) + LOG_WAIT))
LOG_READ_OK=0
while :; do
  LOG_JSON=$(aws logs filter-log-events \
    --log-group-name "$ACCESS_LOG_GROUP" \
    --region "$AWS_REGION_ARG" \
    --start-time "$START_EPOCH_MS" \
    --filter-pattern "\"$MARKER\"" \
    --max-items 200 \
    --output json 2>/dev/null || echo '')

  if [ -n "$LOG_JSON" ]; then
    LOG_READ_OK=1
    printf '%s' "$LOG_JSON" | python3 -c '
import json, sys

try:
    events = json.load(sys.stdin).get("events", [])
except ValueError:
    sys.exit(0)
for event in events:
    try:
        entry = json.loads(event.get("message", ""))
    except ValueError:
        continue
    path = entry.get("path")
    key = entry.get("routeKey")
    if path is not None:
        print("%s\t%s" % (path, key))
' >>"$FOUND_PATHS" || {
      echo "Failed to parse the access log response." >&2
      exit 1
    }
  fi

  MISSING=0
  for path in "${PROBE_PATHS[@]}"; do
    if ! awk -F'\t' -v p="$path" '$1 == p { found = 1 } END { exit !found }' "$FOUND_PATHS"; then
      MISSING=$((MISSING + 1))
    fi
  done
  [ "$MISSING" -eq 0 ] && break

  NOW=$(date +%s)
  [ "$NOW" -ge "$DEADLINE" ] && break
  REMAINING=$((DEADLINE - NOW))
  sleep "$([ "$REMAINING" -lt 5 ] && echo "$REMAINING" || echo 5)"
done

echo

if [ "$LOG_READ_OK" -eq 0 ]; then
  echo "Could not read ${ACCESS_LOG_GROUP}."
  echo "  Either the credentials cannot read it, or the access log is not"
  echo "  being written. The routeKey check is the whole verification, so this"
  echo "  is a failure rather than a skip."
  exit 1
fi

ROUTE_KEYS=$(sort -u "$FOUND_PATHS")

for path in "${PROBE_PATHS[@]}"; do
  want=$(expected_key "$path")
  got=$(printf '%s\n' "$ROUTE_KEYS" | awk -F'\t' -v p="$path" '$1 == p { print $2 }' | tail -n1)

  if [ -z "$want" ]; then
    echo "  ${path} -> no declared route key matches  FAIL"
    echo "        Nothing in ${APIGATEWAY_TF} claims this path, so the probe"
    echo "        would 404 at the gateway. The prefix list in this script and"
    echo "        the route map have drifted apart."
    FAILURES=$((FAILURES + 1))
    continue
  fi

  if [ -z "$got" ]; then
    echo "  ${path} -> no access log entry after ${LOG_WAIT}s  FAIL"
    echo "        The request was not logged within the budget, so nothing can"
    echo "        be concluded about which integration served it. This is not"
    echo "        itself evidence of a bad route: the HTTP probe above reached"
    echo "        the API, and access log delivery is per stream and can lag."
    echo "        Raise CARMODPICKER_LOG_WAIT and run again before treating it"
    echo "        as a routing problem."
    FAILURES=$((FAILURES + 1))
    continue
  fi

  case "$got" in
  "$want")
    echo "  ${path} -> routeKey '${got}'  OK"
    ;;
  '$default')
    echo "  ${path} -> routeKey '\$default'  NOT CUT OVER"
    echo "        Matched the \$default route rather than '${want}'. That route"
    echo "        key did not land. Row 32 removed \$default entirely, so seeing"
    echo "        it here means this stage predates row 32."
    NOT_CUT=$((NOT_CUT + 1))
    ;;
  *)
    echo "  ${path} -> routeKey '${got}'  FAIL"
    echo "        Expected '${want}', derived from the route keys declared in"
    echo "        ${APIGATEWAY_TF}. The gateway and that file disagree, so"
    echo "        either an apply has not landed or a key was changed outside"
    echo "        Terraform."
    FAILURES=$((FAILURES + 1))
    ;;
  esac
done

echo

if [ "$ENV_NAME" = "staging" ] && [ ${#GATE_ARGS[@]} -gt 0 ]; then
  probe=${PROBE_PATHS[0]}
  bare=$(curl -sS --max-time "$TIMEOUT" -o /dev/null -w '%{http_code}' \
    "${BASE_URL}${probe}" 2>/dev/null || echo 000)
  case "$bare" in
  401 | 403)
    echo "Gate check: ${probe} without a credential returned HTTP ${bare}  OK"
    ;;
  *)
    echo "Gate check: ${probe} without a credential returned HTTP ${bare}  FAIL"
    echo "  That route is past the access gate. Check that its routes entry"
    echo "  sets no authorization_type, so the module applies CUSTOM."
    FAILURES=$((FAILURES + 1))
    ;;
  esac
fi

echo
if [ "$FAILURES" -gt 0 ]; then
  echo "FAILED: ${FAILURES} check(s) did not verify."
  exit 1
fi
if [ "$NOT_CUT" -gt 0 ]; then
  echo "NOT CUT OVER: ${NOT_CUT} path(s) resolved to \$default rather than to"
  echo "their own route key. The Terraform apply has not landed, or the routes"
  echo "map does not name these prefixes. Since row 32 there is no \$default"
  echo "route, so a prefix whose key did not land 404s at the gateway instead of"
  echo "reaching this branch."
  exit 1
fi

echo "Every '${DOMAIN}' path resolves to its own route key, not \$default."
