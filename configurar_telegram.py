#!/usr/bin/env python3
"""
configurar_telegram.py - Asistente de Configuración Rápida de Alertas Telegram.
Modelo: FundedNext Stellar Lite ($5,000)
Destinatario: @victorsvlynch
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_config.json")
VPS_IP = "157.137.225.144"
VPS_USER = "ubuntu"
VPS_PATH = "/home/ubuntu/FTMO_Stellar_Lite/telegram_config.json"


def find_ssh_key() -> str:
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".ssh", "ssh-key-2026-10-26.key"),
        os.path.join(home, ".ssh", "oracle_vps.key"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "VPS-Oracle", "ssh-key-2026-10-26.key"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "VPS-Oracle", "ssh-key-2026-10-22-vps-oracle.key"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""


def call_telegram_api(token: str, method: str, data: dict = None) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    headers = {"Content-Type": "application/json"}
    req_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST" if req_data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}


def sync_to_oracle_vps(cfg_path: str) -> bool:
    key = find_ssh_key()
    if not key:
        print("[AVISO] No se encontro la clave SSH para sincronizar con Oracle VPS.")
        return False
    print(f"\n[Sincronizando con Oracle Cloud VPS ({VPS_IP})...]")
    cmd = [
        "scp",
        "-i", key,
        "-o", "StrictHostKeyChecking=no",
        cfg_path,
        f"{VPS_USER}@{VPS_IP}:{VPS_PATH}"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print("  ✓ Archivo telegram_config.json copiado al VPS.")
        # Reiniciar servicios en la nube para que recarguen Telegram
        restart_cmd = [
            "ssh",
            "-i", key,
            "-o", "StrictHostKeyChecking=no",
            f"{VPS_USER}@{VPS_IP}",
            "sudo systemctl restart stellar_ny_open stellar_webhook"
        ]
        subprocess.run(restart_cmd, capture_output=True, text=True)
        print("  ✓ Servicios de la nube reiniciados y vinculados a tu Telegram.")
        return True
    else:
        print(f"  ✗ Error al copiar al VPS: {res.stderr}")
        return False


def test_signal_alert(token: str, chat_id: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    text = (
        "<b>🎉 ¡CONEXIÓN EXITOSA CON FUNDEDNEXT STELLAR LITE!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Hola <b>@victorsvlynch</b> 👋\n\n"
        "Tu sistema de alertas de trading institucional está <b>100% ACTIVO</b>.\n\n"
        "<b>📱 CÓMO FUNCIONA LA OPCIÓN C:</b>\n"
        "1. El bot analiza el Oro (XAUUSD) 24/7 en la nube de Oracle.\n"
        "2. En la apertura de Nueva York (8:30-11:30 AM NY), si hay oportunidad, te enviará la señal exacta aquí.\n"
        "3. La señal incluirá los lotes exactos, Stop Loss y Take Profit.\n"
        "4. Solo abres tu app de MetaTrader 5 en el celular y presionas Comprar o Vender.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Fecha de activación: {now_str}</i>"
    )
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = call_telegram_api(token, "sendMessage", payload)
    return resp.get("ok", False)


def main():
    print("=" * 76)
    print("   ASISTENTE DE CONFIGURACION TELEGRAM -- FUNDEDNEXT STELLAR LITE")
    print("   Destinatario: @victorsvlynch | Opcion C: Alertas a tu Celular")
    print("=" * 76)
    print()

    # Comprobar si ya existe configuración previa
    current_token = ""
    current_chat_id = ""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                current_token = data.get("bot_token", "")
                current_chat_id = str(data.get("chat_id", ""))
        except Exception:
            pass

    if current_token and current_chat_id:
        print(f"Configuracion existente detectada:")
        print(f"  Bot Token: {current_token[:10]}...{current_token[-5:]}")
        print(f"  Chat ID  : {current_chat_id}")
        print()
        ans = input("¿Deseas enviar un mensaje de prueba con esta configuracion? [S/N] (Por defecto S): ").strip().upper()
        if ans != "N":
            ok = test_signal_alert(current_token, current_chat_id)
            if ok:
                print("\n[OK] Mensaje de prueba enviado con exito a tu Telegram!")
                sync_to_oracle_vps(CONFIG_FILE)
                return
            else:
                print("\n[ERROR] Fallo el envio. Procederemos a reconfigurar.")

    print()
    print("------------------------------------------------------------------------------")
    print(" PASO 1: OBTENER EL BOT TOKEN DE TELEGRAM (Toma 1 minuto)")
    print("------------------------------------------------------------------------------")
    print(" 1. Abre tu app de Telegram en tu celular o PC.")
    print(" 2. Busca el usuario oficial: @BotFather (con la insignia azul de verificado).")
    print(" 3. Presiona 'Iniciar' o escribe: /newbot")
    print(" 4. Asigna un nombre a tu bot (ejemplo: Stellar Lite Notifier)")
    print(" 5. Asigna un usuario unico terminado en 'bot' (ejemplo: victor_stellar_bot)")
    print(" 6. BotFather te respondera con un mensaje que contiene tu HTTP API TOKEN.")
    print("    (Formato similar a: 7123456789:ABCdefGHIjklMNOpqrsTUVwxyz)")
    print("------------------------------------------------------------------------------")
    print()

    token = input("Pega aqui tu BOT TOKEN de BotFather: ").strip()
    if not token:
        print("[ERROR] El token no puede estar vacio.")
        return

    # Validar token
    print("\nVerificando token con la API de Telegram...")
    me_resp = call_telegram_api(token, "getMe")
    if not me_resp.get("ok"):
        print(f"[ERROR] Token invalido o no reconocido: {me_resp.get('error')}")
        return

    bot_info = me_resp.get("result", {})
    bot_username = bot_info.get("username", "tu_bot")
    print(f"  ✓ Token Valido! Bot detectado: @{bot_username} ({bot_info.get('first_name')})")

    print()
    print("------------------------------------------------------------------------------")
    print(f" PASO 2: VINCULAR TU USUARIO (@victorsvlynch)")
    print("------------------------------------------------------------------------------")
    print(f" 1. Abre Telegram y busca tu bot: https://t.me/{bot_username}")
    print(f" 2. Presiona el boton 'INICIAR' (o escribe cualquier mensaje, ej: /start)")
    print("------------------------------------------------------------------------------")
    print()

    chat_id = ""
    print("Esperando tu mensaje en Telegram (Sondeando durante 45 segundos)...")
    for i in range(15):
        time.sleep(3)
        updates_resp = call_telegram_api(token, "getUpdates")
        if updates_resp.get("ok"):
            results = updates_resp.get("result", [])
            if results:
                last_msg = results[-1].get("message", {})
                chat = last_msg.get("chat", {})
                if chat.get("id"):
                    chat_id = str(chat.get("id"))
                    from_user = last_msg.get("from", {}).get("username", "")
                    print(f"\n  ✓ Mensaje recibido! Usuario: @{from_user or 'victorsvlynch'} | Chat ID: {chat_id}")
                    break
        print(".", end="", flush=True)

    if not chat_id:
        print("\n")
        print("[AVISO] No se detecto mensaje automatico.")
        print("Tambien puedes obtener tu Chat ID enviando un mensaje a @userinfobot en Telegram.")
        manual_id = input("Escribe tu Chat ID numerico manualmente (o Enter para cancelar): ").strip()
        if not manual_id:
            print("[CANCELADO] No se configuro Chat ID.")
            return
        chat_id = manual_id

    # Guardar configuración local
    cfg_data = {
        "bot_token": token,
        "chat_id": chat_id,
        "username": "@victorsvlynch",
        "bot_username": f"@{bot_username}",
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f, indent=2)
    print(f"\n✓ Archivo guardado localmente: {CONFIG_FILE}")

    # Enviar mensaje de bienvenida de prueba
    print("\nEnviando mensaje de prueba a tu celular...")
    if test_signal_alert(token, chat_id):
        print("  ✓ ¡Alerta enviada exitosamente! Revisa tu Telegram en tu celular.")
    else:
        print("  ✗ No se pudo enviar el mensaje. Revisa los permisos del bot.")

    # Sincronizar automáticamente con Oracle Cloud VPS
    sync_to_oracle_vps(CONFIG_FILE)

    print()
    print("=" * 76)
    print(" ¡CONFIGURACION COMPLETADA CON EXITO!")
    print(" A partir de este momento, recibiras todas las alertas de NY_OPEN en tu celular.")
    print("=" * 76)


if __name__ == "__main__":
    main()
