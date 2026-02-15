# ============================================================
# CRASH LENS - Coolify/Docker Deployment
# Multi-process container: Nginx (static files) + Node.js (API proxy)
# ============================================================

FROM node:18-alpine AS base

# Install nginx and supervisord
RUN apk add --no-cache nginx supervisor

# ------------------------------------------------------------
# Copy application files
# ------------------------------------------------------------

# Copy static site files to Nginx html directory
COPY index.html /usr/share/nginx/html/
COPY config.json /usr/share/nginx/html/
COPY manifest.json /usr/share/nginx/html/

# Copy app directory (main application)
COPY app/ /usr/share/nginx/html/app/

# Copy data directory
COPY data/ /usr/share/nginx/html/data/

# Copy states directory
COPY states/ /usr/share/nginx/html/states/

# Copy assets directory
COPY assets/ /usr/share/nginx/html/assets/

# Copy docs directory (if needed for the app)
COPY docs/ /usr/share/nginx/html/docs/

# Copy any login directory if it exists
COPY logi[n]/ /usr/share/nginx/html/login/

# ------------------------------------------------------------
# Configure Nginx
# ------------------------------------------------------------

# Remove default nginx config
RUN rm -f /etc/nginx/http.d/default.conf

# Copy custom nginx config
COPY nginx.conf /etc/nginx/http.d/default.conf

# Ensure nginx directories exist
RUN mkdir -p /var/log/nginx /var/lib/nginx/tmp /run/nginx

# ------------------------------------------------------------
# Configure Node.js API proxy
# ------------------------------------------------------------

# Copy proxy server
COPY server/ /app/server/

# ------------------------------------------------------------
# Configure supervisord
# ------------------------------------------------------------

COPY supervisord.conf /etc/supervisord.conf

# ------------------------------------------------------------
# Expose port and start
# ------------------------------------------------------------

# Expose port 80 (Coolify will map this automatically)
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

# Start both Nginx and the API proxy via supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
