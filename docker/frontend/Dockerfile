ARG NODE_BASE_IMAGE=node:20-bookworm
ARG NGINX_BASE_IMAGE=nginx:1.27-alpine

FROM ${NODE_BASE_IMAGE} AS build

WORKDIR /app

RUN corepack enable

COPY genesis-ai-frontend/package.json genesis-ai-frontend/pnpm-lock.yaml genesis-ai-frontend/.npmrc ./
RUN pnpm install --frozen-lockfile

COPY genesis-ai-frontend/ ./

ARG VITE_API_URL=http://localhost:8200
ARG ROOT_PATH=/
ARG VITE_CLERK_PUBLISHABLE_KEY=

ENV VITE_API_URL=${VITE_API_URL}
ENV ROOT_PATH=${ROOT_PATH}
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}

RUN pnpm build

FROM ${NGINX_BASE_IMAGE}

COPY docker/frontend/nginx.conf /etc/nginx/templates/default.conf.template
RUN printf '%s\n' \
    'set -eu' \
    '' \
    'ROOT_PATH_VALUE="${ROOT_PATH:-/}"' \
    '' \
    'if [ -z "$ROOT_PATH_VALUE" ]; then' \
    '  ROOT_PATH_VALUE="/"' \
    'fi' \
    '' \
    'case "$ROOT_PATH_VALUE" in' \
    '  /*) ;;' \
    '  *) ROOT_PATH_VALUE="/$ROOT_PATH_VALUE" ;;' \
    'esac' \
    '' \
    'while [ "$ROOT_PATH_VALUE" != "/" ] && [ "${ROOT_PATH_VALUE%/}" != "$ROOT_PATH_VALUE" ]; do' \
    '  ROOT_PATH_VALUE="${ROOT_PATH_VALUE%/}"' \
    'done' \
    '' \
    'if [ "$ROOT_PATH_VALUE" = "/" ]; then' \
    '  export NGINX_ROOT_PATH_PREFIX=""' \
    '  export NGINX_ROOT_PATH_SLASH="/"' \
    '  export NGINX_ROOT_PATH_EXACT="/__genesis_root_redirect_disabled__"' \
    'else' \
    '  export NGINX_ROOT_PATH_PREFIX="$ROOT_PATH_VALUE"' \
    '  export NGINX_ROOT_PATH_SLASH="$ROOT_PATH_VALUE/"' \
    '  export NGINX_ROOT_PATH_EXACT="$ROOT_PATH_VALUE"' \
    'fi' \
    > /docker-entrypoint.d/04-normalize-root-path.envsh \
    && chmod +x /docker-entrypoint.d/04-normalize-root-path.envsh
RUN sed -i 's/worker_processes  auto;/worker_processes  4;/' /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
