#!/usr/bin/env bash
set -e

sudo tee "/etc/systemd/system/stellar_ny_open.service" > /dev/null << 'EOF'
[Unit]
Description=FundedNext Stellar Lite - Portafolio Multi-Activo (Oro, EUR/USD, S&P 500)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/FTMO_Stellar_Lite
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/ubuntu/FTMO_Stellar_Lite/main.py run --symbol GC=F,EURUSD=X,ES=F --provider yfinance --risk 0.005 --personal-cap 0.02 --session PORTFOLIO_DUAL --db trading_ny_open.db --interval 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl restart stellar_ny_open.service stellar_webhook.service
echo "[OK] stellar_ny_open.service actualizado con exito a Portafolio Multi-Activo (Oro, EUR/USD, S&P 500)"
sudo systemctl is-active stellar_ny_open.service stellar_webhook.service
