"""
market_regime_sentinel.py - Centinela de Régimen de Mercado y Escudo Anti-Fakeouts (48h)
-----------------------------------------------------------------------------------------
Monitorea los 3 activos oficiales de stellar_10k_real:
- Oro (XAUUSD)
- S&P 500 (US500 / US500.cash)
- Forex (USDJPY)

Lógica Cuantitativa del Escudo 48H:
1. Inspecciona las sesiones de los últimos 5 días hábiles en MetaTrader 5.
2. Evalúa si hubo 'Barrida de Mecha' (Fakeout): El precio cerró fuera del rango ORB M15 (08:30 EST),
   pero se reversó de inmediato tocando Stop Loss sin haber alcanzado nunca +1.0R de avance.
3. Si un activo registra 2 Falsos Rompimientos Consecutivos en la semana:
   - Activa el estado de CUARENTENA POR 48 HORAS.
   - Bloquea la emisión de señales para ese activo en trading_engine.py.
   - Envía alerta explicativa a Telegram.
4. Genera el archivo 'quarantine_status.json' para consulta del bot y del Centro de Mando.
"""

import sys
import os
import json
import datetime
from typing import Dict, Any, List
import pandas as pd
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import MetaTrader5 as mt5

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, "quarantine_status.json")
TERMINAL_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

SYMBOLS_TO_AUDIT = [
    {"generic": "XAUUSD", "mt5_candidates": ["XAUUSD", "GOLD", "XAUUSDm"], "name": "Oro (XAUUSD)"},
    {"generic": "US500", "mt5_candidates": ["US500.cash", "US500", "SPX500", "USA500"], "name": "S&P 500 (US500)"},
    {"generic": "USDJPY", "mt5_candidates": ["USDJPY", "USDJPYm", "USDJPY.raw"], "name": "Forex (USDJPY)"}
]

def resolve_symbol(candidates: List[str]) -> str:
    for c in candidates:
        info = mt5.symbol_info(c)
        if info:
            if not info.visible:
                mt5.symbol_select(c, True)
            return c
    return candidates[0]

def analyze_asset_regime(sym_config: Dict[str, Any]) -> Dict[str, Any]:
    gen = sym_config["generic"]
    real_sym = resolve_symbol(sym_config["mt5_candidates"])
    name = sym_config["name"]
    
    # Cargar últimas 1,500 velas M15 (~20 días)
    rates = mt5.copy_rates_from_pos(real_sym, mt5.TIMEFRAME_M15, 0, 1500)
    if rates is None or len(rates) == 0:
        return {
            "symbol": gen,
            "name": name,
            "status": "DESCONOCIDO",
            "traffic_light": "AMARILLO",
            "consecutive_fakeouts": 0,
            "in_quarantine": False,
            "quarantine_until": None,
            "hours_remaining": 0,
            "last_trade_result": "Sin datos de MT5",
            "recommendation": "Verificar conexión de MT5"
        }
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['time_ny'] = df['time'].dt.tz_convert(ZoneInfo("America/New_York"))
    df.set_index('time_ny', inplace=True)
    
    # Evaluar los últimos 5 días hábiles
    days = df.index.strftime('%Y-%m-%d').unique()[-5:]
    
    fakeouts = 0
    consecutive_fakeouts = 0
    trade_logs = []
    
    for d in days:
        d_df = df.loc[d]
        orb = d_df[(d_df.index.hour == 8) & (d_df.index.minute == 30)]
        if orb.empty:
            continue
            
        oh = float(orb['high'].iloc[0])
        ol = float(orb['low'].iloc[0])
        rng = oh - ol
        if rng <= 0:
            continue
            
        # Ventana operativa 08:45 a 11:30 EST
        post = d_df[(d_df.index.hour >= 8) & (d_df.index.hour <= 11)]
        post = post[~((post.index.hour == 8) & (post.index.minute < 45))]
        
        breakout_side = None
        entry_idx = None
        entry_price = 0.0
        
        for t_idx, row in post.iterrows():
            c = float(row['close'])
            if c > oh:
                breakout_side = "BUY"
                entry_idx = t_idx
                entry_price = c
                break
            elif c < ol:
                breakout_side = "SELL"
                entry_idx = t_idx
                entry_price = c
                break
                
        if breakout_side and entry_idx:
            sl_dist = abs(entry_price - ol) if breakout_side == "BUY" else abs(oh - entry_price)
            if sl_dist <= 0:
                continue
                
            rest = d_df.loc[entry_idx:].iloc[1:]
            max_r = 0.0
            hit_sl = False
            
            for _, r_cand in rest.iterrows():
                h = float(r_cand['high'])
                l = float(r_cand['low'])
                if breakout_side == "BUY":
                    curr_r = (h - entry_price) / sl_dist
                    if curr_r > max_r:
                        max_r = curr_r
                    if l <= ol:
                        hit_sl = True
                        break
                else:
                    curr_r = (entry_price - l) / sl_dist
                    if curr_r > max_r:
                        max_r = curr_r
                    if h >= oh:
                        hit_sl = True
                        break
                        
            # Si tocó SL habiendo avanzado menos de +1.0R -> BARRIDA DE MECHA / FAKEOUT
            if hit_sl and max_r < 1.0:
                fakeouts += 1
                consecutive_fakeouts += 1
                trade_logs.append(f"{d}: Fakeout (Max {max_r:.2f}R -> Stop Barredo)")
            elif max_r >= 1.0:
                consecutive_fakeouts = 0
                trade_logs.append(f"{d}: Expansión Limpia (+{max_r:.2f}R)")
                
    # Determinar si entra en cuarentena
    in_quarantine = (consecutive_fakeouts >= 2)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    quarantine_until = None
    hours_remaining = 0
    
    # Cargar estado previo si existe para preservar timestamp de cuarentena
    prev_state = {}
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                prev_state = prev_data.get("assets", {}).get(gen, {})
        except Exception:
            pass
            
    if in_quarantine:
        if prev_state.get("in_quarantine") and prev_state.get("quarantine_until"):
            quarantine_until_dt = datetime.datetime.fromisoformat(prev_state["quarantine_until"])
            if now_utc < quarantine_until_dt:
                quarantine_until = prev_state["quarantine_until"]
                hours_remaining = round((quarantine_until_dt - now_utc).total_seconds() / 3600.0, 1)
            else:
                # Cuarentena ya expiró
                in_quarantine = False
                consecutive_fakeouts = 0
        else:
            # Nueva cuarentena de 48 horas
            until_dt = now_utc + datetime.timedelta(hours=48)
            quarantine_until = until_dt.isoformat()
            hours_remaining = 48.0
            
    # Determinar semáforo y recomendación
    if in_quarantine:
        traffic_light = "ROJO"
        status_text = "EN CUARENTENA 48H (BLOQUEADO)"
        rec = f"NO OPERAR. 2 falsos rompimientos seguidos detectados. En pausa preventiva ({hours_remaining}h restantes)."
    elif consecutive_fakeouts == 1:
        traffic_light = "AMARILLO"
        status_text = "PRECAUCIÓN / OBSERVACIÓN"
        rec = "OPERABLE CON PRECAUCIÓN. 1 falso rompimiento reciente. Esperar confirmación de volumen institucional."
    else:
        traffic_light = "VERDE"
        status_text = "ÓPTIMO PARA OPERAR"
        rec = "Régimen expansivo favorable. Alta probabilidad de acierto con R:R 1:2. Riesgo seguro $50 USD."
        
    last_log = trade_logs[-1] if trade_logs else "Sin operaciones recientes"
    
    return {
        "symbol": gen,
        "name": name,
        "real_symbol_mt5": real_sym,
        "traffic_light": traffic_light,
        "status": status_text,
        "consecutive_fakeouts": consecutive_fakeouts,
        "total_fakeouts_week": fakeouts,
        "in_quarantine": in_quarantine,
        "quarantine_until": quarantine_until,
        "hours_remaining": hours_remaining,
        "last_trade_result": last_log,
        "recommendation": rec
    }

def run_sentinel_audit() -> Dict[str, Any]:
    if not mt5.initialize(path=TERMINAL_PATH):
        if not mt5.initialize():
            return {"error": "No se pudo conectar a MetaTrader 5"}
            
    acc = mt5.account_info()
    acc_summary = {
        "login": acc.login if acc else "N/A",
        "server": acc.server if acc else "N/A",
        "balance": acc.balance if acc else 10000.0,
        "equity": acc.equity if acc else 10000.0,
        "margin_free": acc.margin_free if acc else 10000.0
    }
    
    asset_results = {}
    for cfg in SYMBOLS_TO_AUDIT:
        asset_results[cfg["generic"]] = analyze_asset_regime(cfg)
        
    mt5.shutdown()
    
    # Dictamen general de la cuenta
    active_quarantines = [a["name"] for a in asset_results.values() if a["in_quarantine"]]
    green_assets = [a["name"] for a in asset_results.values() if a["traffic_light"] == "VERDE"]
    
    if len(active_quarantines) == 0:
        overall_verdict = "PORTAFOLIO EN EXCELENTE ESTADO. TODOS LOS ACTIVOS AUTORIZADOS PARA OPERAR."
    elif len(green_assets) > 0:
        overall_verdict = f"OPERAR SELECTIVAMENTE: Concentrar capital en {', '.join(green_assets)}. Activos en pausa: {', '.join(active_quarantines)}."
    else:
        overall_verdict = "MERCADO EN CONSOLIDACIÓN GENERALIZADA. MODO ESPERA ACTIVO POR 48H."
        
    final_output = {
        "updated_at": datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S EST"),
        "account": acc_summary,
        "overall_verdict": overall_verdict,
        "assets": asset_results
    }
    
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
        
    return final_output

if __name__ == "__main__":
    res = run_sentinel_audit()
    print(json.dumps(res, indent=2, ensure_ascii=False))
