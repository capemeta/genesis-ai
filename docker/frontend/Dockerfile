ARG NODE_BASE_IMAGE=node:20-bookworm
ARG NGINX_BASE_IMAGE=nginx:1.27-alpine

FROM ${NODE_BASE_IMAGE} AS build

WORKDIR /app

RUN corepack enable

COPY genesis-ai-frontend/package.json genesis-ai-frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY genesis-ai-frontend/ ./

ARG VITE_API_URL=http://localhost:8200
ARG VITE_CLERK_PUBLISHABLE_KEY=

ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}

RUN pnpm build

FROM ${NGINX_BASE_IMAGE}

COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
