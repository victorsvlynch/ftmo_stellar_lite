#!/usr/bin/env bash
# ==============================================================================
# manage_services.sh - Gestor Multi-Servicio de Modalidades FTMO Stellar Lite
# Controla las 5 modalidades independientes:
# 1. stellar_ny_open.service
# 2. stellar_london_open.service
# 3. stellar_crypto_24h.service
# 4. stellar_ny_london.service
# 5. stellar_combo_trio.service
# ==============================================================================

set -e

WINNER_SERVICE="stellar_ny_open.service"
RETIRED_SERVICES=(
    "stellar_london_open.service"
    "stellar_crypto_24h.service"
    "stellar_ny_london.service"
    "stellar_combo_trio.service"
)
SERVICES=(
    "$WINNER_SERVICE"
    "${RETIRED_SERVICES[@]}"
)
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ACTION="${1:-status}"

case "${ACTION}" in
    winner|solo-ganadora|winner-only)
        echo "=============================================================================="
        echo " [MODO EXCLUSIVO] Activando unicamente Estrategia Ganadora: NY_OPEN + Webhook"
        echo "=============================================================================="
        echo "[1/2] Deteniendo y deshabilitando modalidades secundarias y procesos duplicados..."
        sudo systemctl stop "${RETIRED_SERVICES[@]}" fundednext_bot.service 2>/dev/null || true
        sudo systemctl disable "${RETIRED_SERVICES[@]}" fundednext_bot.service 2>/dev/null || true
        echo "[2/2] Iniciando y habilitando servicio ganador ($WINNER_SERVICE) y webhook..."
        sudo systemctl enable "$WINNER_SERVICE" stellar_webhook.service 2>/dev/null || true
        sudo systemctl restart "$WINNER_SERVICE" stellar_webhook.service
        echo "[OK] Estrategia ganadora NY_OPEN y Webhook activos y en ejecucion."
        python3 "${APP_DIR}/main.py" winner
        ;;
    start-all)
        echo "[*] Iniciando todos los servicios de trading..."
        sudo systemctl start "${SERVICES[@]}"
        echo "[OK] Servicios iniciados."
        ;;
    stop-all)
        echo "[*] Deteniendo todos los servicios de trading..."
        sudo systemctl stop "${SERVICES[@]}"
        echo "[OK] Servicios detenidos."
        ;;
    restart-all)
        echo "[*] Reiniciando todos los servicios de trading..."
        sudo systemctl restart "${SERVICES[@]}"
        echo "[OK] Servicios reiniciados."
        ;;
    status)
        echo "=============================================================================="
        echo " Estado de Servicios Systemd de Trading (FTMO Stellar Lite)"
        echo "=============================================================================="
        for s in "${SERVICES[@]}"; do
            ACTIVE=$(systemctl is-active "$s" 2>/dev/null || echo "inactivo")
            ENABLED=$(systemctl is-enabled "$s" 2>/dev/null || echo "deshabilitado")
            printf " - %-30s : Estado: %-10s | Arranque: %s\n" "$s" "$ACTIVE" "$ENABLED"
        done
        echo "=============================================================================="
        python3 "${APP_DIR}/main.py" multi-status
        ;;
    detail)
        python3 "${APP_DIR}/main.py" multi-detail
        ;;
    detail-status)
        python3 "${APP_DIR}/main.py" multi-detail-status
        ;;
    reset-all)
        echo "[*] Reiniciando todas las bases de datos a \$5,000.00..."
        python3 "${APP_DIR}/main.py" reset-all
        ;;
    *)
        echo "Uso: ./manage_services.sh {start-all|stop-all|restart-all|status|detail|detail-status|reset-all}"
        exit 1
        ;;
esac
