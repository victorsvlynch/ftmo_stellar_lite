"""
risk_manager.py - Gestor Cuantitativo de Riesgo y Dimensionamiento de Posición.
Implementa:
1. Position Sizing Calculator (lote dinámico según % de riesgo y distancia SL en pips/puntos).
2. Freno de Mano Personal (Personal Daily Loss Cap, ej. 2% sobre el balance inicial del día).
3. Filtro por Sesión de Mercado (Londres, Nueva York o Apertura NY 08:30 - 11:30 EST).
4. Alerta de Racha Negativa (Tilt Alert: bloqueo tras 3 pérdidas consecutivas en el día).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        import pytz

        def ZoneInfo(key: str):
            return pytz.timezone(key)
from typing import Dict, Any, Optional, Tuple
from database import TradingDatabase


# Especificaciones de contrato por instrumento para conversión precisa de lotes, unidades y fricción institucional
INSTRUMENT_SPECS: Dict[str, Dict[str, float]] = {
    # Oro XAU/USD: 1 lote estándar = 100 onzas troy, 1 pip/punto = $0.10 o $1.00, Comisión $5/lote round-turn, spread típico $0.25
    "GC=F": {"contract_size": 100.0, "pip_size": 0.10, "min_lot": 0.01, "max_lot": 50.0, "lot_step": 0.01, "commission_per_lot": 5.0, "typical_spread": 0.25},
    "XAUUSD": {"contract_size": 100.0, "pip_size": 0.10, "min_lot": 0.01, "max_lot": 50.0, "lot_step": 0.01, "commission_per_lot": 5.0, "typical_spread": 0.25},
    # Forex Pares Mayores: 1 lote estándar = 100,000 unidades, 1 pip = 0.0001, Comisión $5/lote round-turn, spread típico 1.5 pips
    "EURUSD=X": {"contract_size": 100000.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01, "commission_per_lot": 5.0, "typical_spread": 0.00015},
    "GBPUSD=X": {"contract_size": 100000.0, "pip_size": 0.0001, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01, "commission_per_lot": 5.0, "typical_spread": 0.00020},
    # Índices / Cripto (1 lote = 1 unidad subyacente en CFD/Spot)
    "BTC/USDT": {"contract_size": 1.0, "pip_size": 1.0, "min_lot": 0.001, "max_lot": 20.0, "lot_step": 0.001, "commission_per_lot": 2.0, "typical_spread": 2.0},
    "ETH/USDT": {"contract_size": 1.0, "pip_size": 0.10, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01, "commission_per_lot": 0.5, "typical_spread": 0.3},
    "SOL/USDT": {"contract_size": 1.0, "pip_size": 0.01, "min_lot": 0.1, "max_lot": 1000.0, "lot_step": 0.1, "commission_per_lot": 0.1, "typical_spread": 0.05},
}


@dataclass
class PositionSizeResult:
    symbol: str
    side: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_pct: float
    risk_amount_usd: float
    sl_distance_price: float
    sl_distance_pips: float
    lots: float
    units: float
    rr_ratio: float
    expected_reward_usd: float


@dataclass
class PreTradeRiskCheck:
    allowed: bool
    reason: str
    active_session: str
    consecutive_losses_today: int
    tilt_locked: bool
    personal_cap_triggered: bool
    daily_pnl_pct: float
    target_reached_lock: bool = False


class RiskManager:
    """Gestor de Riesgo Institucional para cuentas FundedNext Stellar Lite."""

    MAX_CONSECUTIVE_LOSSES_TILT = 3

    def __init__(
        self,
        db: TradingDatabase,
        default_risk_pct: float = 0.005,       # 0.5% por operación por defecto
        personal_daily_cap_pct: float = 0.02,  # 2.0% freno de mano personal (la mitad del 4% oficial)
        rr_ratio: float = 2.0,                 # Ratio Riesgo:Beneficio 1:2 estricto
        session_mode: str = "NY_OPEN",         # "NY_OPEN", "LONDON_OPEN", "COMBO_DUAL", "COMBO_TRIO", "ALL"
    ) -> None:
        self.db = db
        self.default_risk_pct = default_risk_pct
        self.personal_daily_cap_pct = personal_daily_cap_pct
        self.rr_ratio = rr_ratio
        self.session_mode = session_mode.upper()

    @staticmethod
    def get_instrument_spec(symbol: str) -> Dict[str, float]:
        """Obtiene la especificación del contrato o retorna un estándar seguro."""
        clean_sym = symbol.upper()
        if clean_sym in INSTRUMENT_SPECS:
            return INSTRUMENT_SPECS[clean_sym]
        if "XAU" in clean_sym or "GC" in clean_sym:
            return INSTRUMENT_SPECS["GC=F"]
        if "BTC" in clean_sym:
            return INSTRUMENT_SPECS["BTC/USDT"]
        if "USD" in clean_sym and "/" not in clean_sym:
            return INSTRUMENT_SPECS["EURUSD=X"]
        return {"contract_size": 1.0, "pip_size": 0.01, "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01}

    def calculate_position_size(
        self,
        balance: float,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss: float,
        risk_pct: Optional[float] = None,
        rr_ratio: Optional[float] = None,
    ) -> PositionSizeResult:
        """
        Calcula exactamente el lotaje, unidades y Take Profit (R:R 1:2 por defecto)
        en función del capital a arriesgar y la distancia al Stop Loss en precio/pips.
        """
        spec = self.get_instrument_spec(symbol)
        used_risk_pct = risk_pct if risk_pct is not None else self.default_risk_pct
        used_rr = rr_ratio if rr_ratio is not None else self.rr_ratio

        sl_distance_price = abs(entry_price - stop_loss)
        if sl_distance_price <= 1e-8:
            raise ValueError("La distancia entre el precio de entrada y el Stop Loss debe ser mayor que cero.")

        side_upper = side.upper()
        if side_upper == "BUY":
            if stop_loss >= entry_price:
                stop_loss = round(entry_price - sl_distance_price, 5)
            take_profit = round(entry_price + (sl_distance_price * used_rr), 5)
        elif side_upper == "SELL":
            if stop_loss <= entry_price:
                stop_loss = round(entry_price + sl_distance_price, 5)
            take_profit = round(entry_price - (sl_distance_price * used_rr), 5)
        else:
            raise ValueError(f"Dirección de orden inválida: {side}. Use 'BUY' o 'SELL'.")

        risk_amount_usd = round(balance * used_risk_pct, 2)
        contract_size = spec["contract_size"]
        pip_size = spec["pip_size"]
        sl_distance_pips = round(sl_distance_price / pip_size, 2)

        # Riesgo por 1 lote estándar = sl_distance_price * contract_size
        risk_per_lot = sl_distance_price * contract_size
        raw_lots = risk_amount_usd / risk_per_lot if risk_per_lot > 0 else spec["min_lot"]

        # Ajustar al lot_step y límites del broker
        step = spec["lot_step"]
        lots = round(round(raw_lots / step) * step, 4)
        lots = max(spec["min_lot"], min(spec["max_lot"], lots))
        units = round(lots * contract_size, 6)

        actual_risk_usd = round(units * sl_distance_price, 2)
        expected_reward_usd = round(actual_risk_usd * used_rr, 2)

        return PositionSizeResult(
            symbol=symbol,
            side=side_upper,
            entry_price=round(entry_price, 5),
            stop_loss=round(stop_loss, 5),
            take_profit=round(take_profit, 5),
            risk_pct=used_risk_pct,
            risk_amount_usd=actual_risk_usd,
            sl_distance_price=round(sl_distance_price, 5),
            sl_distance_pips=sl_distance_pips,
            lots=lots,
            units=units,
            rr_ratio=used_rr,
            expected_reward_usd=expected_reward_usd,
        )

    def calculate_trade_friction(self, symbol: str, lots: float, units: float) -> Tuple[float, float]:
        """
        Calcula la fricción institucional estimada (comisión round-turn + costo de spread).
        Retorna: (commission_usd, spread_cost_usd).
        """
        spec = self.get_instrument_spec(symbol)
        comm_per_lot = float(spec.get("commission_per_lot", 5.0))
        typical_spread = float(spec.get("typical_spread", spec.get("pip_size", 0.01) * 2.5))

        commission_usd = round(lots * comm_per_lot, 2)
        spread_cost_usd = round(units * typical_spread, 2)
        return commission_usd, spread_cost_usd

    def is_friday_weekend_close_window(self, now_utc: Optional[datetime] = None) -> bool:
        """
        Detecta si nos encontramos en la ventana de cierre forzoso de fin de semana:
        Viernes a partir de las 15:30 EST (90 minutos antes del cierre de mercados de las 17:00 EST).
        """
        dt_utc = now_utc or datetime.now(timezone.utc)
        ny_tz = ZoneInfo("America/New_York")
        dt_ny = dt_utc.astimezone(ny_tz)
        is_friday = dt_ny.weekday() == 4
        ny_minutes = dt_ny.hour * 60 + dt_ny.minute
        return is_friday and ny_minutes >= (15 * 60 + 30)

    def check_market_session(self, now_utc: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Verifica si la hora actual se encuentra dentro de una sesión de alta liquidez:
        - Apertura NY (NY_OPEN): 08:30 - 11:30 America/New_York (EST/EDT)
        - Apertura Londres (LONDON_OPEN): 03:00 - 06:00 America/New_York (08:00 - 11:00 London)
        - Nueva York Completa: 08:00 - 16:00 America/New_York
        - Londres Completa: 03:00 - 11:30 America/New_York (08:00 - 16:30 London)
        - Combo Dual (COMBO_DUAL / NY_LONDON): 03:00-06:00 EST (Londres Open) + 08:30-11:30 EST (NY Open)
        - Combo Trío / 24H (COMBO_TRIO / ALL / CRYPTO_24H): Continuo 24/7
        """
        dt_utc = now_utc or datetime.now(timezone.utc)
        ny_tz = ZoneInfo("America/New_York")
        dt_ny = dt_utc.astimezone(ny_tz)
        ny_minutes = dt_ny.hour * 60 + dt_ny.minute

        is_london_open = (3 * 60) <= ny_minutes <= (6 * 60)
        is_ny_open = (8 * 60 + 30) <= ny_minutes <= (11 * 60 + 30)
        is_london = (3 * 60) <= ny_minutes <= (11 * 60 + 30)
        is_ny_full = (8 * 60) <= ny_minutes <= (16 * 60)

        active_labels = []
        if is_london_open:
            active_labels.append("LONDRES_OPEN (03:00-06:00 EST)")
        elif is_london:
            active_labels.append("LONDRES")
        if is_ny_open:
            active_labels.append("APERTURA_NY (08:30-11:30 EST)")
        elif is_ny_full:
            active_labels.append("NUEVA_YORK")

        session_str = " + ".join(active_labels) if active_labels else f"FUERA_DE_SESION ({dt_ny.strftime('%H:%M %Z')})"

        if self.session_mode in ("ALL", "CRYPTO_24H", "COMBO_TRIO"):
            return True, f"MODO_24H [{session_str}]"
        if self.session_mode == "NY_OPEN":
            return is_ny_open, session_str
        if self.session_mode in ("LONDON_OPEN", "LONDON"):
            return is_london_open, session_str
        if self.session_mode in ("COMBO_DUAL", "NY_LONDON", "LONDON_NY_OPEN"):
            is_active_combo = is_london_open or is_ny_open
            label_combo = "LONDRES_OPEN" if is_london_open else ("NY_OPEN" if is_ny_open else "PAUSA_SESION")
            return is_active_combo, f"COMBO_DUAL [{label_combo}]"
        if self.session_mode == "LONDON_NY":
            return (is_london or is_ny_full), session_str
        return is_ny_open, session_str

    def is_symbol_session_active(self, symbol: str, now_utc: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Determina si un símbolo específico se encuentra dentro de su ventana operativa activa:
        - Criptoactivo ('BTC', '/' o 'USDT'): 24/7 si el modo es ALL, CRYPTO_24H o COMBO_TRIO.
        - Oro / Metales / Forex ('GC=F', etc.):
          * NY_OPEN: 08:30 - 11:30 EST.
          * LONDON_OPEN: 03:00 - 06:00 EST.
          * COMBO_DUAL: 03:00-06:00 EST o 08:30-11:30 EST.
          * COMBO_TRIO: 03:00-06:00 EST o 08:30-11:30 EST.
          * ALL: 24/7 continuo.
        """
        dt_utc = now_utc or datetime.now(timezone.utc)
        ny_tz = ZoneInfo("America/New_York")
        dt_ny = dt_utc.astimezone(ny_tz)
        ny_minutes = dt_ny.hour * 60 + dt_ny.minute

        is_london_open = (3 * 60) <= ny_minutes <= (6 * 60)
        is_ny_open = (8 * 60 + 30) <= ny_minutes <= (11 * 60 + 30)

        sym_upper = symbol.upper()
        is_crypto = "BTC" in sym_upper or "/" in sym_upper or "USDT" in sym_upper

        if is_crypto:
            if self.session_mode in ("ALL", "CRYPTO_24H", "COMBO_TRIO"):
                return True, "CRIPTO_24H [ACTIVO 24/7]"
            return False, f"CRIPTO_INACTIVO en modo {self.session_mode}"

        # Activo tradicional (Oro GC=F o Forex)
        if not is_crypto and self.is_friday_weekend_close_window(dt_utc):
            return False, "BLOQUEO_VIERNES (15:30 EST: Cierre Anti-Gap Fin de Semana)"

        if self.session_mode == "NY_OPEN":
            lbl = "APERTURA_NY (08:30-11:30 EST)" if is_ny_open else f"FUERA_NY ({dt_ny.strftime('%H:%M %Z')})"
            return is_ny_open, lbl
        if self.session_mode in ("LONDON_OPEN", "LONDON"):
            lbl = "LONDRES_OPEN (03:00-06:00 EST)" if is_london_open else f"FUERA_LONDRES ({dt_ny.strftime('%H:%M %Z')})"
            return is_london_open, lbl
        if self.session_mode in ("COMBO_DUAL", "NY_LONDON"):
            active = is_london_open or is_ny_open
            lbl = "LONDRES_OPEN" if is_london_open else ("NY_OPEN" if is_ny_open else f"PAUSA_SESION ({dt_ny.strftime('%H:%M %Z')})")
            return active, f"COMBO_DUAL [{lbl}]"
        if self.session_mode == "COMBO_TRIO":
            active = is_london_open or is_ny_open
            lbl = "LONDRES_OPEN" if is_london_open else ("NY_OPEN" if is_ny_open else f"PAUSA_ORO ({dt_ny.strftime('%H:%M %Z')})")
            return active, f"COMBO_TRIO_ORO [{lbl}]"
        if self.session_mode in ("ALL", "LONDON_NY"):
            return True, f"ALL_24H ({dt_ny.strftime('%H:%M %Z')})"

        return is_ny_open, "APERTURA_NY" if is_ny_open else "FUERA_DE_SESION"

    def get_consecutive_losses_today(self, trading_date: str) -> int:
        """
        Cuenta cuántas pérdidas consecutivas recientes lleva la cuenta en el día actual.
        Si las últimas 3 operaciones cerradas hoy tienen PnL < 0, activa el Tilt Alert.
        """
        closed_today = self.db.get_trades_by_date(trading_date, status="CLOSED")
        consecutive_losses = 0
        for trade in reversed(closed_today):
            if float(trade["pnl"]) < 0:
                consecutive_losses += 1
            elif float(trade["pnl"]) > 0:
                break
        return consecutive_losses

    def validate_pre_trade(
        self,
        floating_pnl: float = 0.0,
        now_utc: Optional[datetime] = None,
        ignore_session_filter: bool = False,
        symbol: Optional[str] = None,
    ) -> PreTradeRiskCheck:
        """
        Ejecuta todas las validaciones de riesgo previas a abrir una nueva operación:
        1. Estado activo de la cuenta (no FALLADA).
        2. Freno de Mano Personal (Personal Daily Loss Cap, ej. 2%).
        3. Alerta de Racha Negativa (Tilt Alert tras 3 pérdidas consecutivas en el día).
        4. Filtro de Sesión de Mercado (Londres / Apertura NY 08:30 - 11:30 EST / Combo 24H).
        """
        dt_utc = now_utc or datetime.now(timezone.utc)
        acc = self.db.get_account_state()

        if acc.get("status") != "ACTIVE" or acc.get("phase") == "FALLADA":
            return PreTradeRiskCheck(
                allowed=False,
                reason=f"Cuenta inactiva o fallada ({acc.get('fail_reason', 'Hard Breach')}).",
                active_session="N/A",
                consecutive_losses_today=0,
                tilt_locked=False,
                personal_cap_triggered=False,
                daily_pnl_pct=0.0,
            )

        day_start_balance = float(acc["day_start_balance"])
        balance = float(acc["balance"])
        equity = balance + floating_pnl
        personal_cap_pct = float(acc.get("personal_daily_cap_pct", self.personal_daily_cap_pct))

        daily_pnl = equity - day_start_balance
        daily_pnl_pct = (daily_pnl / day_start_balance) if day_start_balance > 0 else 0.0

        trading_date = str(acc["current_trading_day"])
        consecutive_losses = self.get_consecutive_losses_today(trading_date)

        if symbol:
            session_ok, session_name = self.is_symbol_session_active(symbol, dt_utc)
        else:
            session_ok, session_name = self.check_market_session(dt_utc)

        # 1. Freno de Mano Personal (Personal Daily Loss Cap)
        if daily_pnl_pct <= -abs(personal_cap_pct):
            reason = (
                f"FRENO DE MANO PERSONAL ACTIVADO: Pérdida diaria actual ({daily_pnl_pct * 100:.2f}% / "
                f"${daily_pnl:,.2f}) alcanzó el límite personal de -{personal_cap_pct * 100:.2f}%."
            )
            self.db.log_event("PERSONAL_DAILY_CAP", acc["phase"], reason)
            return PreTradeRiskCheck(
                allowed=False,
                reason=reason,
                active_session=session_name,
                consecutive_losses_today=consecutive_losses,
                tilt_locked=False,
                personal_cap_triggered=True,
                daily_pnl_pct=round(daily_pnl_pct, 4),
            )

        # 2. Tilt Alert (3 pérdidas consecutivas en el día)
        if consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES_TILT:
            reason = (
                f"TILT ALERT (Racha Negativa): {consecutive_losses} pérdidas consecutivas hoy ({trading_date}). "
                f"Nuevas entradas bloqueadas por hoy para proteger el capital."
            )
            self.db.log_event("TILT_ALERT", acc["phase"], reason)
            return PreTradeRiskCheck(
                allowed=False,
                reason=reason,
                active_session=session_name,
                consecutive_losses_today=consecutive_losses,
                tilt_locked=True,
                personal_cap_triggered=False,
                daily_pnl_pct=round(daily_pnl_pct, 4),
            )

        # 3. Filtro por Sesión de Mercado
        if not ignore_session_filter and not session_ok:
            reason = (
                f"FILTRO DE SESIÓN: Fuera de ventana operativa ({self.session_mode}). "
                f"Estado actual: {session_name}."
            )
            return PreTradeRiskCheck(
                allowed=False,
                reason=reason,
                active_session=session_name,
                consecutive_losses_today=consecutive_losses,
                tilt_locked=False,
                personal_cap_triggered=False,
                daily_pnl_pct=round(daily_pnl_pct, 4),
            )

        return PreTradeRiskCheck(
            allowed=True,
            reason="Validación de riesgo exitosa. Condiciones óptimas para operar.",
            active_session=session_name,
            consecutive_losses_today=consecutive_losses,
            tilt_locked=False,
            personal_cap_triggered=False,
            daily_pnl_pct=round(daily_pnl_pct, 4),
        )
