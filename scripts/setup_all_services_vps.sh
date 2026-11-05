#!/usr/bin/env bash
set -e

APP_DIR="/home/ubuntu/FTMO_Stellar_Lite"

# 1. Servicio Oficial MT5 (Portafolio 3 Activos $10K con Webhook a MT5)
sudo tee "/etc/systemd/system/stellar_ny_open.service" > /dev/null << 'EOF'
[Unit]
Description=FundedNext Stellar Lite - Portafolio Oficial MT5 (Oro + EUR/USD + S&P 500 $10K)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/FTMO_Stellar_Lite
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/ubuntu/FTMO_Stellar_Lite/main.py run --symbol GC=F,EURUSD=X,ES=F,USDJPY=X --provider mt5 --risk 0.005 --personal-cap 0.02 --session PORTFOLIO_DUAL --db trading_ny_open.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 2. Servicio Test Sandbox 1: ORO Individual ($10K Interno Sin MT5)
sudo tee "/etc/systemd/system/stellar_test_oro.service" > /dev/null << 'EOF'
[Unit]
Description=FundedNext Stellar Lite - Test Individual ORO (Sandbox $10K Interno)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/FTMO_Stellar_Lite
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/ubuntu/FTMO_Stellar_Lite/main.py run --symbol GC=F --provider yfinance --risk 0.005 --personal-cap 0.02 --session NY_OPEN --db trading_test_oro.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 3. Servicio Test Sandbox 2: EUR/USD Individual ($10K Interno Sin MT5)
sudo tee "/etc/systemd/system/stellar_test_eurusd.service" > /dev/null << 'EOF'
[Unit]
Description=FundedNext Stellar Lite - Test Individual EUR/USD (Sandbox $10K Interno)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/FTMO_Stellar_Lite
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/ubuntu/FTMO_Stellar_Lite/main.py run --symbol EURUSD=X --provider yfinance --risk 0.005 --personal-cap 0.02 --session PORTFOLIO_DUAL --db trading_test_eurusd.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 4. Servicio Test Sandbox 3: S&P 500 Individual ($10K Interno Sin MT5)
sudo tee "/etc/systemd/system/stellar_test_sp500.service" > /dev/null << 'EOF'
[Unit]
Description=FundedNext Stellar Lite - Test Individual S&P 500 (Sandbox $10K Interno)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/FTMO_Stellar_Lite
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/ubuntu/FTMO_Stellar_Lite/main.py run --symbol ES=F --provider yfinance --risk 0.005 --personal-cap 0.02 --session PORTFOLIO_DUAL --db trading_test_sp500.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable stellar_ny_open.service stellar_webhook.service stellar_test_oro.service stellar_test_eurusd.service stellar_test_sp500.service
sudo systemctl restart stellar_ny_open.service stellar_webhook.service stellar_test_oro.service stellar_test_eurusd.service stellar_test_sp500.service

echo "=============================================================================="
echo " SERVICIOS INSTALADOS Y EN EJECUCION EN ORACLE CLOUD VPS"
echo "=============================================================================="
sudo systemctl is-active stellar_ny_open.service stellar_webhook.service stellar_test_oro.service stellar_test_eurusd.service stellar_test_sp500.service
