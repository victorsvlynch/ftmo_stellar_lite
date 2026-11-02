# -*- coding: utf-8 -*-
"""
consultar_detalle_operaciones.py
Muestra el detalle exhaustivo de las operaciones de PORTFOLIO MT5
tanto del broker oficial MetaTrader 5 como de la base de datos del servidor.
"""

import sys
import os
import subprocess
from datetime import datetime, timedelta, timezone

def inspect_mt5():
    print("=" * 85)
    print("  1. REGISTRO OFICIAL EN METATRADER 5 (TERMINAL BROKER FUNDEDNEXT)")
    print("=" * 85)
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            print(f"  [!] No se pudo conectar a MetaTrader 5: {mt5.last_error()}")
            return
        
        acc = mt5.account_info()
        if acc:
            print(f"  • Cuenta / Login   : #{acc.login} ({acc.server})")
            print(f"  • Balance Actual   : ${acc.balance:,.2f} {acc.currency}")
            print(f"  • Equidad Actual   : ${acc.equity:,.2f} {acc.currency}")
            print(f"  • Margen Libre     : ${acc.margin_free:,.2f}")
        
        # Posiciones Abiertas
        positions = mt5.positions_get()
        print("-" * 85)
        if positions:
            print(f"  [POSICIONES ABIERTAS EN MT5: {len(positions)}]")
            for p in positions:
                p_type = "BUY" if p.type == 0 else "SELL"
                print(f"    - Ticket #{p.ticket} | {p.symbol} {p_type} {p.volume:.2f}L | Entrada: {p.price_open:.5f} | SL: {p.sl:.5f} | TP: {p.tp:.5f} | Actual: {p.price_current:.5f} | PnL: ${p.profit:+,.2f}")
        else:
            print("  >> POSICIONES ABIERTAS EN MT5: 0 (Sin riesgo flotante activo) <<")
        
        # Historial de Deals hoy
        from_dt = datetime.now() - timedelta(days=1)
        to_dt = datetime.now() + timedelta(days=1)
        deals = mt5.history_deals_get(from_dt, to_dt)
        print("-" * 85)
        print("  [HISTORIAL DE TRANSACCIONES HOY EN MT5 (DEALS CERRADOS)]")
        if deals:
            total_profit = 0.0
            for d in deals:
                if d.entry == 1 or d.profit != 0: # Salidas o transacciones con PnL
                    d_type = "SELL (Cierre Buy)" if d.type == 1 else "BUY (Cierre Sell)"
                    time_str = datetime.fromtimestamp(d.time).strftime("%Y-%m-%d %H:%M:%S")
                    print(f"    - Deal #{d.ticket} | Pos #{d.position_id} | {d.symbol:<7} {d.volume:.2f}L @ {d.price:.5f} | Beneficio: ${d.profit:>+7.2f} | Hora: {time_str}")
                    total_profit += d.profit
            print("-" * 85)
            print(f"  • Beneficio Neto Realizado Hoy en MT5: ${total_profit:+,.2f} USD")
        else:
            print("  >> Sin transacciones cerradas hoy en MT5 <<")
            
        mt5.shutdown()
    except Exception as e:
        print(f"  [!] Error al consultar MT5: {e}")
    print()

def inspect_vps():
    print("=" * 85)
    print("  2. REGISTRO ALGORÍTMICO EN EL SERVIDOR NUBE (trading_ny_open.db)")
    print("=" * 85)
    key_path = os.path.expanduser(r"~\.ssh\oracle_vps.key")
    if not os.path.exists(key_path):
        key_path = os.path.expanduser(r"~\.ssh\ssh-key-2026-10-26.key")
    if not os.path.exists(key_path):
        key_path = os.path.join(os.path.dirname(__file__), "VPS-Oracle", "oracle_vps.key")
        
    script = """
import sqlite3
conn = sqlite3.connect('/home/ubuntu/FTMO_Stellar_Lite/trading_ny_open.db')
cur = conn.cursor()
cur.execute("SELECT id, symbol, side, lots, entry_price, exit_price, pnl, status, opened_at, closed_at, notes FROM trades WHERE status='CLOSED' ORDER BY id DESC LIMIT 10")
rows = cur.fetchall()
if rows:
    for r in rows:
        tid, sym, side, lots, entry, exit_p, pnl, status, op, cl, notes = r
        op_h = str(op)[11:19] if op else '-'
        cl_h = str(cl)[11:19] if cl else '-'
        print(f"    - #{tid:<2} | {sym:<8} {side:<4} {lots:.2f}L | Entrada: {entry:<8.4f} | Salida: {exit_p:<8.4f} | PnL: ${pnl:>+7.2f} | {cl_h} UTC | {notes[:40]}")
else:
    print("    >> Sin trades registrados <<")
conn.close()
"""
    try:
        res = subprocess.run(
            ["ssh", "-i", key_path, "-o", "StrictHostKeyChecking=no", "ubuntu@157.137.225.144", "python3"],
            input=script, text=True, capture_output=True, timeout=10
        )
        print(res.stdout)
    except Exception as e:
        print(f"  [!] No se pudo conectar al VPS: {e}")
    print("=" * 85)

if __name__ == "__main__":
    inspect_mt5()
    inspect_vps()
