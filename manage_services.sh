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
TEST_SERVICES=(
    "stellar_test_oro.service"
    "stellar_test_eurusd.service"
    "stellar_test_sp500.service"
)
WEBHOOK_SERVICE="stellar_webhook.service"
ALL_PORTFOLIO_SERVICES=(
    "$WINNER_SERVICE"
    "$WEBHOOK_SERVICE"
    "${TEST_SERVICES[@]}"
)
SERVICES=(
    "$WINNER_SERVICE"
    "$WEBHOOK_SERVICE"
    "${TEST_SERVICES[@]}"
)
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ACTION="${1:-status}"

case "${ACTION}" in
    winner|solo-ganadora|winner-only)
        echo "=============================================================================="
        echo " [MODO EXCLUSIVO] Activando Portafolio Oficial MT5 (Oro+EUR/USD+SP500) + Webhook"
        echo "=============================================================================="
        sudo systemctl enable "$WINNER_SERVICE" "$WEBHOOK_SERVICE" 2>/dev/null || true
        sudo systemctl restart "$WINNER_SERVICE" "$WEBHOOK_SERVICE"
        echo "[OK] Portafolio Oficial MT5 y Webhook activos."
        python3 "${APP_DIR}/main.py" multi-status
        ;;
    all|start-all|portfolio-test)
        echo "=============================================================================="
        echo " Activando Portafolio Oficial MT5 + 3 Laboratorios de Test Sandbox Internos"
        echo "=============================================================================="
        sudo systemctl enable "${ALL_PORTFOLIO_SERVICES[@]}" 2>/dev/null || true
        sudo systemctl restart "${ALL_PORTFOLIO_SERVICES[@]}"
        echo "[OK] Todos los servicios activos (MT5 Oficial + 3 Sandbox de Test)."
        python3 "${APP_DIR}/main.py" multi-status
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
        echo "[*] Reiniciando todas las bases de datos a \$10,000.00..."
        python3 "${APP_DIR}/main.py" reset-all
        ;;
    *)
        echo "Uso: ./manage_services.sh {start-all|stop-all|restart-all|status|detail|detail-status|reset-all}"
        exit 1
        ;;
esac
