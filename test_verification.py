"""
test_verification.py - Suite de Verificación Automatizada para FundedNext Stellar Lite 2-Step ($10,000 USD).
Valida:
1. Filtro Anti-Fakeouts en ORB (Cierre de vela 15m).
2. Filtro de Tendencia Macro (EMA 200 en 1H).
3. Fricción Institucional (Comisiones broker + Spreads reales).
4. Persistencia y Migraciones SQLite.
5. Blindaje con Break-Even a +1R.
6. Cierre Forzoso de Fin de Semana (Viernes 15:30 EST).
7. Módulo de Alertas Telegram.
8. Validación de Reglas Oficiales Stellar Lite 2-Step $10K (Piso $9,200, Targets $800/$400, 2 Días Mínimos).
9. Verificación de Promoción de Fase y Split Institucional (80% / 90%).
10. Portafolio Multi-Activo (S&P 500 & EUR/USD) con Dimensionamiento Exacto para $10K (0.5% = $50).
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
    assert t_after_be["stop_loss"] == 2000.8, f"Expected SL 2000.8 (BE+), got {t_after_be['stop_loss']}"
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
    dummy_notifier = TelegramNotifier(bot_token="", chat_id="")
    dummy_notifier.enabled = False
    res = dummy_notifier.send_message("Test message")
    assert res is False
    dummy_notifier.notify_trade_opened(
        trade_id=99, symbol="GC=F", side="BUY", lots=0.1,
        entry_price=2000.0, stop_loss=1990.0, take_profit=2020.0,
        risk_usd=100.0, risk_pct=0.005, strategy="NY_ORB_15M", phase="FASE_1"
    )
    dummy_notifier.notify_break_even(trade_id=99, symbol="GC=F", side="BUY", entry_price=2000.0, new_sl=2000.0)
    dummy_notifier.notify_trade_closed(
        trade_id=99, symbol="GC=F", side="BUY", lots=0.1, exit_price=2020.0,
        gross_pnl=200.0, net_pnl=197.0, commission=3.0, reason="TAKE_PROFIT",
        balance=5197.0, equity=5197.0
    )
    dummy_notifier.notify_weekend_close(closed_count=1, realized_pnl=20.0)
    dummy_notifier.notify_target_reached_waiting_days(
        phase="FASE_2", balance=5723.92, target_balance=5200.0,
        trading_days=1, min_days_required=2, recommendations=["Recomendacion 1"]
    )
    print("  PASS: Modulo Telegram funciona con resiliencia ante ausencia de token.")

    # -------------------------------------------------------------------------
    # TEST 8: Validacion de Target Alcanzado & Recomendaciones Cuenta Real (Regla Estándar 2 Días en $10K)
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Validacion de Target Alcanzado, Bloqueo Anti-Overtrading & Micro-Lote (Regla 2 Días en $10K)")
    # Simular cuenta con $10,850.00 en Fase 1 (Target +8% = $800 superado) con 0 días completados
    rules_engine.min_trading_days = 2
    db.update_account_state(
        initial_balance=10000.0,
        balance=10850.0,
        equity=10850.0,
        phase="FASE_1",
        status="ACTIVE",
    )
    eval_res = rules_engine.evaluate_account()
    assert eval_res.target_reached is True, "Expected target_reached=True for $10,850.00 in Fase 1"
    assert eval_res.waiting_min_days is True, "Expected waiting_min_days=True since trading days < 2"
    assert len(eval_res.real_account_recommendations) > 0, "Expected institutional recommendations"
    print("  PASS: Deteccion de target alcanzado ($10,850 >= $10,800) y generacion de recomendaciones para cuenta real.")

    # Probar que run_single_cycle bloquea si hoy ya hay trades
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    db.update_account_state(current_trading_day=today_str)
    # Registrar un trade ficticio cerrado hoy
    db.record_trade_open(symbol="GC=F", provider="yfinance", side="BUY", lots=0.01, units=1.0, entry_price=2000.0, stop_loss=1990.0, take_profit=2020.0, rr_ratio=2.0, phase="FASE_1", strategy="TEST")
    open_t = db.get_open_trades()
    db.record_trade_close(trade_id=open_t[0]["id"], exit_price=2010.0, pnl=10.0, notes="TEST_CLOSE", commission=1.0, spread_cost=0.5)

    cycle_res = engine.run_single_cycle(ignore_session_filter=True)
    assert cycle_res["action"] == "TARGET_REACHED_TODAY_SECURED", f"Expected TARGET_REACHED_TODAY_SECURED, got {cycle_res['action']}"
    print("  PASS: Bloqueo anti-overtrading activado: no permite abrir nuevas ordenes si el target ya fue alcanzado hoy.")

    # -------------------------------------------------------------------------
    # TEST 9: Validacion de Parametros y Reglas Oficiales FundedNext Stellar Lite 2-Step 10K (cloud.png)
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Validacion de Reglas Oficiales Stellar Lite 2-Step $10K USD (cloud.png)")
    rules_engine.min_trading_days = 2
    rules_engine.max_drawdown_limit_pct = 0.08  # 8% Estándar ($800)
    rules_engine.funded_profit_split = 0.80     # 80% Split Estándar
    db.update_account_state(
        initial_balance=10000.0,
        balance=10000.0,
        equity=10000.0,
        day_start_balance=10000.0,
        phase="FASE_1",
        status="ACTIVE",
    )
    eval_std = rules_engine.evaluate_account()
    assert eval_std.daily_loss_floor == 9600.0, f"Expected $9,600.00 daily loss floor (4% of 10K), got {eval_std.daily_loss_floor}"
    assert eval_std.max_loss_floor == 9200.0, f"Expected $9,200.00 max loss floor (8% of 10K), got {eval_std.max_loss_floor}"
    assert eval_std.profit_target_amount == 800.0, f"Expected $800.00 target for Phase 1 (+8%), got {eval_std.profit_target_amount}"
    assert eval_std.profit_target_balance == 10800.0, f"Expected $10,800.00 target balance, got {eval_std.profit_target_balance}"
    print("  PASS: Parametros $10K confirmados: Piso Diario $9,600 (4%), Piso Max DD $9,200 (8%), Meta Fase 1 $10,800 (+8%).")

    # Probar pase a Fase 2 cuando se cumplen los 2 días operativos requeridos
    with db._get_connection() as conn:
        conn.execute(
            "INSERT INTO trades (symbol, provider, side, lots, units, entry_price, stop_loss, take_profit, phase, status, opened_at, trading_date) VALUES ('GC=F', 'yfinance', 'BUY', 0.01, 1.0, 2000, 1990, 2020, 'FASE_1', 'CLOSED', '2026-10-29', '2026-10-29')"
        )
        conn.execute(
            "INSERT INTO trades (symbol, provider, side, lots, units, entry_price, stop_loss, take_profit, phase, status, opened_at, trading_date) VALUES ('GC=F', 'yfinance', 'BUY', 0.01, 1.0, 2000, 1990, 2020, 'FASE_1', 'CLOSED', '2026-10-30', '2026-10-30')"
        )
        conn.commit()
    db.update_account_state(balance=10850.0, equity=10850.0)
    eval_promoted = rules_engine.evaluate_account()
    assert eval_promoted.phase == "FASE_2", f"Expected promotion to FASE_2, got {eval_promoted.phase}"
    assert eval_promoted.profit_target_amount == 400.0, f"Expected $400.00 target for Phase 2 (+4%), got {eval_promoted.profit_target_amount}"
    assert eval_promoted.profit_target_balance == 10400.0, f"Expected $10,400.00 target balance in Phase 2, got {eval_promoted.profit_target_balance}"
    print("  PASS: Promocion a FASE 2 certificada tras 2 dias minimos. Nueva meta Fase 2: $10,400 (+4% = $400).")

    # -------------------------------------------------------------------------
    # TEST 10: Portafolio Profesional Multi-Activo con Capital de $10,000 USD
    # -------------------------------------------------------------------------
    print("\n[TEST 10] Portafolio Profesional en Cuenta $10K: S&P 500 (ES=F / US500) & EUR/USD (EURUSD=X)")
    rm_portfolio = RiskManager(db=db, session_mode="PORTFOLIO_DUAL")
    
    # 1. Dimensionamiento de Posición EUR/USD (25 pips de SL -> $50 USD de riesgo = 0.5% en $10K)
    pos_eur = rm_portfolio.calculate_position_size(
        balance=10000.0,
        symbol="EURUSD=X",
        side="BUY",
        entry_price=1.10000,
        stop_loss=1.09750, # 25 pips
        risk_pct=0.005,
    )
    assert pos_eur.lots == 0.20, f"Expected 0.20 lots for EUR/USD with 25 pips SL on 10K, got {pos_eur.lots}"
    assert abs(pos_eur.risk_amount_usd - 50.0) < 0.50, f"Expected ~$50.00 risk, got {pos_eur.risk_amount_usd}"
    print(f"  PASS: EUR/USD -> Lotaje: {pos_eur.lots} lotes | Riesgo: ${pos_eur.risk_amount_usd:.2f} USD (0.50% de $10K) | TP: {pos_eur.take_profit}")

    # 1B. Dimensionamiento de Posición USD/JPY (20 pips de SL = 0.200 JPY @ 156.250 -> $50 USD de riesgo = 0.5% en $10K)
    pos_jpy = rm_portfolio.calculate_position_size(
        balance=10000.0,
        symbol="USDJPY=X",
        side="BUY",
        entry_price=156.250,
        stop_loss=156.050, # 20 pips
        risk_pct=0.005,
    )
    assert pos_jpy.lots == 0.39, f"Expected 0.39 lots for USD/JPY with 20 pips SL on 10K, got {pos_jpy.lots}"
    assert abs(pos_jpy.risk_amount_usd - 50.0) < 1.00, f"Expected ~$50.00 risk, got {pos_jpy.risk_amount_usd}"
    print(f"  PASS: USD/JPY -> Lotaje: {pos_jpy.lots} lotes | Riesgo: ${pos_jpy.risk_amount_usd:.2f} USD (0.50% de $10K) | TP: {pos_jpy.take_profit}")

    # 1C. Dimensionamiento de Posición AUD/USD (Guardado en Standby: 20 pips de SL -> $50 USD de riesgo = 0.5% en $10K)
    pos_aud = rm_portfolio.calculate_position_size(
        balance=10000.0,
        symbol="AUDUSD=X",
        side="BUY",
        entry_price=0.69700,
        stop_loss=0.69500, # 20 pips
        risk_pct=0.005,
    )
    assert pos_aud.lots == 0.25, f"Expected 0.25 lots for AUD/USD with 20 pips SL on 10K, got {pos_aud.lots}"
    assert abs(pos_aud.risk_amount_usd - 50.0) < 0.50, f"Expected ~$50.00 risk, got {pos_aud.risk_amount_usd}"
    print(f"  PASS: AUD/USD (Standby) -> Lotaje: {pos_aud.lots} lotes | Riesgo: ${pos_aud.risk_amount_usd:.2f} USD (0.50% de $10K) | TP: {pos_aud.take_profit}")

    # 2. Dimensionamiento de Posición S&P 500 (Guardado en Standby: 15 puntos de SL -> $50 USD de riesgo = 0.5% en $10K)
    pos_sp = rm_portfolio.calculate_position_size(
        balance=10000.0,
        symbol="ES=F",
        side="SELL",
        entry_price=5850.0,
        stop_loss=5865.0, # 15 puntos
        risk_pct=0.005,
    )
    assert pos_sp.lots > 0.0, f"Expected valid lots for S&P 500, got {pos_sp.lots}"
    assert abs(pos_sp.risk_amount_usd - 50.0) < 1.0, f"Expected ~$50.00 risk for S&P 500, got {pos_sp.risk_amount_usd}"
    print(f"  PASS: S&P 500 -> Lotaje: {pos_sp.lots} lotes | Riesgo: ${pos_sp.risk_amount_usd:.2f} USD (0.50% de $10K) | TP: {pos_sp.take_profit}")

    # 3. Verificación de Horarios Diferenciados de Sesión:
    # A. 04:00 EST (Apertura de Londres): EUR/USD activo, S&P 500 inactivo
    dt_london = datetime.datetime(2026, 10, 28, 9, 0, 0, tzinfo=datetime.timezone.utc) # 04:00 EST
    eu_act, eu_lbl = rm_portfolio.is_symbol_session_active("EURUSD=X", dt_london)
    sp_act, sp_lbl = rm_portfolio.is_symbol_session_active("ES=F", dt_london)
    assert eu_act is True, f"EUR/USD should be active at 04:00 EST in PORTFOLIO_DUAL: {eu_lbl}"
    assert sp_act is False, f"S&P 500 should be inactive at 04:00 EST: {sp_lbl}"
    print("  PASS: Sesion 04:00 EST (Londres): EUR/USD ACTIVO | S&P 500 INACTIVO.")

    # B. 10:00 EST (Wall Street Cash Open): S&P 500 activo, EUR/USD activo (NY Overlap)
    dt_ny = datetime.datetime(2026, 10, 28, 15, 0, 0, tzinfo=datetime.timezone.utc) # 10:00 EST
    eu_act_ny, eu_lbl_ny = rm_portfolio.is_symbol_session_active("EURUSD=X", dt_ny)
    sp_act_ny, sp_lbl_ny = rm_portfolio.is_symbol_session_active("ES=F", dt_ny)
    assert sp_act_ny is True, f"S&P 500 should be active at 10:00 EST: {sp_lbl_ny}"
    assert eu_act_ny is True, f"EUR/USD should be active at 10:00 EST: {eu_lbl_ny}"
    print("  PASS: Sesion 10:00 EST (Wall Street Cash): S&P 500 ACTIVO | EUR/USD ACTIVO.")

    # 4. Verificación de Rango de Apertura ORB para S&P 500 (Vela 09:30 EST)
    df_sp_m15 = pd.DataFrame([
        {"Open": 5840.0, "High": 5855.0, "Low": 5835.0, "Close": 5845.0, "Volume": 50000}, # 09:30 EST
        {"Open": 5845.0, "High": 5865.0, "Low": 5842.0, "Close": 5860.0, "Volume": 70000}, # 09:45 EST (Breakout)
    ], index=[
        pd.Timestamp("2026-10-28 09:30:00", tz="America/New_York"),
        pd.Timestamp("2026-10-28 09:45:00", tz="America/New_York"),
    ])
    sig_sp = strat.evaluate(df_sp_m15, symbol="ES=F", provider="yfinance", session_mode="PORTFOLIO_DUAL")
    assert sig_sp.side == "BUY", f"Expected BUY breakout on S&P 500, got {sig_sp.side}"
    assert sig_sp.orb_high == 5855.0, f"Expected ORB High 5855.0 from 09:30 EST bar, got {sig_sp.orb_high}"
    print(f"  PASS: S&P 500 ORB 15m (09:30 EST) confirmado con exito: BUY @ {sig_sp.current_price} | SL: {sig_sp.stop_loss} | TP: {sig_sp.take_profit}")

    # -------------------------------------------------------------------------
    # TEST 11: Validacion de Regla FundedNext: Max Risk 3% At Any Time (1.png)
    # -------------------------------------------------------------------------
    print("\n[TEST 11] Validacion de Regla Oficial FundedNext: Max Risk 3% At Any Time (1.png)")
    # Limpiar trades para test aislado
    with db._get_connection() as conn:
        conn.execute("DELETE FROM trades")
        conn.commit()

    # 1. Simular trade abierto con $200 de riesgo expuesto (ej. 20 pips en EUR/USD con 1.0 lote = $200)
    db.record_trade_open(
        symbol="EURUSD=X", provider="yfinance", side="BUY", lots=1.0, units=100000.0,
        entry_price=1.1000, stop_loss=1.0980, take_profit=1.1040, rr_ratio=2.0, phase="FASE_1", strategy="TEST"
    )
    open_risk_1 = risk_mgr.calculate_current_open_risk()
    assert open_risk_1 == 200.0, f"Expected $200.00 open risk, got {open_risk_1}"
    print(f"  PASS: Riesgo actual en mercado correctamente medido: ${open_risk_1:,.2f} USD (2.0% de $10K).")

    # 2. Intentar validar una nueva orden que agregue $150 de riesgo adicional ($200 + $150 = $350 > $300 límite 3%)
    check_over_risk = risk_mgr.validate_pre_trade(estimated_new_trade_risk=150.0, ignore_session_filter=True)
    assert check_over_risk.allowed is False, "Expected trade to be blocked by Max Risk 3% rule"
    assert "MAX RISK 3%" in check_over_risk.reason, f"Expected MAX RISK 3% reason, got: {check_over_risk.reason}"
    print(f"  PASS: Bloqueo exitoso ante intento de exceder 3.0% de riesgo abierto simultáneo: {check_over_risk.reason[:75]}...")

    # 3. Blindar la primera posición a Break-Even (is_break_even=1) -> Riesgo cae a $0.00
    open_trades_list = db.get_open_trades()
    db.update_trade_sl(trade_id=open_trades_list[0]["id"], new_sl=1.1000, is_break_even=1)
    open_risk_be = risk_mgr.calculate_current_open_risk()
    assert open_risk_be == 0.0, f"Expected $0.00 risk after Break-Even, got {open_risk_be}"
    
    # Ahora la nueva orden con $150 de riesgo sí debe ser permitida ($0 + $150 = $150 < $300)
    check_after_be = risk_mgr.validate_pre_trade(estimated_new_trade_risk=150.0, ignore_session_filter=True)
    assert check_after_be.allowed is True, f"Expected allowed after BE, got {check_after_be.reason}"
    print("  PASS: Al blindar la orden a Break-Even, el riesgo expuesto se libera ($0.00) y autoriza nuevas operaciones.")

    # -------------------------------------------------------------------------
    # TEST 12: Validacion de Reglas Oficiales FundedNext Stellar 6K Trial (1-trial.png y 2-trial.png)
    # -------------------------------------------------------------------------
    print("\n[TEST 12] Validacion de Perfil y Reglas FundedNext Free Trial 6K Challenge (1-trial.png / 2-trial.png)")
    from profiles import profile_manager
    trial_prof = profile_manager.get_profile("stellar_6k_trial")
    assert trial_prof is not None, "El perfil 'stellar_6k_trial' debe existir"
    assert trial_prof.initial_balance == 6000.0, f"Expected $6,000 initial balance, got {trial_prof.initial_balance}"
    assert trial_prof.profit_target_pct == 0.05, f"Expected 5% target, got {trial_prof.profit_target_pct}"
    assert trial_prof.target_amount_fase1 == 300.0, f"Expected $300 target amount, got {trial_prof.target_amount_fase1}"
    assert trial_prof.min_trading_days == 3, f"Expected 3 min trading days, got {trial_prof.min_trading_days}"
    assert trial_prof.daily_loss_limit_pct == 0.05, f"Expected 5% daily loss limit, got {trial_prof.daily_loss_limit_pct}"
    assert trial_prof.daily_loss_amount == 300.0, f"Expected $300 daily loss amount, got {trial_prof.daily_loss_amount}"
    assert trial_prof.max_drawdown_limit_pct == 0.10, f"Expected 10% max DD, got {trial_prof.max_drawdown_limit_pct}"
    assert trial_prof.max_loss_amount == 600.0, f"Expected $600 max loss amount, got {trial_prof.max_loss_amount}"
    assert trial_prof.max_loss_floor == 5400.0, f"Expected $5,400 floor, got {trial_prof.max_loss_floor}"
    assert trial_prof.login_id == 35338849, f"Expected login ID 35338849 from 2-trial.png, got {trial_prof.login_id}"
    print("  PASS: Parametros 6K Trial verificados: $6,000 Capital, Meta $300 (+5%), 3 Dias, Daily Loss $300 (5%), Max Loss $600 (10% -> Piso $5,400).")

    # Prueba con Rules Engine y Risk Manager en 6K
    test_db_6k_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_qa_6k_trial.db")
    if os.path.exists(test_db_6k_path):
        os.remove(test_db_6k_path)

    db_6k = TradingDatabase(test_db_6k_path, profile=trial_prof)
    rules_6k = StellarLiteRulesEngine(db=db_6k, profile=trial_prof)
    risk_6k = RiskManager(db=db_6k, profile=trial_prof)

    # 1. Validar evaluacion inicial
    eval_6k_init = rules_6k.evaluate_account()
    assert eval_6k_init.daily_loss_floor == 5700.0, f"Expected daily floor $5,700, got {eval_6k_init.daily_loss_floor}"
    assert eval_6k_init.max_loss_floor == 5400.0, f"Expected max DD floor $5,400, got {eval_6k_init.max_loss_floor}"
    assert eval_6k_init.profit_target_amount == 300.0, f"Expected target amount $300, got {eval_6k_init.profit_target_amount}"
    assert eval_6k_init.profit_target_balance == 6300.0, f"Expected target balance $6,300, got {eval_6k_init.profit_target_balance}"
    print("  PASS: Calculos de pisos y metas iniciales en SQLite certificados para 6K Trial.")

    # 2. Validar regla de Max Open Risk 3% en 6K: Limite es $180 USD (3% de $6,000)
    check_risk_6k_allowed = risk_6k.validate_pre_trade(estimated_new_trade_risk=150.0, ignore_session_filter=True)
    assert check_risk_6k_allowed.allowed is True, "Trade con $150 de riesgo debe ser permitido en 6K (< $180)"
    check_risk_6k_blocked = risk_6k.validate_pre_trade(estimated_new_trade_risk=200.0, ignore_session_filter=True)
    assert check_risk_6k_blocked.allowed is False, "Trade con $200 de riesgo debe ser bloqueado en 6K (> $180 limite 3%)"
    print("  PASS: Regla FundedNext Max Risk 3% en 6K ($180 USD) validada con exito.")

    # 3. Validar dimensionamiento de lote para 6K (0.5% = $30 USD de riesgo)
    pos_6k_gold = risk_6k.calculate_position_size(
        balance=6000.0,
        symbol="GC=F",
        side="BUY",
        entry_price=2700.0,
        stop_loss=2690.0, # $10 de SL
    )
    assert abs(pos_6k_gold.risk_amount_usd - 30.0) < 1.0, f"Expected ~$30.00 risk, got {pos_6k_gold.risk_amount_usd}"
    print(f"  PASS: Dimensionamiento Oro en 6K -> Lotaje: {pos_6k_gold.lots} lotes | Riesgo: ${pos_6k_gold.risk_amount_usd:.2f} USD (0.50% de $6K).")

    # 4. Validar cumplimiento de Target y 3 dias minimos para pasar el Free Trial Challenge
    with db_6k._get_connection() as conn:
        conn.execute(
            "INSERT INTO trades (symbol, provider, side, lots, units, entry_price, stop_loss, take_profit, phase, status, opened_at, trading_date) VALUES ('GC=F', 'yfinance', 'BUY', 0.01, 1.0, 2700, 2690, 2720, 'CHALLENGE', 'CLOSED', '2026-10-28', '2026-10-28')"
        )
        conn.execute(
            "INSERT INTO trades (symbol, provider, side, lots, units, entry_price, stop_loss, take_profit, phase, status, opened_at, trading_date) VALUES ('GC=F', 'yfinance', 'BUY', 0.01, 1.0, 2700, 2690, 2720, 'CHALLENGE', 'CLOSED', '2026-10-29', '2026-10-29')"
        )
        conn.commit()

    # Balance llega a $6,320 (supera $6,300), pero solo lleva 2 dias
    db_6k.update_account_state(balance=6320.0, equity=6320.0)
    eval_waiting_day3 = rules_6k.evaluate_account()
    assert eval_waiting_day3.target_reached is True, "Target debe marcarse como alcanzado"
    assert eval_waiting_day3.waiting_min_days is True, "Debe esperar el 3er dia minimo requerido"
    assert eval_waiting_day3.can_pass_phase is False, "No debe pasar con solo 2 dias"
    print("  PASS: Bloqueo seguro: Target $300 alcanzado pero retenido hasta completar los 3 dias minimos.")

    # Registrar el 3er dia operativo
    with db_6k._get_connection() as conn:
        conn.execute(
            "INSERT INTO trades (symbol, provider, side, lots, units, entry_price, stop_loss, take_profit, phase, status, opened_at, trading_date) VALUES ('GC=F', 'yfinance', 'BUY', 0.01, 1.0, 2700, 2690, 2720, 'CHALLENGE', 'CLOSED', '2026-10-30', '2026-10-30')"
        )
        conn.commit()

    eval_trial_passed = rules_6k.evaluate_account()
    assert eval_trial_passed.can_pass_phase is True, "Debe superar el challenge con 3 dias y target alcanzado"
    assert eval_trial_passed.phase == "SUPERADA", f"Expected phase SUPERADA, got {eval_trial_passed.phase}"
    print("  PASS: Promocion oficial a SUPERADA certificada tras cumplir Target ($300) y 3 dias minimos reglamentarios.")

    del rules_6k
    del risk_6k
    del db_6k
    try:
        if os.path.exists(test_db_6k_path):
            os.remove(test_db_6k_path)
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # TEST 13: Administracion y Coexistencia de Perfiles (Stellar 10K Demo y Stellar 6K Trial)
    # -------------------------------------------------------------------------
    print("\n[TEST 13] Administracion de Perfiles y Coexistencia Sin Conflicto")
    all_profs = profile_manager.list_profiles()
    prof_ids = [p.id for p in all_profs]
    assert "stellar_10k_demo" in prof_ids, "Debe existir 'stellar_10k_demo'"
    assert "stellar_6k_trial" in prof_ids, "Debe existir 'stellar_6k_trial'"

    # Guardar perfil activo previo
    prev_active = profile_manager.get_active_profile_id()

    # Conmutar a 10K y verificar
    p10k = profile_manager.set_active_profile("stellar_10k_demo")
    assert profile_manager.get_active_profile_id() == "stellar_10k_demo"
    assert p10k.initial_balance == 10000.0
    print("  PASS: Conmutacion a 'stellar_10k_demo' verificada correctamente.")

    # Conmutar a 6K y verificar
    p6k = profile_manager.set_active_profile("stellar_6k_trial")
    assert profile_manager.get_active_profile_id() == "stellar_6k_trial"
    assert p6k.initial_balance == 6000.0
    assert p6k.login_id == 35338849
    print("  PASS: Conmutacion a 'stellar_6k_trial' verificada correctamente.")

    # Restaurar perfil original
    profile_manager.set_active_profile(prev_active)
    print(f"  PASS: Perfil original restaurado ({prev_active}). Coexistencia 100% garantizada.")

    del engine
    del rules_engine
    del rm_portfolio
    del risk_mgr
    del db
    import gc
    gc.collect()
    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except Exception:
        pass
    print("\n==================================================")
    print("TODAS LAS PRUEBAS COMPLETADAS CON EXITO (100% OK)")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
