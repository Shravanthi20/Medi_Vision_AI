#!/bin/bash
# ════════════════════════════════════════════════════════════════
#  MediVision AI — One-Click Start Script (Linux / Mac / WSL)
# ════════════════════════════════════════════════════════════════

cd "$(dirname "$0")"

GREEN='\033[0;32m'
ORANGE='\033[0;33m'
RESET='\033[0m'

echo -e "${ORANGE}"
echo " ============================================================"
echo "   MediVision AI - Pharmacy Management Platform"
echo "   Selvam Medicals - SS & Co, Tirunelveli"
echo " ============================================================"
echo -e "${RESET}"

# Check python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "[X] Python not found. Install from https://www.python.org/downloads/"
    exit 1
fi
PY=$(command -v python3 || command -v python)

# Install deps if first run
if [ ! -f ".deps-installed" ]; then
    echo "[*] First-time setup: installing dependencies..."
    $PY -m pip install --quiet flask flask-cors python-dotenv twilio requests pytesseract 2>/dev/null
    touch .deps-installed
    echo "[OK] Dependencies ready."
fi

# Detect local IP
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$LOCAL_IP" ] && LOCAL_IP=$(ifconfig 2>/dev/null | awk '/inet / && !/127/{print $2; exit}')
[ -z "$LOCAL_IP" ] && LOCAL_IP="localhost"

echo -e "${GREEN}"
echo " ============================================================"
echo "   SERVER STARTING ON PORT 5001"
echo " ============================================================"
echo ""
echo "   PC Access:        http://localhost:5001"
echo "   Phone Access:     http://$LOCAL_IP:5001"
echo "                     (phone must be on same Wi-Fi)"
echo ""
echo "   Welcome:          http://$LOCAL_IP:5001/welcome"
echo "   Mobile POS:       http://$LOCAL_IP:5001/mobile-bill"
echo "   Cash Drawer:      http://$LOCAL_IP:5001/cash-drawer"
echo "   Payment Verify:   http://$LOCAL_IP:5001/payment-verify"
echo "   Security:         http://$LOCAL_IP:5001/security-dashboard"
echo ""
echo "   Press Ctrl+C to stop the server."
echo " ============================================================"
echo -e "${RESET}"

$PY app.py
