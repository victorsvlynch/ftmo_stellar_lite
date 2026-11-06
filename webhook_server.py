"""
webhook_server.py - Servidor HTTP de Señales y Webhooks para MetaTrader 5 (MT5).
FundedNext Stellar Lite ($10,000) - Estrategia Ganadora: NY_OPEN (Oro / XAUUSD).

Permite la OP despierta 24/7 en Oracle Cloud:
- El bot corre 24/7 en Linux analizando velas y gestionando riesgo.
- Este servidor HTTP expone endpoints ligeros para que un Expert Advisor (EA en MQL5)
  conectado a FundedNext reciba y ejecute órdenes instantáneamente en cualquier terminal MT5.
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

# Asegurar path local
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import TradingDatabase
from stellar_rules import StellarLiteRulesEngine
from risk_manager import RiskManager
from telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s UTC] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("StellarWebhookServer")

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trading_ny_open.db")
PORT = 8000
MAGIC_NUMBER = 505001

# Tabla para controlar qué acciones ya fueron despachadas y confirmadas por el EA
def init_webhook_tables(db_path: str = DB_FILE) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
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
    conn.commit()
    conn.close()


ACTION_TTL_SECONDS = 180.0  # Caducidad máxima de 3 minutos para evitar ráfagas de órdenes viejas tras reconectar el túnel


def get_pending_action(db_path: str = DB_FILE, magic: Optional[int] = None) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now_dt = datetime.now(timezone.utc)
    now_str = now_dt.isoformat()

    # 1. Expirar automáticamente acciones en cola que tengan más de 3 minutos (180s) de antigüedad
    cur.execute("SELECT id, action, trade_id, created_at FROM webhook_actions WHERE status = 'PENDING' ORDER BY id ASC")
    pending_rows = cur.fetchall()
    expired_any = False
    for r in pending_rows:
        try:
            c_dt = datetime.fromisoformat(r["created_at"])
            if c_dt.tzinfo is None:
                c_dt = c_dt.replace(tzinfo=timezone.utc)
            age_s = (now_dt - c_dt).total_seconds()
            if age_s > ACTION_TTL_SECONDS:
                cur.execute(
                    "UPDATE webhook_actions SET status = 'EXPIRED_STALE', executed_at = ? WHERE id = ?",
                    (now_str, r["id"]),
                )
                if r["action"] in ("OPEN_BUY", "OPEN_SELL") and r["trade_id"]:
                    cur.execute(
                        """
                        UPDATE trades
                        SET status = 'EXPIRED_OFFLINE', pnl = 0.0,
                            notes = notes || ' | EXPIRADA_POR_DESCONEXION_PUENTE (>180s)'
                        WHERE id = ? AND status = 'OPEN'
                        """,
                        (r["trade_id"],),
                    )
                expired_any = True
        except Exception:
            pass
    if expired_any:
        conn.commit()

    # 2. Retornar únicamente la primera acción fresca vigente (aislada por Magic Number si se especifica)
    if magic is not None and magic > 0:
        cur.execute(
            "SELECT * FROM webhook_actions WHERE status = 'PENDING' AND (magic = ? OR magic = 0) ORDER BY id ASC LIMIT 1",
            (magic,),
        )
    else:
        cur.execute(
            "SELECT * FROM webhook_actions WHERE status = 'PENDING' ORDER BY id ASC LIMIT 1"
        )
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def confirm_action(
    action_id: int,
    mt5_ticket: int,
    executed_price: float,
    status: str = "CONFIRMED",
    db_path: str = DB_FILE,
) -> bool:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    now_str = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        UPDATE webhook_actions
        SET status = ?, mt5_ticket = ?, executed_price = ?, executed_at = ?
        WHERE id = ?
        """,
        (status, mt5_ticket, executed_price, now_str, action_id),
    )
    affected = cur.rowcount

    # Si la orden era de apertura y MT5 no abrio ticket (rechazada u omitida por posicion previa)
    if mt5_ticket == 0:
        cur.execute("SELECT action, trade_id FROM webhook_actions WHERE id = ?", (action_id,))
        row = cur.fetchone()
        if row and row[0] in ("OPEN_BUY", "OPEN_SELL") and row[1]:
            cur.execute(
                """
                UPDATE trades
                SET status = 'REJECTED_MT5', pnl = 0.0, notes = notes || ' | RECHAZADA_O_OMITIDA_POR_MT5'
                WHERE id = ? AND status = 'OPEN'
                """,
                (row[1],),
            )
    elif mt5_ticket > 0:
        cur.execute(
            """
            UPDATE trades
            SET mt5_ticket = ?
            WHERE id = (SELECT trade_id FROM webhook_actions WHERE id = ?)
            """,
            (mt5_ticket, action_id),
        )

    conn.commit()
    conn.close()
    return affected > 0


def queue_action(
    action: str,
    symbol: str,
    lots: float,
    sl: float,
    tp: float,
    price: float = 0.0,
    trade_id: int = 0,
    comment: str = "FundedNext NY_ORB",
    db_path: str = DB_FILE,
    magic: int = MAGIC_NUMBER,
) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    now_str = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT INTO webhook_actions (
            action, trade_id, symbol, lots, price, sl, tp, magic, comment, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
        """,
        (action, trade_id, symbol, lots, price, sl, tp, magic, comment, now_str),
    )
    act_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Opción C: Alerta Instantánea a Telegram Móvil (@victorsvlynch)
    try:
        side = "BUY" if "BUY" in action.upper() else ("SELL" if "SELL" in action.upper() else "")
        if side:
            tg = TelegramNotifier()
            if tg.enabled:
                tg.notify_signal_alert(
                    symbol=symbol,
                    side=side,
                    lots=lots,
                    price=price,
                    sl=sl,
                    tp=tp,
                    risk_usd=25.0,
                    risk_pct=0.005,
                    strategy="NY_OPEN",
                    comment=comment,
                )
    except Exception as e:
        logger.warning(f"Aviso Telegram al encolar accion: {e}")

    return act_id


MT5_FEED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mt5_feed.json")
LATEST_MT5_FEED: Dict[str, Any] = {
    "updated_at": "",
    "symbols": {},
}


def update_live_ticks_from_query(qs: Dict[str, Any], now_utc: Optional[datetime] = None) -> None:
    dt = now_utc or datetime.now(timezone.utc)
    now_iso = dt.isoformat()
    symbols_data: Dict[str, Any] = {}

    def _parse_val(key: str) -> float:
        vals = qs.get(key, [])
        if vals:
            try:
                return float(vals[0])
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    # Oro / XAUUSD
    xau_bid = _parse_val("xau_bid")
    xau_ask = _parse_val("xau_ask")
    if xau_bid > 0 and xau_ask > 0:
        sp = round(xau_ask - xau_bid, 4)
        mid = round((xau_bid + xau_ask) / 2.0, 4)
        gold_item = {"symbol": "XAUUSD", "bid": xau_bid, "ask": xau_ask, "mid": mid, "spread": sp, "updated_at": now_iso}
        symbols_data["XAUUSD"] = gold_item
        symbols_data["GC=F"] = gold_item
        symbols_data["GOLD"] = gold_item

    # Plata / XAGUSD (Stellar Lite 10K)
    xag_bid = _parse_val("xag_bid")
    xag_ask = _parse_val("xag_ask")
    if xag_bid > 0 and xag_ask > 0:
        sp = round(xag_ask - xag_bid, 4)
        mid = round((xag_bid + xag_ask) / 2.0, 4)
        silver_item = {"symbol": "XAGUSD", "bid": xag_bid, "ask": xag_ask, "mid": mid, "spread": sp, "updated_at": now_iso}
        symbols_data["XAGUSD"] = silver_item
        symbols_data["SI=F"] = silver_item
        symbols_data["SILVER"] = silver_item

    # Dow Jones 30 / US30 (FTMO 10K Challenge)
    us30_bid = _parse_val("us30_bid")
    us30_ask = _parse_val("us30_ask")
    if us30_bid > 0 and us30_ask > 0:
        sp = round(us30_ask - us30_bid, 2)
        mid = round((us30_bid + us30_ask) / 2.0, 2)
        us30_item = {"symbol": "US30", "bid": us30_bid, "ask": us30_ask, "mid": mid, "spread": sp, "updated_at": now_iso}
        symbols_data["US30"] = us30_item
        symbols_data["YM=F"] = us30_item
        symbols_data["DJ30"] = us30_item

    # EUR/USD
    eur_bid = _parse_val("eur_bid")
    eur_ask = _parse_val("eur_ask")
    if eur_bid > 0 and eur_ask > 0:
        sp = round(eur_ask - eur_bid, 5)
        mid = round((eur_bid + eur_ask) / 2.0, 5)
        eur_item = {"symbol": "EURUSD", "bid": eur_bid, "ask": eur_ask, "mid": mid, "spread": sp, "updated_at": now_iso}
        symbols_data["EURUSD"] = eur_item
        symbols_data["EURUSD=X"] = eur_item

    # USD/JPY (Activo oficial #3 del portafolio NY Open)
    jpy_bid = _parse_val("jpy_bid")
    jpy_ask = _parse_val("jpy_ask")
    if jpy_bid > 0 and jpy_ask > 0:
        sp = round(jpy_ask - jpy_bid, 3)
        mid = round((jpy_bid + jpy_ask) / 2.0, 3)
        jpy_item = {"symbol": "USDJPY", "bid": jpy_bid, "ask": jpy_ask, "mid": mid, "spread": sp, "updated_at": now_iso}
        symbols_data["USDJPY"] = jpy_item
        symbols_data["USDJPY=X"] = jpy_item

    # AUD/USD (Guardado en Standby)
    aud_bid = _parse_val("aud_bid")
    aud_ask = _parse_val("aud_ask")
    if aud_bid > 0 and aud_ask > 0:
        sp = round(aud_ask - aud_bid, 5)
        mid = round((aud_bid + aud_ask) / 2.0, 5)
        aud_item = {"symbol": "AUDUSD", "bid": aud_bid, "ask": aud_ask, "mid": mid, "spread": sp, "updated_at": now_iso}
        symbols_data["AUDUSD"] = aud_item
        symbols_data["AUDUSD=X"] = aud_item

    # S&P 500 (Guardado en Standby para futura reactivación)
    sp_bid = _parse_val("sp_bid")
    sp_ask = _parse_val("sp_ask")
    if sp_bid > 0 and sp_ask > 0:
        sp = round(sp_ask - sp_bid, 2)
        mid = round((sp_bid + sp_ask) / 2.0, 2)
        sp_item = {"symbol": "US500", "bid": sp_bid, "ask": sp_ask, "mid": mid, "spread": sp, "updated_at": now_iso}
        symbols_data["US500"] = sp_item
        symbols_data["ES=F"] = sp_item
        symbols_data["SPX500"] = sp_item

    if symbols_data:
        global LATEST_MT5_FEED
        LATEST_MT5_FEED = {
            "updated_at": now_iso,
            "symbols": symbols_data,
        }
        try:
            tmp = MT5_FEED_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(LATEST_MT5_FEED, f)
            os.replace(tmp, MT5_FEED_FILE)
        except Exception as ex:
            logger.debug(f"Error escribiendo {MT5_FEED_FILE}: {ex}")


def get_current_mt5_feed(now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    dt = now_utc or datetime.now(timezone.utc)
    feed = dict(LATEST_MT5_FEED)
    if not feed.get("symbols") and os.path.exists(MT5_FEED_FILE):
        try:
            with open(MT5_FEED_FILE, "r", encoding="utf-8") as f:
                disk_feed = json.load(f)
                feed.update(disk_feed)
        except Exception:
            pass

    updated_at_str = feed.get("updated_at", "")
    age_s = 9999.0
    if updated_at_str:
        try:
            feed_dt = datetime.fromisoformat(updated_at_str)
            age_s = max(0.0, (dt - feed_dt).total_seconds())
        except Exception:
            pass

    return {
        "status": "ONLINE" if age_s < 30.0 else "STALE",
        "age_seconds": round(age_s, 2),
        "updated_at": updated_at_str,
        "symbols": feed.get("symbols", {}),
    }


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class WebhookRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Silenciar logs ruidosos de polling normal
        return

    def _set_json_headers(self, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_json_headers(200)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)
        now_utc = datetime.now(timezone.utc)
        now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Ingestar feed de ticks en tiempo real desde el EA de MT5
        if "feed" in qs or "xau_bid" in qs or "xag_bid" in qs or "us30_bid" in qs or "eur_bid" in qs or "jpy_bid" in qs or "aud_bid" in qs or "sp_bid" in qs:
            update_live_ticks_from_query(qs, now_utc)

        # Auto-sincronización instantánea de Balance y Equidad de MT5
        if "balance" in qs and "equity" in qs:
            try:
                bal = float(qs["balance"][0])
                eq = float(qs["equity"][0])
                if bal > 0:
                    db_sync = TradingDatabase(DB_FILE)
                    db_sync.update_account_state_from_mt5(balance=bal, equity=eq)
            except Exception as ex:
                logger.debug(f"Error procesando sync balance en GET: {ex}")

        # 0. Feed de Mercado en Tiempo Real para Sandbox y Motores de Trading
        if path == "/api/feed":
            feed = get_current_mt5_feed(now_utc)
            self._set_json_headers(200)
            self.wfile.write(json.dumps(feed).encode("utf-8"))
            return

        # 1. Chequeo de Salud / Ping
        if path == "/api/health" or path == "":
            payload = {
                "status": "ONLINE",
                "service": "FundedNext Stellar Lite - MT5 Webhook Bridge",
                "version": "2.0.0",
                "server_time": now_str,
                "strategy": "NY_OPEN",
                "asset": "XAUUSD (Oro)",
            }
            self._set_json_headers(200)
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        # 2. Polling de Señal de Trading para el EA de MT5
        if path == "/api/signal":
            req_magic = None
            if "magic" in qs:
                try:
                    req_magic = int(qs["magic"][0])
                except (ValueError, TypeError):
                    req_magic = None

            # Verificar si hay una acción en cola (filtrando por Magic Number de la terminal correspondiente)
            pending = get_pending_action(magic=req_magic)
            if pending:
                payload = {
                    "status": "OK",
                    "server_time": now_str,
                    "has_action": True,
                    "action_id": pending["id"],
                    "action": pending["action"],  # 'OPEN_BUY', 'OPEN_SELL', 'MODIFY_SL', 'CLOSE_ALL'
                    "trade_id": pending["trade_id"],
                    "symbol": pending["symbol"],
                    "lots": pending["lots"],
                    "price": pending["price"],
                    "sl": pending["sl"],
                    "tp": pending["tp"],
                    "magic": pending["magic"],
                    "comment": pending["comment"],
                }
                logger.info(f"Despachando accion #{pending['id']} ({pending['action']}) al EA de MT5")
            else:
                # Comprobar si hay trades abiertos en la BD para sincronizar
                db = TradingDatabase(DB_FILE)
                open_trades = db.get_open_trades()
                payload = {
                    "status": "OK",
                    "server_time": now_str,
                    "has_action": False,
                    "action": "NONE",
                    "open_trades_count": len(open_trades),
                    "message": "Sin acciones pendientes. Monitoreando mercado.",
                }

            self._set_json_headers(200)
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        # 3. Estado Financiero y Reglas FundedNext
        if path == "/api/status":
            db = TradingDatabase(DB_FILE)
            rules = StellarLiteRulesEngine(
                db=db,
                max_drawdown_limit_pct=0.08,
                min_trading_days=2,
                funded_profit_split=0.80,
            )
            state = rules.evaluate_account()
            acc = db.get_account_state()
            open_trades = db.get_open_trades()

            payload = {
                "server_time": now_str,
                "phase": state.phase,
                "status": state.status,
                "balance": state.balance,
                "equity": state.equity,
                "daily_loss_floor": state.daily_loss_floor,
                "daily_loss_margin": state.daily_loss_remaining,
                "max_drawdown_floor": state.max_loss_floor,
                "max_drawdown_margin": state.max_loss_remaining,
                "open_trades": len(open_trades),
                "profit_split": state.profit_split,
            }
            self._set_json_headers(200)
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        # Endpoint no encontrado
        self._set_json_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        now_utc = datetime.now(timezone.utc)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        try:
            data = json.loads(body)
        except Exception:
            data = {}

        # 0. Ingestar feed de ticks por POST JSON
        if path == "/api/feed":
            raw_syms = data.get("symbols", {})
            now_iso = now_utc.isoformat()
            if raw_syms:
                global LATEST_MT5_FEED
                parsed_syms = {}
                for k, v in raw_syms.items():
                    if isinstance(v, dict):
                        b = float(v.get("bid", 0.0))
                        a = float(v.get("ask", 0.0))
                        m = float(v.get("mid", (b + a) / 2.0 if (b and a) else 0.0))
                        sp = float(v.get("spread", a - b if (a and b) else 0.0))
                        item = {"symbol": k, "bid": b, "ask": a, "mid": m, "spread": sp, "updated_at": now_iso}
                        parsed_syms[k] = item
                if parsed_syms:
                    LATEST_MT5_FEED = {"updated_at": now_iso, "symbols": parsed_syms}
                    try:
                        tmp = MT5_FEED_FILE + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump(LATEST_MT5_FEED, f)
                        os.replace(tmp, MT5_FEED_FILE)
                    except Exception as ex:
                        logger.debug(f"Error escribiendo {MT5_FEED_FILE}: {ex}")
            self._set_json_headers(200)
            self.wfile.write(json.dumps({"status": "FEED_UPDATED", "symbols_count": len(raw_syms)}).encode("utf-8"))
            return

        # 1. Confirmación de Ejecución enviada por el EA de MT5
        if path == "/api/confirm":
            action_id = int(data.get("action_id", 0))
            mt5_ticket = int(data.get("ticket", data.get("mt5_ticket", 0)))
            fill_price = float(data.get("price", data.get("fill_price", 0.0)))
            success = bool(data.get("success", True))
            status_text = "CONFIRMED" if success else "REJECTED"

            if action_id > 0:
                confirm_action(action_id, mt5_ticket, fill_price, status=status_text)
                logger.info(
                    f"[CONFIRMACION MT5] Accion #{action_id} completada -> Ticket MT5: #{mt5_ticket} @ ${fill_price:,.2f}"
                )

            self._set_json_headers(200)
            self.wfile.write(json.dumps({"status": "ACK", "action_id": action_id}).encode("utf-8"))
            return

        # 2. Notificación en Tiempo Real de Cierre de Deal desde MT5 (SL/TP/Cierre Manual)
        if path == "/api/deal_closed":
            db_sync = TradingDatabase(DB_FILE)
            synced = db_sync.sync_deal_from_mt5(data)
            dt_deal = data.get("deal_ticket", data.get("ticket", 0))
            pnl_val = float(data.get("profit", 0.0)) + float(data.get("swap", 0.0)) + float(data.get("commission", 0.0))
            logger.info(
                f"[MT5 REAL DEAL] Deal #{dt_deal} ({data.get('symbol')}) procesado -> Net PnL: ${pnl_val:+,.2f} | Balance: ${float(data.get('balance', 0)):,.2f}"
            )
            self._set_json_headers(200)
            self.wfile.write(json.dumps({"status": "DEAL_SYNCED", "deal_ticket": dt_deal, "trade_matched": synced}).encode("utf-8"))
            return

        # 3. Sincronización Directa de Cuenta desde MT5
        if path == "/api/sync_account":
            bal = float(data.get("balance", 0.0))
            eq = float(data.get("equity", 0.0))
            if bal > 0:
                db_sync = TradingDatabase(DB_FILE)
                db_sync.update_account_state_from_mt5(balance=bal, equity=eq)
                logger.info(f"[MT5 ACCOUNT SYNC] Balance: ${bal:,.2f} | Equidad: ${eq:,.2f} sincronizados.")
                self._set_json_headers(200)
                self.wfile.write(json.dumps({"status": "ACCOUNT_SYNCED", "balance": bal, "equity": eq}).encode("utf-8"))
                return

        # 2. Endpoint de Prueba: Disparar micro-orden de test hacia MT5
        if path == "/api/test_order":
            symbol = data.get("symbol", "XAUUSD")
            lots = float(data.get("lots", 0.01))
            action = data.get("action", "OPEN_BUY")
            price = float(data.get("price", 4065.0))
            sl = float(data.get("sl", price - 6.50))
            tp = float(data.get("tp", price + 13.00))
            try:
                magic = int(data.get("magic", 505001))
            except (ValueError, TypeError):
                magic = 505001

            act_id = queue_action(
                action=action,
                symbol=symbol,
                lots=lots,
                price=price,
                sl=sl,
                tp=tp,
                comment=f"Prueba EA MT5 Magic {magic}",
                magic=magic,
            )
            logger.info(f"Micro-orden de prueba encolada #{act_id} ({action} {lots} lotes en {symbol} | Magic #{magic})")

            self._set_json_headers(200)
            self.wfile.write(
                json.dumps(
                    {
                        "status": "QUEUED",
                        "action_id": act_id,
                        "action": action,
                        "lots": lots,
                        "symbol": symbol,
                        "magic": magic,
                    }
                ).encode("utf-8")
            )
            return

        self._set_json_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))


def run_server(port: int = PORT) -> None:
    init_webhook_tables(DB_FILE)
    server_address = ("0.0.0.0", port)
    httpd = ThreadedHTTPServer(server_address, WebhookRequestHandler)
    logger.info("=" * 75)
    logger.info(f" SERVIDOR WEBHOOK MT5 ACTIVO EN PUERTO {port} (0.0.0.0:{port})")
    logger.info(" Estrategia: FundedNext Stellar Lite ($10,000) - NY_OPEN")
    logger.info(" Endpoints disponibles:")
    logger.info(f"  * GET  http://157.137.225.144:{port}/api/health")
    logger.info(f"  * GET  http://157.137.225.144:{port}/api/signal")
    logger.info(f"  * GET  http://157.137.225.144:{port}/api/status")
    logger.info(f"  * POST http://157.137.225.144:{port}/api/confirm")
    logger.info(f"  * POST http://157.137.225.144:{port}/api/test_order")
    logger.info("=" * 75)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Deteniendo servidor webhook...")
        httpd.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(port_arg)
