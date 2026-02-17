#!/bin/bash
# =============================================================================
# CRASH LENS - VPS Self-Hosting Setup Script
# =============================================================================
# Sets up Postiz (social media scheduler) and n8n (workflow automation)
# on a Hostinger VPS using Docker Compose.
#
# Requirements:
#   - Ubuntu 20.04+ or Debian 11+ VPS
#   - Minimum 4GB RAM, 2 vCPUs
#   - Root/sudo access
#   - Domain pointed to VPS IP (optional but recommended)
#
# Usage:
#   chmod +x setup_vps.sh
#   sudo ./setup_vps.sh
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "=============================================="
echo "  CRASH LENS Social Media Automation Setup"
echo "  Postiz + n8n on Docker"
echo "=============================================="
echo ""

# -------------------------
# Step 1: Install Docker
# -------------------------
log_info "Step 1: Installing Docker..."

if command -v docker &> /dev/null; then
    log_ok "Docker already installed: $(docker --version)"
else
    log_info "Installing Docker..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    log_ok "Docker installed: $(docker --version)"
fi

# -------------------------
# Step 2: Create directories
# -------------------------
log_info "Step 2: Creating directories..."
INSTALL_DIR="/opt/crashlens-social"
mkdir -p "$INSTALL_DIR"/{postiz,n8n,nginx,data}
log_ok "Created $INSTALL_DIR"

# -------------------------
# Step 3: Generate secrets
# -------------------------
log_info "Step 3: Generating secrets..."
JWT_SECRET=$(openssl rand -hex 32)
NEXT_AUTH_SECRET=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)

# -------------------------
# Step 4: Create Docker Compose
# -------------------------
log_info "Step 4: Creating Docker Compose configuration..."

cat > "$INSTALL_DIR/docker-compose.yml" << 'COMPOSE_EOF'
version: '3.8'

services:
  # =============================================
  # Postiz - Social Media Scheduler
  # =============================================
  postiz:
    image: ghcr.io/gitroomhq/postiz-app:latest
    container_name: postiz
    restart: unless-stopped
    ports:
      - "4200:5000"
    environment:
      - DATABASE_URL=postgresql://postiz:${DB_PASSWORD}@postiz-db:5432/postiz
      - REDIS_URL=redis://postiz-redis:6379
      - JWT_SECRET=${JWT_SECRET}
      - NEXT_AUTH_SECRET=${NEXT_AUTH_SECRET}
      - FRONTEND_URL=${POSTIZ_URL:-http://localhost:4200}
      - NEXT_PUBLIC_BACKEND_URL=${POSTIZ_URL:-http://localhost:4200}/api
      - BACKEND_INTERNAL_URL=http://localhost:3000
    depends_on:
      postiz-db:
        condition: service_healthy
      postiz-redis:
        condition: service_healthy
    volumes:
      - postiz-uploads:/app/uploads
    networks:
      - crashlens

  postiz-db:
    image: postgres:16-alpine
    container_name: postiz-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=postiz
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=postiz
    volumes:
      - postiz-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postiz"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - crashlens

  postiz-redis:
    image: redis:7-alpine
    container_name: postiz-redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - postiz-redis-data:/data
    networks:
      - crashlens

  # =============================================
  # n8n - Workflow Automation
  # =============================================
  n8n:
    image: docker.n8n.io/n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=${N8N_HOST:-localhost}
      - N8N_PORT=5678
      - N8N_PROTOCOL=${N8N_PROTOCOL:-http}
      - WEBHOOK_URL=${N8N_URL:-http://localhost:5678}/
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER:-admin}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD:-changeme}
      - GENERIC_TIMEZONE=America/New_York
    volumes:
      - n8n-data:/home/node/.n8n
    networks:
      - crashlens

volumes:
  postiz-db-data:
  postiz-redis-data:
  postiz-uploads:
  n8n-data:

networks:
  crashlens:
    driver: bridge
COMPOSE_EOF

log_ok "Docker Compose file created"

# -------------------------
# Step 5: Create .env file
# -------------------------
log_info "Step 5: Creating environment file..."

cat > "$INSTALL_DIR/.env" << ENV_EOF
# ===========================================
# CRASH LENS Social Media - Environment Config
# ===========================================
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Database
DB_PASSWORD=${DB_PASSWORD}

# Postiz Auth
JWT_SECRET=${JWT_SECRET}
NEXT_AUTH_SECRET=${NEXT_AUTH_SECRET}

# URLs - Update these with your domain
POSTIZ_URL=http://localhost:4200
N8N_URL=http://localhost:5678

# n8n Auth
N8N_HOST=localhost
N8N_PROTOCOL=http
N8N_USER=admin
N8N_PASSWORD=changeme

# =============================================
# IMPORTANT: Update these with your actual values
# =============================================

# Claude API (for n8n workflows)
ANTHROPIC_API_KEY=your-claude-api-key-here

# Social Media API Keys (add as you set up each platform)
# LINKEDIN_ACCESS_TOKEN=
# TWITTER_API_KEY=
# TWITTER_API_SECRET=
# TWITTER_ACCESS_TOKEN=
# TWITTER_ACCESS_SECRET=
# FACEBOOK_PAGE_TOKEN=
# BLUESKY_HANDLE=
# BLUESKY_APP_PASSWORD=
ENV_EOF

chmod 600 "$INSTALL_DIR/.env"
log_ok "Environment file created (chmod 600)"

# -------------------------
# Step 6: Create management script
# -------------------------
log_info "Step 6: Creating management script..."

cat > "$INSTALL_DIR/manage.sh" << 'MANAGE_EOF'
#!/bin/bash
# CRASH LENS Social Media - Management Commands

COMPOSE_DIR="/opt/crashlens-social"

case "$1" in
    start)
        echo "Starting services..."
        cd "$COMPOSE_DIR" && docker compose up -d
        echo "Postiz: http://$(hostname -I | awk '{print $1}'):4200"
        echo "n8n:    http://$(hostname -I | awk '{print $1}'):5678"
        ;;
    stop)
        echo "Stopping services..."
        cd "$COMPOSE_DIR" && docker compose down
        ;;
    restart)
        echo "Restarting services..."
        cd "$COMPOSE_DIR" && docker compose restart
        ;;
    status)
        cd "$COMPOSE_DIR" && docker compose ps
        ;;
    logs)
        cd "$COMPOSE_DIR" && docker compose logs -f "${2:-}"
        ;;
    update)
        echo "Updating to latest versions..."
        cd "$COMPOSE_DIR" && docker compose pull && docker compose up -d
        ;;
    backup)
        BACKUP_DIR="$COMPOSE_DIR/backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        echo "Backing up databases..."
        docker exec postiz-db pg_dump -U postiz postiz > "$BACKUP_DIR/postiz_db.sql"
        cp "$COMPOSE_DIR/.env" "$BACKUP_DIR/.env.backup"
        echo "Backup saved to: $BACKUP_DIR"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs [service]|update|backup}"
        echo ""
        echo "Services: postiz, postiz-db, postiz-redis, n8n"
        ;;
esac
MANAGE_EOF

chmod +x "$INSTALL_DIR/manage.sh"
ln -sf "$INSTALL_DIR/manage.sh" /usr/local/bin/crashlens-social
log_ok "Management script created (use: crashlens-social start|stop|status|logs|update|backup)"

# -------------------------
# Step 7: Setup firewall
# -------------------------
log_info "Step 7: Configuring firewall..."

if command -v ufw &> /dev/null; then
    ufw allow 4200/tcp comment "Postiz"
    ufw allow 5678/tcp comment "n8n"
    log_ok "Firewall rules added for ports 4200, 5678"
else
    log_warn "UFW not found. Make sure ports 4200 and 5678 are open in your Hostinger panel."
fi

# -------------------------
# Step 8: Start services
# -------------------------
log_info "Step 8: Starting services..."
cd "$INSTALL_DIR"
docker compose up -d

# Wait for services to be ready
log_info "Waiting for services to start..."
sleep 15

# Check status
docker compose ps

VPS_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=============================================="
echo "  Setup Complete!"
echo "=============================================="
echo ""
echo "  Postiz (Social Media Scheduler):"
echo "    URL: http://${VPS_IP}:4200"
echo "    Create your admin account on first visit"
echo ""
echo "  n8n (Workflow Automation):"
echo "    URL: http://${VPS_IP}:5678"
echo "    Username: admin"
echo "    Password: changeme (CHANGE THIS!)"
echo ""
echo "  Management Commands:"
echo "    crashlens-social start     - Start all services"
echo "    crashlens-social stop      - Stop all services"
echo "    crashlens-social status    - Check service status"
echo "    crashlens-social logs      - View logs"
echo "    crashlens-social logs n8n  - View n8n logs only"
echo "    crashlens-social update    - Update to latest versions"
echo "    crashlens-social backup    - Backup databases"
echo ""
echo "  Next Steps:"
echo "    1. Visit Postiz and create your admin account"
echo "    2. Connect your social media accounts in Postiz"
echo "    3. Visit n8n and set up Claude API workflows"
echo "    4. Update .env with your API keys"
echo "    5. (Optional) Set up a domain + SSL with nginx"
echo ""
echo "  Config files: $INSTALL_DIR/"
echo "  Environment:  $INSTALL_DIR/.env"
echo ""
log_warn "IMPORTANT: Change the n8n password in $INSTALL_DIR/.env"
log_warn "IMPORTANT: Add your API keys to $INSTALL_DIR/.env"
echo ""
