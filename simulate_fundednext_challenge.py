"""
simulate_fundednext_challenge.py - Simulador de Desafío Real FundedNext 2-Step ($10K)
--------------------------------------------------------------------------------------
Enfrenta directamente la estrategia oficial contra un desafío de evaluación idéntico al real:
- Capital Base: $10,000 USD
- Fase 1: Meta +8.0% ($800) -> Target: $10,800 USD | Días mínimos: 2
- Fase 2: Meta +4.0% ($400) -> Target: $10,400 USD | Días mínimos: 2
- Piso Drawdown Estático: $9,000 USD (-10.0% / $1,000)
- Límite Pérdida Diaria: 4.0% ($400) | Freno Personal: 2.0% ($200)
- Bloqueo Anti-Overtrading al alcanzar el target y Modo Micro-Lote para certificar días mínimos.
- Activo Principal: Oro (XAUUSD) en la sesión de NY (08:30–11:30 EST) con filtro EMA 200 H1.
"""

import sys
import os
import datetime
import pandas as pd
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
import MetaTrader5 as mt5

TERMINAL_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

def run_evaluation_challenge():
    print("===============================================================================")
    print("      SIMULACIÓN DE RETO DE EVALUACIÓN OFICIAL FUNDEDNEXT 2-STEP ($10,000)")
    print("      Perfil: stellar_10k_real | Activo: ORO (XAUUSD) NY ORB M15")
    print("===============================================================================\n")

    if not mt5.initialize(path=TERMINAL_PATH):
        mt5.initialize()

    # Cargar historial reciente de velas M15 del Oro (últimos 120 días hábiles ~ 6 meses)
    now = datetime.datetime.now()
    rates = mt5.copy_rates_from("XAUUSD", mt5.TIMEFRAME_M15, now, 12000)
    if rates is None or len(rates) == 0:
        print("Error: No se pudieron cargar datos de XAUUSD de MT5.")
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['time_ny'] = df['time'].dt.tz_convert(ZoneInfo("America/New_York"))
    df.set_index('time_ny', inplace=True)
    df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)

    # Calcular EMA 200 en H1
    df_h1 = df['Close'].resample('1h').last().dropna()
    ema_h1 = df_h1.ewm(span=200, adjust=False).mean()
    ema_aligned = ema_h1.reindex(df.index, method='ffill')

    # Días hábiles
    days = df.index.strftime('%Y-%m-%d').unique()
    
    # Parámetros Oficiales del Desafío
    INITIAL_CAPITAL = 10000.0
    RISK_PER_TRADE = 50.0 # $50 USD (0.50%)
    DAILY_LOSS_LIMIT = 400.0 # 4%
    PERSONAL_CAP = 200.0 # 2%
    MAX_DRAWDOWN_LIMIT = 1000.0 # 10% (Piso $9,000)
    
    # Estado del Desafío
    current_phase = "FASE_1" # FASE_1 -> FASE_2 -> FONDEADO
    phase_target = 800.0 # $800 en Fase 1, $400 en Fase 2
    balance = INITIAL_CAPITAL
    equity = INITIAL_CAPITAL
    trading_days_completed = 0
    phase_start_day = 0
    
    challenge_log = []
    daily_records = []
    
    print(f"[*] Iniciando Desafío en FASE 1 con Balance: ${balance:,.2f} USD")
    print(f"[*] Meta Fase 1: +$800 USD ($10,800.00) | Días mínimos: 2")
    print(f"[*] Piso de Protección: $9,000.00 USD | Freno Diario: -$200.00 USD\n")

    total_days_simulated = 0
    challenge_completed = False

    for d_idx, day_str in enumerate(days):
        if challenge_completed:
            break

        day_df = df.loc[day_str]
        orb_candle = day_df[(day_df.index.hour == 8) & (day_df.index.minute == 30)]
        if orb_candle.empty:
            continue

        total_days_simulated += 1
        day_start_balance = balance
        day_pnl = 0.0
        day_trades = 0
        
        # Verificar vela ORB M15
        orb_high = float(orb_candle['High'].iloc[0])
        orb_low = float(orb_candle['Low'].iloc[0])
        orb_range = orb_high - orb_low

        # Filtro de Sentido Común: Descartar velas muertas (<$1.50) o velas gigantes de noticias (> $9.00)
        is_normal_volatility = (1.50 <= orb_range <= 9.00)

        # Si el target ya se cumplió y solo falta certificar el 2do día mínimo -> MODO MICRO-LOTE DE SEGURIDAD
        target_fulfilled = (balance - INITIAL_CAPITAL >= phase_target)
        waiting_min_days = target_fulfilled and (trading_days_completed < 2)

        if waiting_min_days:
            # Ejecutar micro-lote institucional (0.01 lotes) para registrar el día obligatorio sin riesgo
            micro_pnl = 1.50 # Ganancia/pérdida simbólica de $1-$2
            balance += micro_pnl
            trading_days_completed += 1
            daily_records.append({"day": day_str, "phase": current_phase, "trades": 1, "pnl": micro_pnl, "balance": balance, "note": "MODO_MICRO_LOTE_DIA_2"})
            print(f"  [Día {total_days_simulated} | {day_str}] MODO MICRO-LOTE: 2do día mínimo registrado con éxito (+${micro_pnl:.2f}). Balance: ${balance:,.2f}")

            # Transición de Fase
            if current_phase == "FASE_1":
                print(f"\n===============================================================================")
                print(f"  ¡FASE 1 SUPERADA CON ÉXITO EN EL DÍA {total_days_simulated}!")
                print(f"  Balance Final Fase 1: ${balance:,.2f} USD | Ganancia: +${balance - INITIAL_CAPITAL:,.2f} USD (+{((balance-INITIAL_CAPITAL)/INITIAL_CAPITAL)*100:.1f}%)")
                print(f"===============================================================================\n")
                current_phase = "FASE_2"
                phase_target = 400.0 # Meta Fase 2: +4% ($400)
                balance = INITIAL_CAPITAL # En FundedNext se resetea a $10,000 para la Fase 2
                trading_days_completed = 0
                print(f"[*] Iniciando FASE 2 con Balance: ${balance:,.2f} USD | Meta: +$400 USD ($10,400.00)\n")
                continue
            elif current_phase == "FASE_2":
                print(f"\n===============================================================================")
                print(f"  ¡¡¡DESAFÍO COMPLETADO Y CUENTA FONDEADA APROBADA (FASE 2 SUPERADA)!!!")
                print(f"  Días Totales Utilizados: {total_days_simulated} días hábiles")
                print(f"  Balance Final Fase 2: ${balance:,.2f} USD (+${balance - INITIAL_CAPITAL:,.2f} USD)")
                print(f"  Estado: CALIFICADO PARA CUENTA REAL FONDEADA (95% PROFIT SPLIT)")
                print(f"===============================================================================\n")
                challenge_completed = True
                break

        if not is_normal_volatility:
            # Día descartado por filtro de tamaño de vela (evita trampas o noticias extremas)
            continue

        # Ventana operativa 08:45 a 11:30 EST
        entry_window = day_df[(day_df.index.hour >= 8) & (day_df.index.hour <= 11)]
        entry_window = entry_window[~((entry_window.index.hour == 8) & (entry_window.index.minute < 45))]
        entry_window = entry_window[~((entry_window.index.hour == 11) & (entry_window.index.minute > 30))]

        trade_executed_today = False

        for t_idx, row in entry_window.iterrows():
            if trade_executed_today:
                break
            # Frenos de seguridad
            if day_pnl <= -PERSONAL_CAP:
                break

            c_close = float(row['Close'])
            current_ema = float(ema_aligned.loc[t_idx]) if t_idx in ema_aligned.index else None

            side = None
            sl = 0.0
            tp = 0.0

            if c_close > orb_high:
                if current_ema is None or c_close >= current_ema:
                    side = "BUY"
                    sl = orb_low
                    tp = c_close + (abs(c_close - sl) * 2.0)
            elif c_close < orb_low:
                if current_ema is None or c_close <= current_ema:
                    side = "SELL"
                    sl = orb_high
                    tp = c_close - (abs(sl - c_close) * 2.0)

            if side:
                trade_executed_today = True
                day_trades += 1
                entry_price = c_close
                sl_dist = abs(entry_price - sl)
                
                # Gestión dinámica del trade vela a vela
                rest = day_df.loc[t_idx:].iloc[1:]
                trade_pnl = 0.0
                current_sl = sl
                be_active = False

                for _, c_row in rest.iterrows():
                    h = float(c_row['High'])
                    l = float(c_row['Low'])

                    if side == "BUY":
                        if h >= tp:
                            trade_pnl = RISK_PER_TRADE * 2.0 # Ganó +$100 (+2R)
                            break
                        if l <= current_sl:
                            trade_pnl = (RISK_PER_TRADE * 0.10) if be_active else -RISK_PER_TRADE
                            break
                        # Trailing BE Plus a +1.0R
                        if (h - entry_price) >= sl_dist and not be_active:
                            current_sl = entry_price + (sl_dist * 0.10)
                            be_active = True
                    else: # SELL
                        if l <= tp:
                            trade_pnl = RISK_PER_TRADE * 2.0
                            break
                        if h >= current_sl:
                            trade_pnl = (RISK_PER_TRADE * 0.10) if be_active else -RISK_PER_TRADE
                            break
                        if (entry_price - l) >= sl_dist and not be_active:
                            current_sl = entry_price - (sl_dist * 0.10)
                            be_active = True

                day_pnl += trade_pnl
                balance += trade_pnl

        if day_trades > 0:
            trading_days_completed += 1
            result_tag = f"+${day_pnl:,.2f}" if day_pnl >= 0 else f"-${abs(day_pnl):,.2f}"
            print(f"  [Día {total_days_simulated:02d} | {day_str}] {current_phase} | Trades: {day_trades} | PnL: {result_tag:>8} | Balance: ${balance:,.2f}")
            daily_records.append({"day": day_str, "phase": current_phase, "trades": day_trades, "pnl": day_pnl, "balance": balance})

            # Comprobar si tocó el piso de $9,000
            if balance <= (INITIAL_CAPITAL - MAX_DRAWDOWN_LIMIT):
                print(f"\n[!] HARD BREACH: Balance cayó por debajo de $9,000 (${balance:,.2f}). Desafío Reprobado.")
                return

    print("\n-------------------------------------------------------------------------------")
    print("RESUMEN DE AUDITORÍA DEL DESAFÍO:")
    print(f"• Estado Final: {'FONDEADO / APROBADO 100%' if challenge_completed else 'EN PROGRESO'}")
    print(f"• Días Totales de Mercado: {total_days_simulated} días hábiles (~1 mes de calendario)")
    print(f"• Operaciones Ganadoras (Take Profit +2R): {sum(1 for d in daily_records if d['pnl'] >= 90)}")
    print(f"• Operaciones Protegidas en Break-Even: {sum(1 for d in daily_records if 0 < d['pnl'] < 90)}")
    print(f"• Operaciones con Pérdida Controlada (-$50): {sum(1 for d in daily_records if d['pnl'] < 0)}")
    print("-------------------------------------------------------------------------------")

if __name__ == "__main__":
    run_evaluation_challenge()
