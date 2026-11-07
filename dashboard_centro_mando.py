"""
dashboard_centro_mando.py - Renderizador del Centro de Mando Ejecutivo en Español
----------------------------------------------------------------------------------
Presenta de manera simple, visual y con semáforos el diagnóstico del mercado,
el estado de la cuenta en MT5 y la recomendación exacta de qué hacer hoy.
"""

import os
import json
import datetime
from market_regime_sentinel import run_sentinel_audit, STATUS_FILE

def render_dashboard():
    # Ejecutar auditoría fresca
    data = run_sentinel_audit()
    
    acc = data["account"]
    verdict = data["overall_verdict"]
    assets = data["assets"]
    upd = data["updated_at"]
    
    print("\n" + "=" * 86)
    print("      🏛️  CENTRO DE MANDO INTELIGENTE - STELLAR 10K REAL (MAGIC 505003)")
    print("      Sistema Predictivo de Régimen de Mercado y Escudo Anti-Fakeouts (48h)")
    print("=" * 86)
    print(f"  Hora de Diagnóstico : {upd} (Nueva York / EST)")
    print(f"  Cuenta Conectada    : #{acc['login']} ({acc['server']})")
    print(f"  Balance en MT5      : ${acc['balance']:>10,.2f} USD")
    print(f"  Equidad en MT5      : ${acc['equity']:>10,.2f} USD | Margen Libre: ${acc['margin_free']:,.2f}")
    print(f"  Piso Inamovible     : $9,000.00 USD (Drawdown Máximo Permitido: $1,000 USD)")
    print("-" * 86)
    print("  🚦 SEMÁFORO DE ACTIVOS Y ESTADO DEL MERCADO PARA HOY:")
    print("-" * 86)
    
    icons = {"VERDE": "🟢", "AMARILLO": "🟡", "ROJO": "🔴"}
    
    for key, item in assets.items():
        icon = icons.get(item["traffic_light"], "⚪")
        print(f"\n  {icon} {item['name']:<18} | Estado: [{item['status']}]")
        print(f"     • Símbolo MT5     : {item['real_symbol_mt5']}")
        print(f"     • Falsos Romp.    : {item['consecutive_fakeouts']} consecutivos esta semana ({item['total_fakeouts_week']} en total)")
        print(f"     • Último Registro : {item['last_trade_result']}")
        if item["in_quarantine"]:
            print(f"     • 🔒 ESCUDO 48H   : ACTIVO. Reanudación automática en {item['hours_remaining']} horas.")
        print(f"     • 💡 Dictamen     : {item['recommendation']}")

    print("\n" + "=" * 86)
    print("  📋 RECOMENDACIÓN DEL ARQUITECTO CUANTITATIVO PARA LA SESIÓN DE HOY:")
    print("=" * 86)
    print(f"  >> {verdict}")
    print("=" * 86 + "\n")

if __name__ == "__main__":
    render_dashboard()
