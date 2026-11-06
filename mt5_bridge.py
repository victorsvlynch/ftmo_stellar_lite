"""
mt5_bridge.py - Puente Institucional de Conexión Directa entre Python y MetaTrader 5 (MT5).
Diseñado para la Estrategia Ganadora NY_OPEN (Oro / XAUUSD) bajo reglas FundedNext Stellar Lite ($5K).

Funcionalidades:
1. Conexión automática con la terminal MT5 de escritorio (Windows).
2. Detección automática del símbolo de Oro del broker (XAUUSD, XAUUSD.m, GOLD, etc.).
3. Extracción de velas de 15m y 1H con spreads y ticks reales del broker en tiempo real.
4. Ejecución de órdenes de mercado DEAL con Stop Loss, Take Profit (R:R 1:2) y Magic Number institucional.
5. Gestión de Break-Even dinámico y cierre forzoso por gestión de riesgo.
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Tuple, Any, List
import pandas as pd
import numpy as np

logger = logging.getLogger("MT5Bridge")

try:
    from zoneinfo import ZoneInfo
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        import pytz

        def ZoneInfo(key: str):
            return pytz.timezone(key)


def find_mt5_terminal_path() -> Optional[str]:
    """Localiza automáticamente la ruta del ejecutable terminal64.exe en Windows."""
    # 1. Comprobar si hay un proceso terminal64 en ejecución
    try:
        import subprocess
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path -First 1"],
            text=True,
            timeout=3,
        ).strip()
        if out and os.path.exists(out):
            return out
    except Exception:
        pass

    # 2. Rutas estándar conocidas
    common_paths = [
        r"C:\Program Files\MetaTrader 5\terminal64.exe",
        r"C:\Program Files\FundedNext MetaTrader 5\terminal64.exe",
        r"C:\Program Files (x86)\MetaTrader 5\terminal.exe",
        os.path.expandvars(r"%APPDATA%\MetaQuotes\Terminal\terminal64.exe"),
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    return None


class MT5Bridge:
    """Controlador de bajo nivel para MetaTrader 5 vía Python IPC."""

    MAGIC_NUMBER = 505001  # Magic Number único para identificar operaciones del algoritmo

    def __init__(self, terminal_path: Optional[str] = None) -> None:
        self.terminal_path = terminal_path or find_mt5_terminal_path()
        self._mt5 = None
        self.connected = False
        self.account_info = None

    def _ensure_mt5_module(self):
        """Verifica la presencia del módulo oficial de MetaTrader 5."""
        if self._mt5 is not None:
            return self._mt5
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
            return self._mt5
        except ImportError:
            raise ImportError(
                "El paquete oficial 'MetaTrader5' no está instalado en este entorno de Python.\n"
                "Para instalarlo, ejecuta en tu terminal:\n"
                "    pip install MetaTrader5"
            )

    def initialize(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
    ) -> bool:
        """
        Inicia la conexión con el terminal MetaTrader 5 en ejecución o lo abre automáticamente.
        Si se proporcionan credenciales, autentica en la cuenta demo/real especificada.
        """
        mt5 = self._ensure_mt5_module()

        init_kwargs: Dict[str, Any] = {}
        if self.terminal_path and os.path.exists(self.terminal_path):
            init_kwargs["path"] = self.terminal_path

        # 1. Inicializar comunicación con MT5 (reintentar con o sin path si es necesario)
        success = mt5.initialize(**init_kwargs)
        if not success:
            if "path" in init_kwargs:
                success = mt5.initialize()
            elif self.terminal_path and os.path.exists(self.terminal_path):
                success = mt5.initialize(path=self.terminal_path)

        if not success:
            err_code, err_msg = mt5.last_error()
            print(f"[ERROR MT5] Fallo al inicializar terminal: {err_code} - {err_msg}")
            return False

        # 2. Si se pasan credenciales de login, autenticar en el servidor
        if login and password and server:
            authorized = mt5.login(login=int(login), password=str(password), server=str(server))
            if not authorized:
                err_code, err_msg = mt5.last_error()
                print(f"[ERROR MT5] Fallo al iniciar sesión con cuenta {login} en servidor '{server}': {err_code} - {err_msg}")
                mt5.shutdown()
                return False

        # 3. Obtener información de la cuenta
        acc = mt5.account_info()
        if acc is None:
            err_code, err_msg = mt5.last_error()
            print(f"[ERROR MT5] No se pudo leer la información de cuenta: {err_code} - {err_msg}")
            mt5.shutdown()
            return False

        self.account_info = acc._asdict()
        self.connected = True

        # Sincronizar automáticamente especificaciones reales del broker con RiskManager
        try:
            self.sync_specs_to_risk_manager()
        except Exception:
            pass

        return True

    def sync_specs_to_risk_manager(self) -> Dict[str, Dict[str, float]]:
        """
        Lee dinámicamente las especificaciones de contrato de los activos principales
        directamente desde MT5 y las registra en RiskManager.
        """
        from risk_manager import RiskManager
        synced = {}
        for generic in ("XAUUSD", "XAGUSD", "US30", "US500", "USDJPY", "EURUSD", "AUDUSD"):
            real_sym = self.detect_broker_symbol(generic)
            spec = self.get_symbol_specification(real_sym)
            if spec:
                pip_size = float(spec["point"]) * (10.0 if spec.get("digits", 2) in (3, 5) else 1.0)
                is_jpy = "JPY" in real_sym.upper() or "JPY" in generic.upper()
                base_cs = float(spec.get("trade_contract_size", 1.0))
                tv = float(spec.get("trade_tick_value", 0.0))
                ts = float(spec.get("trade_tick_size", 0.0))
                eff_cs = round(tv / ts, 4) if (is_jpy and tv > 0 and ts > 0) else base_cs
                comm_val = 0.0 if any(k in real_sym for k in ("500", "30", "DJ")) else 5.0
                spec_dict = {
                    "contract_size": eff_cs,
                    "base_contract_size": base_cs,
                    "quote_is_jpy": is_jpy,
                    "pip_size": pip_size,
                    "min_lot": float(spec.get("volume_min", 0.01)),
                    "max_lot": float(spec.get("volume_max", 100.0)),
                    "lot_step": float(spec.get("volume_step", 0.01)),
                    "commission_per_lot": comm_val,
                    "typical_spread": float(spec.get("spread", 10)) * float(spec.get("point", 0.01)),
                }
                RiskManager.set_custom_instrument_spec(real_sym, spec_dict)
                RiskManager.set_custom_instrument_spec(generic, spec_dict)
                if generic == "US500":
                    RiskManager.set_custom_instrument_spec("ES=F", spec_dict)
                elif generic == "US30":
                    RiskManager.set_custom_instrument_spec("YM=F", spec_dict)
                    RiskManager.set_custom_instrument_spec("DJ30", spec_dict)
                    RiskManager.set_custom_instrument_spec("WS30", spec_dict)
                elif generic == "XAGUSD":
                    RiskManager.set_custom_instrument_spec("SI=F", spec_dict)
                    RiskManager.set_custom_instrument_spec("SILVER", spec_dict)
                elif generic == "EURUSD":
                    RiskManager.set_custom_instrument_spec("EURUSD=X", spec_dict)
                elif generic == "USDJPY":
                    RiskManager.set_custom_instrument_spec("USDJPY=X", spec_dict)
                elif generic == "AUDUSD":
                    RiskManager.set_custom_instrument_spec("AUDUSD=X", spec_dict)
                elif generic == "XAUUSD":
                    RiskManager.set_custom_instrument_spec("GC=F", spec_dict)
                synced[real_sym] = spec_dict
        return synced

    def get_account_summary(self) -> Dict[str, Any]:
        """Devuelve un resumen estructurado del balance, equidad, apalancamiento y servidor."""
        if not self.connected or not self.account_info:
            return {}
        mt5 = self._ensure_mt5_module()
        acc = mt5.account_info()
        term = mt5.terminal_info()
        if acc:
            self.account_info = acc._asdict()
        terminal_trade_allowed = bool(term.trade_allowed) if term else False
        return {
            "login": self.account_info.get("login"),
            "server": self.account_info.get("server"),
            "balance": float(self.account_info.get("balance", 0.0)),
            "equity": float(self.account_info.get("equity", 0.0)),
            "margin": float(self.account_info.get("margin", 0.0)),
            "free_margin": float(self.account_info.get("margin_free", 0.0)),
            "leverage": int(self.account_info.get("leverage", 100)),
            "currency": self.account_info.get("currency", "USD"),
            "trade_allowed": bool(self.account_info.get("trade_allowed", False)),
            "trade_expert": bool(self.account_info.get("trade_expert", False)),
            "terminal_trade_allowed": terminal_trade_allowed,
        }

    def detect_gold_symbol(self) -> str:
        """
        Detecta dinámicamente cómo nombra el broker el contrato de Oro Spot / CFDs.
        Variaciones comunes en FundedNext y brokers MT5: 'XAUUSD', 'XAUUSD.m', 'XAUUSD.raw', 'GOLD', 'GC=F'.
        """
        return self.detect_broker_symbol("XAUUSD")

    def detect_eurusd_symbol(self) -> str:
        """Detecta dinámicamente cómo nombra el broker el par EUR/USD."""
        return self.detect_broker_symbol("EURUSD")

    def detect_sp500_symbol(self) -> str:
        """Detecta dinámicamente cómo nombra el broker el índice S&P 500."""
        return self.detect_broker_symbol("US500")

    def detect_broker_symbol(self, requested_symbol: str) -> str:
        """
        Detecta inteligentemente la nomenclatura exacta del broker en MT5 para cualquier activo:
        Oro (XAUUSD), EUR/USD, S&P 500 (US500, SPX500) o Nasdaq 100 (US100, NAS100).
        """
        mt5 = self._ensure_mt5_module()
        clean = requested_symbol.upper().replace("=X", "").replace("=F", "").replace("/", "")

        # Bloqueo explícito de Nasdaq 100 (Inactivo por política de riesgo institucional)
        if any(k in clean for k in ("100", "NQ", "NAS", "USTEC")):
            logger.warning(f"Símbolo {requested_symbol} (Nasdaq 100) está INACTIVO por política de riesgo.")
            return None

        # 1. Definir lista de candidatos prioritarios según activo
        if any(k in clean for k in ("30", "DJ", "YM", "DOW", "WS30", "WALL")):
            candidates = ["US30", "US30.cash", "DJ30", "WS30", "USA30", "US30m", "US30.raw", "US30.pro", "YM"]
            match_keywords = ["US30", "DJ30", "WS30"]
            fallback = "US30"
        elif any(k in clean for k in ("500", "ES", "SPX")):
            candidates = ["US500", "US500.cash", "SPX500", "USA500", "US500m", "US500.raw", "US500.pro", "SP500", "ES"]
            match_keywords = ["US500", "SPX500", "SP500"]
            fallback = "US500"
        elif any(k in clean for k in ("XAG", "SILVER", "SI")):
            candidates = ["XAGUSD", "SILVER", "XAGUSD.m", "XAGUSDm", "XAGUSD.raw", "XAGUSD.pro", "XAGUSDb", "SI=F", "SI"]
            match_keywords = ["XAGUSD", "SILVER"]
            fallback = "XAGUSD"
        elif "EUR" in clean:
            candidates = ["EURUSD", "EURUSDm", "EURUSD.raw", "EURUSD.pro", "EURUSDb", "EURUSD.cash", "EURUSD+"]
            match_keywords = ["EURUSD"]
            fallback = "EURUSD"
        elif "JPY" in clean:
            candidates = ["USDJPY", "USDJPYm", "USDJPY.raw", "USDJPY.pro", "USDJPYb", "USDJPY.cash", "USDJPY+"]
            match_keywords = ["USDJPY"]
            fallback = "USDJPY"
        elif "AUD" in clean:
            candidates = ["AUDUSD", "AUDUSDm", "AUDUSD.raw", "AUDUSD.pro", "AUDUSDb", "AUDUSD.cash", "AUDUSD+"]
            match_keywords = ["AUDUSD"]
            fallback = "AUDUSD"
        else:
            candidates = ["XAUUSD", "GOLD", "XAUUSD.m", "XAUUSDm", "XAUUSD.raw", "XAUUSD.pro", "GC=F"]
            match_keywords = ["XAUUSD", "GOLD"]
            fallback = "XAUUSD"

        # 2. Probar candidatos típicos directos
        for cand in candidates:
            info = mt5.symbol_info(cand)
            if info is not None:
                if not info.visible:
                    mt5.symbol_select(cand, True)
                return cand

        # 3. Búsqueda por coincidencia en todos los símbolos del broker
        symbols = mt5.symbols_get()
        if symbols:
            for s in symbols:
                name_upper = s.name.upper()
                if any(kw in name_upper for kw in match_keywords):
                    if not s.visible:
                        mt5.symbol_select(s.name, True)
                    return s.name

        return fallback

    def get_symbol_specification(self, symbol: str) -> Dict[str, Any]:
        """Obtiene las especificaciones exactas del contrato en el broker MT5."""
        mt5 = self._ensure_mt5_module()
        info = mt5.symbol_info(symbol)
        if info is None:
            return {}
        return {
            "name": info.name,
            "digits": info.digits,
            "point": float(info.point),
            "spread": int(info.spread),
            "trade_contract_size": float(info.trade_contract_size),
            "volume_min": float(info.volume_min),
            "volume_max": float(info.volume_max),
            "volume_step": float(info.volume_step),
            "ask": float(info.ask),
            "bid": float(info.bid),
        }

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe_str: str = "15m",
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Descarga velas históricas en tiempo real directamente desde el servidor MT5 del broker.
        Devuelve DataFrame con índice datetime en zona America/New_York.
        """
        mt5 = self._ensure_mt5_module()
        tf_map = {
            "1m": mt5.TIMEFRAME_M1,
            "5m": mt5.TIMEFRAME_M5,
            "15m": mt5.TIMEFRAME_M15,
            "1h": mt5.TIMEFRAME_H1,
            "4h": mt5.TIMEFRAME_H4,
            "1d": mt5.TIMEFRAME_D1,
        }
        mt5_tf = tf_map.get(timeframe_str.lower(), mt5.TIMEFRAME_M15)

        # Descargar tarifas desde la posición 0 hacia atrás
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, limit)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        tz_ny = ZoneInfo("America/New_York")
        df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(tz_ny)
        df.set_index("datetime", inplace=True)
        df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "tick_volume": "Volume",
            },
            inplace=True,
        )
        return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)

    def send_market_order(
        self,
        symbol: str,
        side: str,
        lots: float,
        stop_loss: float,
        take_profit: float,
        comment: str = "FundedNext NY_ORB",
    ) -> Dict[str, Any]:
        """
        Envía una orden directa al mercado en MT5 con Stop Loss, Take Profit y Magic Number.
        Detecta automáticamente el tipo de filling aceptado por el broker (FOK, IOC, RETURN).
        """
        mt5 = self._ensure_mt5_module()

        term = mt5.terminal_info()
        if term and not term.trade_allowed:
            return {
                "success": False,
                "retcode": 10027,
                "error": "El botón 'Trading Algorítmico' (Algo Trading) está apagado en tu terminal MT5. Presiona Ctrl + E en MetaTrader 5 para activarlo (el botón debe estar en verde con el icono de Play).",
            }

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return {"success": False, "error": f"Símbolo {symbol} no encontrado en MT5"}

        if not symbol_info.visible:
            mt5.symbol_select(symbol, True)

        order_side = side.upper().strip()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"success": False, "error": f"No se pudo obtener el tick actual de {symbol}"}

        price = tick.ask if order_side == "BUY" else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if order_side == "BUY" else mt5.ORDER_TYPE_SELL

        # Normalizar lotaje según las reglas del broker (min, max, step)
        vol_step = symbol_info.volume_step
        norm_lots = round(round(lots / vol_step) * vol_step, 2)
        norm_lots = max(symbol_info.volume_min, min(symbol_info.volume_max, norm_lots))

        # Validar y blindar coherencia de Stop Loss y Take Profit frente al precio de ejecución
        sl_val = float(round(stop_loss, symbol_info.digits)) if stop_loss > 0 else 0.0
        tp_val = float(round(take_profit, symbol_info.digits)) if take_profit > 0 else 0.0

        if order_side == "BUY":
            if sl_val >= price or sl_val == 0.0:
                sl_val = round(price - 6.50, symbol_info.digits)
            if tp_val <= price or tp_val == 0.0:
                tp_val = round(price + 13.00, symbol_info.digits)
        else:  # SELL
            if sl_val <= price or sl_val == 0.0:
                sl_val = round(price + 6.50, symbol_info.digits)
            if tp_val >= price or tp_val == 0.0:
                tp_val = round(price - 13.00, symbol_info.digits)

        # Probar modos de filling con auto-fallback inteligente (FOK -> IOC -> RETURN)
        filling_candidates = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]

        result = None
        for fill_mode in filling_candidates:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(norm_lots),
                "type": order_type,
                "price": float(round(price, symbol_info.digits)),
                "sl": sl_val,
                "tp": tp_val,
                "deviation": 50,
                "magic": self.MAGIC_NUMBER,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": fill_mode,
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                result = res
                break
            result = res

        if result is None:
            err_code, err_msg = mt5.last_error()
            return {"success": False, "error": f"order_send retornó None: {err_code} - {err_msg}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "retcode": result.retcode,
                "comment": result.comment,
                "error": f"Rechazo del Broker MT5 (Retcode {result.retcode}): {result.comment}",
            }

        return {
            "success": True,
            "order_ticket": result.order,
            "deal_ticket": result.deal,
            "volume": result.volume,
            "price": result.price,
            "sl": stop_loss,
            "tp": take_profit,
            "comment": result.comment,
        }

    def modify_sl_tp(
        self,
        position_ticket: int,
        new_sl: float,
        new_tp: Optional[float] = None,
        symbol: Optional[str] = None,
    ) -> bool:
        """Modifica el Stop Loss de una posición abierta en MT5 (Break-Even a +1R)."""
        mt5 = self._ensure_mt5_module()
        pos = None
        for p in mt5.positions_get():
            if p.ticket == position_ticket:
                pos = p
                break

        if pos is None:
            return False

        sym = symbol or pos.symbol
        sym_info = mt5.symbol_info(sym)
        digits = sym_info.digits if sym_info else 2
        used_tp = new_tp if new_tp is not None else pos.tp

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": position_ticket,
            "symbol": sym,
            "sl": float(round(new_sl, digits)),
            "tp": float(round(used_tp, digits)),
        }
        res = mt5.order_send(request)
        return res is not None and res.retcode == mt5.TRADE_RETCODE_DONE

    def close_position(self, position_ticket: int) -> bool:
        """Cierra inmediatamente una posición abierta en MT5 a precio de mercado."""
        mt5 = self._ensure_mt5_module()
        pos = None
        for p in mt5.positions_get():
            if p.ticket == position_ticket:
                pos = p
                break
        if pos is None:
            return False

        sym_info = mt5.symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        filling_candidates = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
        for fill_mode in filling_candidates:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "price": float(round(price, sym_info.digits)),
                "deviation": 50,
                "magic": self.MAGIC_NUMBER,
                "comment": "Cierre Algorítmico FundedNext",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": fill_mode,
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                return True

        return False

    def get_open_positions(self, magic: Optional[int] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Devuelve todas las posiciones abiertas actualmente en MT5 con datos institucionales."""
        if not self.connected:
            return []
        mt5 = self._ensure_mt5_module()
        raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if raw is None:
            return []
        result = []
        for p in raw:
            if magic is not None and int(p.magic) != int(magic):
                continue
            result.append({
                "ticket": int(p.ticket),
                "symbol": str(p.symbol),
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": float(p.volume),
                "price_open": float(p.price_open),
                "price_current": float(p.price_current),
                "sl": float(p.sl),
                "tp": float(p.tp),
                "profit": float(p.profit),
                "swap": float(p.swap),
                "magic": int(p.magic),
                "comment": str(p.comment),
                "time": datetime.fromtimestamp(p.time, timezone.utc).isoformat(),
            })
        return result

    def get_closed_deals(
        self,
        days: int = 7,
        magic: Optional[int] = None,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extrae el historial de deals de salida (cierre de operaciones) desde MT5.
        Incluye ticket de deal, position_id, precio exacto, swap, comisión y PnL neto del broker.
        """
        if not self.connected:
            return []
        mt5 = self._ensure_mt5_module()
        from_date = datetime.now(timezone.utc) - timedelta(days=days)
        to_date = datetime.now(timezone.utc) + timedelta(minutes=10)
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            return []

        result = []
        for d in deals:
            # DEAL_ENTRY_OUT (1) indica salida/cierre de posición
            if d.entry != mt5.DEAL_ENTRY_OUT:
                continue
            if magic is not None and int(d.magic) != int(magic):
                continue
            if symbol and str(d.symbol).upper() != str(symbol).upper():
                continue

            net_pnl = round(float(d.profit) + float(d.swap) + float(d.commission) + float(d.fee), 2)
            result.append({
                "ticket": int(d.ticket),
                "order": int(d.order),
                "position_id": int(d.position_id),
                "symbol": str(d.symbol),
                "type": "SELL" if d.type == mt5.DEAL_TYPE_SELL else "BUY",
                "volume": float(d.volume),
                "price": float(d.price),
                "profit": round(float(d.profit), 2),
                "swap": round(float(d.swap), 2),
                "commission": round(abs(float(d.commission)) + abs(float(d.fee)), 2),
                "net_pnl": net_pnl,
                "magic": int(d.magic),
                "comment": str(d.comment),
                "time": datetime.fromtimestamp(d.time, timezone.utc).isoformat(),
            })
        return result

    def reconcile_with_database(
        self,
        db: Any,
        magic: Optional[int] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Motor Maestro de Reconciliación: Sincroniza la base de datos SQLite con los datos
        fidedignos y oficiales de MetaTrader 5 (MT5 como Única Fuente de Verdad).
        
        Acciones automáticas:
        1. Actualiza balance y equidad de account_state al centavo exacto con MT5.
        2. Cierra posiciones que figuren OPEN en SQLite pero ya fueron cerradas en MT5 (por SL/TP del broker).
        3. Corrige PnL, precio de salida, swaps y comisiones de trades cerrados en SQLite con los deals reales.
        4. Detecta y aísla operaciones 'fantasma' que nunca se ejecutaron en la cuenta real del broker.
        5. Actualiza High Water Mark y pisos de Trailing Drawdown con el saldo real.
        """
        if not self.connected:
            if not self.initialize():
                return {"success": False, "reason": "No se pudo conectar al terminal MT5"}

        acc_summary = self.get_account_summary()
        real_balance = float(acc_summary.get("balance", 0.0))
        real_equity = float(acc_summary.get("equity", 0.0))
        login = acc_summary.get("login")
        server = acc_summary.get("server")

        if real_balance <= 0:
            return {"success": False, "reason": "Balance inválido retornado por MT5"}

        open_positions = self.get_open_positions(magic=magic)
        open_pos_map = {p["ticket"]: p for p in open_positions}
        closed_deals = self.get_closed_deals(days=lookback_days, magic=magic)
        deals_by_pos = {d["position_id"]: d for d in closed_deals}

        reconciled_trades = []
        closed_from_mt5 = []
        corrections = []

        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()

        with db._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Reconciliar posiciones que SQLite tiene marcadas como OPEN
            cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
            open_sqlite = [dict(r) for r in cursor.fetchall()]

            for tr in open_sqlite:
                tr_id = tr["id"]
                tr_ticket = tr.get("mt5_ticket", 0)

                # Caso 1.A: Posición sigue abierta en MT5
                if tr_ticket and tr_ticket in open_pos_map:
                    pos = open_pos_map[tr_ticket]
                    cursor.execute(
                        "UPDATE trades SET stop_loss = ?, take_profit = ? WHERE id = ?",
                        (pos["sl"], pos["tp"], tr_id),
                    )
                    continue

                # Caso 1.B: Posición NO está abierta en MT5 -> Buscar deal de cierre en MT5
                matched_deal = None
                if tr_ticket and tr_ticket in deals_by_pos:
                    matched_deal = deals_by_pos[tr_ticket]
                else:
                    clean_sym = tr["symbol"].replace("=X", "").replace("=F", "").replace("GC", "XAUUSD")
                    for d in closed_deals:
                        if clean_sym in d["symbol"] or d["symbol"] in clean_sym:
                            if abs(d["volume"] - float(tr["lots"])) < 0.01:
                                matched_deal = d
                                break

                if matched_deal:
                    net_pnl = matched_deal["net_pnl"]
                    gross_pnl = matched_deal["profit"]
                    comm = matched_deal["commission"]
                    swap = matched_deal["swap"]
                    exit_p = matched_deal["price"]
                    dt_closed = matched_deal["time"]
                    notes = f"{tr.get('notes', '')} | SYNC_MT5_CLOSED_DEAL #{matched_deal['ticket']} ({matched_deal['comment']})".strip(" |")

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
                            notes = ?
                        WHERE id = ?
                        """,
                        (exit_p, net_pnl, gross_pnl, comm, swap, dt_closed, matched_deal["position_id"], matched_deal["ticket"], notes, tr_id),
                    )
                    closed_from_mt5.append({
                        "trade_id": tr_id,
                        "symbol": tr["symbol"],
                        "ticket": matched_deal["ticket"],
                        "exit_price": exit_p,
                        "net_pnl": net_pnl,
                        "swap": swap,
                        "commission": comm,
                    })
                else:
                    cursor.execute(
                        """
                        UPDATE trades
                        SET status = 'EXPIRED_MT5_UNCONFIRMED',
                            pnl = 0.0,
                            notes = notes || ' | NO_EJECUTADA_EN_MT5'
                        WHERE id = ?
                        """,
                        (tr_id,),
                    )

            # 2. Reconciliar trades cerrados en SQLite: asegurar que coincidan al centavo con MT5 deals
            cursor.execute("SELECT * FROM trades WHERE status = 'CLOSED' ORDER BY id DESC LIMIT 50")
            closed_sqlite = [dict(r) for r in cursor.fetchall()]

            for tr in closed_sqlite:
                tr_id = tr["id"]
                tr_ticket = tr.get("mt5_ticket", 0)
                matched_deal = None
                if tr_ticket and tr_ticket in deals_by_pos:
                    matched_deal = deals_by_pos[tr_ticket]
                else:
                    clean_sym = tr["symbol"].replace("=X", "").replace("=F", "").replace("GC", "XAUUSD")
                    for d in closed_deals:
                        if (clean_sym in d["symbol"] or d["symbol"] in clean_sym) and abs(d["volume"] - float(tr["lots"])) < 0.01:
                            if abs(float(tr.get("exit_price", 0.0) or 0.0) - d["price"]) < 2.0 or abs(float(tr.get("pnl", 0.0) or 0.0) - d["net_pnl"]) < 25.0:
                                matched_deal = d
                                break

                if matched_deal:
                    cur_pnl = float(tr.get("pnl", 0.0) or 0.0)
                    cur_exit = float(tr.get("exit_price", 0.0) or 0.0)
                    diff_pnl = abs(cur_pnl - matched_deal["net_pnl"])
                    diff_exit = abs(cur_exit - matched_deal["price"])
                    if diff_pnl > 0.01 or diff_exit > 0.001 or float(tr.get("swap", 0.0) or 0.0) != matched_deal["swap"]:
                        old_pnl = cur_pnl
                        new_pnl = matched_deal["net_pnl"]
                        cursor.execute(
                            """
                            UPDATE trades
                            SET exit_price = ?,
                                pnl = ?,
                                gross_pnl = ?,
                                commission = ?,
                                swap = ?,
                                spread_cost = 0.0,
                                mt5_ticket = ?,
                                mt5_deal_ticket = ?,
                                notes = notes || ' | RECONCILIADO_MT5_CENTAVOS'
                            WHERE id = ?
                            """,
                            (matched_deal["price"], new_pnl, matched_deal["profit"], matched_deal["commission"], matched_deal["swap"], matched_deal["position_id"], matched_deal["ticket"], tr_id),
                        )
                        corrections.append({
                            "trade_id": tr_id,
                            "symbol": tr["symbol"],
                            "old_pnl": old_pnl,
                            "real_mt5_pnl": new_pnl,
                            "real_exit_price": matched_deal["price"],
                            "swap": matched_deal["swap"],
                            "diff": round(new_pnl - old_pnl, 2),
                        })

            # 3. Actualizar account_state de SQLite con el saldo y equidad real de MT5
            cursor.execute("SELECT initial_balance, high_water_mark, max_drawdown_limit_pct, drawdown_type FROM account_state WHERE id = 1")
            acc_row = cursor.fetchone()
            init_b = float(acc_row["initial_balance"]) if acc_row else 10000.0
            cur_hwm = float(acc_row["high_water_mark"]) if acc_row and acc_row["high_water_mark"] else real_balance
            new_hwm = round(max(cur_hwm, real_balance), 2)

            is_trailing = bool(acc_row and (acc_row["drawdown_type"] or "").upper() == "TRAILING")
            max_dd_pct = float(acc_row["max_drawdown_limit_pct"]) if acc_row else 0.08
            trailing_floor = round(new_hwm - (init_b * max_dd_pct), 2) if is_trailing else 0.0

            cursor.execute(
                """
                UPDATE account_state
                SET balance = ?,
                    equity = ?,
                    high_water_mark = ?,
                    trailing_max_loss_floor = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (real_balance, real_equity, new_hwm, trailing_floor, now_iso),
            )
            conn.commit()

        audit_msg = (
            f"Sincronización profesional MT5 #{login} ({server}): Balance ${real_balance:,.2f}, Equidad ${real_equity:,.2f}. "
            f"Trades cerrados MT5: {len(closed_from_mt5)}, Correcciones PnL: {len(corrections)}."
        )
        db.log_event("SINCRONIZACION_AUTOMATICA_MT5", "ALL", audit_msg)
        logger.info(audit_msg)

        return {
            "success": True,
            "login": login,
            "server": server,
            "balance": real_balance,
            "equity": real_equity,
            "open_positions_mt5": len(open_positions),
            "closed_from_mt5": closed_from_mt5,
            "corrections": corrections,
            "high_water_mark": new_hwm,
            "trailing_max_loss_floor": trailing_floor,
        }

    def shutdown(self) -> None:
        """Cierra la conexión con el terminal MT5."""
        if self._mt5 and self.connected:
            self._mt5.shutdown()
            self.connected = False
