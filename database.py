"""
database.py - Persistencia SQLite para el Simulador y Motor FundedNext Stellar Lite.
Gestiona el estado de la cuenta, historial de operaciones cerradas, posiciones abiertas
y snapshots diarios en `trading_history.db`.
"""

import os
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger("TradingDatabase")


def resolve_dual_target_magics(symbol: str, active_profile: Optional[Any] = None) -> List[tuple]:
    """
    Resuelve dinámicamente qué perfiles y Magic Numbers deben recibir la orden para un símbolo dado.
    Inspecciona todos los perfiles de trading en profiles.json:
      - Si 2 o más perfiles contienen el activo en 'allowed_symbols' (ej. Oro, EUR/USD o cualquier par compartido),
        la señal se despacha en paralelo a CADA terminal MT5 correspondiente con su propio Magic Number.
      - Si un activo está configurado en un único perfil (ej. S&P 500 en FTMO o USD/JPY en Stellar),
        se despacha únicamente a la terminal de ese perfil.
      - Si el usuario agrega o modifica activos en cualquier perfil de profiles.json, el sistema los suscribe automáticamente.
    """
    if active_profile and getattr(active_profile, "id", "") == "stellar_6k_trial":
        return [(active_profile.magic_number, "Trial6K")]

    sym_clean = symbol.upper().replace("=X", "").replace("=F", "").replace("/", "")
    is_gold = any(k in sym_clean for k in ("XAU", "GC", "GOLD"))
    is_silver = any(k in sym_clean for k in ("XAG", "SI", "SILVER"))
    is_us30 = any(k in sym_clean for k in ("30", "DJ", "YM", "DOW", "WS30"))
    is_sp500 = any(k in sym_clean for k in ("500", "SPX", "ES", "US500"))
    is_usdjpy = ("JPY" in sym_clean and "USD" in sym_clean) or sym_clean == "USDJPY"
    is_eurusd = ("EUR" in sym_clean and "USD" in sym_clean) or sym_clean == "EURUSD"

    candidate_profiles = []
    try:
        from profiles import profile_manager
        # Respeta el modo de ejecución:
        # En modo INDIVIDUAL: retorna únicamente [active_profile]
        # En modo DUAL: retorna todos los perfiles configurados en active_profiles_dual
        candidate_profiles = profile_manager.get_active_target_profiles()
    except Exception:
        candidate_profiles = []

    if not candidate_profiles and active_profile:
        candidate_profiles = [active_profile]

    matched = []
    for prof in candidate_profiles:
        allowed = getattr(prof, "allowed_symbols", []) or []
        allows = False
        for al in allowed:
            al_clean = al.upper().replace("=X", "").replace("=F", "").replace("/", "")
            if is_gold and any(k in al_clean for k in ("XAU", "GC", "GOLD")):
                allows = True
                break
            if is_silver and any(k in al_clean for k in ("XAG", "SI", "SILVER")):
                allows = True
                break
            if is_us30 and any(k in al_clean for k in ("30", "DJ", "YM", "DOW", "WS30")):
                allows = True
                break
            if is_sp500 and any(k in al_clean for k in ("500", "SPX", "ES", "US500")):
                allows = True
                break
            if is_usdjpy and (("JPY" in al_clean and "USD" in al_clean) or al_clean == "USDJPY"):
                allows = True
                break
            if is_eurusd and (("EUR" in al_clean and "USD" in al_clean) or al_clean == "EURUSD"):
                allows = True
                break
            if al_clean == sym_clean or al_clean in sym_clean or sym_clean in al_clean:
                allows = True
                break

        if allows:
            magic = getattr(prof, "magic_number", 505001)
            prefix = getattr(prof, "name", "PropFirm").split()[0]
            if (magic, prefix) not in matched:
                matched.append((magic, prefix))

    if not matched:
        try:
            from profiles import profile_manager
            act = profile_manager.get_active_profile()
            matched.append((act.magic_number, act.name.split()[0]))
        except Exception:
            matched.append((505001, "PropFirm"))

    return matched


DB_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trading_history.db")


class TradingDatabase:
    """Gestor de persistencia en SQLite para operaciones y estado de la cuenta."""

    def __init__(self, db_path: str = DB_DEFAULT_PATH, profile: Optional[Any] = None) -> None:
        self._profile = profile
        if not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(base_dir, db_path)
        else:
            self.db_path = db_path
        self._init_db()

    def _resolve_profile_magic_and_prefix(self) -> tuple:
        if self._profile and hasattr(self._profile, "magic_number"):
            return self._profile.magic_number, self._profile.name.split()[0]
        try:
            from profiles import profile_manager
            p = profile_manager.get_active_profile()
            return p.magic_number, p.name.split()[0]
        except Exception:
            return 505001, "PropFirm"

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        """Crea las tablas necesarias si no existen e inicializa la cuenta por defecto."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Tabla de estado de la cuenta
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS account_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    initial_balance REAL NOT NULL DEFAULT 10000.0,
                    balance REAL NOT NULL DEFAULT 10000.0,
                    equity REAL NOT NULL DEFAULT 10000.0,
                    day_start_balance REAL NOT NULL DEFAULT 10000.0,
                    current_trading_day TEXT NOT NULL,
                    phase TEXT NOT NULL DEFAULT 'FASE_1',
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    fail_reason TEXT DEFAULT '',
                    profit_split REAL NOT NULL DEFAULT 0.0,
                    personal_daily_cap_pct REAL NOT NULL DEFAULT 0.02,
                    risk_per_trade_pct REAL NOT NULL DEFAULT 0.005,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Tabla de operaciones (abiertas y cerradas)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    side TEXT NOT NULL,
                    lots REAL NOT NULL,
                    units REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    exit_price REAL,
                    pnl REAL NOT NULL DEFAULT 0.0,
                    gross_pnl REAL NOT NULL DEFAULT 0.0,
                    commission REAL NOT NULL DEFAULT 0.0,
                    spread_cost REAL NOT NULL DEFAULT 0.0,
                    rr_ratio REAL NOT NULL DEFAULT 2.0,
                    phase TEXT NOT NULL,
                    strategy TEXT NOT NULL DEFAULT 'NY_ORB_15M',
                    is_news_window INTEGER NOT NULL DEFAULT 0,
                    is_break_even INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    trading_date TEXT NOT NULL,
                    notes TEXT DEFAULT ''
                )
                """
            )

            # Migraciones dinámicas seguras para bases de datos existentes
            for col_sql in (
                "ALTER TABLE trades ADD COLUMN gross_pnl REAL DEFAULT 0.0",
                "ALTER TABLE trades ADD COLUMN commission REAL DEFAULT 0.0",
                "ALTER TABLE trades ADD COLUMN spread_cost REAL DEFAULT 0.0",
                "ALTER TABLE trades ADD COLUMN is_break_even INTEGER DEFAULT 0",
                "ALTER TABLE trades ADD COLUMN mt5_ticket INTEGER DEFAULT 0",
                "ALTER TABLE trades ADD COLUMN mt5_deal_ticket INTEGER DEFAULT 0",
                "ALTER TABLE trades ADD COLUMN swap REAL DEFAULT 0.0",
                "ALTER TABLE trades ADD COLUMN magic INTEGER DEFAULT 0",
                "ALTER TABLE account_state ADD COLUMN max_drawdown_limit_pct REAL DEFAULT 0.08",
                "ALTER TABLE account_state ADD COLUMN min_trading_days INTEGER DEFAULT 2",
                "ALTER TABLE account_state ADD COLUMN funded_profit_split REAL DEFAULT 0.80",
                "ALTER TABLE account_state ADD COLUMN ea_enabled INTEGER DEFAULT 1",
                "ALTER TABLE account_state ADD COLUMN daily_loss_limit_pct REAL DEFAULT 0.04",
                "ALTER TABLE account_state ADD COLUMN profit_target_pct REAL DEFAULT 0.08",
                "ALTER TABLE account_state ADD COLUMN profit_target_phase2_pct REAL DEFAULT 0.04",
                "ALTER TABLE account_state ADD COLUMN profile_id TEXT DEFAULT 'stellar_10k_demo'",
                "ALTER TABLE account_state ADD COLUMN is_trial INTEGER DEFAULT 0",
                "ALTER TABLE account_state ADD COLUMN account_login INTEGER DEFAULT 0",
                "ALTER TABLE account_state ADD COLUMN drawdown_type TEXT DEFAULT 'STATIC'",
                "ALTER TABLE account_state ADD COLUMN high_water_mark REAL DEFAULT 0.0",
                "ALTER TABLE account_state ADD COLUMN trailing_max_loss_floor REAL DEFAULT 0.0",
                "ALTER TABLE account_state ADD COLUMN consistency_rule_pct REAL DEFAULT 0.0",
            ):
                try:
                    cursor.execute(col_sql)
                except Exception:
                    pass

            # Tabla de registro de días operativos por fase
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trading_days (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phase TEXT NOT NULL,
                    trading_date TEXT NOT NULL,
                    trades_count INTEGER NOT NULL DEFAULT 0,
                    daily_pnl REAL NOT NULL DEFAULT 0.0,
                    UNIQUE(phase, trading_date)
                )
                """
            )

            # Tabla de eventos / auditoría de reglas
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )

            # Tabla permanente de histórico archivado de trades (persiste tras resets y retiros)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS archived_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_trade_id INTEGER,
                    symbol TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    side TEXT NOT NULL,
                    lots REAL NOT NULL,
                    units REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    exit_price REAL,
                    pnl REAL NOT NULL DEFAULT 0.0,
                    gross_pnl REAL NOT NULL DEFAULT 0.0,
                    commission REAL NOT NULL DEFAULT 0.0,
                    spread_cost REAL NOT NULL DEFAULT 0.0,
                    rr_ratio REAL NOT NULL DEFAULT 2.0,
                    phase TEXT NOT NULL,
                    strategy TEXT NOT NULL DEFAULT 'NY_ORB_15M',
                    is_news_window INTEGER NOT NULL DEFAULT 0,
                    is_break_even INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'CLOSED',
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    trading_date TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    archived_at TEXT NOT NULL,
                    archive_cycle TEXT DEFAULT 'RESET'
                )
                """
            )

            # Tabla de cola de órdenes para Webhook / EA de MetaTrader 5
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    trade_id INTEGER,
                    symbol TEXT NOT NULL,
                    lots REAL NOT NULL,
                    price REAL,
                    sl REAL,
                    tp REAL,
                    magic INTEGER DEFAULT 505001,
                    comment TEXT,
                    status TEXT DEFAULT 'PENDING',
                    mt5_ticket INTEGER DEFAULT 0,
                    executed_price REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    executed_at TEXT
                )
                """
            )

            # Verificar si existe el registro inicial de la cuenta
            cursor.execute("SELECT COUNT(*) AS cnt FROM account_state WHERE id = 1")
            row = cursor.fetchone()
            if row["cnt"] == 0:
                now_utc = datetime.now(timezone.utc)
                today_str = now_utc.strftime("%Y-%m-%d")

                init_bal = float(self._profile.initial_balance) if self._profile else 10000.0
                daily_loss_pct = float(self._profile.daily_loss_limit_pct) if self._profile else 0.04
                max_dd_pct = float(self._profile.max_drawdown_limit_pct) if self._profile else 0.08
                min_days = int(self._profile.min_trading_days) if self._profile else 2
                target_pct = float(self._profile.profit_target_pct) if self._profile else 0.08
                target_p2_pct = (
                    float(self._profile.profit_target_phase2_pct)
                    if (self._profile and self._profile.profit_target_phase2_pct is not None)
                    else 0.04
                )
                p_cap = float(self._profile.personal_daily_cap_pct) if self._profile else 0.02
                p_risk = float(self._profile.default_risk_per_trade_pct) if self._profile else 0.005
                p_id = str(self._profile.id) if self._profile else "stellar_10k_demo"
                is_trial_val = 1 if (self._profile and self._profile.is_trial) else 0
                acc_login = int(self._profile.login_id) if (self._profile and self._profile.login_id) else 0
                p_dd_type = str(getattr(self._profile, "drawdown_type", "STATIC")) if self._profile else "STATIC"
                p_hwm = float(self._profile.initial_balance) if self._profile else 10000.0
                p_trailing_floor = round(p_hwm * (1.0 - max_dd_pct), 2)
                p_consistency = float(getattr(self._profile, "consistency_rule_pct", 0.0)) if self._profile else 0.0
                initial_phase = "CHALLENGE" if is_trial_val else "FASE_1"

                cursor.execute(
                    """
                    INSERT INTO account_state (
                        id, initial_balance, balance, equity, day_start_balance,
                        current_trading_day, phase, status, fail_reason, profit_split,
                        personal_daily_cap_pct, risk_per_trade_pct, max_drawdown_limit_pct,
                        min_trading_days, funded_profit_split, ea_enabled, daily_loss_limit_pct,
                        profit_target_pct, profit_target_phase2_pct, profile_id, is_trial,
                        account_login, drawdown_type, high_water_mark, trailing_max_loss_floor,
                        consistency_rule_pct, updated_at
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, 'ACTIVE', '', 0.0, ?, ?, ?, ?, 0.80, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        init_bal,
                        init_bal,
                        init_bal,
                        init_bal,
                        today_str,
                        initial_phase,
                        p_cap,
                        p_risk,
                        max_dd_pct,
                        min_days,
                        daily_loss_pct,
                        target_pct,
                        target_p2_pct,
                        p_id,
                        is_trial_val,
                        acc_login,
                        p_dd_type,
                        p_hwm,
                        p_trailing_floor,
                        p_consistency,
                        now_utc.isoformat(),
                    ),
                )
            conn.commit()

    def get_account_state(self) -> Dict[str, Any]:
        """Obtiene el estado actual de la cuenta."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM account_state WHERE id = 1")
            row = cursor.fetchone()
            return dict(row) if row else {}

    def update_account_state(self, **kwargs: Any) -> Dict[str, Any]:
        """Actualiza campos específicos de account_state."""
        if not kwargs:
            return self.get_account_state()

        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        columns = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE account_state SET {columns} WHERE id = 1", values)
            conn.commit()
        return self.get_account_state()

    def reset_account(
        self,
        initial_balance: Optional[float] = None,
        personal_daily_cap_pct: Optional[float] = None,
        risk_per_trade_pct: Optional[float] = None,
        max_drawdown_limit_pct: Optional[float] = None,
        min_trading_days: Optional[int] = None,
        funded_profit_split: Optional[float] = None,
        archive_current_trades: bool = True,
        auto_sync_mt5: bool = True,
    ) -> Dict[str, Any]:
        """
        Reinicia la cuenta a Fase 1 o Challenge respetando el perfil activo.
        1. Preserva el historial completo de operaciones archivándolo en 'archived_trades'.
        2. Si auto_sync_mt5 está activo y MT5 en ejecución, sincroniza initial_balance con el saldo real del broker.
        """
        curr = self.get_account_state()
        if initial_balance is None:
            if self._profile:
                initial_balance = float(self._profile.initial_balance)
            else:
                initial_balance = float(curr.get("initial_balance", 10000.0))

        if personal_daily_cap_pct is None:
            if self._profile:
                personal_daily_cap_pct = float(self._profile.personal_daily_cap_pct)
            else:
                personal_daily_cap_pct = float(curr.get("personal_daily_cap_pct", 0.02))

        if risk_per_trade_pct is None:
            if self._profile:
                risk_per_trade_pct = float(self._profile.default_risk_per_trade_pct)
            else:
                risk_per_trade_pct = float(curr.get("risk_per_trade_pct", 0.005))

        if max_drawdown_limit_pct is None:
            if self._profile:
                max_drawdown_limit_pct = float(self._profile.max_drawdown_limit_pct)
            else:
                max_drawdown_limit_pct = float(curr.get("max_drawdown_limit_pct", 0.08))

        if min_trading_days is None:
            if self._profile:
                min_trading_days = int(self._profile.min_trading_days)
            else:
                min_trading_days = int(curr.get("min_trading_days", 2))

        if funded_profit_split is None:
            if self._profile:
                funded_profit_split = float(self._profile.funded_profit_split)
            else:
                funded_profit_split = float(curr.get("funded_profit_split", 0.80))

        is_trial_flag = bool(self._profile.is_trial) if self._profile else bool(curr.get("is_trial", 0))
        target_phase = "CHALLENGE" if is_trial_flag else "FASE_1"

        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")

        # Intentar auto-sincronizar con MetaTrader 5 si está en ejecución
        synced_mt5_login = None
        if auto_sync_mt5:
            try:
                from mt5_bridge import MT5Bridge
                bridge = MT5Bridge()
                if bridge.initialize():
                    summary = bridge.get_account_summary()
                    live_bal = float(summary.get("balance", 0.0))
                    if live_bal > 0:
                        initial_balance = live_bal
                        synced_mt5_login = summary.get("login")
                        logger.info(f"[*] Saldo sincronizado con MetaTrader 5 #{synced_mt5_login}: ${initial_balance:,.2f}")
                    bridge.shutdown()
            except Exception as e:
                logger.debug(f"Auto-sync MT5 omitido: {e}")

        archived_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Archivar historial de operaciones previo antes de limpiar el ciclo activo
            if archive_current_trades:
                cursor.execute("SELECT COUNT(*) AS cnt FROM trades")
                row_cnt = cursor.fetchone()
                if row_cnt and row_cnt["cnt"] > 0:
                    archived_count = int(row_cnt["cnt"])
                    cursor.execute(
                        """
                        INSERT INTO archived_trades (
                            original_trade_id, symbol, provider, side, lots, units, entry_price, stop_loss,
                            take_profit, exit_price, pnl, gross_pnl, commission, spread_cost, rr_ratio,
                            phase, strategy, is_news_window, is_break_even, status, opened_at, closed_at,
                            trading_date, notes, archived_at, archive_cycle
                        )
                        SELECT id, symbol, provider, side, lots, units, entry_price, stop_loss,
                               take_profit, exit_price, pnl, gross_pnl, commission, spread_cost, rr_ratio,
                               phase, strategy, is_news_window, is_break_even, status, opened_at, closed_at,
                               trading_date, notes, ?, 'RESET_CYCLE'
                        FROM trades
                        """,
                        (now_utc.isoformat(),)
                    )

            reset_dd_type = str(getattr(self._profile, "drawdown_type", "STATIC")) if self._profile else "STATIC"
            reset_hwm = initial_balance
            reset_trailing_floor = round(initial_balance * (1.0 - max_drawdown_limit_pct), 2)
            reset_consistency = float(getattr(self._profile, "consistency_rule_pct", 0.0)) if self._profile else 0.0

            cursor.execute("DELETE FROM trades")
            cursor.execute("DELETE FROM trading_days")
            cursor.execute("DELETE FROM audit_events")
            cursor.execute(
                f"""
                UPDATE account_state
                SET initial_balance = ?,
                    balance = ?,
                    equity = ?,
                    day_start_balance = ?,
                    current_trading_day = ?,
                    phase = ?,
                    status = 'ACTIVE',
                    fail_reason = '',
                    profit_split = 0.0,
                    personal_daily_cap_pct = ?,
                    risk_per_trade_pct = ?,
                    max_drawdown_limit_pct = ?,
                    min_trading_days = ?,
                    funded_profit_split = ?,
                    ea_enabled = 1,
                    drawdown_type = ?,
                    high_water_mark = ?,
                    trailing_max_loss_floor = ?,
                    consistency_rule_pct = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (
                    initial_balance,
                    initial_balance,
                    initial_balance,
                    initial_balance,
                    today_str,
                    target_phase,
                    personal_daily_cap_pct,
                    risk_per_trade_pct,
                    max_drawdown_limit_pct,
                    min_trading_days,
                    funded_profit_split,
                    reset_dd_type,
                    reset_hwm,
                    reset_trailing_floor,
                    reset_consistency,
                    now_utc.isoformat(),
                ),
            )
            conn.commit()

        audit_msg = f"Reinicio de ciclo a ${initial_balance:,.2f} ({target_phase})"
        if synced_mt5_login:
            audit_msg += f" (Sincronizado en vivo con MT5 #{synced_mt5_login})"
        if archived_count > 0:
            audit_msg += f" | {archived_count} operaciones archivadas permanentemente"
        self.log_event("ACCOUNT_RESET", target_phase, audit_msg)

        state = self.get_account_state()
        state["archived_count"] = archived_count
        state["synced_mt5_login"] = synced_mt5_login
        return state

    def sync_with_mt5(self, magic: Optional[int] = None, lookback_days: int = 7) -> Dict[str, Any]:
        """
        Sincroniza en tiempo real la base de datos con MetaTrader 5 (MT5 como Fuente Maestra).
        Reconcilia automáticamente balance, equidad, posiciones abiertas y deals de salida cerrados.
        """
        try:
            from mt5_bridge import MT5Bridge
            bridge = MT5Bridge()
            if not bridge.initialize():
                return {"success": False, "reason": "No se pudo conectar a MetaTrader 5 (¿terminal abierta y AlgoTrading activo?)"}
            res = bridge.reconcile_with_database(self, magic=magic, lookback_days=lookback_days)
            bridge.shutdown()
            return res
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def sync_deal_from_mt5(self, deal: Dict[str, Any]) -> bool:
        """
        Sincroniza un deal de cierre ejecutado en MetaTrader 5 (recibido por EA Webhook o IPC).
        Actualiza el trade correspondiente en SQLite con PnL neto real, swaps, comisiones y precio de salida.
        """
        pos_id = int(deal.get("position_id", 0))
        deal_ticket = int(deal.get("deal_ticket", deal.get("ticket", 0)))
        profit = float(deal.get("profit", 0.0))
        swap = float(deal.get("swap", 0.0))
        comm = float(deal.get("commission", 0.0))
        net_pnl = round(profit + swap + comm, 2)
        exit_p = float(deal.get("exit_price", deal.get("price", 0.0)))
        symbol = str(deal.get("symbol", ""))
        comment = str(deal.get("comment", ""))
        magic = int(deal.get("magic", 0))
        dt_closed = deal.get("closed_at", datetime.now(timezone.utc).isoformat())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            trade = None
            if pos_id > 0:
                cursor.execute("SELECT * FROM trades WHERE mt5_ticket = ? ORDER BY id DESC LIMIT 1", (pos_id,))
                row = cursor.fetchone()
                if row:
                    trade = dict(row)

            if not trade and symbol:
                clean_sym = symbol.replace("XAUUSD", "GC=F")
                cursor.execute(
                    "SELECT * FROM trades WHERE status = 'OPEN' AND (symbol = ? OR symbol = ?) ORDER BY id DESC LIMIT 1",
                    (symbol, clean_sym),
                )
                row = cursor.fetchone()
                if row:
                    trade = dict(row)

            if trade:
                tr_id = trade["id"]
                notes = f"{trade.get('notes', '')} | MT5_DEAL #{deal_ticket} ({comment})".strip(" |")
                cursor.execute(
                    """
                    UPDATE trades
                    SET status = 'CLOSED',
                        exit_price = ?,
                        pnl = ?,
                        gross_pnl = ?,
                        commission = ?,
                        swap = ?,
                        spread_cost = 0.0,
                        closed_at = ?,
                        mt5_ticket = ?,
                        mt5_deal_ticket = ?,
                        magic = ?,
                        notes = ?
                    WHERE id = ?
                    """,
                    (exit_p, net_pnl, profit, abs(comm), swap, dt_closed, pos_id, deal_ticket, magic, notes, tr_id),
                )

                cursor.execute(
                    """
                    INSERT INTO trading_days (phase, trading_date, trades_count, daily_pnl)
                    VALUES (?, ?, 0, ?)
                    ON CONFLICT(phase, trading_date) DO UPDATE SET
                        daily_pnl = ROUND(daily_pnl + ?, 2)
                    """,
                    (trade["phase"], trade["trading_date"], net_pnl, net_pnl),
                )
                conn.commit()

            bal = float(deal.get("balance", 0.0))
            eq = float(deal.get("equity", 0.0))
            if bal > 0:
                self.update_account_state_from_mt5(balance=bal, equity=eq)

            return trade is not None

    def update_account_state_from_mt5(
        self,
        balance: float,
        equity: float,
        login: Optional[int] = None,
        server: Optional[str] = None,
    ) -> None:
        """Actualiza el balance y equidad de account_state con los valores reales reportados por MT5."""
        if balance <= 0:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT initial_balance, high_water_mark, max_drawdown_limit_pct, drawdown_type FROM account_state WHERE id = 1")
            acc = cursor.fetchone()
            if not acc:
                return
            cur_hwm = float(acc["high_water_mark"]) if acc["high_water_mark"] else balance
            new_hwm = round(max(cur_hwm, balance), 2)
            is_trailing = (acc["drawdown_type"] or "").upper() == "TRAILING"
            trailing_floor = 0.0
            if is_trailing:
                init_b = float(acc["initial_balance"])
                max_dd_pct = float(acc["max_drawdown_limit_pct"])
                trailing_floor = round(new_hwm - (init_b * max_dd_pct), 2)

            cursor.execute(
                """
                UPDATE account_state
                SET balance = ?, equity = ?, high_water_mark = ?, trailing_max_loss_floor = ?, updated_at = ?
                WHERE id = 1
                """,
                (round(balance, 2), round(equity, 2), new_hwm, trailing_floor, now_iso),
            )
            conn.commit()

    def get_archived_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Devuelve el historial de operaciones archivadas de ciclos anteriores."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM archived_trades ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_closed_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Devuelve las últimas operaciones cerradas del ciclo actual."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE status = 'CLOSED' ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def record_trade_open(
        self,
        symbol: str,
        provider: str,
        side: str,
        lots: float,
        units: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        rr_ratio: float,
        phase: str,
        strategy: str = "NY_ORB_15M",
        is_news_window: bool = False,
        notes: str = "",
        opened_at: Optional[datetime] = None,
    ) -> int:
        """Inserta una nueva posición abierta y registra el día operativo."""
        dt = opened_at or datetime.now(timezone.utc)
        trading_date = dt.strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO trades (
                    symbol, provider, side, lots, units, entry_price,
                    stop_loss, take_profit, pnl, rr_ratio, phase, strategy,
                    is_news_window, status, opened_at, trading_date, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, 'OPEN', ?, ?, ?)
                """,
                (
                    symbol,
                    provider,
                    side.upper(),
                    round(lots, 4),
                    round(units, 6),
                    round(entry_price, 5),
                    round(stop_loss, 5),
                    round(take_profit, 5),
                    round(rr_ratio, 2),
                    phase,
                    strategy,
                    1 if is_news_window else 0,
                    dt.isoformat(),
                    trading_date,
                    notes,
                ),
            )
            trade_id = int(cursor.lastrowid)

            # Registrar día operativo para la fase actual
            cursor.execute(
                """
                INSERT INTO trading_days (phase, trading_date, trades_count, daily_pnl)
                VALUES (?, ?, 1, 0.0)
                ON CONFLICT(phase, trading_date) DO UPDATE SET
                    trades_count = trades_count + 1
                """,
                (phase, trading_date),
            )

            # Encolar para EA Webhook MT5 (mapeo transparente a símbolos del broker MT5)
            action_type = f"OPEN_{side.upper()}"
            clean_sym = symbol.upper().replace("=X", "").replace("=F", "").replace("/", "")
            if any(k in clean_sym for k in ("GC", "XAU", "GOLD")):
                sym_mt5 = "XAUUSD"
            elif any(k in clean_sym for k in ("SI", "XAG", "SILVER")):
                sym_mt5 = "XAGUSD"
            elif any(k in clean_sym for k in ("YM", "30", "DJ", "WS30", "DOW")):
                sym_mt5 = "US30"
            elif any(k in clean_sym for k in ("ES", "500", "SPX", "US500", "SP500")):
                sym_mt5 = "US500"
            elif any(k in clean_sym for k in ("EURUSD", "EUR")):
                sym_mt5 = "EURUSD"
            elif any(k in clean_sym for k in ("USDJPY", "JPY")):
                sym_mt5 = "USDJPY"
            elif any(k in clean_sym for k in ("AUDUSD", "AUD")):
                sym_mt5 = "AUDUSD"
            else:
                sym_mt5 = clean_sym
            target_pairs = resolve_dual_target_magics(symbol, self._profile)
            for t_magic, prefix in target_pairs:
                cursor.execute(
                    """
                    INSERT INTO webhook_actions (
                        action, trade_id, symbol, lots, price, sl, tp, magic, comment, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
                    """,
                    (
                        action_type,
                        trade_id,
                        sym_mt5,
                        round(lots, 4),
                        round(entry_price, 5),
                        round(stop_loss, 5),
                        round(take_profit, 5),
                        t_magic,
                        f"{prefix} {strategy}",
                        dt.isoformat(),
                    ),
                )
            conn.commit()
        return trade_id

    def record_trade_close(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
        notes: str = "",
        closed_at: Optional[datetime] = None,
        commission: float = 0.0,
        spread_cost: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Cierra una posición abierta con descuento institucional de spread y comisiones.
        - gross_pnl: PnL bruto calculado por movimiento de precio puro.
        - net_pnl: PnL neto tras descontar comisión de broker y costo de spread.
        - Actualiza balance y equidad de la cuenta con el PnL NETO.
        """
        dt = closed_at or datetime.now(timezone.utc)
        gross_pnl = round(pnl, 2)
        comm = round(max(0.0, commission), 2)
        spread = round(max(0.0, spread_cost), 2)
        net_pnl = round(gross_pnl - comm - spread, 2)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE id = ? AND status = 'OPEN'", (trade_id,))
            trade = cursor.fetchone()
            if not trade:
                return None

            merged_notes = f"{trade['notes']} | {notes}".strip(" |") if notes else trade["notes"]
            cursor.execute(
                """
                UPDATE trades
                SET exit_price = ?,
                    pnl = ?,
                    gross_pnl = ?,
                    commission = ?,
                    spread_cost = ?,
                    status = 'CLOSED',
                    closed_at = ?,
                    notes = ?
                WHERE id = ?
                """,
                (round(exit_price, 5), net_pnl, gross_pnl, comm, spread, dt.isoformat(), merged_notes, trade_id),
            )

            # Actualizar balance y equidad de la cuenta con el PnL NETO
            cursor.execute("SELECT balance FROM account_state WHERE id = 1")
            acc = cursor.fetchone()
            new_balance = round(float(acc["balance"]) + net_pnl, 2)

            cursor.execute(
                """
                UPDATE account_state
                SET balance = ?, equity = ?, updated_at = ?
                WHERE id = 1
                """,
                (new_balance, new_balance, dt.isoformat()),
            )

            # Actualizar PnL neto del día operativo
            cursor.execute(
                """
                INSERT INTO trading_days (phase, trading_date, trades_count, daily_pnl)
                VALUES (?, ?, 0, ?)
                ON CONFLICT(phase, trading_date) DO UPDATE SET
                    daily_pnl = ROUND(daily_pnl + ?, 2)
                """,
                (trade["phase"], trade["trading_date"], net_pnl, net_pnl),
            )

            # Encolar cierre para EA Webhook MT5 (Dual Architecture: notificar a todas las terminales que operan el activo)
            raw_sym = trade["symbol"].upper().replace("=X", "").replace("=F", "").replace("/", "")
            if any(k in raw_sym for k in ("GC", "XAU", "GOLD")):
                sym_mt5 = "XAUUSD"
            elif any(k in raw_sym for k in ("SI", "XAG", "SILVER")):
                sym_mt5 = "XAGUSD"
            elif any(k in raw_sym for k in ("YM", "30", "DJ", "WS30", "DOW")):
                sym_mt5 = "US30"
            elif any(k in raw_sym for k in ("ES", "500", "SPX", "US500", "SP500")):
                sym_mt5 = "US500"
            elif any(k in raw_sym for k in ("EURUSD", "EUR")):
                sym_mt5 = "EURUSD"
            elif any(k in raw_sym for k in ("USDJPY", "JPY")):
                sym_mt5 = "USDJPY"
            elif any(k in raw_sym for k in ("AUDUSD", "AUD")):
                sym_mt5 = "AUDUSD"
            else:
                sym_mt5 = trade["symbol"]
            target_pairs = resolve_dual_target_magics(trade["symbol"], self._profile)
            for t_magic, _ in target_pairs:
                cursor.execute(
                    """
                    INSERT INTO webhook_actions (
                        action, trade_id, symbol, lots, price, sl, tp, magic, comment, status, created_at
                    ) VALUES ('CLOSE_POSITION', ?, ?, 0.0, ?, 0.0, 0.0, ?, ?, 'PENDING', ?)
                    """,
                    (trade_id, sym_mt5, round(exit_price, 5), t_magic, notes or "Cierre Algorítmico", dt.isoformat()),
                )

            conn.commit()
            cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
            updated = cursor.fetchone()
            return dict(updated) if updated else None

    def update_trade_sl(
        self,
        trade_id: int,
        new_sl: float,
        notes: str = "",
        is_break_even: int = 1,
    ) -> bool:
        """
        Actualiza el Stop Loss de una posición abierta (ej. para blindar con Break-Even a +1R).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE id = ? AND status = 'OPEN'", (trade_id,))
            trade = cursor.fetchone()
            if not trade:
                return False

            merged_notes = f"{trade['notes']} | {notes}".strip(" |") if notes else trade["notes"]
            cursor.execute(
                """
                UPDATE trades
                SET stop_loss = ?,
                    is_break_even = ?,
                    notes = ?
                WHERE id = ?
                """,
                (round(new_sl, 5), is_break_even, merged_notes, trade_id),
            )

            # Encolar modificación de Stop Loss (Break-Even / Escalera de Candados) para EA Webhook MT5
            if is_break_even:
                raw_sym = trade["symbol"].upper().replace("=X", "").replace("=F", "").replace("/", "")
                if any(k in raw_sym for k in ("GC", "XAU", "GOLD")):
                    sym_mt5 = "XAUUSD"
                elif any(k in raw_sym for k in ("SI", "XAG", "SILVER")):
                    sym_mt5 = "XAGUSD"
                elif any(k in raw_sym for k in ("YM", "30", "DJ", "WS30", "DOW")):
                    sym_mt5 = "US30"
                elif any(k in raw_sym for k in ("ES", "500", "SPX", "US500", "SP500")):
                    sym_mt5 = "US500"
                elif any(k in raw_sym for k in ("EURUSD", "EUR")):
                    sym_mt5 = "EURUSD"
                elif any(k in raw_sym for k in ("USDJPY", "JPY")):
                    sym_mt5 = "USDJPY"
                elif any(k in raw_sym for k in ("AUDUSD", "AUD")):
                    sym_mt5 = "AUDUSD"
                else:
                    sym_mt5 = trade["symbol"]
                action_comment = (notes[:60] if notes else "Break-Even 1R")
                target_pairs = resolve_dual_target_magics(trade["symbol"], self._profile)
                for t_magic, _ in target_pairs:
                    cursor.execute(
                        """
                        INSERT INTO webhook_actions (
                            action, trade_id, symbol, lots, price, sl, tp, magic, comment, status, created_at
                        ) VALUES ('MODIFY_SL', ?, ?, 0.0, 0.0, ?, 0.0, ?, ?, 'PENDING', ?)
                        """,
                        (trade_id, sym_mt5, round(new_sl, 5), t_magic, action_comment, datetime.now(timezone.utc).isoformat()),
                    )

            conn.commit()
            return True

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Retorna todas las posiciones actualmente abiertas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE status = 'OPEN' ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_trades_by_date(self, trading_date: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna las operaciones de una fecha específica (YYYY-MM-DD)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM trades WHERE trading_date = ? AND status = ? ORDER BY id ASC",
                    (trading_date, status),
                )
            else:
                cursor.execute(
                    "SELECT * FROM trades WHERE trading_date = ? ORDER BY id ASC",
                    (trading_date,),
                )
            return [dict(r) for r in cursor.fetchall()]

    def get_trades_by_phase(self, phase: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna las operaciones ejecutadas en una fase determinada."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM trades WHERE phase = ? AND status = ? ORDER BY id ASC",
                    (phase, status),
                )
            else:
                cursor.execute(
                    "SELECT * FROM trades WHERE phase = ? ORDER BY id ASC",
                    (phase,),
                )
            return [dict(r) for r in cursor.fetchall()]

    def get_all_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna las últimas N operaciones registradas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def get_active_trading_days_count(self, phase: str) -> int:
        """Retorna el número de días únicos operados en la fase actual."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(DISTINCT trading_date) AS days_cnt FROM trades WHERE phase = ?",
                (phase,),
            )
            row = cursor.fetchone()
            return int(row["days_cnt"]) if row else 0

    def get_daily_pnl_breakdown(self, phase: str) -> List[Dict[str, Any]]:
        """Retorna el PnL neto desglosado por día para la fase actual (para validar consistencia FTMO)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT trading_date, SUM(pnl) AS daily_pnl, COUNT(*) AS trade_count
                FROM trades
                WHERE phase = ? AND status = 'CLOSED'
                GROUP BY trading_date
                ORDER BY trading_date ASC
                """,
                (phase,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def log_event(self, event_type: str, phase: str, message: str) -> None:
        """Registra un evento de auditoría o alerta de riesgo."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audit_events (timestamp, event_type, phase, message) VALUES (?, ?, ?, ?)",
                (now_iso, event_type, phase, message),
            )
            conn.commit()

    def get_recent_events(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Obtiene los eventos recientes de auditoría."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Métodos de Soporte para EA Webhook de MetaTrader 5 (MT5)
    # -------------------------------------------------------------------------
    def queue_webhook_action(
        self,
        action: str,
        symbol: str,
        lots: float,
        sl: float,
        tp: float,
        price: float = 0.0,
        trade_id: int = 0,
        magic: Optional[int] = None,
        comment: str = "",
    ) -> int:
        """Encola una orden o modificación para que el EA de MT5 la ejecute."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if magic is None or not comment:
            res_magic, prefix = self._resolve_profile_magic_and_prefix()
            if magic is None:
                magic = res_magic
            if not comment:
                comment = f"{prefix} Action"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO webhook_actions (
                    action, trade_id, symbol, lots, price, sl, tp, magic, comment, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
                """,
                (action, trade_id, symbol, lots, price, sl, tp, magic, comment, now_iso),
            )
            act_id = int(cursor.lastrowid)
            conn.commit()
            return act_id

    def get_pending_webhook_action(self) -> Optional[Dict[str, Any]]:
        """Obtiene la acción pendiente más antigua para enviar al EA de MT5."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM webhook_actions WHERE status = 'PENDING' ORDER BY id ASC LIMIT 1"
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def confirm_webhook_action(
        self,
        action_id: int,
        mt5_ticket: int,
        executed_price: float,
        status: str = "CONFIRMED",
    ) -> bool:
        """Confirma la ejecución de una acción por parte del EA de MT5."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE webhook_actions
                SET status = ?, mt5_ticket = ?, executed_price = ?, executed_at = ?
                WHERE id = ?
                """,
                (status, mt5_ticket, executed_price, now_iso, action_id),
            )
            # Si la orden fue rechazada por MT5 (ticket == 0 o status != CONFIRMED), marcar el trade como REJECTED
            if status != "CONFIRMED" or mt5_ticket == 0:
                cursor.execute(
                    """
                    UPDATE trades
                    SET status = 'REJECTED_MT5', notes = notes || ' | RECHAZADA_POR_MT5'
                    WHERE id = (SELECT trade_id FROM webhook_actions WHERE id = ?) AND status = 'OPEN'
                    """,
                    (action_id,),
                )
            elif status == "CONFIRMED" and mt5_ticket > 0:
                cursor.execute(
                    """
                    UPDATE trades
                    SET mt5_ticket = ?
                    WHERE id = (SELECT trade_id FROM webhook_actions WHERE id = ?)
                    """,
                    (mt5_ticket, action_id),
                )
            conn.commit()
            return cursor.rowcount > 0
