#!/usr/bin/env python3
"""
verificar_telegram.py - Escucha activa y envío del mensaje de bienvenida
"""

import urllib.request
import urllib.error
import json
import time
import sys

TOKEN = "9220253435:AAFqviZYArllMS2jOGJYlB_O-MI6zAL9kK8"
CHAT_ID = "5633051604"

def try_send():
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    text = (
        "<b>🎉 ¡CONEXIÓN 100% EXITOSA CON FUNDEDNEXT STELLAR LITE!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Hola <b>@victorsvlynch</b> 👋\n\n"
        "Tu canal de alertas de trading institucional en tu celular está <b>ACTIVO Y VINCULADO</b>.\n\n"
        "<b>📱 RESUMEN DE TU SISTEMA:</b>\n"
        "• <b>Cuenta:</b> FundedNext Stellar Lite ($5,000 USD)\n"
        "• <b>Activo:</b> Oro (XAUUSD)\n"
        "• <b>Estrategia:</b> NY_OPEN (8:30 - 11:30 AM NY)\n"
        "• <b>Gestión de Riesgo:</b> 0.5% por operación ($25 USD) | R:R 1:2\n"
        "• <b>Servidor 24/7:</b> Oracle Cloud VPS (157.137.225.144)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Cuando el bot en la nube detecte una oportunidad, recibirás aquí la señal con lotes, Stop Loss y Take Profit para abrirla en tu app MT5 del celular.\n\n"
        f"<i>Vinculación verificada: {now_str}</i>"
    )
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True, resp.read().decode()
    except urllib.error.HTTPError as e:
        return False, e.read().decode()
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    print("Iniciando escucha activa de Telegram (Esperando que presiones 'INICIAR')...")
    for i in range(45):
        ok, resp = try_send()
        if ok:
            print("\n=======================================================")
            print("[EXITO TOTAL] ¡Mensaje de bienvenida recibido en Telegram!")
            print("=======================================================")
            sys.exit(0)
        time.sleep(2)
        print(".", end="", flush=True)
    print("\nTiempo de espera agotado. Recuerda presionar 'INICIAR' en @victor_stellar_bot.")
