"""
stellar_rules.py - Motor de Validación Estricta de Reglas FundedNext Stellar Lite.
Implementa:
- Fase 1 (+8% Target = $400 en $5K)
- Fase 2 (+4% Target = $200 en $5K)
- Cuenta Fondeada (Sin target, Profit Split 80% escalable a 90%)
- Daily Loss Limit (4% Estático = $200 en $5K sobre balance inicial de jornada, reseteo 00:00 UTC)
- Max Drawdown Limit (8% Estático = $400 en $5K, piso fijo en $4,600)
- Mínimo 2 días operativos por fase
- 40% News Profit Cap Rule (NFP, CPI, FOMC)
- Overnight & Weekend Trading permitido
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from database import TradingDatabase


@dataclass
class RuleCheckResult:
    is_valid: bool
    hard_breach: bool
    phase: str
    status: str
    balance: float
    equity: float
    floating_pnl: float
    day_start_balance: float
    daily_loss_floor: float
    daily_loss_remaining: float
    max_loss_floor: float
    max_loss_remaining: float
    profit_target_amount: Optional[float]
    profit_target_balance: Optional[float]
    current_profit: float
    trading_days_completed: int
    min_trading_days_required: int
    news_profit_ratio: float
    news_cap_warning: bool
    profit_split: float
    alerts: List[str] = field(default_factory=list)
    target_reached: bool = False
    waiting_min_days: bool = False
    can_pass_phase: bool = False
    real_account_recommendations: List[str] = field(default_factory=list)


class StellarLiteRulesEngine:
    """Validador oficial de reglas de fondeo FundedNext - Stellar Lite."""

    PHASE_1 = "FASE_1"
    PHASE_2 = "FASE_2"
    FUNDED = "FONDEADA"
    FAILED = "FALLADA"

    PHASE_1_TARGET_PCT = 0.08          # +8% ($400 en $5,000)
    PHASE_2_TARGET_PCT = 0.04          # +4% ($200 en $5,000)
    DAILY_LOSS_LIMIT_PCT = 0.04        # 4% ($200 en $5,000 sobre balance inicio del día)
    MAX_DRAWDOWN_LIMIT_PCT = 0.08      # 8% ($400 en $5,000 -> piso fijo $4,600)
    MIN_TRADING_DAYS = 2               # 2 días mínimos por fase de evaluación
    NEWS_PROFIT_CAP_PCT = 0.40         # Máximo 40% del profit proveniente de noticias
    DEFAULT_FUNDED_SPLIT = 0.80        # 80% split inicial
    SCALED_FUNDED_SPLIT = 0.90         # 90% split tras escalado (+10% en cuenta fondeada)
    ALLOW_OVERNIGHT_WEEKEND = True     # Permitido mantener operaciones overnight y fin de semana

    def __init__(self, db: TradingDatabase) -> None:
        self.db = db

    def check_daily_rollover(self, now_server: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Verifica si cambió el día del servidor (00:00 UTC) y resetea el
        day_start_balance al balance actual para el cálculo del Daily Loss Limit.
        """
        dt = now_server or datetime.now(timezone.utc)
        today_str = dt.strftime("%Y-%m-%d")
        acc = self.db.get_account_state()

        if acc.get("current_trading_day") != today_str and acc.get("status") == "ACTIVE":
            current_balance = float(acc["balance"])
            acc = self.db.update_account_state(
                day_start_balance=current_balance,
                current_trading_day=today_str,
            )
            self.db.log_event(
                "DAILY_ROLLOVER",
                acc["phase"],
                f"Reset 00:00 Server Time ({today_str}). Nuevo balance inicial del día: ${current_balance:,.2f}",
            )
        return acc

    def is_high_impact_news_window(self, dt_utc: Optional[datetime] = None) -> bool:
        """
        Detecta si el timestamp actual cae dentro de una ventana típica de alta volatilidad
        macroeconómica de EE.UU. (NFP: primer viernes del mes 12:25-12:40 UTC / 08:30 EST,
        CPI: días 10-15 a las 12:25-12:40 UTC, FOMC: miércoles de decisión 18:55-19:35 UTC).
        """
        dt = dt_utc or datetime.now(timezone.utc)
        weekday = dt.weekday()  # 0=Lunes ... 4=Viernes
        hour_min = dt.hour * 60 + dt.minute

        # Ventana 08:30 EST (12:25 a 12:40 UTC o 13:25 a 13:40 UTC según horario)
        is_830_est_window = (12 * 60 + 25 <= hour_min <= 12 * 60 + 40) or (
            13 * 60 + 25 <= hour_min <= 13 * 60 + 40
        )
        # NFP: Primer viernes del mes (día 1 al 7) a las 08:30 EST
        if weekday == 4 and 1 <= dt.day <= 7 and is_830_est_window:
            return True

        # CPI: Entre el día 10 y 14 del mes (martes a jueves) a las 08:30 EST
        if weekday in (1, 2, 3) and 10 <= dt.day <= 14 and is_830_est_window:
            return True

        # FOMC: Miércoles a las 14:00 EST (18:55 a 19:30 UTC)
        is_fomc_window = (18 * 60 + 55 <= hour_min <= 19 * 60 + 30) or (
            19 * 60 + 55 <= hour_min <= 20 * 60 + 30
        )
        if weekday == 2 and 15 <= dt.day <= 22 and is_fomc_window:
            return True

        return False

    def calculate_news_profit_metrics(self, phase: str) -> Dict[str, float]:
        """
        Calcula la proporción de ganancias generadas en ventanas de noticias (NFP, CPI, FOMC)
        respecto al profit neto total acumulado en la fase actual (40% Cap Rule).
        """
        closed_trades = self.db.get_trades_by_phase(phase, status="CLOSED")
        total_profit = sum(float(t["pnl"]) for t in closed_trades)
        news_profit = sum(
            float(t["pnl"]) for t in closed_trades if int(t["is_news_window"]) == 1 and float(t["pnl"]) > 0
        )

        if total_profit <= 0 or news_profit <= 0:
            ratio = 0.0
        else:
            ratio = news_profit / total_profit

        return {
            "total_profit": round(total_profit, 2),
            "news_profit": round(news_profit, 2),
            "news_profit_ratio": round(ratio, 4),
            "exceeds_40_cap": ratio > self.NEWS_PROFIT_CAP_PCT,
        }

    def evaluate_account(
        self,
        floating_pnl: float = 0.0,
        now_server: Optional[datetime] = None,
    ) -> RuleCheckResult:
        """
        Evalúa en tiempo real todas las reglas de FundedNext Stellar Lite:
        - Actualiza la equidad flotante (balance + floating_pnl).
        - Verifica Hard Breaches (Daily Loss 4% y Max Drawdown 8%).
        - Verifica Soft Breaches (40% News Cap y mínimo de 2 días operativos).
        - Promueve automáticamente de Fase 1 -> Fase 2 -> Fondeada si se cumplen los objetivos.
        """
        acc = self.check_daily_rollover(now_server)
        initial_balance = float(acc["initial_balance"])
        balance = float(acc["balance"])
        day_start_balance = float(acc["day_start_balance"])
        phase = str(acc["phase"])
        status = str(acc["status"])
        profit_split = float(acc["profit_split"])

        equity = round(balance + floating_pnl, 2)
        self.db.update_account_state(equity=equity)

        # Cálculos de límites estáticos FundedNext Stellar Lite
        daily_max_loss_allowance = round(initial_balance * self.DAILY_LOSS_LIMIT_PCT, 2)  # $200 en $5,000
        daily_loss_floor = round(day_start_balance - daily_max_loss_allowance, 2)
        max_loss_floor = round(initial_balance * (1.0 - self.MAX_DRAWDOWN_LIMIT_PCT), 2)  # $4,600 en $5,000

        daily_loss_remaining = round(max(0.0, equity - daily_loss_floor), 2)
        max_loss_remaining = round(max(0.0, equity - max_loss_floor), 2)

        alerts: List[str] = []
        hard_breach = False

        # Si la cuenta ya estaba fallada, mantener el estado
        if status == "FAILED" or phase == self.FAILED:
            if acc["fail_reason"]:
                alerts.append(f"CUENTA FALLADA: {acc['fail_reason']}")
            hard_breach = True
        else:
            # 1. Verificación de Límite de Pérdida Máxima (8% Estático -> $4,600)
            if equity <= max_loss_floor or balance <= max_loss_floor:
                reason = (
                    f"Hard Breach: Max Drawdown Limit (8%) alcanzado. "
                    f"Equidad (${equity:,.2f}) tocó o perforó el piso fijo de ${max_loss_floor:,.2f}."
                )
                self._fail_account(phase, reason)
                phase = self.FAILED
                status = "FAILED"
                hard_breach = True
                alerts.append(reason)

            # 2. Verificación de Límite de Pérdida Diaria (4% Estático -> $200 desde day_start_balance)
            elif equity <= daily_loss_floor or balance <= daily_loss_floor:
                reason = (
                    f"Hard Breach: Daily Loss Limit (4% = ${daily_max_loss_allowance:,.2f}) alcanzado. "
                    f"Equidad (${equity:,.2f}) tocó el piso diario de ${daily_loss_floor:,.2f} "
                    f"(Balance inicial del día: ${day_start_balance:,.2f})."
                )
                self._fail_account(phase, reason)
                phase = self.FAILED
                status = "FAILED"
                hard_breach = True
                alerts.append(reason)

        # Evaluación de noticias (40% Cap Rule)
        news_metrics = self.calculate_news_profit_metrics(phase)
        news_ratio = news_metrics["news_profit_ratio"]
        news_warning = bool(news_metrics["exceeds_40_cap"])
        if news_warning:
            alerts.append(
                f"SOFT BREACH / ALERTA 40% NEWS CAP: {news_ratio * 100:.1f}% del profit "
                f"(${news_metrics['news_profit']:,.2f} de ${news_metrics['total_profit']:,.2f}) "
                f"proviene de ventanas de noticias de alto impacto (NFP/CPI/FOMC)."
            )

        # Días operativos completados en la fase actual
        trading_days = self.db.get_active_trading_days_count(phase)
        min_days_req = self.MIN_TRADING_DAYS if phase in (self.PHASE_1, self.PHASE_2) else 0

        # Targets por Fase y Promoción Automática (solo sobre balance cerrado y sin Hard Breach)
        profit_target_amount: Optional[float] = None
        profit_target_balance: Optional[float] = None
        current_profit = round(balance - initial_balance, 2)
        target_reached = False
        waiting_min_days = False
        can_pass_phase = False
        real_account_recommendations: List[str] = []

        if not hard_breach:
            if phase == self.PHASE_1:
                profit_target_amount = round(initial_balance * self.PHASE_1_TARGET_PCT, 2)  # $400.00
                profit_target_balance = round(initial_balance + profit_target_amount, 2)    # $5,400.00
                if balance >= profit_target_balance:
                    target_reached = True
                    if trading_days >= self.MIN_TRADING_DAYS:
                        can_pass_phase = True
                        self._promote_phase(
                            from_phase=self.PHASE_1,
                            to_phase=self.PHASE_2,
                            initial_balance=initial_balance,
                            new_split=0.0,
                        )
                        alerts.append(
                            f"¡FASE 1 SUPERADA! Target +8% (${profit_target_amount:,.2f}) y "
                            f"{trading_days} días operativos cumplidos. Cuenta promovida a FASE 2."
                        )
                        return self.evaluate_account(floating_pnl=0.0, now_server=now_server)
                    else:
                        waiting_min_days = True
                        alerts.append(
                            f"Target de Fase 1 alcanzado (${balance:,.2f}), pero faltan días operativos: "
                            f"{trading_days}/{self.MIN_TRADING_DAYS} días requeridos."
                        )

            elif phase == self.PHASE_2:
                profit_target_amount = round(initial_balance * self.PHASE_2_TARGET_PCT, 2)  # $200.00
                profit_target_balance = round(initial_balance + profit_target_amount, 2)    # $5,200.00
                if balance >= profit_target_balance:
                    target_reached = True
                    if trading_days >= self.MIN_TRADING_DAYS:
                        can_pass_phase = True
                        self._promote_phase(
                            from_phase=self.PHASE_2,
                            to_phase=self.FUNDED,
                            initial_balance=initial_balance,
                            new_split=self.DEFAULT_FUNDED_SPLIT,
                        )
                        alerts.append(
                            f"¡FASE 2 SUPERADA! Target +4% (${profit_target_amount:,.2f}) y "
                            f"{trading_days} días operativos cumplidos. ¡CUENTA FONDEADA (Split 80%)!"
                        )
                        return self.evaluate_account(floating_pnl=0.0, now_server=now_server)
                    else:
                        waiting_min_days = True
                        alerts.append(
                            f"Target de Fase 2 alcanzado (${balance:,.2f}), pero faltan días operativos: "
                            f"{trading_days}/{self.MIN_TRADING_DAYS} días requeridos."
                        )

            elif phase == self.FUNDED:
                profit_target_amount = None
                profit_target_balance = None
                # Escalado automático del Profit Split de 80% a 90% si acumula >= +10% en Fondeada
                if current_profit >= initial_balance * 0.10 and profit_split < self.SCALED_FUNDED_SPLIT:
                    profit_split = self.SCALED_FUNDED_SPLIT
                    self.db.update_account_state(profit_split=profit_split)
                    msg = "Profit Split escalado automáticamente del 80% al 90% por superar +10% de ganancia en cuenta Fondeada."
                    self.db.log_event("PROFIT_SPLIT_SCALE", self.FUNDED, msg)
                    alerts.append(msg)

        # Generar recomendaciones institucionales para cuenta real y prop firm
        if hard_breach:
            real_account_recommendations.append(
                "🚨 [CUENTA FALLADA]: Se alcanzó el límite estricto de pérdida (Daily Loss 4% o Max DD 8%). "
                "Detener de inmediato cualquier servicio. En FundedNext, la cuenta queda descalificada; "
                "se debe solicitar un Reset o adquirir una nueva evaluación."
            )
        elif target_reached and waiting_min_days:
            next_phase_str = "FASE 2" if phase == self.PHASE_1 else "CUENTA FONDEADA (Split 80%)"
            real_account_recommendations.append(
                f"🎯 [OBJETIVO FINANCIERO ALCANZADO]: Tu balance (${balance:,.2f}) superó la meta exigida "
                f"para {phase} (${profit_target_balance:,.2f}). Beneficio asegurado: +${current_profit:,.2f}."
            )
            real_account_recommendations.append(
                "🛑 [FRENO ANTI-SOBREOPERACIÓN]: EN CUENTA REAL, NO ABRAS MÁS POSICIONES HOY. Continuar operando "
                "con el target cumplido es el error #1 por el que se pierden evaluaciones. El capital debe blindarse."
            )
            real_account_recommendations.append(
                f"📅 [DÍAS MÍNIMOS EN PROGRESO]: Llevas {trading_days}/{min_days_req} días requeridos. "
                f"Falta {min_days_req - trading_days} jornada(s) para poder pasar a {next_phase_str}."
            )
            real_account_recommendations.append(
                "💡 [ESTRATEGIA SEGURA DÍA SIGUIENTE]: Espera al cambio de día del broker (00:00 UTC). En la siguiente "
                "jornada, ejecuta una sola micro-operación con lotaje mínimo (0.01 lotes) para certificar el día "
                "obligatorio sin arriesgar tu ganancia acumulada."
            )
            real_account_recommendations.append(
                "🌐 [PORTAL FUNDEDNEXT]: Ingresa al Dashboard web de FundedNext y verifica que el Target aparezca en "
                "verde y los días operativos coincidan antes de solicitar el pase."
            )
        elif target_reached and can_pass_phase:
            real_account_recommendations.append(
                f"🏆 [FASE SUPERADA CON ÉXITO]: Cumpliste tanto el beneficio (${profit_target_amount:,.2f}) "
                f"como los {min_days_req} días mínimos reglamentarios."
            )
            real_account_recommendations.append(
                "📋 [PASOS EN EL BROKER]: 1. Cierra cualquier posición restante. 2. No abras ninguna otra orden. "
                "3. En el panel de FundedNext solicita la emisión de credenciales de la siguiente fase o Cuenta Fondeada."
            )
        elif phase == self.FUNDED:
            real_account_recommendations.append(
                f"💎 [CUENTA FONDEADA ACTIVA]: Operando capital institucional con Profit Split al {profit_split * 100:.0f}%."
            )
            real_account_recommendations.append(
                f"🛡️ [PRESERVACIÓN DE CAPITAL]: Tu piso diario es ${daily_loss_floor:,.2f} y el piso inamovible de "
                f"Max Drawdown es ${max_loss_floor:,.2f}. Retiros disponibles según el calendario oficial de FundedNext."
            )
            if profit_split < self.SCALED_FUNDED_SPLIT:
                needed = round(initial_balance * 0.10 - current_profit, 2)
                real_account_recommendations.append(
                    f"📈 [ESCALADO A 90%]: Genera ${max(0.0, needed):,.2f} adicionales (+10% total) para escalar el "
                    f"Profit Split al 90% de forma vitalicia."
                )
        else:
            pct_needed = round(((profit_target_balance - balance) / initial_balance) * 100, 2) if profit_target_balance else 0.0
            real_account_recommendations.append(
                f"📊 [PROGRESO DE FASE]: Balance actual: ${balance:,.2f} | Meta: ${profit_target_balance:,.2f} "
                f"(Falta: ${profit_target_balance - balance:,.2f} / {pct_needed}%)."
            )
            real_account_recommendations.append(
                f"📅 [DÍAS OPERATIVOS]: {trading_days}/{min_days_req} días completados en {phase}."
            )
            real_account_recommendations.append(
                "🛡️ [GESTIÓN DE RIESGO]: Mantener riesgo por trade entre 0.5% y 1.0%. Respeta el freno personal "
                "diario del 2% y la regla anti-racha (máx. 3 pérdidas = stop por el resto del día)."
            )
            real_account_recommendations.append(
                "⚠️ [REGLA DE NOTICIAS]: No abras operaciones dentro de los 15 minutos previos o posteriores a NFP, "
                "CPI o FOMC (máximo 40% de ganancias provenientes de noticias)."
            )

        return RuleCheckResult(
            is_valid=not hard_breach,
            hard_breach=hard_breach,
            phase=phase,
            status=status,
            balance=balance,
            equity=equity,
            floating_pnl=round(floating_pnl, 2),
            day_start_balance=day_start_balance,
            daily_loss_floor=daily_loss_floor,
            daily_loss_remaining=daily_loss_remaining,
            max_loss_floor=max_loss_floor,
            max_loss_remaining=max_loss_remaining,
            profit_target_amount=profit_target_amount,
            profit_target_balance=profit_target_balance,
            current_profit=current_profit,
            trading_days_completed=trading_days,
            min_trading_days_required=min_days_req,
            news_profit_ratio=news_ratio,
            news_cap_warning=news_warning,
            profit_split=profit_split,
            alerts=alerts,
            target_reached=target_reached,
            waiting_min_days=waiting_min_days,
            can_pass_phase=can_pass_phase,
            real_account_recommendations=real_account_recommendations,
        )

    def _fail_account(self, current_phase: str, reason: str) -> None:
        """Marca la cuenta como FALLADA en SQLite y registra la auditoría."""
        self.db.update_account_state(
            phase=self.FAILED,
            status="FAILED",
            fail_reason=reason,
        )
        self.db.log_event("HARD_BREACH", current_phase, reason)

    def _promote_phase(
        self,
        from_phase: str,
        to_phase: str,
        initial_balance: float,
        new_split: float,
    ) -> None:
        """Promueve la cuenta a la siguiente fase reiniciando el balance base de la nueva fase."""
        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")
        self.db.update_account_state(
            balance=initial_balance,
            equity=initial_balance,
            day_start_balance=initial_balance,
            current_trading_day=today_str,
            phase=to_phase,
            status="ACTIVE",
            profit_split=new_split,
        )
        self.db.log_event(
            "PHASE_PROMOTION",
            to_phase,
            f"Promoción exitosa de {from_phase} a {to_phase}. Balance restablecido a ${initial_balance:,.2f}.",
        )
