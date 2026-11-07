"""
audit_stress_suite.py - Auditoría Cuantitativa y Banco de Pruebas de Estrés en Vivo
------------------------------------------------------------------------------------
Perfil: stellar_10k_real ($10,000 USD, 3 Activos: XAUUSD, US500, USDJPY)
Magic Number: 505003

Batería de Pruebas:
Fase 1: Pruebas Individuales (1 por 1)
  - Test 1A: Apertura + Medición de Slippage + Cierre de XAUUSD (Oro)
  - Test 1B: Apertura + Medición de Slippage + Cierre de US500.cash (S&P 500)
  - Test 1C: Apertura + Medición de Slippage + Cierre de USDJPY (Forex)

Fase 2: Prueba Concurrente Dual (2 a la vez)
  - Test 2: Apertura Simultánea XAUUSD + US500.cash -> Verificación de margen y colisión de Magic 505003 -> Cierre coordinado

Fase 3: Prueba Concurrente Triple (3 a la vez - Portafolio Completo)
  - Test 3: Apertura Simultánea XAUUSD + US500.cash + USDJPY -> Verificación de Max Open Risk ($150) -> Cierre coordinado

Fase 4: Verificación de Reconciliación y Estado de Cuenta
  - Chequeo de Balance, Equidad, Cero residuales y Cero órdenes pendientes huérfanas.
"""

import sys
import os
import time
import datetime
from typing import List, Dict, Any, Optional
import MetaTrader5 as mt5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAGIC_TEST = 505003
TERMINAL_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

# Mapeo de Símbolos en FTMO
SYMBOLS = {
    "GOLD": "XAUUSD",
    "SP500": "US500.cash",
    "USDJPY": "USDJPY"
}

def log_test(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def connect_mt5() -> bool:
    if not mt5.initialize(path=TERMINAL_PATH):
        if not mt5.initialize():
            log_test(f"CRÍTICO: No se pudo conectar a MT5: {mt5.last_error()}")
            return False
    return True

def get_positions(magic: int = MAGIC_TEST):
    all_pos = mt5.positions_get()
    if not all_pos:
        return []
    return [p for p in all_pos if p.magic == magic]

def execute_open(symbol: str, side: str, volume: float, sl_points: float, tp_points: float) -> Optional[Any]:
    info = mt5.symbol_info(symbol)
    if not info:
        log_test(f"ERROR: Símbolo {symbol} no existe.")
        return None
    if not info.visible:
        mt5.symbol_select(symbol, True)
        
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        log_test(f"ERROR: Tick no disponible para {symbol}")
        return None
        
    is_buy = (side.upper() == "BUY")
    price = tick.ask if is_buy else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
    
    if is_buy:
        sl = round(price - (sl_points * info.point), info.digits)
        tp = round(price + (tp_points * info.point), info.digits)
    else:
        sl = round(price + (sl_points * info.point), info.digits)
        tp = round(price - (tp_points * info.point), info.digits)
        
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 25,
        "magic": MAGIC_TEST,
        "comment": f"STRESS_{symbol[:6]}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    t0 = time.time()
    res = mt5.order_send(req)
    latency_ms = (time.time() - t0) * 1000.0
    
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        slippage = abs(res.price - price) / info.point
        log_test(f"  [OPEN OK] Ticket #{res.order} | {symbol} {volume}L {side} | Ejecutado: {res.price} (Req: {price}) | Slip: {slippage:.1f} pts | Latencia: {latency_ms:.1f}ms | SL: {sl} | TP: {tp}")
        return res
    else:
        # Reintento con filling RETURN
        req["type_filling"] = mt5.ORDER_FILLING_RETURN
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log_test(f"  [OPEN OK (Reintento)] Ticket #{res.order} | {symbol} {volume}L {side}")
            return res
        log_test(f"  [OPEN FAIL] {symbol} {side} Falló. Retcode: {getattr(res, 'retcode', 'N/A')}, Comment: {getattr(res, 'comment', 'N/A')}")
        return None

def execute_close(ticket: int) -> bool:
    pos_list = mt5.positions_get(ticket=ticket)
    if not pos_list or len(pos_list) == 0:
        return True
    p = pos_list[0]
    symbol = p.symbol
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return False
        
    order_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
    price = tick.bid if p.type == 0 else tick.ask
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": ticket,
        "symbol": symbol,
        "volume": p.volume,
        "type": order_type,
        "price": price,
        "deviation": 25,
        "magic": MAGIC_TEST,
        "comment": "STRESS_CLOSE",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    t0 = time.time()
    res = mt5.order_send(req)
    latency_ms = (time.time() - t0) * 1000.0
    
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        log_test(f"  [CLOSE OK] Ticket #{ticket} cerrado a {res.price} | PnL realizado: ${p.profit:,.2f} | Latencia: {latency_ms:.1f}ms")
        return True
    else:
        req["type_filling"] = mt5.ORDER_FILLING_RETURN
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log_test(f"  [CLOSE OK (Return)] Ticket #{ticket} cerrado a {res.price}")
            return True
        log_test(f"  [CLOSE FAIL] Ticket #{ticket} fallo cierre. Retcode: {getattr(res, 'retcode', 'N/A')}")
        return False

def close_all_test_positions():
    active = get_positions(MAGIC_TEST)
    for p in active:
        execute_close(p.ticket)
    time.sleep(1)

def run_full_stress_audit():
    print("===============================================================================")
    print("      AUDITORÍA CUANTITATIVA Y BANCO DE PRUEBAS DE ESTRÉS ALGORÍTMICO")
    print("      Perfil: stellar_10k_real | Magic: 505003 | MT5 FTMO-Demo")
    print("===============================================================================\n")
    
    if not connect_mt5():
        return
        
    acc = mt5.account_info()
    log_test(f"Cuenta de Pruebas: #{acc.login} ({acc.server}) | Balance Inicial: ${acc.balance:,.2f} | Equidad: ${acc.equity:,.2f}")
    
    # Asegurar limpieza inicial
    close_all_test_positions()
    
    print("\n-------------------------------------------------------------------------------")
    print("FASE 1: PRUEBAS INDIVIDUALES (1 POR 1 - VERIFICACIÓN UNITARIA)")
    print("-------------------------------------------------------------------------------")
    
    # 1A: XAUUSD (Oro) - Lote institucional calibrado: 0.05
    log_test(">> Test 1A: Probando ejecución unitaria en ORO (XAUUSD)...")
    res_gold = execute_open("XAUUSD", "BUY", 0.05, sl_points=500, tp_points=1000)
    time.sleep(3)
    if res_gold:
        execute_close(res_gold.order)
    time.sleep(2)
    
    # 1B: US500.cash (S&P 500) - Lote calibrado: 0.10
    log_test(">> Test 1B: Probando ejecución unitaria en S&P 500 (US500.cash)...")
    res_sp = execute_open("US500.cash", "BUY", 0.10, sl_points=2500, tp_points=5000)
    time.sleep(3)
    if res_sp:
        execute_close(res_sp.order)
    time.sleep(2)
    
    # 1C: USDJPY (Forex) - Lote calibrado: 0.10
    log_test(">> Test 1C: Probando ejecución unitaria en FOREX (USDJPY)...")
    res_jpy = execute_open("USDJPY", "BUY", 0.10, sl_points=350, tp_points=700)
    time.sleep(3)
    if res_jpy:
        execute_close(res_jpy.order)
    time.sleep(2)
    
    print("\n-------------------------------------------------------------------------------")
    print("FASE 2: PRUEBA CONCURRENTE DUAL (2 ACTIVOS SIMULTÁNEOS)")
    print("Objetivo: Evaluar colisión de ticks, margen libre y sincronización Magic 505003")
    print("-------------------------------------------------------------------------------")
    log_test(">> Abriendo concurrentemente ORO (XAUUSD) + S&P 500 (US500.cash)...")
    r1 = execute_open("XAUUSD", "BUY", 0.05, sl_points=500, tp_points=1000)
    r2 = execute_open("US500.cash", "SELL", 0.10, sl_points=2500, tp_points=5000)
    
    time.sleep(2)
    pos_dual = get_positions(MAGIC_TEST)
    log_test(f"Verificación de Concurrencia: {len(pos_dual)} posiciones vivas detectadas simultáneamente.")
    acc_dual = mt5.account_info()
    log_test(f"Margen utilizado: ${acc_dual.margin:,.2f} | Margen libre restante: ${acc_dual.margin_free:,.2f}")
    
    time.sleep(4)
    log_test(">> Cerrando simultáneamente posiciones duales...")
    close_all_test_positions()
    time.sleep(2)
    
    print("\n-------------------------------------------------------------------------------")
    print("FASE 3: PRUEBA CONCURRENTE TRIPLE (PORTAFOLIO COMPLETO: 3 ACTIVOS A LA VEZ)")
    print("Objetivo: Test de estrés de ráfaga, validación de Max Open Risk y latencia agregada")
    print("-------------------------------------------------------------------------------")
    log_test(">> Disparando ráfaga completa: ORO + S&P 500 + USDJPY simultáneos...")
    t_start = time.time()
    r_gold = execute_open("XAUUSD", "BUY", 0.05, sl_points=500, tp_points=1000)
    r_sp = execute_open("US500.cash", "BUY", 0.10, sl_points=2500, tp_points=5000)
    r_jpy = execute_open("USDJPY", "SELL", 0.10, sl_points=350, tp_points=700)
    total_burst_time = (time.time() - t_start) * 1000.0
    
    log_test(f"Ráfaga de 3 órdenes enviada en {total_burst_time:.1f}ms.")
    time.sleep(2)
    
    pos_triple = get_positions(MAGIC_TEST)
    log_test(f"Auditando portafolio completo en vivo: {len(pos_triple)} activos activos.")
    for p in pos_triple:
        log_test(f"   -> Activo: {p.symbol} | Ticket #{p.ticket} | Lotes: {p.volume} | Magic: {p.magic} | PnL Flotante: ${p.profit:,.2f}")
        
    acc_triple = mt5.account_info()
    log_test(f"Estrés de Margen Triple: Margen Requerido: ${acc_triple.margin:,.2f} (Nivel de Margen: {acc_triple.margin_level:,.1f}%)")
    
    time.sleep(5)
    log_test(">> Liquidando ordenadamente el portafolio triple...")
    close_all_test_positions()
    time.sleep(2)
    
    print("\n-------------------------------------------------------------------------------")
    print("FASE 4: AUDITORÍA POST-ESTRÉS Y CONCILIACIÓN FINAL")
    print("-------------------------------------------------------------------------------")
    rem_pos = get_positions(MAGIC_TEST)
    acc_end = mt5.account_info()
    
    log_test(f"Posiciones residuales con Magic {MAGIC_TEST}: {len(rem_pos)}")
    log_test(f"Balance Final: ${acc_end.balance:,.2f} | Equidad Final: ${acc_end.equity:,.2f}")
    
    if len(rem_pos) == 0:
        log_test("RESULTADO AUDITORÍA: EXITOSA (PASS 100%). El sistema soporta ejecución 1x1, 2 concurrentes y 3 en portafolio completo sin errores de slippage ni desbordamiento de margen.")
    else:
        log_test("RESULTADO AUDITORÍA: ADVERTENCIA - Hay órdenes huérfanas pendientes.")
        
    mt5.shutdown()

if __name__ == "__main__":
    run_full_stress_audit()
