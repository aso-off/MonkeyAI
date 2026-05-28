# ---- Build stage ----
FROM node:22-alpine AS build

WORKDIR /app

# Install dependencies first (Docker layer cache)
COPY mini-app/package.json mini-app/package-lock.json ./
RUN npm ci --prefer-offline

# Copy source
COPY mini-app/ ./

# VITE_API_URL is baked in at build time.
# Override via docker-compose build args or the root .env.
ARG VITE_API_URL=https://api.si881.ru
RUN VITE_API_URL=$VITE_API_URL npm run build-only

# ---- Serve stage ----
FROM nginx:1.27-alpine AS serve

COPY --from=build /app/dist /usr/share/nginx/html
COPY mini-app/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
