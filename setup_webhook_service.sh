#!/usr/bin/env bash
set -e

cat << 'EOF' > /etc/systemd/system/stellar_webhook.service
[Unit]
Description=FundedNext Stellar Lite - MT5 Webhook Bridge Server (Port 8000)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/FTMO_Stellar_Lite
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/ubuntu/FTMO_Stellar_Lite/webhook_server.py 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable stellar_webhook.service
systemctl restart stellar_webhook.service
systemctl status stellar_webhook.service --no-pager
