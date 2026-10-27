#!/usr/bin/env python3
"""
main.py - Punto de Entrada Principal (CLI y Demonio 24/7 para Oracle Cloud Infrastructure).
Simulador y Motor de Trading Automatizado para Cuentas de Fondeo FundedNext - Stellar Lite ($5,000).
100% Python Puro, Persistencia SQLite (`trading_history.db`) y Auto-instalación de Dependencias.
"""

import importlib
import os
import subprocess
import sys
import time
import threading
import argparse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


REQUIRED_PACKAGES = {
    "pandas": "pandas>=2.0.0",
    "numpy": "numpy>=1.24.0",
    "multitasking": "multitasking<=0.0.11",
    "yfinance": "yfinance<=0.2.54",
    "ccxt": "ccxt>=4.2.0",
}
if sys.version_info < (3, 9):
    REQUIRED_PACKAGES["backports.zoneinfo"] = "backports.zoneinfo"


def ensure_dependencies() -> None:
    """
    Verifica si las librerías requeridas están instaladas en el entorno global de Python.
    Si falta alguna o falla el import, la instala/reinstala mediante pip3.
    """
    missing = []
    for mod_name, pkg_spec in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(mod_name)
        except Exception:
            missing.append(pkg_spec)

    if not missing:
        return

    for pkg_spec in missing:
        flags = ["--force-reinstall"] if "multitasking" in pkg_spec else []
        cmd_standard = [sys.executable, "-m", "pip", "install", "-q"] + flags + [pkg_spec]
        res = subprocess.run(cmd_standard, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            cmd_pep668 = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "--break-system-packages",
            ] + flags + [pkg_spec]
            subprocess.run(cmd_pep668, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Patch preventivo en caso de instalación de multitasking con sintaxis PEP 585 en Python 3.8
    if sys.version_info < (3, 9):
        subprocess.run(
            "sed -i 's/type\\[Thread\\]/Thread/g; s/type\\[Process\\]/Process/g' "
            "/usr/local/lib/python3.8/dist-packages/multitasking/__init__.py 2>/dev/null || true",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


# Ejecutar auto-verificación de dependencias antes de importar módulos del motor
ensure_dependencies()

from database import TradingDatabase, DB_DEFAULT_PATH  # noqa: E402
from stellar_rules import StellarLiteRulesEngine  # noqa: E402
from risk_manager import RiskManager  # noqa: E402
from trading_engine import AutomatedTradingEngine, MarketDataConnector  # noqa: E402


def print_console_report(
    db: TradingDatabase,
    rules: StellarLiteRulesEngine,
    risk: RiskManager,
    engine: AutomatedTradingEngine,
) -> None:
    """
    Imprime en consola un reporte resumido claro y formateado con:
    - Balance actual, Equidad flotante y PnL flotante
    - Fase actual y Estado de la cuenta (Fase 1, Fase 2, Fondeada o Fallada)
    - Límites de riesgo estáticos FundedNext (Daily Loss 4%, Max Loss 8%) y Freno Personal (2%)
    - Regla del 40% de Noticias y Días Operativos
    - Resumen de operaciones abiertas y cerradas del día
    """
    floating_pnl, open_positions = engine.calculate_open_positions_floating_pnl()
    state = rules.evaluate_account(floating_pnl=floating_pnl)
    pre_trade = risk.validate_pre_trade(floating_pnl=floating_pnl)
    acc = db.get_account_state()
    trading_date = str(acc["current_trading_day"])
    todays_trades = db.get_trades_by_date(trading_date)

    closed_today = [t for t in todays_trades if t["status"] == "CLOSED"]
    wins_today = sum(1 for t in closed_today if float(t["pnl"]) > 0)
    losses_today = sum(1 for t in closed_today if float(t["pnl"]) < 0)
    realized_today = sum(float(t["pnl"]) for t in closed_today)

    target_str = (
        f"${state.profit_target_balance:,.2f} (+${state.profit_target_amount:,.2f})"
        if state.profit_target_balance is not None
        else f"SIN TARGET (Profit Split: {state.profit_split * 100:.0f}%)"
    )

    sep = "=" * 78
    subsep = "-" * 78
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    strat_label = "NY ORB 15m (08:30 EST)"
    if risk.session_mode in ("LONDON_OPEN", "LONDON"):
        strat_label = "LONDON ORB 15m (03:00 EST)"
    elif risk.session_mode in ("COMBO_DUAL", "NY_LONDON"):
        strat_label = "COMBO DUAL (LDN 03:00 + NY 08:30 EST)"
    elif risk.session_mode == "COMBO_TRIO":
        strat_label = "COMBO TRÍO 24/7 (LDN + NY + CRIPTO)"
    elif risk.session_mode in ("ALL", "CRYPTO_24H"):
        strat_label = "CRIPTO ORB 15m (24/7 Continuo)"

    print(f"\n{sep}")
    print("   FUNDEDNEXT STELLAR LITE ($5K) - MOTOR CUANTITATIVO & GESTOR DE RIESGO")
    print(f"{sep}")
    print(f" Fecha/Hora Servidor : {now_str} | Jornada: {trading_date}")
    print(f" Fase de Cuenta      : {state.phase:<12} | Estado : {state.status}")
    print(f" Activo / Estrategia : {engine.symbol} ({engine.provider}) | {strat_label} (R:R 1:{risk.rr_ratio:.0f})")
    print(f" Sesión de Mercado   : {pre_trade.active_session}")
    print(subsep)
    print(" [MÉTRICAS DE CAPITAL Y EQUIDAD]")
    print(f"  Balance Inicial Fase : ${float(acc['initial_balance']):>10,.2f}   | Balance Inicio Día : ${state.day_start_balance:>10,.2f}")
    print(f"  Balance Cerrado      : ${state.balance:>10,.2f}   | PnL Flotante       : ${state.floating_pnl:>+10,.2f}")
    print(f"  Equidad Actual       : ${state.equity:>10,.2f}   | Profit Acumulado   : ${state.current_profit:>+10,.2f}")
    print(f"  Objetivo de Fase     : {target_str}")
    print(subsep)
    print(" [REGLAS OFICIALES FUNDEDNEXT & GESTIÓN DE RIESGO]")
    print(
        f"  Piso Pérdida Diaria (4% Estático) : ${state.daily_loss_floor:>8,.2f} "
        f"(Margen restante: ${state.daily_loss_remaining:>7,.2f})"
    )
    print(
        f"  Piso Max Drawdown   (8% Estático) : ${state.max_loss_floor:>8,.2f} "
        f"(Margen restante: ${state.max_loss_remaining:>7,.2f})"
    )
    personal_cap_pct = float(acc.get("personal_daily_cap_pct", risk.personal_daily_cap_pct))
    personal_floor = round(state.day_start_balance * (1.0 - personal_cap_pct), 2)
    print(
        f"  Freno Personal Diario (-{personal_cap_pct * 100:.1f}%)     : ${personal_floor:>8,.2f} "
        f"| Riesgo/Trade: {float(acc.get('risk_per_trade_pct', risk.default_risk_pct)) * 100:.2f}%"
    )
    print(
        f"  Días Operativos Fase              : {state.trading_days_completed}/{state.min_trading_days_required} mín. "
        f"| Ratio Profit Noticias (Cap 40%): {state.news_profit_ratio * 100:.1f}%"
    )
    print(
        f"  Racha Pérdidas Hoy (Tilt Alert 3) : {pre_trade.consecutive_losses_today}/3 "
        f"{'[BLOQUEO TILT ACTIVO]' if pre_trade.tilt_locked else '[OK]'}"
    )

    if state.alerts:
        print(subsep)
        print(" [ALERTAS DE REGLAS Y AUDITORÍA]")
        for alert in state.alerts:
            print(f"  ! {alert}")

    if hasattr(state, "real_account_recommendations") and state.real_account_recommendations:
        print(subsep)
        print(" [GUÍA & RECOMENDACIONES PARA CUENTA REAL / PROP FIRM]")
        for rec in state.real_account_recommendations:
            print(f"  * {rec}")

    print(subsep)
    print(" [VERIFICACIÓN DE PASO DE FASE / FONDEO]")
    if state.hard_breach:
        print("  ❌ NO ES POSIBLE AVANZAR: Cuenta en estado FALLADA por Hard Breach.")
    elif state.target_reached and state.waiting_min_days:
        next_step = "Fase 2" if state.phase == "FASE_1" else "Cuenta Fondeada"
        print(f"  ⏳ AÚN NO ES POSIBLE PASAR A {next_step.upper()} (Falta 1 condición):")
        print(f"     1. Objetivo Financiero de Beneficio: CUMPLIDO (${state.balance:,.2f} >= ${state.profit_target_balance:,.2f}) ✅")
        print(f"     2. Días Operativos Requeridos: PENDIENTE ({state.trading_days_completed}/{state.min_trading_days_required} días mínimos) ⚠️")
        print(f"     -> ¿Qué debes hacer?: No operar más hoy para no arriesgar el balance ganado.")
        print(f"     -> En la siguiente jornada UTC (mañana tras 00:00 UTC): El bot operará en Modo Micro-Lote de Seguridad (0.01 lotes)")
        print(f"        para registrar el día 2/2 y certificar el paso a {next_step.upper()} con riesgo casi cero.")
    elif state.target_reached and (state.trading_days_completed >= state.min_trading_days_required or state.can_pass_phase):
        next_step = "Fase 2" if state.phase == "FASE_1" else "Cuenta Fondeada"
        print(f"  ✅ ¡SÍ ES POSIBLE PASAR A {next_step.upper()}!")
        print(f"     - Tanto el objetivo de profit como los {state.min_trading_days_required} días mínimos están 100% CUMPLIDOS.")
        print(f"     -> Acción requerida: Ingresa al dashboard de FundedNext para reclamar las credenciales.")
    elif state.phase == "FONDEADA":
        print(f"  💎 CUENTA FONDEADA ACTIVA (Split {state.profit_split * 100:.0f}%). No requiere target obligatorio.")
    else:
        print(f"  ⏳ EN CURSO: Falta alcanzar el objetivo financiero de {state.phase} (${state.profit_target_balance:,.2f}).")

    print(subsep)
    print(
        f" [RESUMEN DE OPERACIONES DEL DÍA ({trading_date})] -> "
        f"Total: {len(todays_trades)} | Abiertas: {len(open_positions)} | "
        f"Cerradas: {len(closed_today)} (W:{wins_today} / L:{losses_today}) | "
        f"PnL Cerrado Hoy: ${realized_today:+,.2f}"
    )

    if open_positions:
        print("\n  Posiciones Abiertas:")
        print("  ID   Símbolo   Lado  Lotes    Entrada      SL           TP           Precio Act.  PnL Flotante")
        for pos in open_positions:
            print(
                f"  #{pos['id']:<3} {pos['symbol']:<9} {pos['side']:<5} {pos['lots']:<8.4f} "
                f"{pos['entry_price']:<12.4f} {pos['stop_loss']:<12.4f} {pos['take_profit']:<12.4f} "
                f"{pos['mark_price']:<12.4f} ${pos['floating_pnl']:>+9,.2f}"
            )

    if closed_today:
        print("\n  Operaciones Cerradas Hoy:")
        print("  ID   Símbolo   Lado  Lotes    Entrada      Salida       PnL Realizado  Notas")
        for tr in closed_today[-10:]:
            print(
                f"  #{tr['id']:<3} {tr['symbol']:<9} {tr['side']:<5} {tr['lots']:<8.4f} "
                f"{tr['entry_price']:<12.4f} {float(tr['exit_price'] or 0):<12.4f} "
                f"${float(tr['pnl']):>+11,.2f}   {tr['notes'][:28]}"
            )

    print(f"{sep}\n")


def run_simulation_demo(
    db: TradingDatabase,
    rules: StellarLiteRulesEngine,
    risk: RiskManager,
    engine: AutomatedTradingEngine,
) -> None:
    """
    Ejecuta una simulación acelerada de operaciones NY ORB 15m para validar
    el cálculo de lotaje, cobro de TP/SL, control de riesgo y persistencia SQLite.
    """
    print("\n[*] Iniciando simulación de ciclo operativo NY ORB 15m...")
    base_time = datetime.now(timezone.utc)

    # 1. Ejecutar ciclo de apertura forzado en sesión NY
    res = engine.run_single_cycle(ignore_session_filter=True, force_signal_side="BUY", now_utc=base_time)
    print(f" -> Ciclo 1: {res['action']} | {res['message']}")

    # 2. Simular avance de precio al Take Profit (R:R 1:2)
    open_trades = db.get_open_trades()
    if open_trades:
        tr = open_trades[0]
        tp_price = float(tr["take_profit"])
        engine.manage_open_positions(
            current_prices={tr["symbol"]: tp_price},
            now_utc=base_time + timedelta(minutes=30),
        )
        print(f" -> Trade #{tr['id']} alcanzó Take Profit @ {tp_price} (R:R 1:2).")

    print_console_report(db, rules, risk, engine)


def run_interactive_cli(
    db: TradingDatabase,
    rules: StellarLiteRulesEngine,
    risk: RiskManager,
    engine: AutomatedTradingEngine,
) -> None:
    """Modo interactivo por consola para consultas y pruebas manuales."""
    print_console_report(db, rules, risk, engine)
    help_text = (
        "Comandos disponibles:\n"
        "  status                  - Muestra el reporte completo de la cuenta y operaciones del día\n"
        "  cycle                   - Ejecuta un ciclo en vivo de la estrategia NY ORB 15m\n"
        "  force_buy / force_sell  - Abre una operación ORB 15m de prueba (ignorando filtro horario)\n"
        "  close_all               - Cierra todas las posiciones abiertas al precio actual de mercado\n"
        "  calc <entry> <sl>       - Calcula el lotaje exacto para el activo actual según riesgo configurado\n"
        "  history                 - Muestra las últimas 15 operaciones en SQLite\n"
        "  events                  - Muestra el registro de auditoría de reglas\n"
        "  reset                   - Reinicia la cuenta a $5,000.00 en FASE_1\n"
        "  exit / quit             - Sale del programa"
    )
    print(help_text)

    while True:
        try:
            raw_cmd = input("\nstellar-cli> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo del modo interactivo...")
            break

        if not raw_cmd:
            continue

        parts = raw_cmd.split()
        cmd = parts[0].lower()

        if cmd in ("exit", "quit", "q"):
            break
        elif cmd == "help":
            print(help_text)
        elif cmd == "status":
            print_console_report(db, rules, risk, engine)
        elif cmd == "cycle":
            res = engine.run_single_cycle(ignore_session_filter=False)
            print(f"[{res['action']}] {res['message']}")
            print_console_report(db, rules, risk, engine)
        elif cmd in ("force_buy", "force_sell"):
            side = "BUY" if cmd == "force_buy" else "SELL"
            res = engine.run_single_cycle(ignore_session_filter=True, force_signal_side=side)
            print(f"[{res['action']}] {res['message']}")
            print_console_report(db, rules, risk, engine)
        elif cmd == "close_all":
            _, open_pos = engine.calculate_open_positions_floating_pnl()
            if not open_pos:
                print("No hay posiciones abiertas para cerrar.")
            else:
                for p in open_pos:
                    db.record_trade_close(
                        trade_id=int(p["id"]),
                        exit_price=float(p["mark_price"]),
                        pnl=float(p["floating_pnl"]),
                        notes="CIERRE_MANUAL_CLI",
                    )
                print(f"Se cerraron {len(open_pos)} posiciones abiertas.")
                print_console_report(db, rules, risk, engine)
        elif cmd == "calc" and len(parts) >= 3:
            try:
                entry_p = float(parts[1])
                sl_p = float(parts[2])
                acc = db.get_account_state()
                side = "BUY" if entry_p > sl_p else "SELL"
                sz = risk.calculate_position_size(
                    balance=float(acc["balance"]),
                    symbol=engine.symbol,
                    side=side,
                    entry_price=entry_p,
                    stop_loss=sl_p,
                )
                print(
                    f" -> Calculadora de Lote ({sz.symbol} {sz.side}): "
                    f"Lotes={sz.lots} ({sz.units} uds) | Riesgo=${sz.risk_amount_usd:,.2f} ({sz.risk_pct * 100:.2f}%) | "
                    f"SL={sz.stop_loss} ({sz.sl_distance_pips} pips) | TP={sz.take_profit} (Reward=${sz.expected_reward_usd:,.2f})"
                )
            except Exception as exc:
                print(f"Error en cálculo: {exc}")
        elif cmd == "telegram_test":
            if engine.notifier.enabled:
                ok = engine.notifier.send_message("<b>🤖 TEST NOTIFICACIÓN</b>: Conexión exitosa con FundedNext Stellar Lite Bot.")
                print(" [*] Notificación de prueba enviada a Telegram." if ok else " [!] Error al contactar con la API de Telegram.")
            else:
                print(" [!] Telegram no configurado. Cree 'telegram_config.json' o use variables de entorno TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.")
        elif cmd == "history":
            trades = db.get_all_trades(limit=15)
            if not trades:
                print("No hay operaciones registradas en la base de datos.")
            else:
                for t in trades:
                    print(
                        f" #{t['id']} | {t['trading_date']} | {t['phase']} | {t['symbol']} {t['side']} "
                        f"{t['lots']} lotes | Entry:{t['entry_price']} Exit:{t['exit_price']} | "
                        f"PnL:${float(t['pnl']):+,.2f} | {t['status']} ({t['notes']})"
                    )
        elif cmd == "events":
            events = db.get_recent_events(limit=15)
            for ev in events:
                print(f" [{ev['timestamp']}] ({ev['phase']}) {ev['event_type']}: {ev['message']}")
        elif cmd == "reset":
            db.reset_account()
            print("Cuenta reiniciada a $5,000.00 (FASE_1).")
            print_console_report(db, rules, risk, engine)
        else:
            print("Comando no reconocido. Escriba 'help' para ver la lista de comandos.")


import threading


class LiveDataWorker:
    """Hilo secundario para consulta asíncrona de precios y base de datos sin congelar el reloj."""

    def __init__(
        self,
        db: TradingDatabase,
        rules: StellarLiteRulesEngine,
        risk: RiskManager,
        engine: AutomatedTradingEngine,
    ) -> None:
        self.db = db
        self.rules = rules
        self.risk = risk
        self.engine = engine
        self.lock = threading.Lock()
        self.price = 0.0
        self.price_label = "CONSULTANDO..."
        self.floating_pnl = 0.0
        self.open_positions: list = []
        self.rule_state = None
        self.pre_trade = None
        self.acc = self.db.get_account_state()
        self.todays_trades: list = []
        self.closed_today: list = []
        self.wins_today = 0
        self.losses_today = 0
        self.realized_today = 0.0
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def _worker_loop(self) -> None:
        while self.running:
            try:
                # 1. Obtener precio en segundo plano sin bloquear el reloj UI
                try:
                    price = self.engine.connector.get_latest_price(
                        symbol=self.engine.symbol, provider=self.engine.provider
                    )
                    price_lbl = f"${price:,.2f}"
                except Exception:
                    price = self.price
                    price_lbl = f"${price:,.2f}" if price > 0 else "CONECTANDO..."

                # 2. Consultar SQLite y reglas de riesgo
                cached_prices = {self.engine.symbol: price} if price > 0 else {}
                floating_pnl, open_pos = self.engine.calculate_open_positions_floating_pnl(
                    current_prices=cached_prices
                )
                rule_st = self.rules.evaluate_account(floating_pnl=floating_pnl)
                pre_tr = self.risk.validate_pre_trade(floating_pnl=floating_pnl)
                acc_st = self.db.get_account_state()
                t_date = str(acc_st.get("current_trading_day", ""))
                t_trades = self.db.get_trades_by_date(t_date) if t_date else []
                c_today = [t for t in t_trades if t["status"] == "CLOSED"]
                w_today = sum(1 for t in c_today if float(t["pnl"]) > 0)
                l_today = sum(1 for t in c_today if float(t["pnl"]) < 0)
                r_today = sum(float(t["pnl"]) for t in c_today)

                with self.lock:
                    self.price = price
                    self.price_label = price_lbl
                    self.floating_pnl = floating_pnl
                    self.open_positions = open_pos
                    self.rule_state = rule_st
                    self.pre_trade = pre_tr
                    self.acc = acc_st
                    self.todays_trades = t_trades
                    self.closed_today = c_today
                    self.wins_today = w_today
                    self.losses_today = l_today
                    self.realized_today = r_today
            except Exception:
                pass
            time.sleep(3.0)


def run_live_dashboard(
    db: TradingDatabase,
    rules: StellarLiteRulesEngine,
    risk: RiskManager,
    engine: AutomatedTradingEngine,
    refresh_rate: float = 1.0,
) -> None:
    """
    Monitor en Vivo de Alta Velocidad (100% In-Place, sin parpadeo y reloj fluido).
    - Hilo secundario para consultas de red.
    - El hilo principal redibuja en el lugar exacto sin hacer scroll vertical.
    - Sincronización milimétrica con el segundo natural de la hora UTC.
    """
    worker = LiveDataWorker(db, rules, risk, engine)
    time.sleep(0.4)

    sep = "=" * 78
    subsep = "-" * 78

    try:
        while True:
            now_utc = datetime.now(timezone.utc)
            now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

            with worker.lock:
                state = worker.rule_state
                pre_trade = worker.pre_trade
                acc = worker.acc
                price_tag = worker.price_label
                floating_pnl = worker.floating_pnl
                open_positions = list(worker.open_positions)
                closed_today = list(worker.closed_today)
                wins_today = worker.wins_today
                losses_today = worker.losses_today
                realized_today = worker.realized_today
                total_trades_count = len(worker.todays_trades)
                trading_date = str(acc.get("current_trading_day", now_utc.strftime("%Y-%m-%d")))

            if state is None or pre_trade is None:
                time.sleep(0.1)
                continue

            target_str = (
                f"${state.profit_target_balance:,.2f} (+${state.profit_target_amount:,.2f})"
                if state.profit_target_balance is not None
                else f"SIN TARGET (Split: {state.profit_split * 100:.0f}%)"
            )
            personal_cap_pct = float(acc.get("personal_daily_cap_pct", risk.personal_daily_cap_pct))
            personal_floor = round(state.day_start_balance * (1.0 - personal_cap_pct), 2)

            strat_label = "NY ORB 15m"
            if risk.session_mode in ("LONDON_OPEN", "LONDON"):
                strat_label = "LONDON ORB 15m"
            elif risk.session_mode in ("COMBO_DUAL", "NY_LONDON"):
                strat_label = "NY+LDN ORB 15m"
            elif risk.session_mode == "COMBO_TRIO":
                strat_label = "TRIO 24/7 ORB"
            elif risk.session_mode in ("ALL", "CRYPTO_24H"):
                strat_label = "CRIPTO 15m"

            # Bloque compacto de exactamente 19 líneas: CERO scroll en cualquier terminal
            lines = [
                "\033[H\033[J" + sep,
                f" FUNDEDNEXT STELLAR LITE ($5K) | HORA SERVIDOR: {now_str}",
                sep,
                f" Cuenta   : {state.phase:<9} Estado: {state.status:<7} | Activo : {engine.symbol} ({price_tag})",
                f" Estrategia: {strat_label} (R:R 1:{risk.rr_ratio:.0f}) | Sesion : {pre_trade.active_session}",
                subsep,
                f" Balance Base : ${float(acc['initial_balance']):>9,.2f}  | Inicio Dia  : ${state.day_start_balance:>9,.2f}",
                f" Balance Cerr : ${state.balance:>9,.2f}  | Flotante    : ${floating_pnl:>+9,.2f}",
                f" Equidad Act  : ${state.equity:>9,.2f}  | Profit Total: ${state.current_profit:>+9,.2f}",
                f" Objetivo     : {target_str}",
                subsep,
                f" Piso Diario (4%): ${state.daily_loss_floor:>8,.2f} (Margen: ${state.daily_loss_remaining:>7,.2f}) | Freno Pers (-2%): ${personal_floor:>8,.2f}",
                f" Piso Max DD (8%): ${state.max_loss_floor:>8,.2f} (Margen: ${state.max_loss_remaining:>7,.2f}) | Riesgo/Trade    : {float(acc.get('risk_per_trade_pct', risk.default_risk_pct)) * 100:.2f}%",
                f" Dias Minimos    : {state.trading_days_completed}/{state.min_trading_days_required} cumplidos       | Racha Perdidas  : {pre_trade.consecutive_losses_today}/3 {'[TILT]' if pre_trade.tilt_locked else '[OK]'}",
                subsep,
                f" Operaciones Hoy ({trading_date}): Total={total_trades_count} | Abiertas={len(open_positions)} | Cerradas={len(closed_today)} (W:{wins_today} L:{losses_today}) | PnL Hoy=${realized_today:+,.2f}",
            ]

            if open_positions:
                p = open_positions[0]
                lines.append(
                    f" Posicion Activa: #{p['id']} {p['symbol']} {p['side']} {p['lots']}L @ {p['entry_price']} | Flotante: ${p.get('floating_pnl', 0.0):+,.2f}"
                )
            else:
                lines.append(" Posicion Activa: Ninguna en curso. Monitoreando vela NY ORB 15m...")

            lines.append(sep)
            lines.append(" >> EN VIVO | Actualizando cada 1s en su lugar | Presione Ctrl+C para salir <<")

            # Escritura directa en memoria de terminal
            sys.stdout.write("\n".join(lines))
            sys.stdout.flush()

            # Sincronización exacta con el segundo del reloj real
            time.sleep(max(0.1, 1.0 - (time.time() % 1.0)))

    except KeyboardInterrupt:
        worker.running = False
        print("\n\n[*] Monitor en vivo finalizado.")


MODALITIES_METADATA = [
    {
        "id": "1_NY_OPEN",
        "num": "1",
        "label": "NY_OPEN (Apertura NY)",
        "db": "trading_ny_open.db",
        "symbol": "GC=F",
        "provider": "yfinance",
        "session": "NY_OPEN",
        "hours": "08:30-11:30 EST",
        "service": "stellar_ny_open.service",
    },
    {
        "id": "2_LONDON_OPEN",
        "num": "2",
        "label": "LONDON_OPEN (Apertura)",
        "db": "trading_london_open.db",
        "symbol": "GC=F",
        "provider": "yfinance",
        "session": "LONDON_OPEN",
        "hours": "03:00-06:00 EST",
        "service": "stellar_london_open.service",
    },
    {
        "id": "3_CRYPTO_24H",
        "num": "3",
        "label": "CRYPTO_24H (24/7)",
        "db": "trading_crypto_24h.db",
        "symbol": "BTC/USDT",
        "provider": "ccxt",
        "session": "ALL",
        "hours": "24h Continuo",
        "service": "stellar_crypto_24h.service",
    },
    {
        "id": "4_NY_LONDON",
        "num": "4",
        "label": "NY_OPEN + LONDON",
        "db": "trading_ny_london.db",
        "symbol": "GC=F",
        "provider": "yfinance",
        "session": "COMBO_DUAL",
        "hours": "03-06 & 08:30-11",
        "service": "stellar_ny_london.service",
    },
    {
        "id": "5_COMBO_TRIO",
        "num": "5",
        "label": "NY + LDN + CRYPTO 24H",
        "db": "trading_combo_trio.db",
        "symbol": "GC=F,BTC/USDT",
        "provider": "multi",
        "session": "COMBO_TRIO",
        "hours": "24h (Dual+Crpt)",
        "service": "stellar_combo_trio.service",
    },
]


class MultiPriceWorker:
    """Hilo secundario para consulta asíncrona periódica de precios de activos sin congelar el reloj."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.prices: dict = {"GC=F": 0.0, "BTC/USDT": 0.0}
        self.running = True
        self.connector = MarketDataConnector()
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def _worker_loop(self) -> None:
        while self.running:
            for sym, prov in [("GC=F", "yfinance"), ("BTC/USDT", "ccxt")]:
                try:
                    p = self.connector.get_latest_price(symbol=sym, provider=prov)
                    if p > 0:
                        with self.lock:
                            self.prices[sym] = p
                except Exception:
                    pass
            time.sleep(3.0)

    def get_prices(self) -> dict:
        with self.lock:
            return dict(self.prices)


def get_modality_snapshot(cfg: dict, now_utc: datetime, cached_prices: Optional[dict] = None) -> dict:
    db = TradingDatabase(db_path=cfg["db"])
    rules = StellarLiteRulesEngine(db=db)
    risk = RiskManager(db=db, session_mode=cfg["session"])
    acc = db.get_account_state()
    is_session_active, s_name = risk.check_market_session(now_utc)

    t_date = str(acc.get("current_trading_day", now_utc.strftime("%Y-%m-%d")))
    t_trades = db.get_trades_by_date(t_date) if t_date else []
    closed_today = [t for t in t_trades if t["status"] == "CLOSED"]
    open_pos = db.get_open_trades()

    # Enriquecer posiciones abiertas con precio actual y PnL flotante en tiempo real
    tot_floating = 0.0
    for p in open_pos:
        sym = p["symbol"]
        mark = 0.0
        if cached_prices and sym in cached_prices and cached_prices[sym] > 0:
            mark = cached_prices[sym]
        else:
            mark = float(p.get("mark_price") or p["entry_price"])
        p["mark_price"] = mark
        side = str(p["side"]).upper()
        units = float(p.get("units", 1.0))
        entry = float(p["entry_price"])
        comm = float(p.get("commission", 0.0))
        spread = float(p.get("spread_cost", 0.0))
        gross = (mark - entry) * units if side == "BUY" else (entry - mark) * units
        floating = round(gross - comm - spread, 2)
        p["floating_pnl"] = floating
        tot_floating += floating

    balance = float(acc.get("balance", 5000.0))
    equity = round(balance + tot_floating, 2)
    rule_res = rules.evaluate_account(floating_pnl=tot_floating)

    wins = sum(1 for t in closed_today if float(t["pnl"]) > 0)
    losses = sum(1 for t in closed_today if float(t["pnl"]) < 0)
    pnl_today_realized = sum(float(t["pnl"]) for t in closed_today)
    pnl_today = round(pnl_today_realized + tot_floating, 2)

    consec_losses = risk.get_consecutive_losses_today(t_date)
    is_tilt = consec_losses >= 3

    if is_tilt:
        status_str = "BLOQ_TILT"
    elif open_pos:
        status_str = f"TRADE({len(open_pos)})"
    elif rule_res.target_reached and rule_res.waiting_min_days and len(closed_today) > 0:
        status_str = "META_OK"
    elif rule_res.can_pass_phase:
        status_str = "APROBADA"
    elif is_session_active:
        status_str = "ACTIVA"
    else:
        status_str = "ESPERA"

    return {
        "cfg": cfg,
        "acc": acc,
        "rules": rule_res,
        "balance": balance,
        "equity": equity,
        "floating_pnl": tot_floating,
        "initial_balance": float(acc.get("initial_balance", 5000.0)),
        "pnl_today": pnl_today,
        "pnl_today_realized": pnl_today_realized,
        "profit_total": float(rule_res.current_profit),
        "open_trades": len(open_pos),
        "closed_trades": len(closed_today),
        "wins": wins,
        "losses": losses,
        "consec_losses": consec_losses,
        "is_tilt": is_tilt,
        "status_str": status_str,
        "session_str": s_name,
        "open_pos_list": open_pos,
        "closed_trades_list": closed_today,
    }


def build_multi_dashboard_text(
    now_utc: datetime,
    detailed: bool = False,
    cached_prices: Optional[dict] = None,
) -> str:
    now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    sep = "=" * 122
    subsep = "-" * 122

    snapshots = [get_modality_snapshot(c, now_utc, cached_prices=cached_prices) for c in MODALITIES_METADATA]

    title_mode = "DETALLADO EN VIVO (CON OPERACIONES)" if detailed else "EN VIVO (5 ESTRATEGIAS)"
    lines = [
        "\033[H\033[J" + sep,
        f" FUNDEDNEXT STELLAR LITE ($5K) | TABLERO MULTI-MODALIDAD {title_mode} | HORA UTC: {now_str}",
        sep,
        f" {'#':<2} | {'MODALIDAD':<22} | {'ACTIVO':<13} | {'HORARIO':<16} | {'BALANCE':<10} | {'EQUIDAD':<10} | {'PNL HOY':<9} | {'W / L':<7} | {'ESTADO':<8}",
        subsep,
    ]

    tot_bal = sum(s["balance"] for s in snapshots)
    tot_eq = sum(s["equity"] for s in snapshots)
    tot_pnl_today = sum(s["pnl_today"] for s in snapshots)
    tot_wins = sum(s["wins"] for s in snapshots)
    tot_losses = sum(s["losses"] for s in snapshots)

    for s in snapshots:
        c = s["cfg"]
        wl_str = f"{s['wins']}W/{s['losses']}L"
        lines.append(
            f" {c['num']:<2} | {c['label']:<22} | {c['symbol']:<13} | {c['hours']:<16} | "
            f"${s['balance']:>9,.2f} | ${s['equity']:>9,.2f} | ${s['pnl_today']:>+8,.2f} | {wl_str:<7} | {s['status_str']:<8}"
        )

    lines.append(subsep)
    lines.append(
        f" {'*':<2} | {'CONSOLIDADO (5 CTAS)':<22} | {'PORTAFOLIO':<13} | {'MULTISESION':<16} | "
        f"${tot_bal:>9,.2f} | ${tot_eq:>9,.2f} | ${tot_pnl_today:>+8,.2f} | {tot_wins}W/{tot_losses}L   | GLOBAL"
    )

    if detailed:
        # 1. POSICIONES ABIERTAS EN TIEMPO REAL
        lines.append(sep)
        lines.append(" [POSICIONES ABIERTAS EN TIEMPO REAL (TODAS LAS ESTRATEGIAS)]")
        all_open = []
        for s in snapshots:
            c = s["cfg"]
            for pos in s["open_pos_list"]:
                all_open.append((c, pos))

        if not all_open:
            lines.append("  >> Sin posiciones abiertas en curso en ninguna modalidad. Monitoreando mercado... <<")
        else:
            lines.append(
                f"  {'ID':<4} {'MODALIDAD':<22} {'ACTIVO':<9} {'LADO':<5} {'LOTES':<7} "
                f"{'ENTRADA':<10} {'SL':<10} {'TP':<10} {'ACTUAL':<10} {'PNL FLOT.':<10} {'NOTAS'}"
            )
            lines.append(subsep)
            for c, pos in all_open:
                pnl_str = f"${float(pos.get('floating_pnl', 0.0)):>+9,.2f}"
                note_short = str(pos.get("notes", "ORB_ACTIVO"))[:20]
                lines.append(
                    f"  #{pos['id']:<3} {c['label'][:22]:<22} {pos['symbol']:<9} {pos['side']:<5} {float(pos['lots']):<7.4f} "
                    f"{float(pos['entry_price']):<10.2f} {float(pos['stop_loss']):<10.2f} {float(pos['take_profit']):<10.2f} "
                    f"{float(pos.get('mark_price', pos['entry_price'])):<10.2f} {pnl_str:<10} {note_short}"
                )

        # 2. HISTORIAL DETALLADO DE OPERACIONES DE HOY (CERRADAS)
        lines.append(sep)
        lines.append(" [HISTORIAL DETALLADO DE OPERACIONES DE HOY (CERRADAS)]")
        all_closed = []
        for s in snapshots:
            c = s["cfg"]
            for tr in s["closed_trades_list"]:
                all_closed.append((c, tr))

        if not all_closed:
            lines.append("  >> Sin operaciones cerradas hoy en ninguna modalidad. <<")
        else:
            lines.append(
                f"  {'ID':<4} {'MODALIDAD':<22} {'ACTIVO':<9} {'LADO':<5} {'LOTES':<7} "
                f"{'ENTRADA':<10} {'SALIDA':<10} {'PNL NETO':<11} {'HORA (UTC)':<10} {'MOTIVO / NOTAS'}"
            )
            lines.append(subsep)
            for c, tr in all_closed:
                pnl_net = float(tr.get("pnl", 0.0))
                pnl_str = f"${pnl_net:>+10,.2f}"
                close_time_str = str(tr.get("closed_at") or tr.get("opened_at") or "")[11:19]
                note_str = str(tr.get("notes", ""))[:28]
                lines.append(
                    f"  #{tr['id']:<3} {c['label'][:22]:<22} {tr['symbol']:<9} {tr['side']:<5} {float(tr['lots']):<7.4f} "
                    f"{float(tr['entry_price']):<10.2f} {float(tr.get('exit_price') or 0):<10.2f} {pnl_str:<11} "
                    f"{close_time_str:<10} {note_str}"
                )

    lines.append(sep)
    lines.append(" [DETALLE DE RIESGO POR MODALIDAD]")
    for s in snapshots:
        c = s["cfg"]
        r = s["rules"]
        pos_msg = (
            f"#{s['open_pos_list'][0]['id']} {s['open_pos_list'][0]['symbol']} {s['open_pos_list'][0]['side']} {s['open_pos_list'][0]['lots']}L"
            if s["open_pos_list"]
            else "Sin posicion abierta"
        )
        tilt_tag = f"Tilt: {s['consec_losses']}/3 [BLOQUEO TILT]" if s["is_tilt"] else f"Tilt: {s['consec_losses']}/3 [OK]"
        lines.append(
            f"  [{c['num']}] {c['label']:<22}: Piso Diario: ${r.daily_loss_floor:,.2f} (Margen: ${r.daily_loss_remaining:>6,.2f}) | "
            f"Max DD: ${r.max_loss_floor:,.2f} (Margen: ${r.max_loss_remaining:>6,.2f}) | {tilt_tag} | Posicion: {pos_msg}"
        )

    # 3. ESTADO DE OBJETIVOS & RECOMENDACIONES EN CUENTA REAL
    lines.append(sep)
    lines.append(" [ESTADO DE OBJETIVOS & RECOMENDACIONES PARA CUENTA REAL (5 MODALIDADES)]")
    has_target_info = False
    for s in snapshots:
        c = s["cfg"]
        r = s["rules"]
        if r.target_reached and r.waiting_min_days:
            has_target_info = True
            lines.append(
                f"  [{c['num']}] {c['label']:<22}: 🎯 META ALCANZADA (${s['balance']:>9,.2f} / Meta ${r.profit_target_balance:>9,.2f}) | "
                f"Días: {r.trading_days_completed}/{r.min_trading_days_required} mín. | "
                f"RECOMENDACIÓN: Blindar capital (no operar más hoy). En día 2 usar micro-lote 0.01."
            )
        elif r.can_pass_phase:
            has_target_info = True
            lines.append(
                f"  [{c['num']}] {c['label']:<22}: 🏆 ¡FASE APROBADA! (Target y días completados) | "
                f"RECOMENDACIÓN: Entrar a panel FundedNext y solicitar siguiente fase / fondeo."
            )
    if not has_target_info:
        lines.append("  >> Todas las cuentas en progreso regular. Mantener riesgo estricto (0.5% - 1.0%) y protección de noticias. <<")
    lines.append(sep)
    tag_ref = "MODO DETALLADO EN VIVO" if detailed else "EN VIVO"
    lines.append(f" >> {tag_ref} | Refresco cada 1s en su lugar | Presione Ctrl+C para salir <<")
    return "\n".join(lines)


def run_multi_live_dashboard(refresh_rate: float = 1.0, detailed: bool = False) -> None:
    worker = MultiPriceWorker() if detailed else None
    if worker:
        time.sleep(0.3)
    try:
        while True:
            now_utc = datetime.now(timezone.utc)
            cached_prices = worker.get_prices() if worker else None
            sys.stdout.write(build_multi_dashboard_text(now_utc, detailed=detailed, cached_prices=cached_prices))
            sys.stdout.flush()
            time.sleep(max(0.1, refresh_rate - (time.time() % refresh_rate)))
    except KeyboardInterrupt:
        if worker:
            worker.running = False
        print("\n\n[*] Tablero Multi-Modalidad finalizado.")


def print_multi_status(detailed: bool = False) -> None:
    now_utc = datetime.now(timezone.utc)
    text = build_multi_dashboard_text(now_utc, detailed=detailed)
    text_clean = text.replace("\033[H\033[J", "")
    print(text_clean)


def reset_all_modalities(personal_cap_pct: float = 0.02, risk_pct: float = 0.005) -> None:
    db_list = [
        "trading_ny_open.db",
        "trading_london_open.db",
        "trading_crypto_24h.db",
        "trading_ny_london.db",
        "trading_combo_trio.db",
        "trading_london_ny.db",
        "trading_history.db",
    ]
    print("=" * 78)
    print(" REINICIO DE TODAS LAS MODALIDADES DE TRADING (FTMO / FUNDEDNEXT $5K)")
    print("=" * 78)
    for db_file in db_list:
        db = TradingDatabase(db_path=db_file)
        db.reset_account(
            initial_balance=5000.0,
            personal_daily_cap_pct=personal_cap_pct,
            risk_per_trade_pct=risk_pct,
        )
        print(f" [*] Base de datos '{db_file}' -> Reiniciada a $5,000.00 (FASE_1 ACTIVA).")
    print("=" * 78)
    print(" [OK] Todas las modalidades (1 a 5) han sido restablecidas exitosamente.")
    print("=" * 78)


def run_continuous_bot_loop(
    db: TradingDatabase,
    rules: StellarLiteRulesEngine,
    risk: RiskManager,
    engine: AutomatedTradingEngine,
    interval_seconds: int = 60,
) -> None:
    """
    Bucle de ejecución continua 24/7 diseñado para correr como servicio systemd en Oracle Cloud.
    """
    print(
        f"[*] Iniciando bucle continuo del Bot FundedNext Stellar Lite "
        f"(Intervalo: {interval_seconds}s | Activo: {engine.symbol} via {engine.provider})"
    )
    print_console_report(db, rules, risk, engine)

    try:
        while True:
            try:
                result = engine.run_single_cycle(ignore_session_filter=False)
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                print(f"[{now_str}] Ciclo completado -> Acción: {result['action']} | {result['message']}", flush=True)

                if result["action"] in ("TRADE_OPENED", "BLOCKED_HARD_BREACH") or result.get("closed_positions"):
                    print_console_report(db, rules, risk, engine)

                if result["action"] == "BLOCKED_HARD_BREACH":
                    print("[!] La cuenta ha sufrido un Hard Breach. Deteniendo nuevas aperturas.", flush=True)
            except Exception as e:
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                print(f"[{now_str}] [ERROR] Excepción inesperada en ciclo continuo: {e}", flush=True)
                import traceback
                traceback.print_exc()

            time.sleep(max(5, interval_seconds))
    except KeyboardInterrupt:
        print("\n[*] Bucle continuo detenido manualmente por el usuario.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulador y Motor Automatizado FundedNext Stellar Lite (Python Puro para OCI)."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=[
            "status",
            "run",
            "interactive",
            "simulate",
            "reset",
            "live",
            "multi",
            "multi-status",
            "multi-detail",
            "multi-detail-status",
            "reset-all",
        ],
        help="Comando a ejecutar: 'status', 'live', 'multi', 'multi-detail' (tablero con detalle de operaciones), 'multi-status', 'multi-detail-status', 'reset-all', 'run', 'interactive', 'simulate', 'reset'.",
    )
    parser.add_argument(
        "--detailed",
        "--detail",
        dest="detailed",
        action="store_true",
        default=False,
        help="Activa el modo detallado con desglose de operaciones abiertas y cerradas de cada modalidad.",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="GC=F",
        help="Símbolo(s) a operar (ej. 'GC=F', 'BTC/USDT', o 'GC=F,BTC/USDT').",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="yfinance",
        choices=["yfinance", "ccxt", "multi"],
        help="Proveedor de datos ('yfinance', 'ccxt' o 'multi').",
    )
    parser.add_argument(
        "--risk",
        type=float,
        default=0.005,
        help="Fracción de riesgo por operación (ej. 0.005 = 0.5%%, 0.01 = 1.0%%).",
    )
    parser.add_argument(
        "--personal-cap",
        type=float,
        default=0.02,
        help="Freno de mano personal de pérdida diaria (ej. 0.02 = 2.0%%).",
    )
    parser.add_argument(
        "--session",
        type=str,
        default="NY_OPEN",
        choices=["NY_OPEN", "LONDON_OPEN", "LONDON_NY", "ALL", "CRYPTO_24H", "COMBO_DUAL", "COMBO_TRIO"],
        help="Filtro de sesión operativa ('NY_OPEN', 'LONDON_OPEN', 'ALL', 'COMBO_DUAL', 'COMBO_TRIO').",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Segundos de espera entre cada ciclo en modo 'run' (por defecto 60s).",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=1.0,
        help="Segundos de refresco para el monitor en vivo (por defecto 1.0s).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DB_DEFAULT_PATH,
        help="Ruta del archivo SQLite local (por defecto 'trading_history.db').",
    )
    parser.add_argument(
        "--telegram-token",
        type=str,
        default="",
        help="Token del Bot de Telegram para alertas en tiempo real.",
    )
    parser.add_argument(
        "--telegram-chat",
        type=str,
        default="",
        help="Chat ID de Telegram para recibir alertas en el móvil.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Configurar Telegram si se pasan argumentos por línea de comandos
    if args.telegram_token:
        os.environ["TELEGRAM_BOT_TOKEN"] = args.telegram_token
    if args.telegram_chat:
        os.environ["TELEGRAM_CHAT_ID"] = args.telegram_chat

    db = TradingDatabase(db_path=args.db)

    # Sincronizar parámetros de riesgo con la base de datos
    db.update_account_state(
        personal_daily_cap_pct=args.personal_cap,
        risk_per_trade_pct=args.risk,
    )

    rules = StellarLiteRulesEngine(db=db)
    risk = RiskManager(
        db=db,
        default_risk_pct=args.risk,
        personal_daily_cap_pct=args.personal_cap,
        rr_ratio=2.0,
        session_mode=args.session,
    )
    engine = AutomatedTradingEngine(
        db=db,
        rules_engine=rules,
        risk_manager=risk,
        symbol=args.symbol,
        provider=args.provider,
    )

    if args.command == "status":
        print_console_report(db, rules, risk, engine)
    elif args.command == "live":
        run_live_dashboard(db, rules, risk, engine, refresh_rate=args.refresh)
    elif args.command in ("multi", "multi-detail"):
        is_det = (args.command == "multi-detail") or args.detailed
        run_multi_live_dashboard(refresh_rate=args.refresh, detailed=is_det)
    elif args.command in ("multi-status", "multi-detail-status"):
        is_det = (args.command == "multi-detail-status") or args.detailed
        print_multi_status(detailed=is_det)
    elif args.command == "reset-all":
        reset_all_modalities(personal_cap_pct=args.personal_cap, risk_pct=args.risk)
    elif args.command == "reset":
        db.reset_account(
            initial_balance=5000.0,
            personal_daily_cap_pct=args.personal_cap,
            risk_per_trade_pct=args.risk,
        )
        print("[*] Cuenta reiniciada exitosamente a $5,000.00 en FASE_1.")
        print_console_report(db, rules, risk, engine)
    elif args.command == "simulate":
        run_simulation_demo(db, rules, risk, engine)
    elif args.command == "interactive":
        run_interactive_cli(db, rules, risk, engine)
    elif args.command == "run":
        run_continuous_bot_loop(db, rules, risk, engine, interval_seconds=args.interval)


if __name__ == "__main__":
    main()
