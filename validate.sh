#!/bin/bash
# Finapify Payments - Troubleshooting & Validation Script

BENCH_PATH="${BENCH_PATH:-$HOME/frappe-bench}"
SITE_NAME="${SITE_NAME:-site1.local}"
APP_NAME="finapify_payments"
APP_PATH="$BENCH_PATH/apps/$APP_NAME"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    Finapify Payments - Troubleshooting & Validation Tool     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Test 1: Check if module exists
echo -e "${BLUE}[TEST 1]${NC} Checking if module exists..."
if [ -d "$APP_PATH" ]; then
    echo -e "${GREEN}✓${NC} Module found at $APP_PATH"
else
    echo -e "${RED}✗${NC} Module not found at $APP_PATH"
    exit 1
fi
echo ""

# Test 2: Check Python syntax
echo -e "${BLUE}[TEST 2]${NC} Checking Python syntax..."
python_files=()
while IFS= read -r file; do
    python_files+=("$file")
done < <(find "$APP_PATH" -name "*.py" -type f)

syntax_errors=0
for py_file in "${python_files[@]}"; do
    if ! python3 -m py_compile "$py_file" 2>/dev/null; then
        echo -e "${RED}✗${NC} Syntax error in $py_file"
        syntax_errors=$((syntax_errors + 1))
    fi
done

if [ $syntax_errors -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All Python files have valid syntax"
else
    echo -e "${RED}✗${NC} Found $syntax_errors files with syntax errors"
fi
echo ""

# Test 3: Check for Odoo imports (should not exist)
echo -e "${BLUE}[TEST 3]${NC} Checking for Odoo imports (should be none)..."
odoo_imports=$(grep -r "from odoo import" "$APP_PATH" 2>/dev/null | wc -l)
if [ $odoo_imports -eq 0 ]; then
    echo -e "${GREEN}✓${NC} No Odoo imports found"
else
    echo -e "${RED}✗${NC} Found $odoo_imports Odoo imports (should be Frappe instead)"
    grep -r "from odoo import" "$APP_PATH" | sed 's/^/  /'
fi
echo ""

# Test 4: Check for Frappe imports
echo -e "${BLUE}[TEST 4]${NC} Checking for Frappe imports..."
frappe_imports=$(grep -r "import frappe" "$APP_PATH" 2>/dev/null | wc -l)
echo -e "${GREEN}✓${NC} Found $frappe_imports files with Frappe imports"
echo ""

# Test 5: Check hooks.py exists
echo -e "${BLUE}[TEST 5]${NC} Checking hooks.py..."
if [ -f "$APP_PATH/hooks.py" ]; then
    echo -e "${GREEN}✓${NC} hooks.py found"
    if grep -q "app_name" "$APP_PATH/hooks.py"; then
        echo -e "${GREEN}✓${NC} app_name configured"
    else
        echo -e "${RED}✗${NC} app_name not configured in hooks.py"
    fi
else
    echo -e "${RED}✗${NC} hooks.py not found"
fi
echo ""

# Test 6: Check setup.py exists
echo -e "${BLUE}[TEST 6]${NC} Checking setup.py..."
if [ -f "$APP_PATH/setup.py" ]; then
    echo -e "${GREEN}✓${NC} setup.py found"
    if grep -q "after_install" "$APP_PATH/setup.py"; then
        echo -e "${GREEN}✓${NC} after_install function found"
    else
        echo -e "${YELLOW}!${NC} after_install function not found"
    fi
else
    echo -e "${YELLOW}!${NC} setup.py not found (optional)"
fi
echo ""

# Test 7: Check documentation
echo -e "${BLUE}[TEST 7]${NC} Checking documentation..."
docs_found=0
for doc in README.md INSTALLATION.md MIGRATION.md FIX_SUMMARY.md; do
    if [ -f "$APP_PATH/$doc" ]; then
        echo -e "${GREEN}✓${NC} $doc found"
        docs_found=$((docs_found + 1))
    fi
done
echo -e "${GREEN}✓${NC} Found $docs_found documentation files"
echo ""

# Test 8: Check module installation (if bench available)
echo -e "${BLUE}[TEST 8]${NC} Checking module installation in Bench..."
if [ -d "$BENCH_PATH" ] && command -v bench &> /dev/null; then
    cd "$BENCH_PATH"
    
    # Check if module is installed
    if bench --site $SITE_NAME list-apps 2>/dev/null | grep -q "$APP_NAME"; then
        echo -e "${GREEN}✓${NC} Module is installed in Bench"
    else
        echo -e "${YELLOW}!${NC} Module not installed (use: bench --site $SITE_NAME install-app $APP_NAME)"
    fi
else
    echo -e "${YELLOW}!${NC} Bench not available, skipping installation check"
fi
echo ""

# Test 9: Check for common issues
echo -e "${BLUE}[TEST 9]${NC} Checking for common issues..."
issues=0

# Check for Odoo model classes
odoo_models=$(grep -r "class.*models\.Model" "$APP_PATH" 2>/dev/null | wc -l)
if [ $odoo_models -gt 0 ]; then
    echo -e "${RED}✗${NC} Found $odoo_models Odoo model classes (use Document instead)"
    issues=$((issues + 1))
fi

# Check for http.Controller
http_controllers=$(grep -r "http.Controller" "$APP_PATH" 2>/dev/null | wc -l)
if [ $http_controllers -gt 0 ]; then
    echo -e "${RED}✗${NC} Found $http_controllers http.Controller classes (use @frappe.whitelist() instead)"
    issues=$((issues + 1))
fi

# Check for @api.model decorators
api_models=$(grep -r "@api.model" "$APP_PATH" 2>/dev/null | wc -l)
if [ $api_models -gt 0 ]; then
    echo -e "${RED}✗${NC} Found $api_models @api.model decorators (remove - not used in Frappe)"
    issues=$((issues + 1))
fi

# Check for fields.Char, fields.Many2one (Odoo field definitions)
odoo_fields=$(grep -r "fields\.Char\|fields\.Many2one\|fields\.Integer" "$APP_PATH" 2>/dev/null | wc -l)
if [ $odoo_fields -gt 0 ]; then
    echo -e "${RED}✗${NC} Found $odoo_fields Odoo field definitions (define in JSON doctypes instead)"
    issues=$((issues + 1))
fi

if [ $issues -eq 0 ]; then
    echo -e "${GREEN}✓${NC} No common Odoo/Frappe compatibility issues found"
fi
echo ""

# Test 10: Performance check
echo -e "${BLUE}[TEST 10]${NC} Checking module size..."
module_size=$(du -sh "$APP_PATH" | cut -f1)
echo -e "${GREEN}✓${NC} Module size: $module_size"
echo ""

# Summary
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                        SUMMARY                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Module: $APP_NAME"
echo "Location: $APP_PATH"
echo "Python Files: ${#python_files[@]}"
echo "Frappe Imports: $frappe_imports"
echo "Odoo Imports: $odoo_imports"
echo ""

if [ $odoo_imports -eq 0 ] && [ $syntax_errors -eq 0 ]; then
    echo -e "${GREEN}✓ Module is ready for deployment!${NC}"
    echo ""
    echo "Deploy with:"
    echo "  cd $BENCH_PATH"
    echo "  bench --site $SITE_NAME install-app $APP_NAME"
else
    echo -e "${RED}✗ Module has issues that need to be fixed${NC}"
    exit 1
fi
echo ""
