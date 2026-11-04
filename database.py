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
                initial_phase = "CHALLENGE" if is_trial_val else "FASE_1"

                cursor.execute(
                    """
                    INSERT INTO account_state (
                        id, initial_balance, balance, equity, day_start_balance,
                        current_trading_day, phase, status, fail_reason, profit_split,
                        personal_daily_cap_pct, risk_per_trade_pct, max_drawdown_limit_pct,
                        min_trading_days, funded_profit_split, ea_enabled, daily_loss_limit_pct,
                        profit_target_pct, profit_target_phase2_pct, profile_id, is_trial,
                        account_login, updated_at
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, 'ACTIVE', '', 0.0, ?, ?, ?, ?, 0.80, 1, ?, ?, ?, ?, ?, ?, ?)
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

    def sync_with_mt5(self) -> Dict[str, Any]:
        """
        Sincroniza en tiempo real el balance y equidad de la base de datos
        con la cuenta activa en MetaTrader 5.
        """
        try:
            from mt5_bridge import MT5Bridge
            bridge = MT5Bridge()
            if not bridge.initialize():
                return {"success": False, "reason": "No se pudo conectar a MetaTrader 5 (¿terminal abierta y AlgoTrading activo?)"}
            summary = bridge.get_account_summary()
            bal = float(summary.get("balance", 0.0))
            eq = float(summary.get("equity", 0.0))
            bridge.shutdown()
            if bal <= 0:
                return {"success": False, "reason": "Balance inválido retornado por MT5"}

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE account_state
                    SET balance = ?, equity = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (bal, eq, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()

            self.log_event("SINCRONIZACION_MT5", "ALL", f"Sincronizado con MT5 #{summary.get('login')}: Balance ${bal:,.2f}, Equidad ${eq:,.2f}")
            return {
                "success": True,
                "login": summary.get("login"),
                "server": summary.get("server"),
                "balance": bal,
                "equity": eq,
                "currency": summary.get("currency", "USD"),
            }
        except Exception as e:
            return {"success": False, "reason": str(e)}

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
            elif any(k in clean_sym for k in ("EURUSD", "EUR")):
                sym_mt5 = "EURUSD"
            elif any(k in clean_sym for k in ("USDJPY", "JPY")):
                sym_mt5 = "USDJPY"
            elif any(k in clean_sym for k in ("AUDUSD", "AUD")):
                sym_mt5 = "AUDUSD"
            elif any(k in clean_sym for k in ("ES", "500", "SPX", "US500", "SP500")):
                sym_mt5 = "US500"
            else:
                sym_mt5 = clean_sym
            cursor.execute(
                """
                INSERT INTO webhook_actions (
                    action, trade_id, symbol, lots, price, sl, tp, magic, comment, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 505001, ?, 'PENDING', ?)
                """,
                (
                    action_type,
                    trade_id,
                    sym_mt5,
                    round(lots, 4),
                    round(entry_price, 5),
                    round(stop_loss, 5),
                    round(take_profit, 5),
                    f"FundedNext {strategy}",
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

            # Encolar cierre para EA Webhook MT5
            sym_mt5 = "XAUUSD" if "GC" in trade["symbol"].upper() else trade["symbol"]
            cursor.execute(
                """
                INSERT INTO webhook_actions (
                    action, trade_id, symbol, lots, price, sl, tp, magic, comment, status, created_at
                ) VALUES ('CLOSE_POSITION', ?, ?, 0.0, ?, 0.0, 0.0, 505001, ?, 'PENDING', ?)
                """,
                (trade_id, sym_mt5, round(exit_price, 5), notes or "Cierre Algorítmico", dt.isoformat()),
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
                raw_sym = trade["symbol"].upper()
                if "GC" in raw_sym or "XAU" in raw_sym:
                    sym_mt5 = "XAUUSD"
                elif "EUR" in raw_sym:
                    sym_mt5 = "EURUSD"
                elif "JPY" in raw_sym:
                    sym_mt5 = "USDJPY"
                elif "AUD" in raw_sym:
                    sym_mt5 = "AUDUSD"
                elif "ES" in raw_sym or "500" in raw_sym:
                    sym_mt5 = "US500"
                else:
                    sym_mt5 = trade["symbol"]
                action_comment = (notes[:60] if notes else "Break-Even 1R")
                cursor.execute(
                    """
                    INSERT INTO webhook_actions (
                        action, trade_id, symbol, lots, price, sl, tp, magic, comment, status, created_at
                    ) VALUES ('MODIFY_SL', ?, ?, 0.0, 0.0, ?, 0.0, 505001, ?, 'PENDING', ?)
                    """,
                    (trade_id, sym_mt5, round(new_sl, 5), action_comment, datetime.now(timezone.utc).isoformat()),
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
        magic: int = 505001,
        comment: str = "FundedNext NY_ORB",
    ) -> int:
        """Encola una orden o modificación para que el EA de MT5 la ejecute."""
        now_iso = datetime.now(timezone.utc).isoformat()
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
            conn.commit()
            return cursor.rowcount > 0
