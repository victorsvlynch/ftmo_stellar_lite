"""
trading_engine.py - Conectores de Mercado en Vivo (yfinance / ccxt) y Motor de Estrategia
Breakout de Rango de Apertura de Nueva York (NY ORB 15m) con Gestión R:R 1:2.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import os
import json
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

    @staticmethod
    def resolve_yahoo_symbol(symbol: str) -> str:
        """Mapea símbolos de brokers/índices a los tickers oficiales de Yahoo Finance."""
        clean_upper = symbol.upper().replace(".M", "").replace(".RAW", "").replace(".PRO", "")
        if clean_upper in ("XAUUSD", "XAU/USD", "GOLD"):
            return "GC=F"
        if clean_upper in ("XAGUSD", "XAG/USD", "SILVER"):
            return "SI=F"
        if any(k in clean_upper for k in ("US30", "DJ30", "WS30", "USA30", "DOW")):
            return "YM=F"
        if clean_upper in ("EURUSD", "EUR/USD"):
            return "EURUSD=X"
        if clean_upper in ("USDJPY", "USD/JPY"):
            return "USDJPY=X"
        if clean_upper in ("AUDUSD", "AUD/USD"):
            return "AUDUSD=X"
        if clean_upper in ("GBPUSD", "GBP/USD"):
            return "GBPUSD=X"
        if any(k in clean_upper for k in ("US500", "SPX500", "SP500", "USA500")) and "NQ" not in clean_upper:
            return "ES=F"
        if any(k in clean_upper for k in ("US100", "NAS100", "USTEC")):
            return "NQ=F"
        return symbol

    @staticmethod
    def resolve_mt5_symbol(symbol: str) -> str:
        """Resuelve el símbolo estándar o ticker de Yahoo a la nomenclatura oficial de MT5 (FundedNext/FTMO)."""
        clean = symbol.upper().replace("=X", "").replace("=F", "").replace("/", "")
        if any(k in clean for k in ("GC", "XAU", "GOLD")):
            return "XAUUSD"
        if any(k in clean for k in ("SI", "XAG", "SILVER")):
            return "XAGUSD"
        if ("JPY" in clean and "USD" in clean) or clean == "USDJPY" or "JPY" in clean:
            return "USDJPY"
        if ("EUR" in clean and "USD" in clean) or clean == "EURUSD" or "EUR" in clean:
            return "EURUSD"
        if "AUD" in clean:
            return "AUDUSD"
        if any(k in clean for k in ("ES", "500", "SPX", "US500", "SP500")):
            return "US500"
        if any(k in clean for k in ("US30", "DJ30", "YM", "DOW", "WS30")) or clean == "30" or clean.endswith("30"):
            return "US30"
        return clean

    @classmethod
    def get_mt5_tick(cls, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el tick oficial de MT5 (Bid, Ask, Mid, Spread) con latencia mínima:
        1. En Windows con MetaTrader5 disponible: consulta nativa por IPC (< 1ms).
        2. En Linux (VPS) o fallback: lee mt5_feed.json o consulta http://localhost:8000/api/feed.
        Retorna: {"symbol": str, "bid": float, "ask": float, "mid": float, "spread": float, "age_s": float} o None.
        """
        mt5_sym = cls.resolve_mt5_symbol(symbol)
        now_dt = datetime.now(timezone.utc)

        # 1. Intento nativo en Windows
        try:
            import MetaTrader5 as mt5
            if not mt5.terminal_info():
                mt5.initialize()
            if mt5.terminal_info():
                tick = mt5.symbol_info_tick(mt5_sym)
                if tick and tick.bid > 0 and tick.ask > 0:
                    mid = round((tick.bid + tick.ask) / 2.0, 5)
                    sp = round(tick.ask - tick.bid, 5)
                    return {
                        "symbol": mt5_sym,
                        "bid": float(tick.bid),
                        "ask": float(tick.ask),
                        "mid": mid,
                        "spread": sp,
                        "age_s": 0.001,
                        "source": "MT5_Native_IPC",
                    }
        except Exception:
            pass

        # 2. Intento de lectura desde cache mt5_feed.json en disco
        feed_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mt5_feed.json")
        if os.path.exists(feed_file):
            try:
                with open(feed_file, "r", encoding="utf-8") as f:
                    feed = json.load(f)
                up_str = feed.get("updated_at", "")
                age_s = 9999.0
                if up_str:
                    age_s = max(0.0, (now_dt - datetime.fromisoformat(up_str)).total_seconds())
                syms = feed.get("symbols", {})
                item = syms.get(symbol) or syms.get(mt5_sym) or syms.get(symbol.upper())
                if item and age_s <= 35.0:
                    res = dict(item)
                    res["age_s"] = round(age_s, 2)
                    res["source"] = "MT5_Feed_Cache"
                    return res
            except Exception:
                pass

        # 3. Intento vía HTTP loopback hacia el servidor webhook
        try:
            import urllib.request
            url = "http://127.0.0.1:8000/api/feed"
            req = urllib.request.Request(url, headers={"User-Agent": "TradingEngine/1.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    age_s = float(data.get("age_seconds", 9999.0))
                    syms = data.get("symbols", {})
                    item = syms.get(symbol) or syms.get(mt5_sym) or syms.get(symbol.upper())
                    if item and age_s <= 35.0:
                        res = dict(item)
                        res["age_s"] = age_s
                        res["source"] = "MT5_Feed_HTTP"
                        return res
        except Exception:
            pass

        return None

    @classmethod
    def _fetch_mt5_ohlcv(cls, symbol: str, timeframe: str = "15m", limit: int = 120) -> Optional[pd.DataFrame]:
        """Obtiene velas históricas directas de MT5 mediante la librería oficial en Windows."""
        try:
            import MetaTrader5 as mt5
            if not mt5.terminal_info():
                if not mt5.initialize():
                    return None
            broker_sym = cls.resolve_mt5_symbol(symbol)
            tf = mt5.TIMEFRAME_M15 if timeframe == "15m" else mt5.TIMEFRAME_H1
            rates = mt5.copy_rates_from_pos(broker_sym, tf, 0, limit)
            if rates is None or len(rates) == 0:
                return None
            df = pd.DataFrame(rates)
            tz_ny = "America/New_York"
            df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(tz_ny)
            df.set_index("datetime", inplace=True)
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "tick_volume": "Volume"}, inplace=True)
            cols = ["Open", "High", "Low", "Close", "Volume"]
            res = df[cols].astype(float)
            res.attrs["is_synthetic"] = False
            res.attrs["data_source"] = "MT5_Native_Broker"
            return res
        except Exception:
            return None

    @staticmethod
    def _fetch_yahoo_direct(
        symbol: str,
        interval: str = "15m",
        range_str: str = "5d",
    ) -> Optional[pd.DataFrame]:
        """
        Descarga velas en tiempo real directamente desde los endpoints REST v8 de Yahoo Finance.
        Evita bloqueos de rate-limit (HTTP 429) y problemas de cookies/crumbs de la librería yfinance.
        """
        import requests

        yf_symbol = MarketDataConnector.resolve_yahoo_symbol(symbol)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
        endpoints = [
            f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}?interval={interval}&range={range_str}",
            f"https://query2.finance.yahoo.com/v8/finance/chart/{yf_symbol}?interval={interval}&range={range_str}",
        ]
        tz_ny = "America/New_York"

        for url in endpoints:
            try:
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    chart = data.get("chart", {})
                    results = chart.get("result", [])
                    if results and "timestamp" in results[0]:
                        res = results[0]
                        ts = res["timestamp"]
                        quote = res.get("indicators", {}).get("quote", [{}])[0]
                        open_vals = quote.get("open", [])
                        close_vals = quote.get("close", [])
                        if not open_vals or not close_vals:
                            continue
                        df = pd.DataFrame(
                            {
                                "Open": quote.get("open"),
                                "High": quote.get("high"),
                                "Low": quote.get("low"),
                                "Close": quote.get("close"),
                                "Volume": quote.get("volume", [0] * len(ts)),
                            },
                            index=pd.to_datetime(ts, unit="s", utc=True),
                        )
                        df = df.dropna()
                        if not df.empty:
                            df.index = df.index.tz_convert(tz_ny)
                            df.attrs["is_synthetic"] = False
                            df.attrs["data_source"] = "YahooDirect"
                            return df.astype(float)
            except Exception:
                continue
        return None

    def fetch_ohlcv_15m(
        self,
        symbol: str = "GC=F",
        provider: str = "yfinance",
        limit: int = 120,
        allow_synthetic: bool = False,
    ) -> pd.DataFrame:
        """
        Descarga velas de 15 minutos en tiempo real desde Yahoo Finance Direct / yfinance (ej. GC=F)
        o `ccxt` (ej. BTC/USDT). Retorna un DataFrame con índice datetime en zona America/New_York
        y columnas: ['Open', 'High', 'Low', 'Close', 'Volume'].
        """
        provider_clean = provider.lower().strip()
        tz_ny = "America/New_York"

        # Conector ccxt para pares Cripto
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
                    df.attrs["is_synthetic"] = False
                    df.attrs["data_source"] = "ccxt"
                    return df.astype(float)
            except Exception:
                pass

        # Conector MT5 (Broker Directo en Windows o Híbrido en Nube)
        if provider_clean in ("mt5", "mt5_bridge", "broker"):
            # A. Intento nativo directo en MT5 (Windows)
            df_mt5 = self._fetch_mt5_ohlcv(symbol, timeframe="15m", limit=limit)
            if df_mt5 is not None and not df_mt5.empty:
                return df_mt5

            # B. Intento Híbrido en Nube / VPS: Velas base Yahoo Direct + Tick actual de MT5
            df_direct = self._fetch_yahoo_direct(symbol=symbol, interval="15m", range_str="5d")
            if df_direct is not None and not df_direct.empty:
                tick = self.get_mt5_tick(symbol)
                if tick and float(tick.get("mid", 0.0)) > 0:
                    last_mid = float(tick["mid"])
                    df_direct.iloc[-1, df_direct.columns.get_loc("Close")] = last_mid
                    df_direct.iloc[-1, df_direct.columns.get_loc("High")] = max(
                        float(df_direct.iloc[-1]["High"]), last_mid
                    )
                    df_direct.iloc[-1, df_direct.columns.get_loc("Low")] = min(
                        float(df_direct.iloc[-1]["Low"]), last_mid
                    )
                    df_direct.attrs["data_source"] = f"MT5_Feed_Hybrid ({tick.get('source', 'MT5')})"
                    df_direct.attrs["is_synthetic"] = False
                    return df_direct

        # 1. Conector principal de alta velocidad: REST v8 Directo (Sin Rate-Limits)
        df_direct = self._fetch_yahoo_direct(symbol=symbol, interval="15m", range_str="5d")
        if df_direct is not None and not df_direct.empty:
            return df_direct

        # 2. Conector secundario de respaldo vía librería yfinance
        try:
            import yfinance as yf
            yf_symbol = self.resolve_yahoo_symbol(symbol)
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="5d", interval="15m")
            if df is not None and not df.empty:
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC").tz_convert(tz_ny)
                else:
                    df.index = df.index.tz_convert(tz_ny)
                cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                res = df[cols].dropna().astype(float)
                res.attrs["is_synthetic"] = False
                res.attrs["data_source"] = "yfinance"
                return res
        except Exception:
            pass

        # 3. Fallback solo si está explícitamente permitido (tests o simulación)
        if allow_synthetic:
            return self._generate_fallback_ohlcv(symbol=symbol, limit=limit, freq="15min")

        return pd.DataFrame()

    def fetch_ohlcv_1h(
        self,
        symbol: str = "GC=F",
        provider: str = "yfinance",
        limit: int = 200,
        allow_synthetic: bool = False,
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
                    df.attrs["is_synthetic"] = False
                    df.attrs["data_source"] = "ccxt"
                    return df.astype(float)
            except Exception:
                pass

        # Conector MT5 (Broker Directo en Windows)
        if provider_clean in ("mt5", "mt5_bridge", "broker"):
            df_mt5 = self._fetch_mt5_ohlcv(symbol, timeframe="1h", limit=limit)
            if df_mt5 is not None and not df_mt5.empty:
                return df_mt5

        # 1. Conector principal de alta velocidad: REST v8 Directo (Sin Rate-Limits)
        df_direct = self._fetch_yahoo_direct(symbol=symbol, interval="1h", range_str="1mo")
        if df_direct is not None and not df_direct.empty:
            return df_direct

        # 2. Conector secundario de respaldo vía librería yfinance
        try:
            import yfinance as yf
            yf_symbol = self.resolve_yahoo_symbol(symbol)
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="1mo", interval="1h")
            if df is not None and not df.empty:
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC").tz_convert(tz_ny)
                else:
                    df.index = df.index.tz_convert(tz_ny)
                cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                res = df[cols].dropna().astype(float)
                res.attrs["is_synthetic"] = False
                res.attrs["data_source"] = "yfinance"
                return res
        except Exception:
            pass

        if allow_synthetic:
            return self._generate_fallback_ohlcv(symbol=symbol, limit=limit, freq="1h")

        return pd.DataFrame()

    def get_latest_price(self, symbol: str = "GC=F", provider: str = "yfinance") -> float:
        """Obtiene el último precio de mercado disponible."""
        prov_clean = provider.lower().strip()
        if prov_clean in ("mt5", "mt5_bridge", "broker"):
            tick = self.get_mt5_tick(symbol)
            if tick and float(tick.get("bid", 0.0)) > 0:
                return round(float(tick["bid"]), 5)

        df = self.fetch_ohlcv_15m(symbol=symbol, provider=provider, limit=5, allow_synthetic=False)
        if df.empty:
            df = self._generate_fallback_ohlcv(symbol=symbol, limit=5, freq="15min")
        return round(float(df["Close"].iloc[-1]), 5)

    @staticmethod
    def _generate_fallback_ohlcv(symbol: str, limit: int = 96, freq: str = "15min") -> pd.DataFrame:
        """
        Genera una serie temporal sintética realista para asegurar continuidad en pruebas y simulación.
        """
        tz_ny = "America/New_York"
        end_time = pd.Timestamp.now(tz=tz_ny).floor(freq)
        date_index = pd.date_range(end=end_time, periods=limit, freq=freq, tz=tz_ny)

        sym_u = symbol.upper()
        if "GC" in sym_u or "XAU" in sym_u or "GOLD" in sym_u:
            base_price = 2700.0
        elif any(k in sym_u for k in ("ES", "500", "SPX")):
            base_price = 5850.0
        elif any(k in sym_u for k in ("NQ", "100", "NAS")):
            base_price = 20500.0
        elif "EUR" in sym_u:
            base_price = 1.0950
        elif "JPY" in sym_u:
            base_price = 156.50
        elif "BTC" in sym_u:
            base_price = 85000.0
        else:
            base_price = 1.0850
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
        res = df.astype(float)
        res.attrs["is_synthetic"] = True
        res.attrs["data_source"] = "SYNTHETIC_FALLBACK"
        return res


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
        # Bloqueo explícito de Nasdaq 100 (Inactivo por política de riesgo institucional)
        clean_upper = symbol.upper().replace("=X", "").replace("=F", "")
        if any(k in clean_upper for k in ("US100", "NAS100", "USTEC", "NQ")):
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
                reason="Nasdaq 100 (NQ/US100/USTEC) se encuentra INACTIVO por configuración institucional.",
            )

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
        is_index = any(k in clean_sym for k in ("ES", "500", "SPX", "NQ", "100", "NAS", "USTEC"))
        is_forex = any(k in clean_sym for k in ("EUR", "GBP", "JPY", "AUD", "CAD", "CHF"))
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

        # Determinar si buscamos vela de Wall Street (09:30 EST), Londres (03:00 EST), NY (08:30 EST), o dinámico
        target_hour = None
        target_minute = None
        orb_type = "NY ORB 15m"

        if is_crypto or mode_upper in ("CRYPTO_24H", "ALL"):
            target_hour = None
            orb_type = "CRYPTO 15m"
        elif is_index and mode_upper in ("NY_OPEN", "PORTFOLIO_DUAL", "SP500_EURUSD", "DEFAULT"):
            target_hour = 9
            target_minute = 30
            orb_type = "WALL_STREET ORB 15m"
        elif mode_upper in ("LONDON_OPEN", "LONDON"):
            target_hour = 3
            target_minute = 0
            orb_type = "LONDON ORB 15m"
        elif mode_upper in ("PORTFOLIO_DUAL", "SP500_EURUSD"):
            if is_index:
                target_hour = 9
                target_minute = 30
                orb_type = "WALL_STREET ORB 15m"
            elif is_forex and ny_minutes < (8 * 60 + 30):
                target_hour = 3
                target_minute = 0
                orb_type = "LONDON ORB 15m (Dual)"
            else:
                target_hour = 8
                target_minute = 30
                orb_type = "NY ORB 15m (Dual)"
        elif mode_upper == "NY_OPEN":
            if is_index:
                target_hour = 9
                target_minute = 30
                orb_type = "WALL_STREET ORB 15m"
            else:
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
                        f"Ruptura alcista descartada por tendencia bajista macro (Cierre {current_close} < EMA). "
                        f"Rango {orb_type} [{orb_low} - {orb_high}] ({orb_date_label})."
                    ),
                )

            stop_loss = orb_low
            sl_dist = current_price - stop_loss
            # Especialización Institucional USD/JPY (Apertura de Bonos US10Y 08:30 EST):
            # Si la vela ORB tuvo un spike macro > 35 pips (0.350 JPY), anclar el SL al 60% estructural (máx 30 pips)
            # para mantener el Take Profit (2.0R <= 60 pips) dentro del rango NY Open promedio (40.8p - 86.8p ADR).
            if "JPY" in clean_sym and sl_dist > 0.350:
                sl_dist = round(min(sl_dist * 0.60, 0.300), 3)
                stop_loss = round(current_price - sl_dist, 3)
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
                        f"Ruptura bajista descartada por tendencia alcista macro (Cierre {current_close} > EMA). "
                        f"Rango {orb_type} [{orb_low} - {orb_high}] ({orb_date_label})."
                    ),
                )

            stop_loss = orb_high
            sl_dist = stop_loss - current_price
            if "JPY" in clean_sym and sl_dist > 0.350:
                sl_dist = round(min(sl_dist * 0.60, 0.300), 3)
                stop_loss = round(current_price + sl_dist, 3)
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
                f"{f' | Macro 1H EMA{ema_span}={ema_200_1h:,.2f}' if ema_200_1h else ''}"
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

        # 1. Cierre forzoso de fin de semana (Viernes 15:30 EST) o fin de jornada (16:15 EST si no permite overnight, ej. FTMO)
        is_friday_close = self.risk.is_friday_weekend_close_window(dt)
        is_no_overnight_close = (not getattr(self.risk, "allow_overnight_weekend", True)) and self.risk.is_market_nearing_daily_close(dt)
        if is_friday_close or is_no_overnight_close:
            remaining_trades = []
            close_reason = "CIERRE_FORZOSO_VIERNES_ANTI_GAP" if is_friday_close else "CIERRE_FORZOSO_DIARIO_NO_OVERNIGHT_FTMO"
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
                        notes=close_reason,
                        closed_at=dt,
                        commission=comm,
                        spread_cost=spread,
                    )
                    if closed:
                        closed_events.append(closed)
                        self.db.log_event(
                            "PROTECCION_HORARIO_REGLAS",
                            rule_state.phase,
                            f"Trade #{tr['id']} ({tr['symbol']}) cerrado por regla horario ({close_reason}) | PnL Neto: ${closed['pnl']:+,.2f}",
                        )
                        self.notifier.notify_weekend_close(1, float(closed["pnl"]))
                else:
                    remaining_trades.append(tr)
            open_trades = remaining_trades

        # 1.5. Sincronización en vivo con MetaTrader 5 (si el broker ya cerró la orden, capturar deal real)
        if self.provider == "mt5" and open_trades:
            try:
                from mt5_bridge import MT5Bridge
                bridge = MT5Bridge()
                if bridge.initialize():
                    mt5_open = {p["ticket"]: p for p in bridge.get_open_positions()}
                    deals = bridge.get_closed_deals(days=2)
                    deals_by_pos = {d["position_id"]: d for d in deals}
                    bridge.shutdown()

                    unclosed_trades = []
                    for tr in open_trades:
                        tr_ticket = tr.get("mt5_ticket", 0)
                        if tr_ticket and tr_ticket not in mt5_open and tr_ticket in deals_by_pos:
                            d = deals_by_pos[tr_ticket]
                            closed = self.db.record_trade_close(
                                trade_id=int(tr["id"]),
                                exit_price=float(d["price"]),
                                pnl=float(d["net_pnl"]),
                                notes=f"MT5_BROKER_EXECUTION | Deal #{d['ticket']} ({d['comment']})",
                                closed_at=dt,
                                commission=float(d["commission"]),
                                spread_cost=0.0,
                            )
                            if closed:
                                closed_events.append(closed)
                                self.notifier.notify_trade_closed(
                                    trade_id=int(tr["id"]),
                                    symbol=tr["symbol"],
                                    side=tr["side"],
                                    lots=float(tr["lots"]),
                                    exit_price=float(d["price"]),
                                    gross_pnl=float(d["profit"]),
                                    net_pnl=float(d["net_pnl"]),
                                    commission=float(d["commission"]),
                                    reason=f"MT5_BROKER_EXECUTION ({d['comment']})",
                                    balance=rule_state.balance + float(d["net_pnl"]),
                                    equity=rule_state.equity + float(d["net_pnl"]),
                                )
                        else:
                            unclosed_trades.append(tr)
                    open_trades = unclosed_trades
            except Exception:
                pass

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

            # A. Escalera Institucional Personalizada por Activo (Break-Even+ y Candados de Ganancia)
            rr_target = float(tr.get("rr_ratio", 2.0) or 2.0)
            if abs(tp - entry) > 1e-8 and rr_target > 0:
                initial_risk_dist = abs(tp - entry) / rr_target
            else:
                initial_risk_dist = abs(entry - sl)

            if initial_risk_dist > 1e-8:
                sym_upper = str(tr["symbol"]).upper()
                is_gold = ("GC" in sym_upper or "XAU" in sym_upper or "GOLD" in sym_upper)
                is_silver = ("SI" in sym_upper or "XAG" in sym_upper or "SILVER" in sym_upper)
                is_jpy = (not is_gold and not is_silver and (("JPY" in sym_upper and "USD" in sym_upper) or "JPY" in sym_upper))
                is_us30 = (not is_jpy and ("30" in sym_upper or "DJ30" in sym_upper or "US30" in sym_upper or "YM" in sym_upper or "DOW" in sym_upper or "WS30" in sym_upper))
                is_sp500 = ("500" in sym_upper or "SPX" in sym_upper or "ES" in sym_upper)
                is_aud = (not is_gold and not is_silver and not is_jpy and "AUD" in sym_upper)
                is_forex = (not is_gold and not is_silver and not is_jpy and not is_aud and not is_us30 and not is_sp500 and (any(k in sym_upper for k in ("EUR", "GBP", "=X")) or entry < 10.0))

                if is_gold:
                    # XAUUSD (Oro): BE+ ($0.80) a +1.00R | Candado 1 (+0.60R) a +1.40R | Candado 2 (+1.10R) a +1.75R | Pre-Rollover (+1.35R)
                    be_trigger_r = 1.00
                    be_offset = min(0.80, initial_risk_dist * 0.15)
                    lock1_trigger_r, lock1_gain_r = 1.40, 0.60
                    lock2_trigger_r, lock2_gain_r = 1.75, 1.10
                    preroll_gain_r = 1.35
                    decimals = 4
                elif is_silver:
                    # XAGUSD (Plata Spot / SI=F - Alta Volatilidad Metales, ADR ~$1.50):
                    # BE+ ($0.04) a +1.00R | Candado 1 (+0.60R) a +1.40R | Candado 2 (+1.10R) a +1.75R | Pre-Rollover (+1.35R)
                    be_trigger_r = 1.00
                    be_offset = min(0.04, initial_risk_dist * 0.15)
                    lock1_trigger_r, lock1_gain_r = 1.40, 0.60
                    lock2_trigger_r, lock2_gain_r = 1.75, 1.10
                    preroll_gain_r = 1.35
                    decimals = 3
                elif is_us30:
                    # US30 (Dow Jones 30 Industrial - Índice Accionario de Alto Rango, ADR ~450 pts):
                    # BE+ (12 pts) a +0.95R | Candado 1 (+0.60R) a +1.35R | Candado 2 (+1.15R) a +1.70R | Pre-Rollover (+1.35R)
                    be_trigger_r = 0.95
                    be_offset = min(12.0, initial_risk_dist * 0.15)
                    lock1_trigger_r, lock1_gain_r = 1.35, 0.60
                    lock2_trigger_r, lock2_gain_r = 1.70, 1.15
                    preroll_gain_r = 1.35
                    decimals = 1
                elif is_sp500:
                    # S&P 500 (ES=F / US500): BE+ (1.0 pt) a +1.00R | Candado 1 (+0.60R) a +1.35R | Candado 2 (+1.15R) a +1.70R | Pre-Rollover (+1.35R)
                    be_trigger_r = 1.00
                    be_offset = min(1.00, initial_risk_dist * 0.15)
                    lock1_trigger_r, lock1_gain_r = 1.35, 0.60
                    lock2_trigger_r, lock2_gain_r = 1.70, 1.15
                    preroll_gain_r = 1.35
                    decimals = 2
                elif is_jpy:
                    # USDJPY (Forex Bonos US/NY - Alta Eficiencia Tendencial 44.9%, ADR ~87p): BE+ (1.5 pips = 0.015) a +0.95R | Candado 1 (+0.55R) a +1.35R | Candado 2 (+1.15R) a +1.70R | Pre-Rollover (+1.35R)
                    be_trigger_r = 0.95
                    be_offset = min(0.015, initial_risk_dist * 0.15)
                    lock1_trigger_r, lock1_gain_r = 1.35, 0.55
                    lock2_trigger_r, lock2_gain_r = 1.70, 1.15
                    preroll_gain_r = 1.35
                    decimals = 3
                elif is_aud:
                    # AUDUSD (Standby): BE+ (1.2 pips) a +0.95R | Candado 1 (+0.55R) a +1.30R | Candado 2 (+1.10R) a +1.65R | Pre-Rollover (+1.30R)
                    be_trigger_r = 0.95
                    be_offset = min(0.00012, initial_risk_dist * 0.15)
                    lock1_trigger_r, lock1_gain_r = 1.30, 0.55
                    lock2_trigger_r, lock2_gain_r = 1.65, 1.10
                    preroll_gain_r = 1.30
                    decimals = 5
                elif is_forex:
                    # EURUSD (Forex Europeo/NY): BE+ (1.5 pips) a +0.95R | Candado 1 (+0.50R) a +1.35R | Candado 2 (+1.10R) a +1.70R | Pre-Rollover (+1.30R)
                    be_trigger_r = 0.95
                    be_offset = min(0.00015, initial_risk_dist * 0.15)
                    lock1_trigger_r, lock1_gain_r = 1.35, 0.50
                    lock2_trigger_r, lock2_gain_r = 1.70, 1.10
                    preroll_gain_r = 1.30
                    decimals = 5
                else:
                    # Genérico
                    be_trigger_r = 1.00
                    be_offset = initial_risk_dist * 0.10
                    lock1_trigger_r, lock1_gain_r = 1.35, 0.60
                    lock2_trigger_r, lock2_gain_r = 1.70, 1.15
                    preroll_gain_r = 1.35
                    decimals = 2

                gain = (mark - entry) if side == "BUY" else (entry - mark)
                current_r = gain / initial_risk_dist

                # Detectar si ya alcanzó Nivel 3 anteriormente (Memoria Persistente) y si estamos en ventana Pre-Rollover (16:30-16:59 EST)
                locked_dist = (sl - entry) if side == "BUY" else (entry - sl)
                locked_r = locked_dist / initial_risk_dist
                latched_level3 = locked_r >= (lock2_gain_r - 0.02)
                dt_ny = dt.astimezone(ZoneInfo("America/New_York"))
                ny_mins = dt_ny.hour * 60 + dt_ny.minute
                is_prerollover = (16 * 60 + 30) <= ny_mins <= (16 * 60 + 59)

                target_sl = None
                step_note = ""
                if is_prerollover and (latched_level3 or current_r >= 1.50) and current_r > (preroll_gain_r + 0.08):
                    off = initial_risk_dist * preroll_gain_r
                    target_sl = round(entry + off if side == "BUY" else entry - off, decimals)
                    step_note = f"ESCUDO_PRE_ROLLOVER (+{preroll_gain_r:.2f}R asegurado)"
                elif current_r >= lock2_trigger_r:
                    off = initial_risk_dist * lock2_gain_r
                    target_sl = round(entry + off if side == "BUY" else entry - off, decimals)
                    step_note = f"CANDADO_NIVEL_3 (+{lock2_gain_r:.2f}R asegurado)"
                elif current_r >= lock1_trigger_r:
                    off = initial_risk_dist * lock1_gain_r
                    target_sl = round(entry + off if side == "BUY" else entry - off, decimals)
                    step_note = f"CANDADO_NIVEL_2 (+{lock1_gain_r:.2f}R asegurado)"
                elif current_r >= be_trigger_r:
                    target_sl = round(entry + be_offset if side == "BUY" else entry - be_offset, decimals)
                    step_note = "BREAK_EVEN_1R_ACTIVADO"

                min_step = 1e-5 if decimals == 5 else (1e-3 if decimals == 3 else 0.01)
                if target_sl is not None:
                    is_better = (
                        (side == "BUY" and target_sl > (sl + min_step) and target_sl < mark)
                        or (side == "SELL" and target_sl < (sl - min_step) and target_sl > mark)
                    )
                    if is_better:
                        updated = self.db.update_trade_sl(
                            trade_id=int(tr["id"]),
                            new_sl=target_sl,
                            notes=step_note,
                            is_break_even=1,
                        )
                        if updated:
                            tr["stop_loss"] = target_sl
                            tr["is_break_even"] = 1
                            sl = target_sl
                            is_be = 1
                            self.db.log_event(
                                "BREAK_EVEN_1R",
                                rule_state.phase,
                                f"Trade #{tr['id']} ({tr['symbol']} {side}): Blindado con {step_note} @ {target_sl} (+{current_r:.2f}R alcanzado). Riesgo actual: $0.00",
                            )
                            self.notifier.notify_break_even(
                                trade_id=int(tr["id"]),
                                symbol=tr["symbol"],
                                side=side,
                                entry_price=entry,
                                new_sl=target_sl,
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

        # Determinar lista de símbolos a evaluar: Portafolio Oficial Exclusivo (Oro, EUR/USD, S&P 500)
        if "," in self.symbol:
            symbols_to_run = [s.strip() for s in self.symbol.split(",") if s.strip()]
        elif self.symbol.upper() in ("MULTI", "PORTFOLIO", "PORTFOLIO_TRIO", "TRIO", "PORTFOLIO_DUAL", "SP500_EURUSD", "DEFAULT", "ALL"):
            symbols_to_run = ["GC=F", "EURUSD=X", "ES=F"]
        elif self.symbol.upper() in ("COMBO_TRIO", "COMBO"):
            symbols_to_run = ["GC=F", "EURUSD=X", "ES=F"]
        else:
            symbols_to_run = [self.symbol]

        last_signal = None
        has_holding_open = False
        skipped_session_reasons = []

        for sym in symbols_to_run:
            # 0. Escudo Anti-Fakeouts Cuarentena 48H
            try:
                q_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quarantine_status.json")
                if os.path.exists(q_file):
                    with open(q_file, "r", encoding="utf-8") as f_q:
                        q_data = json.load(f_q)
                        clean_check = sym.replace("=F", "").replace("=X", "").replace(".cash", "").replace(".m", "")
                        q_asset = q_data.get("assets", {}).get(clean_check) or q_data.get("assets", {}).get(sym)
                        if q_asset and q_asset.get("in_quarantine"):
                            rem_h = q_asset.get("hours_remaining", 48.0)
                            skipped_session_reasons.append(f"{sym}: 🔒 ESCUDO CUARENTENA 48H ACTIVO ({rem_h}h restantes por falsos rompimientos)")
                            continue
            except Exception:
                pass

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
            df_15m = self.connector.fetch_ohlcv_15m(symbol=sym, provider=prov, limit=96, allow_synthetic=False)
            df_1h = self.connector.fetch_ohlcv_1h(symbol=sym, provider=prov, limit=200, allow_synthetic=False)

            if df_15m.empty:
                if len(symbols_to_run) > 1:
                    skipped_session_reasons.append(f"{sym}: Feed de mercado en vivo inaccesible ({prov})")
                    continue
                return {
                    "timestamp": dt.isoformat(),
                    "action": "DATA_FEED_ERROR",
                    "rule_status": rule_status,
                    "closed_positions": closed_positions,
                    "open_positions": open_positions,
                    "message": f"Feed de mercado en vivo inaccesible para {sym} ({prov}). Ciclo pausado para proteger la cuenta.",
                }

            if df_15m.attrs.get("is_synthetic", False) and not ignore_session_filter:
                return {
                    "timestamp": dt.isoformat(),
                    "action": "DATA_FEED_FALLBACK_ALERT",
                    "rule_status": rule_status,
                    "closed_positions": closed_positions,
                    "open_positions": open_positions,
                    "message": (
                        f"[ALERTA CRÍTICA] Datos en vivo inaccesibles para {sym}. "
                        f"Operativa bloqueada para proteger la cuenta contra datos sintéticos."
                    ),
                }

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

            # 4.5 Regla Anti-Persecución Institucional (1 Disparo por Vela ORB por Activo):
            # Si el activo ya registró una operación en esta misma ventana ORB (ej. '2026-11-04 03:00 EST' o '08:30 EST')
            # con ganancia/Break-Even (o ya acumuló 1 intento en la misma ventana), no volver a re-entrar tarde en la misma ola.
            if not force_signal_side:
                acc_chk = self.db.get_account_state()
                t_date_chk = str(acc_chk.get("current_trading_day", dt.strftime("%Y-%m-%d")))
                all_today_sym = [
                    t for t in self.db.get_trades_by_date(t_date_chk)
                    if t.get("symbol") == sym
                ]
                orb_tag = ""
                for tag_cand in ("03:00 EST", "08:30 EST", "09:30 EST"):
                    if tag_cand in signal.reason:
                        orb_tag = tag_cand
                        break
                if orb_tag:
                    same_orb_trades = [t for t in all_today_sym if orb_tag in str(t.get("notes", ""))]
                    already_won_orb = any(float(t.get("pnl", 0.0)) > 0 or int(t.get("is_break_even", 0)) == 1 for t in same_orb_trades)
                    if already_won_orb or len(same_orb_trades) >= 1:
                        skipped_session_reasons.append(
                            f"{sym}: Ventana ORB ({orb_tag}) ya procesada hoy ({len(same_orb_trades)} trade previo). Evitando re-entrada tardía."
                        )
                        continue

                # Debounce / Cooldown de Seguridad: Evitar re-intentos continuos si se ejecutó un trade hace menos de 5 min
                recent_attempts = [
                    t for t in all_today_sym
                    if t.get("opened_at") and abs((dt - datetime.fromisoformat(str(t["opened_at"]).replace("Z", "+00:00"))).total_seconds()) < 300
                ]
                if recent_attempts:
                    skipped_session_reasons.append(
                        f"{sym}: Debounce activo (trade #{recent_attempts[-1]['id']} ejecutado hace <5 min). Esperando estabilización."
                    )
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

            # 5.1 Regla Oficial FundedNext (1.png): Max Risk 3% At Any Time
            current_open_risk = self.risk.calculate_current_open_risk()
            max_allowed_risk = float(acc.get("initial_balance", rule_status.balance)) * self.risk.MAX_OPEN_RISK_EXPOSURE_PCT
            if (current_open_risk + sizing.risk_amount_usd) > (max_allowed_risk + 1e-4):
                skip_msg = (
                    f"REGLA FUNDEDNEXT MAX RISK 3% AT ANY TIME: Riesgo abierto simultáneo (${current_open_risk:,.2f}) "
                    f"+ nuevo trade (${sizing.risk_amount_usd:,.2f}) = ${current_open_risk + sizing.risk_amount_usd:,.2f}, "
                    f"supera el límite oficial de 3.0% (${max_allowed_risk:,.2f}). Operación omitida."
                )
                self.db.log_event("MAX_RISK_3PCT_BLOCKED", rule_status.phase, skip_msg)
                return {
                    "timestamp": dt.isoformat(),
                    "action": "SKIPPED_MAX_RISK_3PCT",
                    "rule_status": rule_status,
                    "risk_check": pre_trade,
                    "closed_positions": closed_positions,
                    "open_positions": open_positions,
                    "message": skip_msg,
                }

            is_news = self.rules.is_high_impact_news_window(dt)
            if not is_safety_day_pass:
                sym_up = sym.upper()
                if any(k in sym_up for k in ("ES", "500", "SPX")):
                    strat_tag = "SP500_ORB_15M"
                elif any(k in sym_up for k in ("EUR", "EURUSD")):
                    strat_tag = "EURUSD_ORB_15M"
                elif any(k in sym_up for k in ("JPY", "USDJPY")):
                    strat_tag = "USDJPY_ORB_15M"
                elif any(k in sym_up for k in ("AUD", "AUDUSD")):
                    strat_tag = "AUDUSD_ORB_15M"
                elif any(k in sym_up for k in ("NQ", "100", "NAS")):
                    strat_tag = "NAS100_ORB_15M"
                elif sym in ("GC=F", "XAUUSD", "GOLD") or self.risk.session_mode == "NY_OPEN":
                    strat_tag = "NY_ORB_15M"
                elif self.risk.session_mode in ("LONDON_OPEN", "LONDON"):
                    strat_tag = "LONDON_ORB_15M"
                elif self.risk.session_mode in ("COMBO_DUAL", "NY_LONDON"):
                    strat_tag = "COMBO_DUAL_ORB"
                elif self.risk.session_mode == "COMBO_TRIO":
                    strat_tag = "COMBO_TRIO_ORB"
                elif self.risk.session_mode in ("ALL", "CRYPTO_24H"):
                    strat_tag = "CRYPTO_ORB_15M"
                else:
                    strat_tag = "ORB_15M"

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
                "data_source": getattr(df_15m, "attrs", {}).get("data_source", "LIVE"),
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
            "data_source": getattr(df_15m, "attrs", {}).get("data_source", "LIVE") if "df_15m" in locals() and df_15m is not None else "LIVE",
            "rule_status": rule_status,
            "risk_check": pre_trade,
            "closed_positions": closed_positions,
            "open_positions": open_positions,
            "message": last_signal.reason if last_signal else "Sin señal de ruptura en la ventana actual.",
        }
