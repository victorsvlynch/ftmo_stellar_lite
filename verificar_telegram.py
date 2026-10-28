#!/usr/bin/env python3
"""
verificar_telegram.py - Escucha activa y envío del mensaje de bienvenida
Configuración segura: Lee credenciales de variables de entorno o telegram_config.json
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from typing import Tuple


def load_credentials() -> Tuple[str, str, str, str]:
    """
    Carga de forma segura bot_token, chat_id, username y bot_username sin exponer secretos.
    Prioridad:
    1. Variables de entorno (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    2. Archivo local seguro telegram_config.json (ignorado por git)
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    username = os.getenv("TELEGRAM_USERNAME", "@victorsvlynch").strip()
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "@victor_stellar_bot").strip()

    # Si no están completos en variables de entorno, buscar en telegram_config.json
    if not token or not chat_id:
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_config.json"),
            os.path.join(os.getcwd(), "telegram_config.json"),
            "/home/ubuntu/FTMO_Stellar_Lite/telegram_config.json",
        ]
        for cfg_path in candidates:
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        token = token or cfg.get("bot_token", "").strip()
                        chat_id = chat_id or str(cfg.get("chat_id", "")).strip()
                        username = cfg.get("username", username).strip()
                        bot_username = cfg.get("bot_username", bot_username).strip()
                        if token and chat_id:
                            break
                except Exception:
                    pass

    return token, chat_id, username, bot_username


def try_send(token: str, chat_id: str, username: str) -> Tuple[bool, str]:
    """Envía mensaje de bienvenida al canal de Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    text = (
        "<b>🎉 ¡CONEXIÓN 100% EXITOSA CON FUNDEDNEXT STELLAR LITE!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Hola <b>{username}</b> 👋\n\n"
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
        "chat_id": chat_id,
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


def main():
    token, chat_id, username, bot_username = load_credentials()

    if not token or not chat_id:
        print("[ERROR] No se encontraron credenciales de Telegram configuradas.")
        print("Por favor realiza una de las siguientes opciones:")
        print(" 1. Ejecuta 'Configurar_Telegram.bat' (o 'python configurar_telegram.py').")
        print(" 2. Crea 'telegram_config.json' a partir de 'telegram_config.json.example'.")
        print(" 3. Establece las variables de entorno TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.")
        sys.exit(1)

    print(f"Iniciando escucha activa de Telegram (Esperando que presiones 'INICIAR' en {bot_username})...")
    for i in range(45):
        ok, resp = try_send(token, chat_id, username)
        if ok:
            print("\n=======================================================")
            print("[EXITO TOTAL] ¡Mensaje de bienvenida recibido en Telegram!")
            print("=======================================================")
            sys.exit(0)
        time.sleep(2)
        print(".", end="", flush=True)
    print(f"\nTiempo de espera agotado. Recuerda presionar 'INICIAR' en {bot_username}.")


if __name__ == "__main__":
    main()
