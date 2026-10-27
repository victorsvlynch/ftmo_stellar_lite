"""
test_verification.py - Suite de Verificación Automatizada para FundedNext / FTMO Stellar Lite ($5,000).
Valida:
1. Filtro Anti-Fakeouts en ORB (Cierre de vela 15m).
2. Filtro de Tendencia Macro (EMA 200 en 1H).
3. Fricción Institucional (Comisiones broker + Spreads reales).
4. Persistencia y Migraciones SQLite.
5. Blindaje con Break-Even a +1R.
6. Cierre Forzoso de Fin de Semana (Viernes 15:30 EST).
7. Módulo de Alertas Telegram.
"""

import os
import sys
import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import TradingDatabase
from stellar_rules import StellarLiteRulesEngine
from risk_manager import RiskManager
from trading_engine import OpeningRangeBreakoutStrategy, AutomatedTradingEngine
from telegram_notifier import TelegramNotifier


def run_tests():
    print("==================================================")
    print("VERIFICACION INTEGRAL FASE 1 & FASE 2")
    print("==================================================")
    
    test_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_qa_suite.db")
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    db = TradingDatabase(test_db_path)
    rules_engine = StellarLiteRulesEngine(db)
    risk_mgr = RiskManager(db=db)
    engine = AutomatedTradingEngine(
        db=db,
        rules_engine=rules_engine,
        risk_manager=risk_mgr,
        symbol="GC=F"
    )

    # -------------------------------------------------------------------------
    # TEST 1: Anti-fakeout Filter (Wick vs Close) & 1H EMA 200 Macro Trend Filter
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Estrategia ORB: Anti-Fakeout & EMA 200 Trend Filter")
    strat = OpeningRangeBreakoutStrategy(rr_ratio=2.0)
    
    tz_ny = "America/New_York"
    dates_15m = [
        pd.Timestamp("2026-10-23 08:30:00", tz=tz_ny),
        pd.Timestamp("2026-10-23 08:45:00", tz=tz_ny),
    ]
    
    # Case A: Fakeout wick
    df_fakeout = pd.DataFrame([
        {"Open": 102.0, "High": 110.0, "Low": 100.0, "Close": 105.0, "Volume": 1000},
        {"Open": 105.0, "High": 112.0, "Low": 104.0, "Close": 108.5, "Volume": 1500},
    ], index=dates_15m)

    sig_fakeout = strat.evaluate(
        df_15m=df_fakeout,
        symbol="GC=F",
        provider="yfinance",
        session_mode="NY_OPEN"
    )
    assert sig_fakeout.side == "NONE", f"Expected NONE for fakeout wick, got {sig_fakeout.side}"
    print("  PASS: Fakeout rechazado (mecha rompio rango pero vela cerro adentro).")

    # Case B: Close breaks 110, but 1H EMA 200 is 125.0 (Bear trend filter rejection)
    df_breakout = pd.DataFrame([
        {"Open": 102.0, "High": 110.0, "Low": 100.0, "Close": 105.0, "Volume": 1000},
        {"Open": 105.0, "High": 112.0, "Low": 104.0, "Close": 111.5, "Volume": 1500},
    ], index=dates_15m)

    dates_1h = pd.date_range("2026-10-20 00:00:00", periods=20, freq="1h", tz=tz_ny)
    df_1h_bear = pd.DataFrame({
        "Open": [125.0] * 20,
        "High": [126.0] * 20,
        "Low": [124.0] * 20,
        "Close": [125.0] * 20,
        "Volume": [5000] * 20
    }, index=dates_1h)

    sig_counter_trend = strat.evaluate(
        df_15m=df_breakout,
        symbol="GC=F",
        provider="yfinance",
        session_mode="NY_OPEN",
        df_1h=df_1h_bear
    )
    assert sig_counter_trend.side == "NONE", f"Expected NONE for counter-trend buy, got {sig_counter_trend.side}"
    assert "Anti-Fakeout Tendencial" in sig_counter_trend.reason
    print("  PASS: Compra contra-tendencia rechazada (Cierre 111.5 < EMA 200 1H 125.0).")

    # Case C: Close breaks 110 AND 1H EMA 200 is 100.0 (Trend aligned bull) -> BUY accepted
    df_1h_bull = pd.DataFrame({
        "Open": [100.0] * 20,
        "High": [101.0] * 20,
        "Low": [99.0] * 20,
        "Close": [100.0] * 20,
        "Volume": [5000] * 20
    }, index=dates_1h)

    sig_valid_buy = strat.evaluate(
        df_15m=df_breakout,
        symbol="GC=F",
        provider="yfinance",
        session_mode="NY_OPEN",
        df_1h=df_1h_bull
    )
    assert sig_valid_buy.side == "BUY", f"Expected BUY, got {sig_valid_buy.side}"
    assert sig_valid_buy.stop_loss == 100.0
    assert sig_valid_buy.take_profit == round(111.5 + (11.5 * 2.0), 5)
    print("  PASS: Compra con confirmacion de cierre y alineada con EMA 200 1H APROBADA.")

    # -------------------------------------------------------------------------
    # TEST 2: Friccion Institucional (Spread + Comisiones)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Friccion Institucional (Comisiones + Spread)")
    comm_gold, spread_gold = risk_mgr.calculate_trade_friction("GC=F", lots=1.0, units=100.0)
    assert comm_gold == 5.0, f"Expected 5.0 commission for 1 lot gold, got {comm_gold}"
    assert spread_gold == 25.0, f"Expected 25.0 spread cost for 1 lot gold ($0.25 * 100), got {spread_gold}"
    print(f"  PASS: Oro (GC=F) 1 Lote -> Comision: ${comm_gold:.2f}, Spread: ${spread_gold:.2f}")

    comm_btc, spread_btc = risk_mgr.calculate_trade_friction("BTC-USD", lots=0.5, units=0.5)
    print(f"  PASS: BTC-USD 0.5 Lote -> Comision: ${comm_btc:.2f}, Spread: ${spread_btc:.2f}")

    # -------------------------------------------------------------------------
    # TEST 3: Base de Datos & Registro con Descuento Institucional
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Base de Datos SQLite: Migraciones y Descuento Institucional")
    trade_id = db.record_trade_open(
        symbol="GC=F",
        provider="yfinance",
        side="BUY",
        lots=0.1,
        units=10.0,
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit=2020.0,
        rr_ratio=2.0,
        phase="FASE_1",
        strategy="NY_ORB_15M",
    )
    print(f"  PASS: Trade #{trade_id} registrado en BD abierta.")

    # -------------------------------------------------------------------------
    # TEST 4: Break-Even Automático a +1R
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Gestion de Break-Even a +1R")
    simulated_prices = {"GC=F": 2010.5}
    engine.manage_open_positions(simulated_prices)

    t_after_be = db.get_open_trades()[0]
    assert t_after_be["stop_loss"] == 2000.0, f"Expected SL 2000.0, got {t_after_be['stop_loss']}"
    assert t_after_be["is_break_even"] == 1, f"Expected is_break_even=1, got {t_after_be['is_break_even']}"
    print(f"  PASS: Break-Even activado. Nuevo SL: ${t_after_be['stop_loss']}, is_break_even: {t_after_be['is_break_even']}")

    # -------------------------------------------------------------------------
    # TEST 5: Cierre en TP con Descuento Neto de Comision y Spread
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Cierre en Take-Profit con Liquidacion Neta Institucional")
    simulated_prices_tp = {"GC=F": 2021.0}
    engine.manage_open_positions(simulated_prices_tp)

    closed_trades = db.get_trades_by_phase("FASE_1", status="CLOSED")
    assert len(closed_trades) == 1, f"Expected 1 closed trade, got {len(closed_trades)}"
    c_trade = closed_trades[0]
    print(f"  Detalle Trade Cerrado:")
    print(f"    - Gross PnL: ${c_trade['gross_pnl']:.2f}")
    print(f"    - Comision:  -${c_trade['commission']:.2f}")
    print(f"    - Spread:    -${c_trade['spread_cost']:.2f}")
    print(f"    - Net PnL:   ${c_trade['pnl']:.2f}")
    print(f"    - Exit Reason: {c_trade['notes']}")

    assert "TP" in c_trade['notes'] or "TAKE_PROFIT" in c_trade['notes']
    assert c_trade['gross_pnl'] == 200.0
    assert c_trade['commission'] > 0.0
    assert c_trade['spread_cost'] > 0.0
    assert c_trade['pnl'] < c_trade['gross_pnl']
    print("  PASS: Calculo de friccion institucional verificado en BD.")

    # -------------------------------------------------------------------------
    # TEST 6: Cierre Forzoso de Fin de Semana (Viernes 15:30 EST)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Cierre Forzoso de Fin de Semana (Viernes 15:30 EST)")
    tid_gold = db.record_trade_open(
        symbol="GC=F", provider="yfinance", side="BUY", lots=0.1, units=10.0,
        entry_price=2000.0, stop_loss=1980.0, take_profit=2040.0,
        rr_ratio=2.0, phase="FASE_1", strategy="TEST_WEEKEND"
    )
    tid_btc = db.record_trade_open(
        symbol="BTC-USD", provider="yfinance", side="BUY", lots=0.01, units=0.01,
        entry_price=60000.0, stop_loss=58000.0, take_profit=64000.0,
        rr_ratio=2.0, phase="FASE_1", strategy="TEST_CRYPTO"
    )

    friday_window_time = datetime.datetime(2026, 10, 23, 20, 45, 0, tzinfo=datetime.timezone.utc)
    assert risk_mgr.is_friday_weekend_close_window(friday_window_time) is True
    print("  PASS: Detector de ventana de Viernes 15:30 EST activado correctamente.")

    engine.manage_open_positions({"GC=F": 2002.0, "BTC-USD": 60500.0}, now_utc=friday_window_time)

    open_trades_after = db.get_open_trades()
    open_symbols = [t["symbol"] for t in open_trades_after]
    assert "GC=F" not in open_symbols, "Expected GC=F to be flattened for weekend!"
    assert "BTC-USD" in open_symbols, "Expected BTC-USD to remain open 24/7 during weekend!"
    print(f"  PASS: GC=F liquidado forzosamente por fin de semana. BTC-USD conservado abierto.")

    # -------------------------------------------------------------------------
    # TEST 7: Telegram Notifier Test
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Telegram Notifier Verificacion Estructural")
    notifier = TelegramNotifier()
    res = notifier.send_message("Test message")
    assert res is False
    notifier.notify_trade_opened(
        trade_id=99, symbol="GC=F", side="BUY", lots=0.1,
        entry_price=2000.0, stop_loss=1990.0, take_profit=2020.0,
        risk_usd=100.0, risk_pct=0.005, strategy="NY_ORB_15M", phase="FASE_1"
    )
    notifier.notify_break_even(trade_id=99, symbol="GC=F", side="BUY", entry_price=2000.0, new_sl=2000.0)
    notifier.notify_trade_closed(
        trade_id=99, symbol="GC=F", side="BUY", lots=0.1, exit_price=2020.0,
        gross_pnl=200.0, net_pnl=197.0, commission=3.0, reason="TAKE_PROFIT",
        balance=5197.0, equity=5197.0
    )
    notifier.notify_weekend_close(closed_count=1, realized_pnl=20.0)
    notifier.notify_target_reached_waiting_days(
        phase="FASE_2", balance=5723.92, target_balance=5200.0,
        trading_days=1, min_days_required=2, recommendations=["Recomendacion 1"]
    )
    print("  PASS: Modulo Telegram funciona con resiliencia ante ausencia de token.")

    # -------------------------------------------------------------------------
    # TEST 8: Validacion de Target Alcanzado & Recomendaciones Cuenta Real (Regla Estándar 2 Días)
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Validacion de Target Alcanzado, Bloqueo Anti-Overtrading & Micro-Lote (Regla 2 Días)")
    # Simular cuenta con $5,723.92 en Fase 2 bajo regla estándar de 2 días
    rules_engine.min_trading_days = 2
    db.update_account_state(balance=5723.92, equity=5723.92, phase="FASE_2", status="ACTIVE")
    eval_res = rules_engine.evaluate_account()
    assert eval_res.target_reached is True, "Expected target_reached=True for $5723.92 in Fase 2"
    assert eval_res.waiting_min_days is True, "Expected waiting_min_days=True since trading days < 2"
    assert len(eval_res.real_account_recommendations) > 0, "Expected institutional recommendations"
    print("  PASS: Deteccion de target alcanzado y generacion de recomendaciones para cuenta real.")

    # Probar que run_single_cycle bloquea si hoy ya hay trades
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    db.update_account_state(current_trading_day=today_str)
    # Registrar un trade ficticio cerrado hoy
    db.record_trade_open(symbol="GC=F", provider="yfinance", side="BUY", lots=0.01, units=1.0, entry_price=2000.0, stop_loss=1990.0, take_profit=2020.0, rr_ratio=2.0, phase="FASE_2", strategy="TEST")
    open_t = db.get_open_trades()
    db.record_trade_close(trade_id=open_t[0]["id"], exit_price=2010.0, pnl=8.5, notes="TEST_CLOSE", commission=1.0, spread_cost=0.5)

    cycle_res = engine.run_single_cycle(ignore_session_filter=True)
    assert cycle_res["action"] == "TARGET_REACHED_TODAY_SECURED", f"Expected TARGET_REACHED_TODAY_SECURED, got {cycle_res['action']}"
    print("  PASS: Bloqueo anti-overtrading activado: no permite abrir nuevas ordenes si el target ya fue alcanzado hoy.")

    # -------------------------------------------------------------------------
    # TEST 9: Validacion de Add-ons FundedNext Checkout (cloud.png)
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Validacion de Add-ons FundedNext (cloud.png: No Min Days, 10% Max Loss, 95% Split)")
    rules_engine.min_trading_days = 0
    rules_engine.max_drawdown_limit_pct = 0.10
    rules_engine.funded_profit_split = 0.95
    db.update_account_state(balance=5723.92, equity=5723.92, phase="FASE_2", status="ACTIVE")
    eval_addon = rules_engine.evaluate_account()
    assert eval_addon.phase == "FONDEADA", f"Expected promotion to FONDEADA, got {eval_addon.phase}"
    assert eval_addon.profit_split == 0.95, f"Expected 95% profit split, got {eval_addon.profit_split}"
    assert eval_addon.max_loss_floor == 4500.0, f"Expected $4,500.00 floor (10% Max DD), got {eval_addon.max_loss_floor}"
    print("  PASS: Aprobacion instantanea a FONDEADA con No Min Trading Days, Piso $4,500 (10% DD) y Split 95%.")

    del engine
    del rules_engine
    del db
    import gc
    gc.collect()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    print("\n==================================================")
    print("TODAS LAS PRUEBAS COMPLETADAS CON EXITO (100% OK)")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
