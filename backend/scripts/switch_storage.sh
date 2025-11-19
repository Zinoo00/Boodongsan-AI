#!/bin/bash
# Storage backend switching script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$BACKEND_DIR/.env"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_usage() {
    echo "Usage: $0 [postgresql|local]"
    echo ""
    echo "Switch storage backend between PostgreSQL and Local mode"
    echo ""
    echo "Options:"
    echo "  postgresql  - Switch to PostgreSQL (production mode)"
    echo "  local       - Switch to Local (development mode)"
    echo ""
    echo "Examples:"
    echo "  $0 postgresql"
    echo "  $0 local"
}

if [ $# -eq 0 ]; then
    print_usage
    exit 1
fi

BACKEND=$1

case $BACKEND in
    postgresql|pg)
        echo -e "${BLUE}Switching to PostgreSQL backend...${NC}"

        # Check if .env exists
        if [ ! -f "$ENV_FILE" ]; then
            echo -e "${RED}Error: .env file not found${NC}"
            echo "Please copy .env.example to .env first"
            exit 1
        fi

        # Update STORAGE_BACKEND
        if grep -q "^STORAGE_BACKEND=" "$ENV_FILE"; then
            sed -i.bak 's/^STORAGE_BACKEND=.*/STORAGE_BACKEND=postgresql/' "$ENV_FILE"
        else
            echo "STORAGE_BACKEND=postgresql" >> "$ENV_FILE"
        fi

        echo -e "${GREEN}✓ Storage backend set to: postgresql${NC}"
        echo ""
        echo -e "${YELLOW}Important:${NC}"
        echo "1. Make sure DATABASE_URL is configured in .env"
        echo "2. Run migrations: uv run alembic upgrade head"
        echo "3. Restart the application"
        echo ""
        echo "Example DATABASE_URL:"
        echo "DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/boda"
        ;;

    local|loc)
        echo -e "${BLUE}Switching to Local backend...${NC}"

        # Check if .env exists
        if [ ! -f "$ENV_FILE" ]; then
            echo -e "${RED}Error: .env file not found${NC}"
            echo "Please copy .env.example to .env first"
            exit 1
        fi

        # Update STORAGE_BACKEND
        if grep -q "^STORAGE_BACKEND=" "$ENV_FILE"; then
            sed -i.bak 's/^STORAGE_BACKEND=.*/STORAGE_BACKEND=local/' "$ENV_FILE"
        else
            echo "STORAGE_BACKEND=local" >> "$ENV_FILE"
        fi

        echo -e "${GREEN}✓ Storage backend set to: local${NC}"
        echo ""
        echo -e "${YELLOW}Note:${NC}"
        echo "1. No database setup required"
        echo "2. Data will be stored in: ./lightrag_storage/BODA"
        echo "3. Restart the application"
        ;;

    *)
        echo -e "${RED}Error: Invalid backend: $BACKEND${NC}"
        echo ""
        print_usage
        exit 1
        ;;
esac

# Clean up backup file
rm -f "$ENV_FILE.bak"

echo ""
echo -e "${GREEN}Done!${NC} Storage backend switched successfully."
echo "Current configuration:"
grep "^STORAGE_BACKEND=" "$ENV_FILE"
