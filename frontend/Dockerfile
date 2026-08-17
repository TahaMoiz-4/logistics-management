# syntax=docker/dockerfile:1
#
# Nightingale web console (Vite + React) served by nginx.
#
# nginx does two jobs here:
#   1. Serve the compiled static bundle.
#   2. Reverse-proxy /v1/* to the backend container - replacing the dev-time
#      Vite proxy in vite.config.ts. Because the app calls *relative* /v1 paths,
#      no frontend source change is needed for this to work.
#
# The result is a single origin (port 80) for both UI and API, which is also why
# the backend no longer needs wildcard CORS.

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: build the static bundle
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Alpine is fine on this side: these dependencies are pure JS/TS with no
# compiled native modules, so musl vs glibc never comes up.

# Lockfile + manifest first, for the same layer-caching reason as the backend:
# editing a .tsx file must not trigger a fresh npm install.
COPY package.json package-lock.json ./

# `npm ci` (not `npm install`): installs exactly what package-lock.json pins and
# fails if the lockfile is out of sync, so a build is reproducible rather than
# quietly picking up a newer minor version than what was tested.
RUN npm ci

COPY . .

# `npm run build` is "tsc -b && vite build" - a type error fails the image build
# rather than shipping a broken bundle.
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: serve
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Only the compiled output crosses the stage boundary. Node, npm and
# node_modules stay behind - the final image is nginx plus static files.
COPY --from=builder /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
