#!/bin/bash
#==============================================================================
# Enterprise 3855 Labs - Automated Deployment (Linux/WSL2)
#==============================================================================
# Usage:
#   ./deploy.sh           - Full deployment
#   ./deploy.sh --check   - Pre-flight checks only
#==============================================================================

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory (works even when called from other locations)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "==============================================================================="
echo "  Enterprise 3855 Labs - Automated Deployment"
echo "==============================================================================="
echo "Project root: $SCRIPT_DIR"
echo ""

#==============================================================================
# Pre-flight Checks
#==============================================================================
echo "[1/5] Running pre-flight checks..."

# Check Ansible
if ! command -v ansible &> /dev/null; then
    echo -e "${RED}[ERROR] Ansible is not installed!${NC}"
    echo "Install with: sudo apt install -y ansible"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Ansible found"

# Check inventory
if [ ! -f "inventory.yml" ]; then
    echo -e "${RED}[ERROR] inventory.yml not found!${NC}"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Inventory file found"

# Check playbook
if [ ! -f "playbook.yml" ]; then
    echo -e "${RED}[ERROR] playbook.yml not found!${NC}"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Playbook file found"

# Check SSH key
SSH_KEY=$(grep "ansible_ssh_private_key_file" inventory.yml | sed 's/.*: *"\?\([^"]*\)"\?.*/\1/')
# Expand ~ to home directory
SSH_KEY="${SSH_KEY/#\~/$HOME}"

if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}[ERROR] SSH key not found: $SSH_KEY${NC}"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} SSH key found"

# Fix SSH key permissions (ignore if on Windows mount)
chmod 600 "$SSH_KEY" 2>/dev/null || true
echo -e "${GREEN}[OK]${NC} SSH key permissions checked"

#==============================================================================
# Install Ansible Collections
#==============================================================================
echo ""
echo "[2/5] Installing Ansible collections..."

if [ -f "requirements.yml" ]; then
    ansible-galaxy collection install -r requirements.yml --force > /dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[OK]${NC} Ansible collections installed"
    else
        echo -e "${RED}[ERROR]${NC} Failed to install collections"
        exit 1
    fi
else
    echo -e "${YELLOW}[WARN]${NC} requirements.yml not found, skipping"
fi

#==============================================================================
# Test Connection
#==============================================================================
echo ""
echo "[3/5] Testing SSH connection to EC2..."

# Extract connection details from inventory (strip Windows line endings)
EC2_IP=$(grep "ansible_host:" inventory.yml | awk '{print $2}' | tr -d '\r')
ANSIBLE_USER=$(grep "ansible_user:" inventory.yml | awk '{print $2}' | tr -d '\r')

# Simple SSH test (doesn't need vault password)
if ssh -i "${SSH_KEY}" -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes ${ANSIBLE_USER}@${EC2_IP} exit 2>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Successfully connected to EC2"
else
    echo -e "${RED}[ERROR]${NC} Cannot connect to EC2 instance!"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check EC2 instance is running"
    echo "  2. Verify security group allows SSH from your IP"
    echo "  3. Verify SSH key path in inventory.yml"
    exit 1
fi

# Exit here if --check flag
if [ "$1" == "--check" ]; then
    echo ""
    echo -e "${GREEN}SUCCESS!${NC} Pre-flight checks passed"
    echo "Run without --check flag to deploy: ./deploy.sh"
    exit 0
fi

#==============================================================================
# Run Deployment
#==============================================================================
echo ""
echo "[4/5] Running deployment playbook..."
echo -e "${YELLOW}TIME WARNING:${NC} This will take 3-5 minutes (Kafka initialization)"
echo ""

ansible-playbook -i inventory.yml playbook.yml --ask-vault-pass

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}[ERROR]${NC} Deployment failed!"
    exit 1
fi

#==============================================================================
# Verify Deployment
#==============================================================================
echo ""
echo "[5/5] Testing service endpoints..."

# Get EC2 IP from inventory
EC2_IP=$(grep "ansible_host:" inventory.yml | awk '{print $2}')

# Test endpoints
ENDPOINTS=("8080:Receiver" "8090:Storage" "8100:Processing" "8110:Analyzer")
ALL_OK=true

for endpoint in "${ENDPOINTS[@]}"; do
    PORT=$(echo $endpoint | cut -d: -f1)
    SERVICE=$(echo $endpoint | cut -d: -f2)
    
    if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://${EC2_IP}:${PORT}/health" | grep -q "200\|404"; then
        echo -e "${GREEN}[OK]${NC} $SERVICE (port $PORT) is responding"
    else
        echo -e "${RED}[ERROR]${NC} $SERVICE (port $PORT) is not responding (Ignore this for now. This is for assignment 1)"
        ALL_OK=false
    fi
done

echo ""
if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}SUCCESS!${NC} Deployment complete!"
    echo ""
    echo "Service URLs:"
    echo "  Receiver:   http://${EC2_IP}:8080"
    echo "  Storage:    http://${EC2_IP}:8090"
    echo "  Processing: http://${EC2_IP}:8100"
    echo "  Analyzer:   http://${EC2_IP}:8110"
else
    echo -e "${YELLOW}[WARN]${NC} Deployment completed but some services may not be ready"
    echo "Give Kafka 1-2 more minutes to initialize, then check again"
fi
