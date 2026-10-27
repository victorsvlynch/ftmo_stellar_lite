"""
telegram_notifier.py - Módulo de Notificaciones en Tiempo Real para Telegram.
Envía alertas inmediatas a tu teléfono móvil (@victorsvlynch) sobre:
- Señales de Trading en Tiempo Real (Opción C: Ejecución Manual en MT5 Móvil)
- Apertura de operaciones institucionales (con SL, TP, lotaje y riesgo en USD)
- Activación de Break-Even (+1R protegido sin riesgo)
- Cierre de operaciones (con PnL realizado y balance actualizado)
- Alertas de riesgo y cumplimiento de objetivos FundedNext Stellar Lite ($5,000)
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


class TelegramNotifier:
    """Gestor de notificaciones push vía Telegram Bot API (sin dependencias externas)."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

        # Si no están en env vars, intentar leer de telegram_config.json en múltiples rutas
        if not self.bot_token or not self.chat_id:
            candidates = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_config.json"),
                os.path.join(os.getcwd(), "telegram_config.json"),
                "/home/ubuntu/FTMO_Stellar_Lite/telegram_config.json",
            ]
            for cfg_path in candidates:
                if os.path.exists(cfg_path):
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                            self.bot_token = self.bot_token or cfg.get("bot_token", "").strip()
                            self.chat_id = self.chat_id or str(cfg.get("chat_id", "")).strip()
                            if self.bot_token and self.chat_id:
                                break
                    except Exception:
                        pass

        self.enabled = bool(self.bot_token and self.chat_id)

    def send_message(self, message: str) -> bool:
        """Envía un mensaje de texto formateado en HTML a Telegram."""
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
            with urllib.request.urlopen(req, timeout=6) as response:
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
        phase: str = "FONDEADA",
    ) -> bool:
        """Notificación de orden ejecutada con instrucciones para seguimiento en móvil."""
        emoji = "🟢 COMPRA (BUY)" if side.upper() == "BUY" else "🔴 VENTA (SELL)"
        sym_clean = "XAUUSD (Oro)" if "GC" in symbol.upper() or "XAU" in symbol.upper() else symbol
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = (
            f"<b>🚀 ORDEN INSTITUCIONAL #{trade_id} ABIERTA</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Cuenta:</b> FundedNext Stellar Lite ($5,000)\n"
            f"<b>Estrategia:</b> <code>{strategy}</code>\n"
            f"<b>Activo:</b> <b>{sym_clean}</b>\n"
            f"<b>Acción:</b> <b>{emoji}</b>\n"
            f"<b>Volumen:</b> <b>{lots:.2f} Lotes</b>\n"
            f"<b>Precio Entrada:</b> ${entry_price:,.2f}\n"
            f"<b>Stop Loss (SL):</b> ${stop_loss:,.2f}\n"
            f"<b>Take Profit (TP):</b> ${take_profit:,.2f} (R:R 1:2)\n"
            f"<b>Riesgo Controlado:</b> ${risk_usd:,.2f} ({risk_pct * 100:.2f}% capital)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>MONITOREO EN TU CELULAR:</b>\n"
            f"• Abre <b>MetaTrader 5</b> en tu teléfono para ver la operación en vivo.\n"
            f"• El bot gestionará automáticamente el <b>Break-Even (+1R)</b> y te avisará aquí.\n"
            f"<i>Hora: {now_str}</i>"
        )
        return self.send_message(msg)

    def notify_signal_alert(
        self,
        symbol: str,
        side: str,
        lots: float,
        price: float,
        sl: float,
        tp: float,
        risk_usd: float = 25.0,
        risk_pct: float = 0.005,
        strategy: str = "NY_OPEN",
        comment: str = "Señal Manual Móvil",
    ) -> bool:
        """
        OPCIÓN C: Envía la señal exacta lista para ejecución manual
        en la app MetaTrader 5 del celular.
        """
        emoji = "🟢 COMPRAR (BUY)" if side.upper() == "BUY" else "🔴 VENDER (SELL)"
        btn_action = "COMPRAR" if side.upper() == "BUY" else "VENDER"
        sym_mt5 = "XAUUSD" if "GC" in symbol.upper() or "XAU" in symbol.upper() else symbol
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = (
            f"<b>⚡ SEÑAL DE TRADING AL INSTANTE (OPCIÓN C)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Estrategia:</b> <code>{strategy}</code>\n"
            f"<b>Activo:</b> <b>{sym_mt5} (Oro)</b>\n"
            f"<b>Orden:</b> <b>{emoji}</b>\n"
            f"<b>Volumen Sugerido:</b> <b>{lots:.2f} lotes</b>\n"
            f"<b>Precio Referencia:</b> ${price:,.2f}\n"
            f"<b>Stop Loss (SL):</b> <code>{sl:.2f}</code>\n"
            f"<b>Take Profit (TP):</b> <code>{tp:.2f}</code> (R:R 1:2)\n"
            f"<b>Riesgo Máximo:</b> ${risk_usd:,.2f} ({risk_pct * 100:.2f}% de $5,000)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📲 <b>PASOS PARA EJECUTAR EN TU CELULAR:</b>\n"
            f"1. Abre <b>MetaTrader 5</b> en tu móvil.\n"
            f"2. Busca <b>{sym_mt5}</b> ➔ Selecciona <i>Nueva Orden</i>.\n"
            f"3. Ajusta el lote a: <b>{lots:.2f}</b>.\n"
            f"4. Escribe Stop Loss: <b>{sl:.2f}</b>\n"
            f"5. Escribe Take Profit: <b>{tp:.2f}</b>\n"
            f"6. Presiona el botón <b>{btn_action}</b>.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Usuario: @victorsvlynch | <i>Hora: {now_str}</i>"
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
        """Alerta de Break-Even activado."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            f"<b>🛡️ BREAK-EVEN ACTIVADO (+1R ALCANZADO)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Operación #{trade_id}:</b> {symbol} ({side})\n"
            f"<b>Precio Entrada:</b> ${entry_price:,.2f}\n"
            f"<b>Nuevo Stop Loss:</b> ${new_sl:,.2f} (Al precio de entrada)\n"
            f"<b>Riesgo Actual:</b> <b>$0.00 (OPERACIÓN BLINDADA)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 Si operas en el celular: Modifica la orden en MT5 y coloca tu Stop Loss en ${new_sl:,.2f}.\n"
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
        """Alerta de trade cerrado."""
        is_win = net_pnl > 0
        emoji = "🏆 WIN (GANANCIA)" if is_win else ("❌ LOSS (PÉRDIDA)" if net_pnl < 0 else "⚪ BREAK-EVEN ($0)")
        sign = "+" if net_pnl > 0 else ""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = (
            f"<b>{emoji} — OPERACIÓN CERRADA #{trade_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Activo:</b> {symbol} ({side} {lots:.2f} lotes)\n"
            f"<b>Precio Salida:</b> ${exit_price:,.2f} | <b>Motivo:</b> {reason}\n"
            f"<b>Beneficio Neto:</b> <b>{sign}${net_pnl:,.2f}</b>\n"
            f"<b>Comisiones:</b> -${commission:,.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Nuevo Balance:</b> ${balance:,.2f}\n"
            f"<b>Equidad:</b> ${equity:,.2f}\n"
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
        """Alerta de riesgo FundedNext."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            f"<b>🚨 ALERTA DE GESTIÓN DE RIESGO: {alert_type}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{message}\n"
            f"<b>Balance Actual:</b> ${balance:,.2f}\n"
            f"<b>Margen Diario Restante:</b> ${daily_loss_remaining:,.2f}\n"
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
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>De:</b> {old_phase} ➡️ <b>A:</b> {new_phase}\n"
            f"<b>Balance:</b> ${balance:,.2f}\n"
            f"<b>Beneficio Acumulado:</b> +${total_profit:,.2f}\n"
            f"¡Felicitaciones! Cuenta promovida exitosamente en FundedNext.\n"
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
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Posiciones cerradas:</b> {closed_count}\n"
            f"<b>PnL Realizado:</b> ${realized_pnl:+,.2f}\n"
            f"<b>Motivo:</b> Protección contra Gaps de fin de semana.\n"
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
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Balance Actual:</b> ${balance:,.2f} (Meta: ${target_balance:,.2f})\n"
            f"<b>Días Operativos:</b> {trading_days}/{min_days_required} completados\n"
            f"<b>Estado:</b> 🛡️ Capital blindado. Operativa pausada por hoy para evitar overtrading.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>RECOMENDACIONES PARA CUENTA REAL:</b>\n"
            f"{recs_formatted}\n"
            f"<i>Hora: {now_str}</i>"
        )
        return self.send_message(msg)
