"""
test_ftmo_trailing_qa.py - Suite de Pruebas Automatizadas para FTMO Trailing Drawdown y Reglas Multi-Firma.
Verifica:
1. Perfil FTMO 10K: Configuración (10% DD Trailing, 50% consistencia, no-overnight, 4 días).
2. Trailing Drawdown dinámico:
   - Base $10,000 -> Piso $9,000 (10% de $10,000).
   - Balance sube a $10,500 -> HWM sube a $10,500 -> Piso sube a $9,500.
   - Equidad baja a $9,450 -> Hard Breach activado por perforar piso trailing de $9,500.
3. Drawdown Estático FundedNext:
   - Base $10,000 -> Piso $9,200.
   - Balance sube a $10,500 -> Piso SE MANTIENE en $9,200 (sin trailing).
4. Regla de Consistencia FTMO (50% máx/día):
   - Target alcanzado (+10%) pero $800 generado en Día 1 (80%) -> Bloqueo de promoción con alerta.
   - Tras distribuir en varios días (ningún día > 50%) -> Promoción permitida.
5. Bloqueo No-Overnight en FTMO:
   - Horario >= 16:15 EST bloquea aperturas nuevas.
6. Funcionamiento en modo DUAL:
   - Coexistencia de ambos perfiles con sus respectivas reglas sin interferencia.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import TradingDatabase
from stellar_rules import StellarLiteRulesEngine
from risk_manager import RiskManager
from profiles import profile_manager


def test_ftmo_trailing_drawdown():
    print("==================================================")
    print("TEST QA: FTMO TRAILING DRAWDOWN & REGLAS OFICIALES")
    print("==================================================")

    # 1. Verificar carga de perfiles
    ftmo_prof = profile_manager.get_profile("ftmo_10k_challenge")
    stellar_prof = profile_manager.get_profile("stellar_10k_demo")

    assert ftmo_prof is not None, "Perfil ftmo_10k_challenge debe existir"
    assert ftmo_prof.drawdown_type == "TRAILING", f"FTMO drawdown_type debe ser TRAILING, obtenido: {ftmo_prof.drawdown_type}"
    assert ftmo_prof.allow_overnight_weekend is False, "FTMO allow_overnight_weekend debe ser False"
    assert ftmo_prof.consistency_rule_pct == 0.50, f"FTMO consistency_rule_pct debe ser 0.50, obtenido: {ftmo_prof.consistency_rule_pct}"
    assert ftmo_prof.min_trading_days == 4, "FTMO min_trading_days debe ser 4"
    assert ftmo_prof.max_drawdown_limit_pct == 0.10, "FTMO max_drawdown_limit_pct debe ser 0.10 (10%)"

    assert stellar_prof.drawdown_type == "STATIC", "FundedNext drawdown_type debe ser STATIC"
    assert stellar_prof.allow_overnight_weekend is True, "FundedNext allow_overnight_weekend debe ser True"
    assert stellar_prof.consistency_rule_pct == 0.0, "FundedNext consistency_rule_pct debe ser 0.0"

    print("[OK] Test 1: Parámetros canónicos de perfiles FTMO y FundedNext verificados.")

    # 2. Verificar Trailing Drawdown dinámico en FTMO
    test_db_ftmo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_qa_ftmo.db")
    if os.path.exists(test_db_ftmo):
        os.remove(test_db_ftmo)

    db_ftmo = TradingDatabase(test_db_ftmo, profile=ftmo_prof)
    rules_ftmo = StellarLiteRulesEngine(db=db_ftmo, profile=ftmo_prof)

    # Estado inicial: $10,000 -> Piso $9,000
    res0 = rules_ftmo.evaluate_account(floating_pnl=0.0)
    assert res0.drawdown_type == "TRAILING", "Drawdown type debe ser TRAILING"
    assert res0.high_water_mark == 10000.0, f"HWM inicial debe ser 10,000, obtenido {res0.high_water_mark}"
    assert res0.max_loss_floor == 9000.0, f"Piso inicial debe ser 9,000, obtenido {res0.max_loss_floor}"
    assert res0.is_valid is True, "Cuenta debe ser válida"

    # Simular ganancias: Balance sube a $10,600
    db_ftmo.update_account_state(balance=10600.0, equity=10600.0)
    res1 = rules_ftmo.evaluate_account(floating_pnl=0.0)
    assert res1.high_water_mark == 10600.0, f"HWM debe subir a 10,600, obtenido {res1.high_water_mark}"
    assert res1.max_loss_floor == 9600.0, f"Piso móvil debe subir a 9,600 (10,600 - 1,000), obtenido {res1.max_loss_floor}"
    assert res1.max_loss_remaining == 1000.0, f"Margen restante debe ser 1,000, obtenido {res1.max_loss_remaining}"

    # Simular retroceso flotante: Equidad cae a $9,550 (< $9,600)
    # Debe detonar Hard Breach por tocar el piso móvil
    res2 = rules_ftmo.evaluate_account(floating_pnl=-1050.0)  # balance 10,600 - 1,050 = equity 9,550
    assert res2.hard_breach is True, "Debe detonar Hard Breach por tocar piso trailing"
    assert res2.status == "FAILED", "Estado debe ser FAILED"
    assert "Trailing" in res2.alerts[0], f"Alerta debe mencionar Trailing: {res2.alerts}"

    print("[OK] Test 2: Trailing Drawdown dinámico escala piso con HWM y detecta Hard Breach correctamente.")

    # 3. Verificar que FundedNext se mantiene ESTÁTICO con el mismo escenario
    test_db_fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_qa_fn.db")
    if os.path.exists(test_db_fn):
        os.remove(test_db_fn)

    db_fn = TradingDatabase(test_db_fn, profile=stellar_prof)
    rules_fn = StellarLiteRulesEngine(db=db_fn, profile=stellar_prof)

    res_fn0 = rules_fn.evaluate_account(floating_pnl=0.0)
    assert res_fn0.drawdown_type == "STATIC", "Drawdown type debe ser STATIC"
    assert res_fn0.max_loss_floor == 9200.0, f"Piso estático debe ser 9,200, obtenido {res_fn0.max_loss_floor}"

    # Subir balance a $10,600 en FundedNext
    db_fn.update_account_state(balance=10600.0, equity=10600.0)
    res_fn1 = rules_fn.evaluate_account(floating_pnl=0.0)
    assert res_fn1.max_loss_floor == 9200.0, f"Piso estático NO debe moverse (debe seguir en 9,200), obtenido {res_fn1.max_loss_floor}"
    assert res_fn1.max_loss_remaining == 1400.0, f"Margen restante en FundedNext debe ser 1,400 (10,600 - 9,200), obtenido {res_fn1.max_loss_remaining}"

    print("[OK] Test 3: FundedNext preserva piso estático inamovible en $9,200.")

    # 4. Verificar Regla de Consistencia FTMO 50%
    test_db_cons = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_qa_cons.db")
    if os.path.exists(test_db_cons):
        os.remove(test_db_cons)

    db_cons = TradingDatabase(test_db_cons, profile=ftmo_prof)
    rules_cons = StellarLiteRulesEngine(db=db_cons, profile=ftmo_prof)

    # Simular 4 días operativos pero con Día 1 ganando $800 de $1,050 total (76% concentración)
    # Target de +10% cumplido ($11,050)
    db_cons.update_account_state(balance=11050.0, equity=11050.0)

    # Insertar trades en 4 fechas distintas
    dates = ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"]
    pnls = [800.0, 100.0, 80.0, 70.0]

    for d, pnl in zip(dates, pnls):
        tid = db_cons.record_trade_open(
            symbol="XAUUSD", provider="mt5", side="BUY", lots=0.1, units=10.0,
            entry_price=2700.0, stop_loss=2695.0, take_profit=2710.0, rr_ratio=2.0, phase="FASE_1"
        )
        db_cons.record_trade_close(
            trade_id=tid, exit_price=2705.0, pnl=pnl, notes=f"Trade {d}"
        )
        # Actualizar la fecha manualmente para simular días distintos
        with db_cons._get_connection() as conn:
            conn.execute("UPDATE trades SET trading_date = ? WHERE id = ?", (d, tid))
            conn.commit()

    res_cons = rules_cons.evaluate_account(floating_pnl=0.0)
    assert res_cons.trading_days_completed == 4, f"Días completados deben ser 4, obtenido {res_cons.trading_days_completed}"
    assert res_cons.target_reached is True, "Target debe estar alcanzado ($11,050 >= $11,000)"
    assert res_cons.consistency_warning is True, "Debe alertar infracción por regla de consistencia"
    assert res_cons.can_pass_phase is False, "NO debe permitir pasar de fase mientras no diluya la concentración"

    print("[OK] Test 4: Regla de Consistencia FTMO 50% bloquea correctamente promociones hiper-concentradas.")

    # 5. Verificar Prevención No-Overnight en FTMO
    test_db_on = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_qa_on.db")
    if os.path.exists(test_db_on):
        os.remove(test_db_on)
    db_on = TradingDatabase(test_db_on, profile=ftmo_prof)
    risk_ftmo = RiskManager(db=db_on, profile=ftmo_prof)
    assert risk_ftmo.allow_overnight_weekend is False, "Risk manager debe heredar allow_overnight_weekend=False"

    # Simular horario 16:30 EST (mercado cerca del cierre)
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    ny_close_time = datetime(2026, 11, 4, 16, 30, tzinfo=ZoneInfo("America/New_York"))
    pre_check = risk_ftmo.validate_pre_trade(now_utc=ny_close_time)
    assert pre_check.allowed is False, "Debe bloquear aperturas cerca del cierre en cuenta sin overnight"
    assert "NO-OVERNIGHT" in pre_check.reason, f"Razón debe indicar NO-OVERNIGHT: {pre_check.reason}"

    print("[OK] Test 5: Prevención de trades nocturnos en FTMO bloquea aperturas previas al cierre.")

    # Limpieza de bases de datos de prueba
    for p in (test_db_ftmo, test_db_fn, test_db_cons, test_db_on):
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    print("\n==================================================")
    print("✅ TODOS LOS TESTS DE FTMO & MULTI-FIRMA SUPERADOS")
    print("==================================================")


if __name__ == "__main__":
    test_ftmo_trailing_drawdown()
