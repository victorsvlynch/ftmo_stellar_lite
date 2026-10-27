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
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple, Any
import pandas as pd
import numpy as np

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
        return True

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
        mt5 = self._ensure_mt5_module()
        candidates = ["XAUUSD", "XAUUSD.m", "XAUUSD.raw", "XAUUSD.pro", "GOLD", "GC=F"]

        # 1. Probar candidatos típicos
        for cand in candidates:
            info = mt5.symbol_info(cand)
            if info is not None:
                if not info.visible:
                    mt5.symbol_select(cand, True)
                return cand

        # 2. Búsqueda por coincidencia en todos los símbolos del broker
        symbols = mt5.symbols_get()
        if symbols:
            for s in symbols:
                name_upper = s.name.upper()
                if "XAU" in name_upper and "USD" in name_upper:
                    if not s.visible:
                        mt5.symbol_select(s.name, True)
                    return s.name
            for s in symbols:
                if s.name.upper() == "GOLD":
                    if not s.visible:
                        mt5.symbol_select(s.name, True)
                    return s.name

        return "XAUUSD"

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

    def shutdown(self) -> None:
        """Cierra la conexión con el terminal MT5."""
        if self._mt5 and self.connected:
            self._mt5.shutdown()
            self.connected = False
