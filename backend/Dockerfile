# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=432410731887.dkr.ecr.us-west-2.amazonaws.com/webbpulse/python-lambda-base@sha256:b5298b4b773ad6c9e311057cf5d43f37ceb98f0367347d714c6817f250a5cef7

FROM ${BASE_IMAGE} AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.10@sha256:2bb3ebca0a796a155094a27773d290c4b074572e6107f171d88d086682fd2500 /uv /usr/local/bin/uv

USER root

WORKDIR /build

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON=/usr/local/bin/python3.13

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev --no-install-project --no-install-package webbpulse

ARG DEPENDENCY_RESOLUTION=local

RUN --mount=type=secret,id=codeartifact_token,required=true \
    set -eu; \
    UV_INDEX_CODEARTIFACT_USERNAME=aws \
    UV_INDEX_CODEARTIFACT_PASSWORD="$(cat /run/secrets/codeartifact_token)" \
    uv lock --upgrade-package webbpulse; \
    UV_INDEX_CODEARTIFACT_USERNAME=aws \
    UV_INDEX_CODEARTIFACT_PASSWORD="$(cat /run/secrets/codeartifact_token)" \
    uv sync --frozen --no-dev --no-install-project; \
    /opt/venv/bin/python -c "import importlib.metadata as m; print('webbpulse', m.version('webbpulse'))"

RUN find /opt/venv -type d -name "__pycache__" -prune -exec rm -rf {} + \
    && find /opt/venv -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

FROM ${BASE_IMAGE} AS runtime

USER root

ARG DOMAIN
RUN set -eu; \
    test -n "${DOMAIN}" || { \
        echo "DOMAIN build arg is required: one of identity, users, catalog," >&2; \
        echo "vehicles, build-lists, build-logs, moderation, media, admin." >&2; \
        echo "  docker buildx build --build-arg DOMAIN=media ..." >&2; \
        exit 1; \
    }; \
    case "${DOMAIN}" in \
        identity|users|catalog|vehicles|build-lists|build-logs|moderation|media|admin) ;; \
        *) \
            echo "DOMAIN=${DOMAIN} is not a domain. Expected one of identity, users," >&2; \
            echo "catalog, vehicles, build-lists, build-logs, moderation, media, admin." >&2; \
            exit 1 ;; \
    esac; \
    module="${DOMAIN%%-*}"; \
    rest="${DOMAIN#"${module}"}"; \
    case "${rest}" in -*) module="${module}_${rest#-}" ;; esac; \
    echo "app.entrypoints.${module}" > /etc/carmodpicker-entrypoint

COPY --from=builder /opt/venv /opt/venv
COPY app/ /var/task/app/

RUN set -eu; \
    module="$(sed 's/^app\.entrypoints\.//' /etc/carmodpicker-entrypoint)"; \
    test -f "/var/task/app/entrypoints/${module}.py" || { \
        echo "DOMAIN=${DOMAIN} maps to app/entrypoints/${module}.py, which is not in the image." >&2; \
        exit 1; \
    }

ENV DOMAIN=${DOMAIN} \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/var/task \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AWS_LWA_PORT=8080 \
    PORT=8080 \
    AWS_LWA_ASYNC_INIT=true \
    AWS_LWA_READINESS_CHECK_PATH=/health \
    AWS_LWA_READINESS_CHECK_PROTOCOL=http \
    RUN_STARTUP_TASKS=false

WORKDIR /var/task

USER app

CMD ["sh", "-c", "exec python -m \"$(cat /etc/carmodpicker-entrypoint)\""]
