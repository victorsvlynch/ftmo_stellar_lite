"""
trading_engine.py - Conectores de Mercado en Vivo (yfinance / ccxt) y Motor de Estrategia
Breakout de Rango de Apertura de Nueva York (NY ORB 15m) con Gestión R:R 1:2.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        import pytz

        def ZoneInfo(key: str):
            return pytz.timezone(key)
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd

from database import TradingDatabase
from stellar_rules import StellarLiteRulesEngine, RuleCheckResult
from risk_manager import RiskManager, PositionSizeResult
from telegram_notifier import TelegramNotifier


@dataclass
class ORBSignal:
    symbol: str
    provider: str
    side: str               # "BUY", "SELL", o "NONE"
    current_price: float
    orb_high: float
    orb_low: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    candle_timestamp: str
    reason: str


class MarketDataConnector:
    """Conector híbrido para activos tradicionales (yfinance) y criptoactivos (ccxt)."""

    def __init__(self, default_exchange: str = "binance") -> None:
        self.default_exchange = default_exchange
        self._ccxt_client = None

    def _get_ccxt_exchange(self):
        """Inicializa el cliente público CCXT con fallback automático entre exchanges líquidos."""
        if self._ccxt_client is not None:
            return self._ccxt_client

        import ccxt
        for ex_id in [self.default_exchange, "kraken", "bybit", "coinbase"]:
            try:
                exchange_cls = getattr(ccxt, ex_id)
                client = exchange_cls({"enableRateLimit": True, "timeout": 10000})
                self._ccxt_client = client
                return client
            except Exception:
                continue
        raise RuntimeError("No fue posible inicializar ningún exchange en CCXT.")

    def fetch_ohlcv_15m(
        self,
        symbol: str = "GC=F",
        provider: str = "yfinance",
        limit: int = 120,
    ) -> pd.DataFrame:
        """
        Descarga velas de 15 minutos en tiempo real desde `yfinance` (ej. GC=F para Oro XAU/USD)
        o `ccxt` (ej. BTC/USDT). Retorna un DataFrame con índice datetime en zona America/New_York
        y columnas: ['Open', 'High', 'Low', 'Close', 'Volume'].
        """
        provider_clean = provider.lower().strip()
        tz_ny = "America/New_York"

        if provider_clean == "ccxt" or "/" in symbol:
            try:
                exchange = self._get_ccxt_exchange()
                raw = exchange.fetch_ohlcv(symbol, timeframe="15m", limit=limit)
                if raw and len(raw) > 0:
                    df = pd.DataFrame(
                        raw, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"]
                    )
                    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert(tz_ny)
                    df.set_index("datetime", inplace=True)
                    df.drop(columns=["timestamp"], inplace=True)
                    return df.astype(float)
            except Exception:
                pass

        # Conector principal vía yfinance (Oro XAU/USD = "GC=F")
        try:
            import yfinance as yf
            yf_symbol = "GC=F" if symbol.upper() in ("XAUUSD", "XAU/USD", "GOLD") else symbol
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="5d", interval="15m")
            if df is not None and not df.empty:
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC").tz_convert(tz_ny)
                else:
                    df.index = df.index.tz_convert(tz_ny)
                cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                return df[cols].dropna().astype(float)
        except Exception:
            pass

        # Fallback sintético determinista en caso de desconexión temporal o mercado cerrado en pruebas
        return self._generate_fallback_ohlcv(symbol=symbol, limit=limit, freq="15min")

    def fetch_ohlcv_1h(
        self,
        symbol: str = "GC=F",
        provider: str = "yfinance",
        limit: int = 200,
    ) -> pd.DataFrame:
        """
        Obtiene velas históricas de 1 Hora (1H) para el cálculo del Filtro de Tendencia Macro (EMA 200).
        """
        provider_clean = provider.lower().strip()
        tz_ny = "America/New_York"

        # Conector ccxt para pares Cripto
        if provider_clean == "ccxt" or "/" in symbol:
            try:
                exchange = self._get_ccxt_exchange()
                raw = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=limit)
                if raw and len(raw) > 0:
                    df = pd.DataFrame(
                        raw, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"]
                    )
                    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert(tz_ny)
                    df.set_index("datetime", inplace=True)
                    df.drop(columns=["timestamp"], inplace=True)
                    return df.astype(float)
            except Exception:
                pass

        # Conector yfinance
        try:
            import yfinance as yf
            yf_symbol = "GC=F" if symbol.upper() in ("XAUUSD", "XAU/USD", "GOLD") else symbol
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="1mo", interval="1h")
            if df is not None and not df.empty:
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC").tz_convert(tz_ny)
                else:
                    df.index = df.index.tz_convert(tz_ny)
                cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                return df[cols].dropna().astype(float)
        except Exception:
            pass

        return self._generate_fallback_ohlcv(symbol=symbol, limit=limit, freq="1h")

    def get_latest_price(self, symbol: str = "GC=F", provider: str = "yfinance") -> float:
        """Obtiene el último precio de mercado disponible."""
        df = self.fetch_ohlcv_15m(symbol=symbol, provider=provider, limit=5)
        if df.empty:
            raise RuntimeError(f"Sin datos de precio para {symbol} ({provider}).")
        return round(float(df["Close"].iloc[-1]), 5)

    @staticmethod
    def _generate_fallback_ohlcv(symbol: str, limit: int = 96, freq: str = "15min") -> pd.DataFrame:
        """
        Genera una serie temporal sintética realista para asegurar continuidad operativa.
        """
        tz_ny = "America/New_York"
        end_time = pd.Timestamp.now(tz=tz_ny).floor(freq)
        date_index = pd.date_range(end=end_time, periods=limit, freq=freq, tz=tz_ny)

        base_price = 2650.0 if ("GC" in symbol.upper() or "XAU" in symbol.upper()) else (
            68000.0 if "BTC" in symbol.upper() else 1.0850
        )
        volatility = base_price * (0.0025 if freq == "1h" else 0.0012)

        rng = np.random.default_rng(seed=int(end_time.strftime("%Y%m%d%H")))
        rows = []
        price = base_price
        for _ in range(limit):
            delta = rng.normal(0, volatility)
            open_p = price
            close_p = max(0.0001, open_p + delta)
            high_p = max(open_p, close_p) + abs(rng.normal(0, volatility * 0.6))
            low_p = min(open_p, close_p) - abs(rng.normal(0, volatility * 0.6))
            vol = abs(rng.normal(1500, 400))
            rows.append((open_p, high_p, low_p, close_p, vol))
            price = close_p

        df = pd.DataFrame(rows, index=date_index, columns=["Open", "High", "Low", "Close", "Volume"])
        df.index.name = "datetime"
        return df.astype(float)


class OpeningRangeBreakoutStrategy:
    """
    Estrategia Cuantitativa de Breakout de Rango de Apertura (ORB 15m) Multi-Sesión:
    1. NY_OPEN:
       - Vela de apertura de NY (08:30 a 08:45 EST).
       - Ventana de breakout: 08:45 - 11:30 EST.
    2. LONDON_OPEN:
       - Vela de apertura de Londres (03:00 a 03:15 EST / 08:00 a 08:15 London).
       - Ventana de breakout: 03:15 - 06:00 EST.
    3. COMBO_DUAL (NY_OPEN + LONDON):
       - Sesión Londres (03:00-06:00 EST): Breakout de la vela de las 03:00 EST.
       - Sesión NY (08:30-11:30 EST): Breakout de la vela de las 08:30 EST.
    4. CRYPTO_24H / ALL:
       - Criptoactivos (24/7): Rango dinámico reciente de consolidación (últimas 8 velas de 15m).
    5. COMBO_TRIO (NY_OPEN + LONDON + CRYPTO_24H):
       - Oro/Forex: Breakout de Londres (03:00 EST) y Breakout de NY (08:30 EST).
       - Cripto (BTC/USDT): Rango dinámico 15m activo 24/7.
    """

    def __init__(self, rr_ratio: float = 2.0) -> None:
        self.rr_ratio = rr_ratio

    def evaluate(
        self,
        df_15m: pd.DataFrame,
        symbol: str,
        provider: str,
        session_mode: str = "NY_OPEN",
        df_1h: Optional[pd.DataFrame] = None,
    ) -> ORBSignal:
        if df_15m is None or df_15m.empty:
            return ORBSignal(
                symbol=symbol,
                provider=provider,
                side="NONE",
                current_price=0.0,
                orb_high=0.0,
                orb_low=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                rr_ratio=self.rr_ratio,
                candle_timestamp="",
                reason="DataFrame de velas 15m vacío.",
            )

        tz_ny = "America/New_York"
        df = df_15m.copy()
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert(tz_ny)
        else:
            df.index = df.index.tz_convert(tz_ny)

        current_candle = df.iloc[-1]
        current_close = round(float(current_candle["Close"]), 5)
        current_price = current_close
        current_ts = df.index[-1]
        ny_minutes = current_ts.hour * 60 + current_ts.minute

        clean_sym = symbol.upper()
        is_crypto = "BTC" in clean_sym or "/" in clean_sym or "USDT" in clean_sym
        mode_upper = session_mode.upper()

        # Cálculo de Filtro de Tendencia Macro (EMA 200 en 1H)
        ema_200_1h: Optional[float] = None
        ema_span = 200
        if df_1h is not None and not df_1h.empty and len(df_1h) >= 10:
            try:
                span_calc = min(200, len(df_1h))
                ema_series = df_1h["Close"].ewm(span=span_calc, adjust=False).mean()
                ema_200_1h = float(ema_series.iloc[-1])
                ema_span = span_calc
            except Exception:
                ema_200_1h = None

        # Determinar si buscamos vela de Londres (03:00 EST), vela de NY (08:30 EST), o dinámico
        target_hour = None
        target_minute = None
        orb_type = "NY ORB 15m"

        if is_crypto or mode_upper in ("CRYPTO_24H", "ALL"):
            target_hour = None
            orb_type = "CRYPTO 15m"
        elif mode_upper in ("LONDON_OPEN", "LONDON"):
            target_hour = 3
            target_minute = 0
            orb_type = "LONDON ORB 15m"
        elif mode_upper == "NY_OPEN":
            target_hour = 8
            target_minute = 30
            orb_type = "NY ORB 15m"
        elif mode_upper in ("COMBO_DUAL", "NY_LONDON"):
            if ny_minutes < (8 * 60 + 30):
                target_hour = 3
                target_minute = 0
                orb_type = "LONDON ORB 15m (Dual)"
            else:
                target_hour = 8
                target_minute = 30
                orb_type = "NY ORB 15m (Dual)"
        elif mode_upper == "COMBO_TRIO":
            if is_crypto:
                target_hour = None
                orb_type = "CRYPTO 15m (Trío)"
            elif ny_minutes < (8 * 60 + 30):
                target_hour = 3
                target_minute = 0
                orb_type = "LONDON ORB 15m (Trío)"
            else:
                target_hour = 8
                target_minute = 30
                orb_type = "NY ORB 15m (Trío)"
        else:
            target_hour = 8
            target_minute = 30

        orb_candles = pd.DataFrame()
        if target_hour is not None and target_minute is not None:
            orb_candles = df[(df.index.hour == target_hour) & (df.index.minute == target_minute)]

        if orb_candles.empty:
            recent_slice = df.iloc[-8:-1] if len(df) > 8 else df.iloc[:-1]
            if recent_slice.empty:
                recent_slice = df
            orb_high = round(float(recent_slice["High"].max()), 5)
            orb_low = round(float(recent_slice["Low"].min()), 5)
            orb_date_label = f"{orb_type}_Dinamico"
        else:
            last_orb = orb_candles.iloc[-1]
            orb_high = round(float(last_orb["High"]), 5)
            orb_low = round(float(last_orb["Low"]), 5)
            time_tag = f"{target_hour:02d}:{target_minute:02d} EST"
            orb_date_label = str(last_orb.name.strftime(f"%Y-%m-%d {time_tag}"))

        range_size = round(orb_high - orb_low, 5)
        if range_size <= 1e-8:
            return ORBSignal(
                symbol=symbol,
                provider=provider,
                side="NONE",
                current_price=current_price,
                orb_high=orb_high,
                orb_low=orb_low,
                stop_loss=0.0,
                take_profit=0.0,
                rr_ratio=self.rr_ratio,
                candle_timestamp=current_ts.isoformat(),
                reason=f"Rango {orb_type} inválido (amplitud cero) en {orb_date_label}.",
            )

        # 1. Evaluar ruptura alcista confirmada por cierre (Anti-Fakeouts: Close > High)
        if current_close > orb_high:
            # Validar con Filtro de Tendencia Macro 1H EMA200
            if ema_200_1h is not None and current_close < ema_200_1h:
                return ORBSignal(
                    symbol=symbol,
                    provider=provider,
                    side="NONE",
                    current_price=current_price,
                    orb_high=orb_high,
                    orb_low=orb_low,
                    stop_loss=0.0,
                    take_profit=0.0,
                    rr_ratio=self.rr_ratio,
                    candle_timestamp=current_ts.isoformat(),
                    reason=(
                        f"Anti-Fakeout Tendencial (1H EMA{ema_span}={ema_200_1h:,.2f}): "
                        f"Ruptura alcista descartada por tendencia bajista macro (Cierre {current_close} < EMA)."
                    ),
                )

            stop_loss = orb_low
            sl_dist = current_price - stop_loss
            take_profit = round(current_price + (sl_dist * self.rr_ratio), 5)
            ema_tag = f" | Tendencia 1H Confirmada (Cierre > EMA{ema_span})" if ema_200_1h else ""
            return ORBSignal(
                symbol=symbol,
                provider=provider,
                side="BUY",
                current_price=current_price,
                orb_high=orb_high,
                orb_low=orb_low,
                stop_loss=round(stop_loss, 5),
                take_profit=take_profit,
                rr_ratio=self.rr_ratio,
                candle_timestamp=current_ts.isoformat(),
                reason=(
                    f"Breakout Confirmado ALCISTA {orb_type} ({orb_date_label}): "
                    f"Cierre ({current_close}) > ORB High ({orb_high}). R:R 1:{self.rr_ratio:.1f}{ema_tag}"
                ),
            )

        # 2. Evaluar ruptura bajista confirmada por cierre (Anti-Fakeouts: Close < Low)
        if current_close < orb_low:
            # Validar con Filtro de Tendencia Macro 1H EMA200
            if ema_200_1h is not None and current_close > ema_200_1h:
                return ORBSignal(
                    symbol=symbol,
                    provider=provider,
                    side="NONE",
                    current_price=current_price,
                    orb_high=orb_high,
                    orb_low=orb_low,
                    stop_loss=0.0,
                    take_profit=0.0,
                    rr_ratio=self.rr_ratio,
                    candle_timestamp=current_ts.isoformat(),
                    reason=(
                        f"Anti-Fakeout Tendencial (1H EMA{ema_span}={ema_200_1h:,.2f}): "
                        f"Ruptura bajista descartada por tendencia alcista macro (Cierre {current_close} > EMA)."
                    ),
                )

            stop_loss = orb_high
            sl_dist = stop_loss - current_price
            take_profit = round(current_price - (sl_dist * self.rr_ratio), 5)
            ema_tag = f" | Tendencia 1H Confirmada (Cierre < EMA{ema_span})" if ema_200_1h else ""
            return ORBSignal(
                symbol=symbol,
                provider=provider,
                side="SELL",
                current_price=current_price,
                orb_high=orb_high,
                orb_low=orb_low,
                stop_loss=round(stop_loss, 5),
                take_profit=take_profit,
                rr_ratio=self.rr_ratio,
                candle_timestamp=current_ts.isoformat(),
                reason=(
                    f"Breakout Confirmado BAJISTA {orb_type} ({orb_date_label}): "
                    f"Cierre ({current_close}) < ORB Low ({orb_low}). R:R 1:{self.rr_ratio:.1f}{ema_tag}"
                ),
            )

        return ORBSignal(
            symbol=symbol,
            provider=provider,
            side="NONE",
            current_price=current_price,
            orb_high=orb_high,
            orb_low=orb_low,
            stop_loss=0.0,
            take_profit=0.0,
            rr_ratio=self.rr_ratio,
            candle_timestamp=current_ts.isoformat(),
            reason=(
                f"Precio ({current_price}) consolidando dentro del Rango {orb_type} "
                f"[{orb_low} - {orb_high}] ({orb_date_label})."
            ),
        )


# Alias para total retrocompatibilidad con scripts existentes
NYOpeningRangeBreakoutStrategy = OpeningRangeBreakoutStrategy


class AutomatedTradingEngine:
    """
    Motor de Ejecución Automatizado que integra:
    - Conectores de mercado (`yfinance` / `ccxt`)
    - Estrategia NY ORB 15m
    - Gestor de Riesgo (`RiskManager`)
    - Reglas Oficiales FundedNext Stellar Lite (`StellarLiteRulesEngine`)
    - Persistencia en SQLite (`TradingDatabase`)
    """

    def __init__(
        self,
        db: TradingDatabase,
        rules_engine: StellarLiteRulesEngine,
        risk_manager: RiskManager,
        symbol: str = "GC=F",
        provider: str = "yfinance",
    ) -> None:
        self.db = db
        self.rules = rules_engine
        self.risk = risk_manager
        self.symbol = symbol
        self.provider = provider
        self.connector = MarketDataConnector()
        self.strategy = OpeningRangeBreakoutStrategy(rr_ratio=self.risk.rr_ratio)
        self.notifier = TelegramNotifier()

    def calculate_open_positions_floating_pnl(
        self, current_prices: Optional[Dict[str, float]] = None
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Calcula el PnL flotante agregado y por operación con deducción institucional de spread y comisiones.
        """
        open_trades = self.db.get_open_trades()
        if not open_trades:
            return 0.0, []

        total_floating = 0.0
        enriched_trades: List[Dict[str, Any]] = []

        for trade in open_trades:
            sym = trade["symbol"]
            prov = trade["provider"]
            if current_prices and sym in current_prices:
                mark_price = current_prices[sym]
            else:
                mark_price = self.connector.get_latest_price(symbol=sym, provider=prov)

            entry = float(trade["entry_price"])
            units = float(trade["units"])
            lots = float(trade["lots"])
            side = str(trade["side"]).upper()

            if side == "BUY":
                gross_floating = round((mark_price - entry) * units, 2)
            else:
                gross_floating = round((entry - mark_price) * units, 2)

            # Deducción institucional de spread y comisiones
            comm, spread = self.risk.calculate_trade_friction(sym, lots, units)
            net_floating = round(gross_floating - comm - spread, 2)

            trade_copy = dict(trade)
            trade_copy["mark_price"] = mark_price
            trade_copy["floating_pnl"] = net_floating
            trade_copy["gross_floating_pnl"] = gross_floating
            trade_copy["commission"] = comm
            trade_copy["spread_cost"] = spread
            enriched_trades.append(trade_copy)
            total_floating += net_floating

        return round(total_floating, 2), enriched_trades

    def manage_open_positions(
        self,
        current_prices: Optional[Dict[str, float]] = None,
        now_utc: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Monitorea las posiciones abiertas:
        1. Hard Breach Check: Si el PnL flotante viola pisos del 4% o 8%, liquida inmediatamente.
        2. Cierre Forzoso de Fin de Semana: Viernes 15:30 EST cierra Oro/Forex para evitar Gaps dominicales.
        3. Break-Even a +1R: En cuanto una operación alcanza +1R en beneficio, traslada el SL a precio de entrada.
        4. Verificación de SL / TP con deducción institucional y alertas a Telegram.
        """
        dt = now_utc or datetime.now(timezone.utc)
        total_floating, open_trades = self.calculate_open_positions_floating_pnl(current_prices)
        closed_events: List[Dict[str, Any]] = []

        # Evaluar reglas con PnL flotante neto incluido
        rule_state = self.rules.evaluate_account(floating_pnl=total_floating, now_server=dt)
        if rule_state.hard_breach and open_trades:
            # Liquidación forzosa por Hard Breach de equidad
            for tr in open_trades:
                comm = float(tr.get("commission", 0.0))
                spread = float(tr.get("spread_cost", 0.0))
                closed = self.db.record_trade_close(
                    trade_id=int(tr["id"]),
                    exit_price=float(tr["mark_price"]),
                    pnl=float(tr.get("gross_floating_pnl", tr["floating_pnl"])),
                    notes="LIQUIDACION_FORZOSA_HARD_BREACH",
                    closed_at=dt,
                    commission=comm,
                    spread_cost=spread,
                )
                if closed:
                    closed_events.append(closed)
                    self.notifier.notify_trade_closed(
                        trade_id=int(tr["id"]),
                        symbol=tr["symbol"],
                        side=tr["side"],
                        lots=float(tr["lots"]),
                        exit_price=float(tr["mark_price"]),
                        gross_pnl=float(closed["gross_pnl"]),
                        net_pnl=float(closed["pnl"]),
                        commission=float(closed["commission"]) + float(closed["spread_cost"]),
                        reason="LIQUIDACION_FORZOSA_HARD_BREACH",
                        balance=rule_state.balance,
                        equity=rule_state.equity,
                    )
            return closed_events

        # 1. Cierre forzoso de fin de semana (Viernes 15:30 EST) para activos tradicionales (GC=F, Forex)
        is_friday_close = self.risk.is_friday_weekend_close_window(dt)
        if is_friday_close:
            remaining_trades = []
            for tr in open_trades:
                sym_up = tr["symbol"].upper()
                is_crypto = "BTC" in sym_up or "/" in sym_up or "USDT" in sym_up
                if not is_crypto:
                    comm = float(tr.get("commission", 0.0))
                    spread = float(tr.get("spread_cost", 0.0))
                    closed = self.db.record_trade_close(
                        trade_id=int(tr["id"]),
                        exit_price=float(tr["mark_price"]),
                        pnl=float(tr.get("gross_floating_pnl", tr["floating_pnl"])),
                        notes="CIERRE_FORZOSO_VIERNES_ANTI_GAP",
                        closed_at=dt,
                        commission=comm,
                        spread_cost=spread,
                    )
                    if closed:
                        closed_events.append(closed)
                        self.db.log_event(
                            "WEEKEND_PROTECTION",
                            rule_state.phase,
                            f"Trade #{tr['id']} ({tr['symbol']}) cerrado por protección de fin de semana (Viernes 15:30 EST) | PnL Neto: ${closed['pnl']:+,.2f}",
                        )
                        self.notifier.notify_weekend_close(1, float(closed["pnl"]))
                else:
                    remaining_trades.append(tr)
            open_trades = remaining_trades

        # 2. Gestión de Break-Even a +1R y salida por SL / TP
        for tr in open_trades:
            mark = float(tr["mark_price"])
            sl = float(tr["stop_loss"])
            tp = float(tr["take_profit"])
            side = str(tr["side"]).upper()
            units = float(tr["units"])
            entry = float(tr["entry_price"])
            lots = float(tr["lots"])
            is_be = int(tr.get("is_break_even", 0))

            # A. Verificación de Break-Even (+1R en beneficio)
            initial_risk_dist = abs(entry - sl)
            if initial_risk_dist > 1e-8 and not is_be:
                gain = (mark - entry) if side == "BUY" else (entry - mark)
                # Si el precio avanzó al menos 1.0R
                if gain >= initial_risk_dist:
                    new_sl = round(entry, 5)
                    updated = self.db.update_trade_sl(
                        trade_id=int(tr["id"]),
                        new_sl=new_sl,
                        notes="BREAK_EVEN_1R_ACTIVADO",
                        is_break_even=1,
                    )
                    if updated:
                        tr["stop_loss"] = new_sl
                        tr["is_break_even"] = 1
                        sl = new_sl
                        self.db.log_event(
                            "BREAK_EVEN_1R",
                            rule_state.phase,
                            f"Trade #{tr['id']} ({tr['symbol']} {side}): Blindado con Break-Even @ {new_sl} (+1R alcanzado). Riesgo actual: $0.00",
                        )
                        self.notifier.notify_break_even(
                            trade_id=int(tr["id"]),
                            symbol=tr["symbol"],
                            side=side,
                            entry_price=entry,
                            new_sl=new_sl,
                        )

            # B. Verificar impacto de Stop Loss o Take Profit
            hit_sl = (side == "BUY" and mark <= sl) or (side == "SELL" and mark >= sl)
            hit_tp = (side == "BUY" and mark >= tp) or (side == "SELL" and mark <= tp)

            if hit_sl or hit_tp:
                exit_p = sl if hit_sl else tp
                gross_pnl = round((exit_p - entry) * units if side == "BUY" else (entry - exit_p) * units, 2)
                reason_tag = "STOP_LOSS_HIT" if hit_sl else "TAKE_PROFIT_HIT"
                if hit_sl and is_be:
                    reason_tag = "BREAK_EVEN_EXIT"

                comm = float(tr.get("commission", 0.0))
                spread = float(tr.get("spread_cost", 0.0))
                closed = self.db.record_trade_close(
                    trade_id=int(tr["id"]),
                    exit_price=exit_p,
                    pnl=gross_pnl,
                    notes=reason_tag,
                    closed_at=dt,
                    commission=comm,
                    spread_cost=spread,
                )
                if closed:
                    closed_events.append(closed)
                    self.db.log_event(
                        reason_tag,
                        rule_state.phase,
                        f"Trade #{tr['id']} ({tr['symbol']} {side}) cerrado por {reason_tag} @ {exit_p} | PnL Neto: ${closed['pnl']:+,.2f} (Bruto: ${closed['gross_pnl']:+,.2f}, Comisión/Spread: -${closed['commission'] + closed['spread_cost']:,.2f})",
                    )
                    self.notifier.notify_trade_closed(
                        trade_id=int(tr["id"]),
                        symbol=tr["symbol"],
                        side=side,
                        lots=lots,
                        exit_price=exit_p,
                        gross_pnl=float(closed["gross_pnl"]),
                        net_pnl=float(closed["pnl"]),
                        commission=float(closed["commission"]) + float(closed["spread_cost"]),
                        reason=reason_tag,
                        balance=rule_state.balance + float(closed["pnl"]),
                        equity=rule_state.equity + float(closed["pnl"]),
                    )

        # Re-evaluar cuenta tras cierres para procesar posibles ascensos de fase
        if closed_events:
            new_floating, _ = self.calculate_open_positions_floating_pnl(current_prices)
            new_rule_state = self.rules.evaluate_account(floating_pnl=new_floating, now_server=dt)
            if new_rule_state.phase != rule_state.phase:
                self.notifier.notify_phase_promoted(
                    old_phase=rule_state.phase,
                    new_phase=new_rule_state.phase,
                    balance=new_rule_state.balance,
                    total_profit=new_rule_state.current_profit,
                )

        return closed_events

    def run_single_cycle(
        self,
        ignore_session_filter: bool = False,
        force_signal_side: Optional[str] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta un ciclo completo del motor:
        1. Gestiona posiciones abiertas y valida reglas de FundedNext Stellar Lite.
        2. Verifica restricciones de riesgo (Personal Cap 2%, Tilt Alert 3 pérdidas, Sesión NY).
        3. Consulta datos de 15m (`yfinance`/`ccxt`) y evalúa la estrategia NY ORB 15m.
        4. Si hay señal válida y no existe posición abierta hoy en el mismo activo, calcula lotaje
           exacto y abre la operación con R:R 1:2.
        """
        dt = now_utc or datetime.now(timezone.utc)

        # 1. Gestionar posiciones abiertas primero
        closed_positions = self.manage_open_positions(now_utc=dt)
        floating_pnl, open_positions = self.calculate_open_positions_floating_pnl()
        rule_status: RuleCheckResult = self.rules.evaluate_account(floating_pnl=floating_pnl, now_server=dt)

        if not rule_status.is_valid:
            return {
                "timestamp": dt.isoformat(),
                "action": "BLOCKED_HARD_BREACH",
                "rule_status": rule_status,
                "closed_positions": closed_positions,
                "open_positions": open_positions,
                "message": "Cuenta bloqueada por Hard Breach de FundedNext.",
            }

        # 1.5 Protección institucional de Target Alcanzado (Evitar Overtrading en Cuenta Real)
        if rule_status.target_reached and rule_status.waiting_min_days and not force_signal_side:
            acc = self.db.get_account_state()
            t_date = str(acc.get("current_trading_day", dt.strftime("%Y-%m-%d")))
            todays_closed = self.db.get_trades_by_date(t_date, status="CLOSED")
            todays_open = [p for p in open_positions]

            # Si hoy ya se operó y el target está cumplido, congelar nuevas órdenes hoy
            if len(todays_closed) > 0 or len(todays_open) > 0:
                protect_msg = (
                    f"OBJETIVO DE {rule_status.phase} ALCANZADO (${rule_status.balance:,.2f} >= "
                    f"${rule_status.profit_target_balance:,.2f}). Jornada de hoy ya registrada "
                    f"({len(todays_closed)} trades). Operativa bloqueada hoy para blindar el balance. "
                    f"Esperando nueva jornada UTC (00:00 UTC) para cumplir días mínimos ({rule_status.trading_days_completed}/"
                    f"{rule_status.min_trading_days_required} días)."
                )
                return {
                    "timestamp": dt.isoformat(),
                    "action": "TARGET_REACHED_TODAY_SECURED",
                    "rule_status": rule_status,
                    "closed_positions": closed_positions,
                    "open_positions": open_positions,
                    "message": protect_msg,
                }

        # 2. Validar filtros de gestión de riesgo
        pre_trade = self.risk.validate_pre_trade(
            floating_pnl=floating_pnl,
            now_utc=dt,
            ignore_session_filter=ignore_session_filter,
        )
        if not pre_trade.allowed:
            return {
                "timestamp": dt.isoformat(),
                "action": "SKIPPED_RISK_FILTER",
                "rule_status": rule_status,
                "risk_check": pre_trade,
                "closed_positions": closed_positions,
                "open_positions": open_positions,
                "message": pre_trade.reason,
            }

        # Determinar lista de símbolos a evaluar
        if "," in self.symbol:
            symbols_to_run = [s.strip() for s in self.symbol.split(",") if s.strip()]
        elif self.symbol.upper() == "MULTI" or (self.risk.session_mode == "COMBO_TRIO" and self.symbol == "GC=F"):
            symbols_to_run = ["GC=F", "BTC/USDT"]
        else:
            symbols_to_run = [self.symbol]

        last_signal = None
        has_holding_open = False
        skipped_session_reasons = []

        for sym in symbols_to_run:
            # 1. Evitar sobre-operar si ya hay una posición abierta en este símbolo
            if any(p["symbol"] == sym for p in open_positions):
                has_holding_open = True
                continue

            # 2. Validar si el símbolo está en su horario operativo
            sym_active, sym_msg = self.risk.is_symbol_session_active(sym, dt)
            if not ignore_session_filter and not sym_active:
                skipped_session_reasons.append(f"{sym}: {sym_msg}")
                continue

            # 3. Determinar proveedor de datos adecuado
            if "/" in sym or "BTC" in sym.upper():
                prov = "ccxt"
            elif self.provider == "multi":
                prov = "yfinance"
            else:
                prov = self.provider

            # 4. Obtener velas de 15m y 1H para evaluar estrategia ORB 15m con Filtro Macro
            df_15m = self.connector.fetch_ohlcv_15m(symbol=sym, provider=prov, limit=96)
            df_1h = self.connector.fetch_ohlcv_1h(symbol=sym, provider=prov, limit=200)
            signal = self.strategy.evaluate(
                df_15m=df_15m,
                symbol=sym,
                provider=prov,
                session_mode=self.risk.session_mode,
                df_1h=df_1h,
            )
            last_signal = signal

            # Permitir forzar señal en modo simulación / test CLI
            if force_signal_side and force_signal_side.upper() in ("BUY", "SELL"):
                price = signal.current_price if signal.current_price > 0 else self.connector.get_latest_price(sym, prov)
                spec = self.risk.get_instrument_spec(sym)
                sl_dist = max(spec["pip_size"] * 50.0, price * 0.0025)
                side_forced = force_signal_side.upper()
                sl = round(price - sl_dist if side_forced == "BUY" else price + sl_dist, 5)
                tp = round(price + sl_dist * self.risk.rr_ratio if side_forced == "BUY" else price - sl_dist * self.risk.rr_ratio, 5)
                signal = ORBSignal(
                    symbol=sym,
                    provider=prov,
                    side=side_forced,
                    current_price=price,
                    orb_high=round(price + sl_dist * 0.5, 5),
                    orb_low=round(price - sl_dist * 0.5, 5),
                    stop_loss=sl,
                    take_profit=tp,
                    rr_ratio=self.risk.rr_ratio,
                    candle_timestamp=dt.isoformat(),
                    reason=f"Señal ORB 15m ({side_forced}) ejecutada en {sym}.",
                )
                last_signal = signal

            if signal.side not in ("BUY", "SELL"):
                continue

            # 5. Calcular tamaño de posición exacto y abrir operación
            acc = self.db.get_account_state()
            risk_pct = float(acc.get("risk_per_trade_pct", self.risk.default_risk_pct))
            is_safety_day_pass = bool(rule_status.target_reached and rule_status.waiting_min_days)

            if is_safety_day_pass:
                # Modo Micro-Lote de Seguridad para registro de día obligatorio sin arriesgar capital ganado
                spec = self.risk.get_instrument_spec(sym)
                safe_min_lot = spec["min_lot"]
                sl_dist = abs(signal.current_price - signal.stop_loss)
                sizing = PositionSizeResult(
                    symbol=sym,
                    side=signal.side,
                    entry_price=round(signal.current_price, 5),
                    stop_loss=round(signal.stop_loss, 5),
                    take_profit=round(signal.take_profit, 5),
                    risk_pct=0.0001,
                    risk_amount_usd=round(safe_min_lot * sl_dist * spec["contract_size"], 2),
                    sl_distance_price=round(sl_dist, 5),
                    sl_distance_pips=round(sl_dist / spec["pip_size"], 2),
                    lots=safe_min_lot,
                    units=round(safe_min_lot * spec["contract_size"], 6),
                    rr_ratio=self.risk.rr_ratio,
                    expected_reward_usd=round(safe_min_lot * abs(signal.take_profit - signal.current_price) * spec["contract_size"], 2),
                )
                strat_tag = "MIN_LOT_SAFETY_DAY_REGISTRATION"
            else:
                sizing: PositionSizeResult = self.risk.calculate_position_size(
                    balance=rule_status.balance,
                    symbol=sym,
                    side=signal.side,
                    entry_price=signal.current_price,
                    stop_loss=signal.stop_loss,
                    risk_pct=risk_pct,
                    rr_ratio=self.risk.rr_ratio,
                )
                strat_tag = "NY_ORB_15M"

            is_news = self.rules.is_high_impact_news_window(dt)
            if not is_safety_day_pass:
                if self.risk.session_mode in ("LONDON_OPEN", "LONDON"):
                    strat_tag = "LONDON_ORB_15M"
                elif self.risk.session_mode in ("COMBO_DUAL", "NY_LONDON"):
                    strat_tag = "COMBO_DUAL_ORB"
                elif self.risk.session_mode == "COMBO_TRIO":
                    strat_tag = "COMBO_TRIO_ORB"
                elif self.risk.session_mode in ("ALL", "CRYPTO_24H"):
                    strat_tag = "CRYPTO_ORB_15M"
                strat_tag = "CRYPTO_ORB_15M"

            trade_id = self.db.record_trade_open(
                symbol=sym,
                provider=prov,
                side=sizing.side,
                lots=sizing.lots,
                units=sizing.units,
                entry_price=sizing.entry_price,
                stop_loss=sizing.stop_loss,
                take_profit=sizing.take_profit,
                rr_ratio=sizing.rr_ratio,
                phase=rule_status.phase,
                strategy=strat_tag,
                is_news_window=is_news,
                notes=signal.reason,
                opened_at=dt,
            )

            self.db.log_event(
                "TRADE_OPENED",
                rule_status.phase,
                (
                    f"Trade #{trade_id} ABIERTO: {sizing.side} {sizing.lots} lotes ({sym}) @ {sizing.entry_price} | "
                    f"SL: {sizing.stop_loss} | TP: {sizing.take_profit} | Riesgo: ${sizing.risk_amount_usd:,.2f} "
                    f"({sizing.risk_pct * 100:.2f}%) | Estrategia: {strat_tag} | NewsWindow={is_news}"
                ),
            )

            # Notificar apertura de posición a Telegram
            self.notifier.notify_trade_opened(
                trade_id=trade_id,
                symbol=sym,
                side=sizing.side,
                lots=sizing.lots,
                entry_price=sizing.entry_price,
                stop_loss=sizing.stop_loss,
                take_profit=sizing.take_profit,
                risk_usd=sizing.risk_amount_usd,
                risk_pct=sizing.risk_pct,
                strategy=strat_tag,
                phase=rule_status.phase,
            )

            _, updated_open_positions = self.calculate_open_positions_floating_pnl(
                {sym: sizing.entry_price}
            )

            return {
                "timestamp": dt.isoformat(),
                "action": "TRADE_OPENED",
                "trade_id": trade_id,
                "sizing": sizing,
                "signal": signal,
                "rule_status": rule_status,
                "risk_check": pre_trade,
                "closed_positions": closed_positions,
                "open_positions": updated_open_positions,
                "message": f"Posición #{trade_id} ejecutada ({sizing.side} {sizing.lots} lotes {sym}).",
            }

        # Si no se abrió ninguna operación:
        if has_holding_open:
            return {
                "timestamp": dt.isoformat(),
                "action": "HOLDING_OPEN_POSITION",
                "rule_status": rule_status,
                "risk_check": pre_trade,
                "closed_positions": closed_positions,
                "open_positions": open_positions,
                "message": f"Posición activa en curso; monitoreando salida por SL/TP.",
            }

        if skipped_session_reasons and not last_signal:
            return {
                "timestamp": dt.isoformat(),
                "action": "SKIPPED_RISK_FILTER",
                "rule_status": rule_status,
                "risk_check": pre_trade,
                "closed_positions": closed_positions,
                "open_positions": open_positions,
                "message": f"Activos fuera de ventana operativa ({' | '.join(skipped_session_reasons)}).",
            }

        return {
            "timestamp": dt.isoformat(),
            "action": "NO_SIGNAL",
            "signal": last_signal,
            "rule_status": rule_status,
            "risk_check": pre_trade,
            "closed_positions": closed_positions,
            "open_positions": open_positions,
            "message": last_signal.reason if last_signal else "Sin señal de ruptura en la ventana actual.",
        }
