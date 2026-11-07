"""
friday_guardian.py - Guardián Autónomo de Cierre de Viernes y Protección Anti-Gap
----------------------------------------------------------------------------------
Diseñado para operar de forma independiente a cualquier bucle o servicio.
Inspecciona directamente todas las instancias locales de MetaTrader 5 activas.

Lógica Institucional de Viernes:
1. Verifica si es viernes y si la hora de Nueva York (EST) ha alcanzado la ventana
   de cierre de fin de semana (por defecto a partir de las 15:30 EST / 3:30 PM).
2. Si encuentra posiciones abiertas en activos tradicionales (Forex, Índices, Metales):
   - Cierra ordenadamente cada posición a mercado mediante la API oficial de MT5.
   - Registra el cierre en el log local.
   - Envía notificación crítica a Telegram si está configurado.
3. Si el parámetro --force está presente o es invocado manualmente, realiza el chequeo
   y cierre inmediato sin importar el horario.
"""

import sys
import os
import time
import argparse
import datetime
from typing import List, Dict, Any, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import MetaTrader5 as mt5

# Directorio base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "friday_guardian.log")

# Rutas estándar de terminales MT5 en el entorno
KNOWN_TERMINAL_PATHS = [
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
    r"C:\Program Files\MetaTrader 5 - 2\terminal64.exe",
]


def log_msg(msg: str):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{now_str}] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def send_telegram_alert(text: str):
    """Envía notificación usando el módulo telegram_notifier del proyecto si existe."""
    try:
        sys.path.insert(0, BASE_DIR)
        from telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        if notifier.is_configured():
            notifier.send_message(text)
    except Exception as e:
        log_msg(f"Aviso: No se pudo enviar alerta por Telegram: {e}")


def is_friday_close_time(now_utc: Optional[datetime.datetime] = None, trigger_minute_est: int = 15 * 60 + 30) -> bool:
    """
    Retorna True si es viernes y la hora de NY (EST) es >= 15:30 (o trigger_minute_est).
    """
    if now_utc is None:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
    
    try:
        ny_tz = ZoneInfo("America/New_York")
    except Exception:
        # Fallback a UTC-5 fijo
        ny_tz = datetime.timezone(datetime.timedelta(hours=-5))
        
    dt_ny = now_utc.astimezone(ny_tz)
    is_friday = (dt_ny.weekday() == 4)
    current_minutes = dt_ny.hour * 60 + dt_ny.minute
    
    return is_friday and (current_minutes >= trigger_minute_est)


def close_single_position(pos, terminal_path: str) -> bool:
    """Cierra una posición abierta en MT5 con reintentos y tolerancia a slippage."""
    ticket = pos.ticket
    symbol = pos.symbol
    lot = pos.volume
    pos_type = pos.type  # 0: BUY, 1: SELL
    
    # Preparar orden contraria
    order_type = mt5.ORDER_TYPE_SELL if pos_type == 0 else mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(symbol).bid if pos_type == 0 else mt5.symbol_info_tick(symbol).ask
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": ticket,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": pos.magic,
        "comment": "Auto-Friday Close Guardian",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    # Intento 1: con ORDER_FILLING_IOC
    res = mt5.order_send(request)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        log_msg(f"EXITO: Posición #{ticket} ({symbol} {lot}L) cerrada correctamente a {price}. Retcode: {res.retcode}")
        return True
        
    # Reintento con filling FOK o RETURN si el broker lo rechaza
    for filling in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
        request["type_filling"] = filling
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            request["price"] = tick.bid if pos_type == 0 else tick.ask
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log_msg(f"EXITO: Posición #{ticket} ({symbol}) cerrada en reintento filling {filling}. Retcode: {res.retcode}")
            return True
            
    err_code = mt5.last_error()
    log_msg(f"ERROR: Falló el cierre de posición #{ticket} ({symbol}). Retcode: {getattr(res, 'retcode', 'N/A')}, Error MT5: {err_code}")
    return False


def inspect_and_close_friday(force: bool = False) -> int:
    """
    Inspecciona todas las terminales MT5 activas.
    Si se cumple la ventana de viernes (o force=True), liquida posiciones abiertas.
    Retorna el número de posiciones cerradas.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    in_window = is_friday_close_time(now_utc)
    
    if not in_window and not force:
        # Si no está en ventana pero es viernes por la tarde, registrar monitoreo en log
        try:
            ny_tz = ZoneInfo("America/New_York")
        except Exception:
            ny_tz = datetime.timezone(datetime.timedelta(hours=-5))
        dt_ny = now_utc.astimezone(ny_tz)
        if dt_ny.weekday() == 4 and dt_ny.hour >= 12:
            log_msg(f"Monitoreo de Viernes en curso (Hora NY: {dt_ny.strftime('%H:%M:%S')}). Ventana 15:30 EST aun en espera.")
        return 0
        
    log_msg(f"=== ACTIVANDO PROTOCOLO CIERRE DE VIERNES (Force={force}, Window={in_window}) ===")
    total_closed = 0
    closed_summary = []
    
    for t_path in KNOWN_TERMINAL_PATHS:
        if not os.path.exists(t_path):
            continue
            
        initialized = mt5.initialize(path=t_path)
        if not initialized:
            # Intentar conexión por defecto sin path
            if not mt5.initialize():
                continue
                
        try:
            acc = mt5.account_info()
            positions = mt5.positions_get()
            
            if positions and len(positions) > 0:
                acc_id = acc.login if acc else "Desconocido"
                srv = acc.server if acc else "Desconocido"
                log_msg(f"Terminal [{t_path}] - Cuenta: {acc_id} ({srv}) tiene {len(positions)} posición(es) abierta(s).")
                
                for pos in positions:
                    sym_upper = pos.symbol.upper()
                    # Cripto no cierra los fines de semana (24/7)
                    is_crypto = any(c in sym_upper for c in ("BTC", "ETH", "SOL", "USDT"))
                    if is_crypto and not force:
                        log_msg(f"Saltando {pos.symbol} (Criptoactivo 24/7 permitido en weekend).")
                        continue

                    # Discriminación Inteligente por Broker / Perfil:
                    # 1. FTMO (Magic 505001 o Servidor FTMO): Prohibido Weekend Holding -> CIERRE OBLIGATORIO
                    # 2. FundedNext (Magic 505002, 505003 / Servidor FundedNext): Weekend holding permitido
                    srv_lower = (acc.server if acc else "").lower()
                    is_ftmo = (pos.magic == 505001) or ("ftmo" in srv_lower)
                    is_fundednext = (pos.magic in (505002, 505003)) or ("fundednext" in srv_lower)

                    if not force and is_fundednext:
                        # Para FundedNext (stellar_10k_real):
                        # Analizar si la posición está protegida en Break-Even / Ganancia
                        # pos.type == 0 -> BUY, pos.type == 1 -> SELL
                        pos_type = pos.type
                        entry = pos.price_open
                        sl = pos.sl
                        is_be_protected = False
                        
                        if sl > 0.0:
                            if pos_type == 0 and sl >= entry:
                                is_be_protected = True
                            elif pos_type == 1 and sl <= entry:
                                is_be_protected = True

                        # Si está en profit sustancial (> 0) y protegida a Break-Even, permitir weekend holding
                        if is_be_protected and pos.profit >= 0.0:
                            log_msg(
                                f"FundedNext (stellar_10k_real) #{pos.ticket} ({pos.symbol}): "
                                f"Posición PROTEGIDA en Break-Even (SL: {sl} vs Open: {entry}, PnL: ${pos.profit:,.2f}). "
                                f"Se permite Weekend Holding institucional sin riesgo para el capital base."
                            )
                            continue
                        else:
                            log_msg(
                                f"FundedNext (stellar_10k_real) #{pos.ticket} ({pos.symbol}): "
                                f"Posición en riesgo o sin Break-Even (SL: {sl}, Open: {entry}, PnL: ${pos.profit:,.2f}). "
                                f"Liquidando preventivamente antes del cierre para evitar Gap de apertura el domingo."
                            )

                    elif not force and is_ftmo:
                        log_msg(
                            f"FTMO (ftmo_10k_challenge) #{pos.ticket} ({pos.symbol}): "
                            f"Regla estricta NO-WEEKEND. Procediendo a liquidación forzosa a mercado."
                        )

                    log_msg(f"-> Ejecutando cierre institucional para Ticket #{pos.ticket} ({pos.symbol}, PnL: ${pos.profit:,.2f})...")
                    if close_single_position(pos, t_path):
                        total_closed += 1
                        closed_summary.append(f"#{pos.ticket} {pos.symbol} PnL: ${pos.profit:,.2f}")
                        
        finally:
            mt5.shutdown()
            
    if total_closed > 0:
        alert_msg = (
            f"🚨 <b>GUARDIÁN DE VIERNES: CIERRE AUTOMÁTICO EJECUTADO</b>\n\n"
            f"Se cerraron <b>{total_closed}</b> posición(es) abierta(s) para prevenir gaps de fin de semana:\n"
            + "\n".join([f"• {item}" for item in closed_summary]) +
            f"\n\n<i>Cuentas protegidas al 100% para el cierre semanal.</i>"
        )
        send_telegram_alert(alert_msg)
        log_msg(f"Protocolo finalizado. Total de posiciones cerradas: {total_closed}")
    else:
        log_msg("Protocolo de viernes verificado: No se encontraron posiciones que requieran cierre.")
        
    return total_closed


def run_guardian_daemon(poll_interval: int = 30):
    """
    Ejecución continua (Modo Guardián de Fondo):
    Monitorea de forma permanente y, al entrar en la ventana de las 15:30 EST cada viernes,
    procede automáticamente al cierre seguro.
    """
    log_msg("=== INICIANDO GUARDIÁN AUTÓNOMO DE CIERRE DE VIERNES (MODO DAEMON) ===")
    log_msg("Monitoreando cada semana: Viernes a partir de las 15:30 EST (Nueva York).")
    
    while True:
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if is_friday_close_time(now_utc):
                inspect_and_close_friday(force=False)
                # Dormir 60 segundos tras liquidar
                time.sleep(60)
            else:
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            log_msg("Guardián detenido por el usuario.")
            break
        except Exception as e:
            log_msg(f"Excepción en bucle guardián: {e}")
            time.sleep(poll_interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Guardián de Cierre de Viernes MT5")
    parser.add_argument("--force", action="store_true", help="Fuerza el cierre inmediato de posiciones abiertas ahora mismo.")
    parser.add_argument("--check", action="store_true", help="Solo verifica el estado de las posiciones y la ventana de viernes.")
    parser.add_argument("--daemon", action="store_true", help="Inicia el servicio guardián en bucle permanente.")
    args = parser.parse_args()
    
    if args.check:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        in_win = is_friday_close_time(now_utc)
        print(f"Estado de ventana de viernes (15:30 EST): {'ACTIVA' if in_win else 'INACTIVA'}")
        # Reportar posiciones
        for t_path in KNOWN_TERMINAL_PATHS:
            if os.path.exists(t_path) and mt5.initialize(path=t_path):
                acc = mt5.account_info()
                pos = mt5.positions_get()
                print(f"Terminal {t_path}: Cuenta {acc.login if acc else 'N/A'} - Posiciones abiertas: {len(pos) if pos else 0}")
                mt5.shutdown()
        sys.exit(0)
        
    if args.force:
        closed = inspect_and_close_friday(force=True)
        print(f"Cierre forzado completado. Posiciones cerradas: {closed}")
        sys.exit(0)
        
    if args.daemon:
        run_guardian_daemon()
    else:
        # Por defecto si se ejecuta sin parámetros, inspecciona la ventana
        inspect_and_close_friday(force=False)
