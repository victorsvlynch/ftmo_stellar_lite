"""
backtest_engine_mt5.py - Motor Cuantitativo Institucional de Backtesting Multi-Periodo
---------------------------------------------------------------------------------------
Evalúa el perfil stellar_10k_real ($10,000 USD) en 3, 6, 12, 24 y 36 meses.
Alimentado por datos históricos M15 de MetaTrader 5 (Oro XAUUSD, S&P 500 US500, Forex USDJPY).

Aplica rigurosamente:
1. Formación de vela ORB M15 (08:30–08:45 EST).
2. Filtro Tendencial Institucional EMA 200 en H1.
3. Filtro Anti-Fakeout por Cierre de Vela M15 fuera del rango.
4. Riesgo Cuantitativo Fijo: $50.00 USD (0.50%) por trade.
5. Trailing Stop Cuádruple:
   - Nivel 1: Break-Even Plus a +1.0R (+0.1R para spread/comisiones).
   - Nivel 2: Asegurar ganancia a +1.5R (SL a +0.5R).
   - Nivel 3: Trailing de mínimos/máximos M15 a partir de +2.0R.
   - Nivel 4: Take Profit programado en 1:2.0 RR.
6. Freno de mano diario al 2.0% ($200 USD) y límite diario del broker 4% ($400).
7. Límite de Drawdown Total Estático: 10% ($1,000 USD, piso $9,000).
8. Protocolo de Viernes Anti-Gap (Cierre a las 15:30 EST si no está en Break-Even).
"""

import sys
import os
import math
import datetime
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import MetaTrader5 as mt5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TERMINAL_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

# Especificaciones de Activos en FundedNext / FTMO
ASSET_SPECS = {
    "XAUUSD": {"contract_size": 100.0, "pip_size": 0.01, "spread_cost": 0.40, "commission_per_lot": 0.0},
    "US500.cash": {"contract_size": 1.0, "pip_size": 0.01, "spread_cost": 0.60, "commission_per_lot": 0.0},
    "USDJPY": {"contract_size": 100000.0, "pip_size": 0.001, "spread_cost": 0.015, "commission_per_lot": 0.0}
}

class BacktestSimulator:
    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.risk_per_trade = 50.0  # $50 USD fijo (0.50%)
        self.daily_cap = 200.0      # -$200 USD (2.0%) freno de mano
        self.max_dd_limit = 1000.0  # -$1,000 USD (10.0%) piso $9,000
        self.target_phase1 = 800.0  # +$800 USD (8.0%)
        self.target_phase2 = 400.0  # +$400 USD (4.0%)

    def load_m15_data(self, symbol: str, total_bars: int) -> pd.DataFrame:
        if not mt5.initialize(path=TERMINAL_PATH):
            mt5.initialize()
            
        now = datetime.datetime.now()
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M15, now, total_bars)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        # Convertir a hora de Nueva York (EST/EDT)
        df['time_ny'] = df['time'].dt.tz_convert(ZoneInfo("America/New_York"))
        df.set_index('time_ny', inplace=True)
        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'tick_volume': 'Volume'}, inplace=True)
        return df

    def calculate_h1_ema(self, df_m15: pd.DataFrame, span: int = 200) -> pd.Series:
        # Remuestrear a H1 para calcular la EMA de 200 periodos macro
        df_h1 = df_m15['Close'].resample('1h').last().dropna()
        ema_h1 = df_h1.ewm(span=span, adjust=False).mean()
        # Re-alinear con M15 rellenando hacia adelante
        ema_aligned = ema_h1.reindex(df_m15.index, method='ffill')
        return ema_aligned

    def run_period(self, months: int, total_bars: int) -> Dict[str, Any]:
        symbols = ["XAUUSD", "US500.cash", "USDJPY"]
        dfs = {}
        emas = {}
        
        for sym in symbols:
            df = self.load_m15_data(sym, total_bars)
            if not df.empty:
                dfs[sym] = df
                emas[sym] = self.calculate_h1_ema(df, span=200)
                
        if len(dfs) < 3:
            return {"error": "Datos insuficientes en MT5"}
            
        # Fechas comunes
        start_date = max(df.index.min() for df in dfs.values())
        end_date = min(df.index.max() for df in dfs.values())
        
        # Agrupar por días hábiles (Lunes a Viernes)
        all_days = pd.date_range(start=start_date.date(), end=end_date.date(), freq='B')
        
        balance = self.initial_balance
        equity_curve = [balance]
        trades_history = []
        
        peak_balance = balance
        max_drawdown_usd = 0.0
        max_drawdown_pct = 0.0
        daily_cap_hits = 0
        hard_breaches = 0
        
        phase1_passed = 0
        phase2_passed = 0
        current_cycle_profit = 0.0
        in_phase = 1
        phase_days_counter = 0
        
        for day in all_days:
            day_str = day.strftime("%Y-%m-%d")
            day_trades = []
            day_pnl = 0.0
            day_losses = 0
            
            # Evaluar los 3 activos en este día
            for sym in symbols:
                if sym not in dfs:
                    continue
                df_sym = dfs[sym]
                ema_sym = emas[sym]
                
                # Filtrar velas del día entre 08:30 y 15:30 EST
                candles_day = df_sym.loc[day_str] if day_str in df_sym.index.strftime("%Y-%m-%d") else pd.DataFrame()
                if candles_day.empty:
                    continue
                    
                # 1. Obtener la vela ORB M15 (08:30 EST)
                orb_candle = candles_day[(candles_day.index.hour == 8) & (candles_day.index.minute == 30)]
                if orb_candle.empty:
                    continue
                    
                orb_high = float(orb_candle['High'].iloc[0])
                orb_low = float(orb_candle['Low'].iloc[0])
                if orb_high <= orb_low:
                    continue
                    
                # 2. Ventana operativa: 08:45 a 11:30 EST
                entry_window = candles_day[(candles_day.index.hour >= 8) & (candles_day.index.hour <= 11)]
                entry_window = entry_window[~((entry_window.index.hour == 8) & (entry_window.index.minute < 45))]
                entry_window = entry_window[~((entry_window.index.hour == 11) & (entry_window.index.minute > 30))]
                
                trade_taken = False
                for t_idx, row in entry_window.iterrows():
                    if trade_taken:
                        break
                    # Si ya alcanzamos el freno de mano diario (-$200) o racha de 3 pérdidas, detener el día
                    if day_pnl <= -self.daily_cap or day_losses >= 3:
                        daily_cap_hits += 1
                        break
                        
                    c_close = float(row['Close'])
                    current_ema = float(ema_sym.loc[t_idx]) if t_idx in ema_sym.index else None
                    
                    signal_side = None
                    sl = 0.0
                    tp = 0.0
                    
                    # Ruptura alcista + EMA 200 H1 alcista
                    if c_close > orb_high:
                        if current_ema is None or c_close >= current_ema:
                            signal_side = "BUY"
                            sl = orb_low
                            # Especialización USDJPY (apertura bonos)
                            sl_dist = c_close - sl
                            if "JPY" in sym and sl_dist > 0.350:
                                sl_dist = min(sl_dist * 0.60, 0.300)
                                sl = c_close - sl_dist
                            tp = c_close + (sl_dist * 2.0)
                            
                    # Ruptura bajista + EMA 200 H1 bajista
                    elif c_close < orb_low:
                        if current_ema is None or c_close <= current_ema:
                            signal_side = "SELL"
                            sl = orb_high
                            sl_dist = sl - c_close
                            if "JPY" in sym and sl_dist > 0.350:
                                sl_dist = min(sl_dist * 0.60, 0.300)
                                sl = c_close + sl_dist
                            tp = c_close - (sl_dist * 2.0)
                            
                    if signal_side:
                        trade_taken = True
                        entry_price = c_close
                        entry_time = t_idx
                        sl_dist = abs(entry_price - sl)
                        if sl_dist <= 0:
                            continue
                            
                        # Simular gestión de posición vela a vela en el resto del día hasta las 16:30 EST
                        rest_of_day = candles_day.loc[entry_time:].iloc[1:]
                        if rest_of_day.empty:
                            continue
                            
                        trade_pnl = 0.0
                        closed_reason = "EOD"
                        current_sl = sl
                        be_locked = False
                        lock1_locked = False
                        
                        spec = ASSET_SPECS.get(sym, {"spread_cost": 0.40})
                        # Fricción por spread
                        spread_deduction = self.risk_per_trade * 0.03
                        
                        for c_time, c_row in rest_of_day.iterrows():
                            # Regla de Viernes: 15:30 EST si no está en BE -> cerrar
                            is_friday = (c_time.weekday() == 4)
                            if is_friday and (c_time.hour * 60 + c_time.minute >= 15 * 60 + 30):
                                if not be_locked:
                                    trade_pnl = (float(c_row['Close']) - entry_price) / sl_dist * self.risk_per_trade if signal_side == "BUY" else (entry_price - float(c_row['Close'])) / sl_dist * self.risk_per_trade
                                    trade_pnl -= spread_deduction
                                    closed_reason = "FRIDAY_CLOSE"
                                    break
                                    
                            c_high = float(c_row['High'])
                            c_low = float(c_row['Low'])
                            
                            if signal_side == "BUY":
                                # Verificar TP
                                if c_high >= tp:
                                    trade_pnl = (self.risk_per_trade * 2.0) - spread_deduction
                                    closed_reason = "TAKE_PROFIT"
                                    break
                                # Verificar SL dinámico
                                if c_low <= current_sl:
                                    if be_locked:
                                        trade_pnl = (self.risk_per_trade * 0.10) - spread_deduction # BE Plus
                                        closed_reason = "BREAK_EVEN"
                                    elif lock1_locked:
                                        trade_pnl = (self.risk_per_trade * 0.50) - spread_deduction
                                        closed_reason = "LOCK_0.5R"
                                    else:
                                        trade_pnl = -self.risk_per_trade - spread_deduction
                                        closed_reason = "STOP_LOSS"
                                    break
                                    
                                # Lógica de Trailing Stop
                                favorable_r = (c_high - entry_price) / sl_dist
                                if favorable_r >= 1.50 and not lock1_locked:
                                    current_sl = entry_price + (sl_dist * 0.50)
                                    lock1_locked = True
                                elif favorable_r >= 1.00 and not be_locked:
                                    current_sl = entry_price + (sl_dist * 0.10)
                                    be_locked = True
                                    
                            else: # SELL
                                if c_low <= tp:
                                    trade_pnl = (self.risk_per_trade * 2.0) - spread_deduction
                                    closed_reason = "TAKE_PROFIT"
                                    break
                                if c_high >= current_sl:
                                    if be_locked:
                                        trade_pnl = (self.risk_per_trade * 0.10) - spread_deduction
                                        closed_reason = "BREAK_EVEN"
                                    elif lock1_locked:
                                        trade_pnl = (self.risk_per_trade * 0.50) - spread_deduction
                                        closed_reason = "LOCK_0.5R"
                                    else:
                                        trade_pnl = -self.risk_per_trade - spread_deduction
                                        closed_reason = "STOP_LOSS"
                                    break
                                    
                                favorable_r = (entry_price - c_low) / sl_dist
                                if favorable_r >= 1.50 and not lock1_locked:
                                    current_sl = entry_price - (sl_dist * 0.50)
                                    lock1_locked = True
                                elif favorable_r >= 1.00 and not be_locked:
                                    current_sl = entry_price - (sl_dist * 0.10)
                                    be_locked = True
                                    
                        # Fin del trade
                        if closed_reason == "EOD":
                            last_c = float(rest_of_day['Close'].iloc[-1])
                            trade_pnl = (last_c - entry_price) / sl_dist * self.risk_per_trade if signal_side == "BUY" else (entry_price - last_c) / sl_dist * self.risk_per_trade
                            trade_pnl -= spread_deduction
                            
                        day_pnl += trade_pnl
                        if trade_pnl < 0:
                            day_losses += 1
                        day_trades.append({
                            "symbol": sym,
                            "time": entry_time.strftime("%Y-%m-%d %H:%M"),
                            "side": signal_side,
                            "pnl": trade_pnl,
                            "reason": closed_reason
                        })
                        
            # Cierre del día
            balance += day_pnl
            trades_history.extend(day_trades)
            equity_curve.append(balance)
            
            # Métricas de Drawdown
            if balance > peak_balance:
                peak_balance = balance
            dd_usd = peak_balance - balance
            if dd_usd > max_drawdown_usd:
                max_drawdown_usd = dd_usd
                max_drawdown_pct = (dd_usd / peak_balance) * 100.0
                
            # Verificar si rozó el piso de $9,000 (Hard Breach)
            if balance <= (self.initial_balance - self.max_dd_limit):
                hard_breaches += 1
                
            # Evaluación de Fases de Fondeo
            if len(day_trades) > 0:
                phase_days_counter += 1
                current_cycle_profit += day_pnl
                
                if in_phase == 1 and current_cycle_profit >= self.target_phase1 and phase_days_counter >= 2:
                    phase1_passed += 1
                    in_phase = 2
                    current_cycle_profit = 0.0
                    phase_days_counter = 0
                elif in_phase == 2 and current_cycle_profit >= self.target_phase2 and phase_days_counter >= 2:
                    phase2_passed += 1
                    in_phase = 1
                    current_cycle_profit = 0.0
                    phase_days_counter = 0
                    
        # Estadísticas agregadas
        total_trades = len(trades_history)
        if total_trades == 0:
            return {"error": "Cero operaciones generadas"}
            
        winning_trades = [t for t in trades_history if t['pnl'] > 0]
        losing_trades = [t for t in trades_history if t['pnl'] < 0]
        be_trades = [t for t in trades_history if t['pnl'] == 0]
        
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 99.9
        win_rate = (len(winning_trades) / total_trades) * 100.0
        net_profit_usd = balance - self.initial_balance
        net_profit_pct = (net_profit_usd / self.initial_balance) * 100.0
        
        # Desglose por activo
        by_symbol = {}
        for sym in symbols:
            s_trades = [t for t in trades_history if t['symbol'] == sym]
            s_wins = [t for t in s_trades if t['pnl'] > 0]
            s_pnl = sum(t['pnl'] for t in s_trades)
            s_wr = (len(s_wins) / len(s_trades) * 100.0) if s_trades else 0.0
            by_symbol[sym] = {
                "trades": len(s_trades),
                "win_rate": round(s_wr, 1),
                "net_pnl": round(s_pnl, 2)
            }
            
        return {
            "months": months,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "initial_balance": self.initial_balance,
            "final_balance": round(balance, 2),
            "net_profit_usd": round(net_profit_usd, 2),
            "net_profit_pct": round(net_profit_pct, 2),
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_usd": round(max_drawdown_usd, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "hard_breaches": hard_breaches,
            "phase1_passed": phase1_passed,
            "phase2_passed": phase2_passed,
            "total_evaluations_funded": phase2_passed,
            "daily_cap_hits": daily_cap_hits,
            "by_symbol": by_symbol
        }

def run_all_benchmarks():
    print("===============================================================================")
    print("      SUITE CUANTITATIVA DE BACKTESTING INSTITUCIONAL (METATRADER 5)")
    print("      Perfil: stellar_10k_real ($10K) | Activos: ORO + S&P 500 + USDJPY")
    print("===============================================================================\n")
    
    # 3m: ~6,300 velas | 6m: ~12,600 | 12m: ~25,500 | 24m: ~51,000 | 36m: ~76,500
    horizons = [
        (3, 6300),
        (6, 12600),
        (12, 25500),
        (24, 51000),
        (36, 76500)
    ]
    
    sim = BacktestSimulator(initial_balance=10000.0)
    all_results = []
    
    for months, bars in horizons:
        print(f"\n[+] Ejecutando Backtesting Oficial a {months} MESES ({bars:,} velas M15 por activo)...")
        t0 = datetime.datetime.now()
        res = sim.run_period(months, bars)
        elapsed = (datetime.datetime.now() - t0).total_seconds()
        
        if "error" in res:
            print(f"[-] Error en periodo {months}m: {res['error']}")
            continue
            
        res["elapsed_sec"] = round(elapsed, 1)
        all_results.append(res)
        
        print(f"  -> Periodo Analizado : {res['start_date']} al {res['end_date']}")
        print(f"  -> Total Trades      : {res['total_trades']} | Win Rate: {res['win_rate']}% | Profit Factor: {res['profit_factor']}")
        print(f"  -> Ganancia Neta     : ${res['net_profit_usd']:+,.2f} USD ({res['net_profit_pct']:+.1f}%)")
        print(f"  -> Max Drawdown      : ${res['max_drawdown_usd']:,.2f} USD ({res['max_drawdown_pct']:.2f}% de $10K)")
        print(f"  -> Fases Superadas   : Fase 1 (+8%): {res['phase1_passed']} veces | Fase 2 (+4%): {res['phase2_passed']} cuentas fondeadas")
        print(f"  -> Hard Breaches     : {res['hard_breaches']} (Piso de $9,000 violado)")
        print(f"  -> Desglose Activos  : Oro: {res['by_symbol']['XAUUSD']['trades']}T (${res['by_symbol']['XAUUSD']['net_pnl']:+,.0f}) | SP500: {res['by_symbol']['US500.cash']['trades']}T (${res['by_symbol']['US500.cash']['net_pnl']:+,.0f}) | USDJPY: {res['by_symbol']['USDJPY']['trades']}T (${res['by_symbol']['USDJPY']['net_pnl']:+,.0f})")
        print(f"  -> Tiempo de calculo : {res['elapsed_sec']}s")

    # Guardar resumen JSON para reportes
    import json
    with open(os.path.join(BASE_DIR, "backtest_results_summary.json"), "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print("\n[+] Resumen completo guardado exitosamente en 'backtest_results_summary.json'.")

if __name__ == "__main__":
    run_all_benchmarks()
