# Stage 1: Build Stage
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Add environment variables if needed during build (Vite requires these at build time)
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Copy package files first to leverage Docker layer caching
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Production Stage
FROM nginx:stable-alpine

# Copy the custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built files from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

# ---------------------------------------------------------------------------
# Prepare runtime directories for non‑root operation
# ---------------------------------------------------------------------------
# The official nginx image includes a low‑privilege "nginx" user (uid 101).
# Ensure the directories that nginx writes to are owned by that user.
RUN mkdir -p /var/cache/nginx /var/run /var/log/nginx && \
    chown -R nginx:nginx /var/cache/nginx /var/run /var/log/nginx

# Switch to the non‑root nginx user
USER nginx

# Expose a non‑privileged port (8080) – nginx will bind to this port.
EXPOSE 8080

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
