#!/bin/bash
# Finapify Payments - Quick Deployment Script
# Run this script to automatically deploy and test the module

set -e

echo "=========================================="
echo "Finapify Payments - Deployment Script"
echo "=========================================="
echo ""

# Configuration
BENCH_PATH="${BENCH_PATH:-$HOME/frappe-bench}"
SITE_NAME="${SITE_NAME:-site1.local}"
APP_NAME="finapify_payments"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if bench directory exists
if [ ! -d "$BENCH_PATH" ]; then
    log_error "Bench directory not found at $BENCH_PATH"
    exit 1
fi

log_info "Using Bench path: $BENCH_PATH"
log_info "Using Site: $SITE_NAME"
echo ""

# Step 1: Stop the bench
log_info "Stopping Frappe bench..."
cd "$BENCH_PATH"
bench stop 2>/dev/null || true
sleep 2

# Step 2: Copy/Update the module
log_info "Preparing module files..."
if [ ! -d "$BENCH_PATH/apps/$APP_NAME" ]; then
    log_warn "Module not found, please copy it to $BENCH_PATH/apps/$APP_NAME first"
    exit 1
fi

# Step 3: Clear cache
log_info "Clearing cache..."
bench --site $SITE_NAME clear-cache || true

# Step 4: Migrate
log_info "Running migrations..."
bench --site $SITE_NAME migrate

# Step 5: Uninstall and reinstall app
log_info "Reinstalling app..."
bench --site $SITE_NAME uninstall-app $APP_NAME 2>/dev/null || true
bench --site $SITE_NAME install-app $APP_NAME

# Step 6: Run setup
log_info "Running setup hooks..."
bench --site $SITE_NAME execute $APP_NAME.setup.after_install

# Step 7: Start bench
log_info "Starting Frappe bench..."
bench start &
BENCH_PID=$!

# Wait for server to start
log_info "Waiting for server to start..."
sleep 5

# Step 8: Test connection
log_info "Testing module connection..."
bench --site $SITE_NAME execute $APP_NAME.setup.test_finapify_connection || true

echo ""
echo "=========================================="
echo -e "${GREEN}✅ Deployment completed!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Open ERPNext web UI: http://localhost:8000"
echo "2. Navigate to Setup > Finapify Settings"
echo "3. Configure your Finapify API credentials"
echo "4. Test the connection"
echo "5. Setup webhook endpoints"
echo ""
echo "For more details, see:"
echo "  - README.md"
echo "  - INSTALLATION.md"
echo "  - FIX_SUMMARY.md"
echo ""
