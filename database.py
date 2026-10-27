"""
database.py - Persistencia SQLite para el Simulador y Motor FundedNext Stellar Lite.
Gestiona el estado de la cuenta, historial de operaciones cerradas, posiciones abiertas
y snapshots diarios en `trading_history.db`.
"""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


DB_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trading_history.db")


class TradingDatabase:
    """Gestor de persistencia en SQLite para operaciones y estado de la cuenta."""

    def __init__(self, db_path: str = DB_DEFAULT_PATH) -> None:
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
                    initial_balance REAL NOT NULL DEFAULT 5000.0,
                    balance REAL NOT NULL DEFAULT 5000.0,
                    equity REAL NOT NULL DEFAULT 5000.0,
                    day_start_balance REAL NOT NULL DEFAULT 5000.0,
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

            # Verificar si existe el registro inicial de la cuenta
            cursor.execute("SELECT COUNT(*) AS cnt FROM account_state WHERE id = 1")
            row = cursor.fetchone()
            if row["cnt"] == 0:
                now_utc = datetime.now(timezone.utc)
                today_str = now_utc.strftime("%Y-%m-%d")
                cursor.execute(
                    """
                    INSERT INTO account_state (
                        id, initial_balance, balance, equity, day_start_balance,
                        current_trading_day, phase, status, fail_reason, profit_split,
                        personal_daily_cap_pct, risk_per_trade_pct, updated_at
                    ) VALUES (1, 5000.0, 5000.0, 5000.0, 5000.0, ?, 'FASE_1', 'ACTIVE', '', 0.0, 0.02, 0.005, ?)
                    """,
                    (today_str, now_utc.isoformat()),
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
        initial_balance: float = 5000.0,
        personal_daily_cap_pct: float = 0.02,
        risk_per_trade_pct: float = 0.005,
    ) -> Dict[str, Any]:
        """Reinicia la cuenta a Fase 1 y limpia el historial de trades."""
        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades")
            cursor.execute("DELETE FROM trading_days")
            cursor.execute("DELETE FROM audit_events")
            cursor.execute(
                """
                UPDATE account_state
                SET initial_balance = ?,
                    balance = ?,
                    equity = ?,
                    day_start_balance = ?,
                    current_trading_day = ?,
                    phase = 'FASE_1',
                    status = 'ACTIVE',
                    fail_reason = '',
                    profit_split = 0.0,
                    personal_daily_cap_pct = ?,
                    risk_per_trade_pct = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (
                    initial_balance,
                    initial_balance,
                    initial_balance,
                    initial_balance,
                    today_str,
                    personal_daily_cap_pct,
                    risk_per_trade_pct,
                    now_utc.isoformat(),
                ),
            )
            conn.commit()
        self.log_event("ACCOUNT_RESET", "FASE_1", f"Cuenta reiniciada con balance ${initial_balance:,.2f}")
        return self.get_account_state()

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
