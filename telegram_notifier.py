"""
telegram_notifier.py - Módulo de Notificaciones en Tiempo Real para Telegram.
Envía alertas inmediatas a tu teléfono móvil sobre:
- Apertura de operaciones (con SL, TP y riesgo)
- Cierre de operaciones (con PnL realizado y motivo)
- Activación de Break-Even (+1R protegido)
- Cierre forzoso de fin de semana (Viernes 15:30 EST)
- Alertas de riesgo (Pérdidas consecutivas, Freno al 2%, Hard Breach Warning)
- Ascensos de fase y cumplimiento de objetivos (Fase 1 +8%, Fase 2 +4%)
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class TelegramNotifier:
    """Gestor de notificaciones push vía Telegram Bot API (sin dependencias externas)."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

        # Si no están en env vars, intentar leer de telegram_config.json si existe
        if not self.bot_token or not self.chat_id:
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        self.bot_token = self.bot_token or cfg.get("bot_token", "").strip()
                        self.chat_id = self.chat_id or cfg.get("chat_id", "").strip()
                except Exception:
                    pass

        self.enabled = bool(self.bot_token and self.chat_id)

    def send_message(self, message: str) -> bool:
        """Envía un mensaje de texto formateado a Telegram."""
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception as e:
            # Nunca bloquear el ciclo del motor si falla la red
            print(f"[Telegram] Aviso: No se pudo enviar notificación: {e}")
            return False

    def notify_trade_opened(
        self,
        trade_id: int,
        symbol: str,
        side: str,
        lots: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        risk_usd: float,
        risk_pct: float,
        strategy: str,
        phase: str,
    ) -> bool:
        emoji = "🟢 BUY" if side.upper() == "BUY" else "🔴 SELL"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            f"<b>🚀 NUEVA OPERACIÓN ABIERTA #{trade_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Activo:</b> {symbol} | <b>Fase:</b> {phase}\n"
            f"<b>Orden:</b> {emoji} {lots:.4f} lotes\n"
            f"<b>Estrategia:</b> <code>{strategy}</code>\n"
            f"<b>Precio Entrada:</b> ${entry_price:,.4f}\n"
            f"<b>Stop Loss:</b> ${stop_loss:,.4f}\n"
            f"<b>Take Profit:</b> ${take_profit:,.4f} (R:R 1:2)\n"
            f"<b>Riesgo Inicial:</b> ${risk_usd:,.2f} ({risk_pct * 100:.2f}%)\n"
            f"<i>Hora: {now_str}</i>"
        )
        return self.send_message(msg)

    def notify_break_even(
        self,
        trade_id: int,
        symbol: str,
        side: str,
        entry_price: float,
        new_sl: float,
    ) -> bool:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            f"<b>🛡️ BREAK-EVEN ACTIVADO (+1R ALCANZADO)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Trade #{trade_id}:</b> {symbol} ({side})\n"
            f"<b>Entrada:</b> ${entry_price:,.4f}\n"
            f"<b>Nuevo Stop Loss:</b> ${new_sl:,.4f} (A precio de entrada)\n"
            f"<b>Riesgo actual:</b> $0.00 (Operación blindada sin riesgo)\n"
            f"<i>Hora: {now_str}</i>"
        )
        return self.send_message(msg)

    def notify_trade_closed(
        self,
        trade_id: int,
        symbol: str,
        side: str,
        lots: float,
        exit_price: float,
        gross_pnl: float,
        net_pnl: float,
        commission: float,
        reason: str,
        balance: float,
        equity: float,
    ) -> bool:
        is_win = net_pnl > 0
        emoji = "🏆 WIN" if is_win else ("❌ LOSS" if net_pnl < 0 else "⚪ BE")
        sign = "+" if net_pnl > 0 else ""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = (
            f"<b>{emoji} OPERACIÓN CERRADA #{trade_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Activo:</b> {symbol} ({side} {lots:.4f} lotes)\n"
            f"<b>Salida:</b> ${exit_price:,.4f} | <b>Motivo:</b> {reason}\n"
            f"<b>PnL Bruto:</b> ${gross_pnl:+,.2f}\n"
            f"<b>Comisión & Spread:</b> -${commission:,.2f}\n"
            f"<b>PnL Neto:</b> <b>{sign}${net_pnl:,.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Balance Actual:</b> ${balance:,.2f}\n"
            f"<b>Equidad Actual:</b> ${equity:,.2f}\n"
            f"<i>Hora: {now_str}</i>"
        )
        return self.send_message(msg)

    def notify_weekend_close(
        self,
        closed_count: int,
        realized_pnl: float,
    ) -> bool:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            f"<b>⚠️ CIERRE FORZOSO DE FIN DE SEMANA (VIERNES 15:30 EST)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Posiciones liquidadas:</b> {closed_count}\n"
            f"<b>PnL Realizado:</b> ${realized_pnl:+,.2f}\n"
            f"<b>Motivo:</b> Protección estricta contra Gaps de apertura dominical.\n"
            f"<i>Mercados tradicionales cerrados hasta el domingo.</i>\n"
            f"<i>Hora: {now_str}</i>"
        )
        return self.send_message(msg)

    def notify_risk_alert(
        self,
        alert_type: str,
        message: str,
        balance: float,
        daily_loss_remaining: float,
    ) -> bool:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            f"<b>🚨 ALERTA DE GESTIÓN DE RIESGO: {alert_type}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"{message}\n"
            f"<b>Balance:</b> ${balance:,.2f}\n"
            f"<b>Margen restante piso diario:</b> ${daily_loss_remaining:,.2f}\n"
            f"<i>Hora: {now_str}</i>"
        )
        return self.send_message(msg)

    def notify_phase_promoted(
        self,
        old_phase: str,
        new_phase: str,
        balance: float,
        total_profit: float,
    ) -> bool:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            f"<b>🎉 ¡OBJETIVO LOGRADO! ASCENSO DE FASE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>De:</b> {old_phase} ➡️ <b>A:</b> {new_phase}\n"
            f"<b>Balance:</b> ${balance:,.2f}\n"
            f"<b>Beneficio Acumulado:</b> +${total_profit:,.2f}\n"
            f"¡Felicitaciones! Cuenta promovida exitosamente según las reglas FTMO / FundedNext.\n"
            f"<i>Hora: {now_str}</i>"
        )
        return self.send_message(msg)

    def notify_target_reached_waiting_days(
        self,
        phase: str,
        balance: float,
        target_balance: float,
        trading_days: int,
        min_days_required: int,
        recommendations: list,
    ) -> bool:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        recs_formatted = "\n".join(f"• {r}" for r in recommendations[:4])
        msg = (
            f"<b>🎯 ¡OBJETIVO FINANCIERO ALCANZADO EN {phase}!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Balance Actual:</b> ${balance:,.2f} (Meta: ${target_balance:,.2f})\n"
            f"<b>Días Operativos:</b> {trading_days}/{min_days_required} completados\n"
            f"<b>Estado:</b> 🛡️ Capital blindado. Operativa pausada por hoy para evitar overtrading.\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>RECOMENDACIONES PARA CUENTA REAL:</b>\n"
            f"{recs_formatted}\n"
            f"<i>Hora: {now_str}</i>"
        )
        return self.send_message(msg)
