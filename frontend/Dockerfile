# syntax=docker/dockerfile:1.7

# ---------- build the SPA ----------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---------- serve with nginx (also the reverse proxy for the API) ----------
FROM nginx:1.28-alpine
# Rendered at start by the image's envsubst step (TRUSTED_PROXIES).
COPY docker/default.conf.template /etc/nginx/templates/default.conf.template
ENV TRUSTED_PROXIES=127.0.0.1/32
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s CMD wget -qO- http://127.0.0.1/nginx-health || exit 1
