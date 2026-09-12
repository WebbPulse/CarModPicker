# Rate Limiting

The CarModPicker API rate limits every request against one shared counter held in
DynamoDB. There is a single layer; the per-process in-memory limiter that used to sit
in front of it has been removed.

## Why the in-memory limiter is gone

Each domain runs as a Lambda function, so a per-process counter only ever saw the
traffic that happened to land in one execution environment. Under concurrency the real
limit was the configured limit multiplied by the number of warm sandboxes, and the
`X-RateLimit-Remaining-*` headers it returned advertised an allowance no caller had.
It also disagreed with the shared limiter about who was being limited and for how long,
which made a 429 hard to explain. Removing it leaves one counter that is correct across
every environment.

## How the shared limiter works

`app/api/middleware/shared_rate_limiter.py` keeps one item per caller in the
`rate-limits` table, keyed `RATE#<identity>`. The item carries a request count and a
DynamoDB TTL, so the window is a fixed window anchored on the caller's first request
rather than on the wall clock, and expired rows are reclaimed by DynamoDB itself.

The caller's identity is the source IP as API Gateway observed it. Three sources are
tried in order: the `x-amzn-request-context` header the Lambda Web Adapter forwards, the
`aws.event` scope key an event-driven adapter populates, and finally the connection's
own peer address.

Every backend failure fails open. A `get_item` or `update_item` that raises is logged
with `rate_limit_failed_open: true` and the request is allowed through, so a DynamoDB
outage degrades the limit rather than the API.

## Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `ENABLE_RATE_LIMITING` | `true` | Master switch for the middleware. |
| `ENABLE_SHARED_RATE_LIMITING` | `true` | Whether the shared counter runs. |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `60` | Requests allowed per caller per 60 second window. |
| `RATE_LIMITS_TABLE` | `""` | Table name override. Terraform sets it from `module.dynamodb.table_names["rate-limits"]`. |

The environment variable `ENABLE_RATE_LIMITING=false` also disables the middleware
independently of the setting, which is how the test suite turns it off.

## Exempted paths

Matched exactly:

- `/`
- `/health`
- `/ready`
- `/openapi.json`

Matched as prefixes, so their sub-resources are exempt too:

- `/docs`
- `/redoc`

The split is deliberate: a prefix entry for `/` would exempt the whole API and silently
disable the limiter.

## Rate limit exceeded response

```json
{
  "detail": "Too many requests",
  "message": "Rate limit exceeded",
  "retry_after": 42
}
```

With headers:

```
Retry-After: 42
X-RateLimit-Remaining-Minute: 0
```

`retry_after` is the number of seconds left on the caller's current window, read back
from the row's TTL, and falls back to 60 when the row cannot be read.

## Testing

Rate limiting is disabled in the test suite by default. Enable it with
`ENABLE_RATE_LIMITING=true`. `tests/test_shared_rate_limiter.py` drives the limiter
against a fake table client, so it needs neither moto nor network access.
