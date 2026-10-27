#!/usr/bin/env python3
"""
test_telegram_signal.py - Disparador de Alerta de Señal Simulada hacia Telegram.
Envía una señal idéntica a una real de la estrategia NY_OPEN en Oro (XAUUSD).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_notifier import TelegramNotifier

def main():
    notifier = TelegramNotifier()
    if not notifier.enabled:
        print("[ERROR] Telegram no esta configurado.")
        print("Por favor ejecuta primero: Configurar_Telegram.bat")
        sys.exit(1)

    print("Enviando señal de prueba institucional NY_OPEN a Telegram (@victorsvlynch)...")
    ok = notifier.notify_signal_alert(
        symbol="XAUUSD",
        side="BUY",
        lots=0.05,
        price=4062.50,
        sl=4056.00,
        tp=4075.50,
        risk_usd=25.00,
        risk_pct=0.005,
        strategy="NY_OPEN",
        comment="Señal de Prueba fundednext",
    )

    if ok:
        print("[EXITO] ¡Alerta enviada correctamente! Revisa tu celular en Telegram.")
    else:
        print("[FALLO] No se pudo enviar el mensaje. Verifica tu token y conexión.")

if __name__ == "__main__":
    main()
