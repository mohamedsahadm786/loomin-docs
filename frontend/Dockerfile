# ── Stage 1: Build the React app ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first (better Docker layer caching)
COPY package.json package-lock.json* ./

# Install all dependencies
RUN npm ci

# Copy all source files
COPY . .

# Build the production React bundle
RUN npm run build

# ── Stage 2: Serve with nginx ──────────────────────────────────────────────────
FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom nginx config
COPY nginx.conf /etc/nginx/conf.d/loomin.conf

# Copy the built React files from Stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 3000
EXPOSE 3000

# Start nginx in foreground (required for Docker)
CMD ["nginx", "-g", "daemon off;"]