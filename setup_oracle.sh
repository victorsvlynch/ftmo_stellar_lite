#!/usr/bin/env bash
# ==============================================================================
# setup_oracle.sh - Script de Aprovisionamiento Automatizado para Oracle Cloud (OCI)
# Sistema Operativo Objetivo: Linux Ubuntu (20.04 / 22.04 / 24.04 LTS)
# ==============================================================================

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="fundednext_bot.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
RUN_USER="${SUDO_USER:-$(whoami)}"

echo "=============================================================================="
echo " Iniciando configuración de FundedNext Stellar Lite Bot en Oracle Cloud (OCI)"
echo " Directorio de aplicación : ${APP_DIR}"
echo " Usuario de ejecución     : ${RUN_USER}"
echo "=============================================================================="

# 1. Verificar e instalar python3, python3-pip y tzdata
echo "[1/5] Verificando paquetes del sistema (python3, python3-pip, tzdata)..."
sudo apt-get update -y -q
if ! command -v python3 >/dev/null 2>&1; then
    sudo apt-get install -y python3
fi
if ! command -v pip3 >/dev/null 2>&1; then
    sudo apt-get install -y python3-pip
fi
sudo apt-get install -y tzdata iptables-persistent || true

# 2. Instalar dependencias globales desde requirements.txt (sin venv ni Docker)
echo "[2/5] Instalando librerías de Python en entorno global (pandas, numpy, yfinance, ccxt, multitasking, backports, tzdata)..."
sudo pip3 install --no-cache-dir "multitasking<=0.0.11" "backports.zoneinfo" "tzdata" 2>/dev/null || true
if pip3 install --help | grep -q -- "--break-system-packages"; then
    sudo pip3 install --break-system-packages -r "${APP_DIR}/requirements.txt"
else
    sudo pip3 install -r "${APP_DIR}/requirements.txt"
fi
sudo sed -i 's/type\[Thread\]/Thread/g; s/type\[Process\]/Process/g' /usr/local/lib/python3.8/dist-packages/multitasking/__init__.py 2>/dev/null || true

# 3. Abrir puerto 8501 en el firewall del servidor (UFW / iptables en OCI)
echo "[3/5] Configurando reglas de red y abriendo el puerto TCP 8501..."
if command -v ufw >/dev/null 2>&1; then
    sudo ufw allow 8501/tcp || true
fi
sudo iptables -C INPUT -p tcp --dport 8501 -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT 1 -p tcp --dport 8501 -j ACCEPT
if command -v netfilter-persistent >/dev/null 2>&1; then
    sudo netfilter-persistent save || true
fi

# 4. Asegurar permisos de ejecución y propiedad del directorio
echo "[4/5] Ajustando permisos de archivos..."
chmod +x "${APP_DIR}/main.py"
chmod +x "${APP_DIR}/manage_services.sh" 2>/dev/null || true
sudo chown -R "${RUN_USER}:${RUN_USER}" "${APP_DIR}"

# 5. Crear y habilitar los 5 servicios systemd independientes para cada modalidad
echo "[5/5] Creando servicios systemd para las 5 modalidades independientes..."

# Detener y remover servicio antiguo de London_NY si existe
sudo systemctl stop stellar_london_ny.service 2>/dev/null || true
sudo systemctl disable stellar_london_ny.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/stellar_london_ny.service 2>/dev/null || true

# Modalidad 1: NY_OPEN (Apertura 08:30-11:30 EST | Oro GC=F | Base de datos trading_ny_open.db)
sudo tee "/etc/systemd/system/stellar_ny_open.service" > /dev/null <<EOF
[Unit]
Description=FundedNext Stellar Lite - Modalidad 1: NY_OPEN (Oro GC=F)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${APP_DIR}
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 ${APP_DIR}/main.py run --symbol GC=F --provider yfinance --risk 0.005 --personal-cap 0.02 --session NY_OPEN --db trading_ny_open.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Modalidad 2: LONDON_OPEN (Apertura 03:00-06:00 EST | Oro GC=F | Base de datos trading_london_open.db)
sudo tee "/etc/systemd/system/stellar_london_open.service" > /dev/null <<EOF
[Unit]
Description=FundedNext Stellar Lite - Modalidad 2: LONDON_OPEN (Oro GC=F)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${APP_DIR}
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 ${APP_DIR}/main.py run --symbol GC=F --provider yfinance --risk 0.005 --personal-cap 0.02 --session LONDON_OPEN --db trading_london_open.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Modalidad 3: CRYPTO_24H (24 Horas Continuas | BTC/USDT | Base de datos trading_crypto_24h.db)
sudo tee "/etc/systemd/system/stellar_crypto_24h.service" > /dev/null <<EOF
[Unit]
Description=FundedNext Stellar Lite - Modalidad 3: CRYPTO_24H (BTC/USDT)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${APP_DIR}
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 ${APP_DIR}/main.py run --symbol BTC/USDT --provider ccxt --risk 0.005 --personal-cap 0.02 --session ALL --db trading_crypto_24h.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Modalidad 4: NY_OPEN + LONDON (Combo Dual: 03:00-06:00 EST + 08:30-11:30 EST | Oro GC=F | Base de datos trading_ny_london.db)
sudo tee "/etc/systemd/system/stellar_ny_london.service" > /dev/null <<EOF
[Unit]
Description=FundedNext Stellar Lite - Modalidad 4: NY_OPEN + LONDON (Oro GC=F)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${APP_DIR}
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 ${APP_DIR}/main.py run --symbol GC=F --provider yfinance --risk 0.005 --personal-cap 0.02 --session COMBO_DUAL --db trading_ny_london.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Modalidad 5: NY + LDN + CRYPTO 24H (Combo Trío 24/7: Oro en Londres/NY + Cripto BTC 24/7 | Base de datos trading_combo_trio.db)
sudo tee "/etc/systemd/system/stellar_combo_trio.service" > /dev/null <<EOF
[Unit]
Description=FundedNext Stellar Lite - Modalidad 5: NY_OPEN + LONDON + CRYPTO_24H (Multi-Activo)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${APP_DIR}
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 ${APP_DIR}/main.py run --symbol GC=F,BTC/USDT --provider multi --risk 0.005 --personal-cap 0.02 --session COMBO_TRIO --db trading_combo_trio.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Limpiar y remover servicio duplicado fundednext_bot si existe
sudo systemctl stop fundednext_bot.service 2>/dev/null || true
sudo systemctl disable fundednext_bot.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/fundednext_bot.service 2>/dev/null || true

# Servicio Webhook Bridge para MetaTrader 5 (Puerto 8000)
sudo tee "/etc/systemd/system/stellar_webhook.service" > /dev/null <<EOF
[Unit]
Description=FundedNext Stellar Lite - MT5 Webhook Bridge Server (Port 8000)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${APP_DIR}
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 ${APP_DIR}/webhook_server.py 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
# Habilitar y arrancar unicamente la Estrategia Ganadora NY_OPEN y el Webhook Bridge
sudo systemctl enable stellar_ny_open.service stellar_webhook.service
sudo systemctl restart stellar_ny_open.service stellar_webhook.service

echo "=============================================================================="
echo " Instalación y despliegue completado con éxito."
echo " - Estrategia Ganadora : sudo systemctl status stellar_ny_open"
echo " - Servidor Webhook    : sudo systemctl status stellar_webhook"
echo " - Gestor de Servicios : ${APP_DIR}/manage_services.sh solo-ganadora"
echo " - Monitor Consolidado : python3 ${APP_DIR}/main.py multi"
echo "=============================================================================="
