"""
stellar_rules.py - Motor de Validación Estricta de Reglas Multi-Prop Firm.
Soporta dos modelos de drawdown y reglas diferenciadas:

[FundedNext Stellar Lite 2-Step] (Perfil: stellar_10k_demo)
- Cuenta Base: $10,000 USD
- Fase 1 (+8% Target), Fase 2 (+4% Target)
- Daily Loss Limit 4% Estático, Max Drawdown 8% ESTÁTICO (piso fijo $9,200)
- Mínimo 2 días operativos, 40% News Profit Cap, EA autorizado
- Overnight & Weekend Trading permitido, Sin regla de consistencia

[FTMO Challenge 2-Step] (Perfil: ftmo_10k_challenge)
- Cuenta Base: $10,000 USD
- Fase 1 (+10% Target), Fase 2 (+5% Target)
- Daily Loss Limit 5% Estático, Max Drawdown 10% TRAILING (piso sube con HWM)
- Mínimo 4 días operativos, Sin News Profit Cap
- Overnight & Weekend Trading PROHIBIDO (Estándar 1:100)
- Regla de Consistencia 50% (ningún día > 50% del profit total)
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
    drawdown_type: str = "STATIC"
    high_water_mark: float = 0.0
    consistency_ratio: float = 0.0
    consistency_warning: bool = False
    alerts: List[str] = field(default_factory=list)
    target_reached: bool = False
    waiting_min_days: bool = False
    can_pass_phase: bool = False
    real_account_recommendations: List[str] = field(default_factory=list)


class StellarLiteRulesEngine:
    """
    Validador oficial de reglas de fondeo Multi-Prop Firm.
    Soporta FundedNext Stellar Lite (DD Estático) y FTMO Challenge (DD Trailing).
    """

    PHASE_1 = "FASE_1"
    PHASE_2 = "FASE_2"
    CHALLENGE = "CHALLENGE"
    SUPERADA = "SUPERADA"
    FUNDED = "FONDEADA"
    FAILED = "FALLADA"

    PHASE_1_TARGET_PCT = 0.08          # +8% ($800 en $10,000)
    PHASE_2_TARGET_PCT = 0.04          # +4% ($400 en $10,000)
    DAILY_LOSS_LIMIT_PCT = 0.04        # 4% ($400 en $10,000 sobre balance inicio del día)
    MAX_DRAWDOWN_LIMIT_PCT = 0.08      # 8% Estándar ($800 en $10,000 -> piso fijo $9,200)
    MIN_TRADING_DAYS = 2               # 2 días mínimos estándar por fase de evaluación
    NEWS_PROFIT_CAP_PCT = 0.40         # Máximo 40% del profit proveniente de noticias
    DEFAULT_FUNDED_SPLIT = 0.80        # 80% split estándar inicial (Reward Share 80% en 1.png)
    SCALED_FUNDED_SPLIT = 0.90         # 90% split tras escalado (+10% en cuenta fondeada)
    MAX_RISK_AT_ANY_TIME_PCT = 0.03    # 3% Max Risk At Any Time (Regla Oficial FundedNext, 1.png)
    FIRST_WITHDRAWAL_DAYS = 10         # Retiros cada 10 días (1.png)
    SUBSEQUENT_WITHDRAWAL_DAYS = 10    # Retiros subsecuentes cada 10 días
    FEE_REFUND_CYCLE = "3rd Reward"    # Devolución de la tarifa ($64.99) en el 3er cobro de beneficios (1.png)
    ALLOW_OVERNIGHT_WEEKEND = True     # Permitido mantener operaciones overnight y fin de semana

    def __init__(
        self,
        db: TradingDatabase,
        max_drawdown_limit_pct: Optional[float] = None,
        min_trading_days: Optional[int] = None,
        funded_profit_split: Optional[float] = None,
        daily_loss_limit_pct: Optional[float] = None,
        profit_target_pct: Optional[float] = None,
        profit_target_phase2_pct: Optional[float] = None,
        is_trial: Optional[bool] = None,
        profile: Optional[Any] = None,
        use_cloud_addons: bool = True,
        drawdown_type: Optional[str] = None,
        consistency_rule_pct: Optional[float] = None,
        allow_overnight_weekend: Optional[bool] = None,
    ) -> None:
        self.db = db
        acc = self.db.get_account_state()

        self.profile = profile
        if self.profile is None and acc.get("profile_id"):
            try:
                from profiles import profile_manager
                self.profile = profile_manager.get_profile(acc["profile_id"])
            except Exception:
                self.profile = None

        # Resolver si es cuenta Trial
        if is_trial is not None:
            self.is_trial = bool(is_trial)
        elif self.profile is not None:
            self.is_trial = bool(self.profile.is_trial)
        elif acc.get("is_trial") is not None:
            self.is_trial = bool(acc["is_trial"])
        else:
            self.is_trial = False

        # Profit targets
        if profit_target_pct is not None:
            self.profit_target_pct = float(profit_target_pct)
        elif self.profile is not None:
            self.profit_target_pct = float(self.profile.profit_target_pct)
        elif acc.get("profit_target_pct") is not None:
            self.profit_target_pct = float(acc["profit_target_pct"])
        else:
            self.profit_target_pct = self.PHASE_1_TARGET_PCT

        if profit_target_phase2_pct is not None:
            self.profit_target_phase2_pct = float(profit_target_phase2_pct)
        elif self.profile is not None:
            self.profit_target_phase2_pct = self.profile.profit_target_phase2_pct
        elif acc.get("profit_target_phase2_pct") is not None:
            self.profit_target_phase2_pct = float(acc["profit_target_phase2_pct"])
        else:
            self.profit_target_phase2_pct = self.PHASE_2_TARGET_PCT

        # Max drawdown limit
        if max_drawdown_limit_pct is not None:
            self.max_drawdown_limit_pct = float(max_drawdown_limit_pct)
        elif self.profile is not None:
            self.max_drawdown_limit_pct = float(self.profile.max_drawdown_limit_pct)
        elif acc.get("max_drawdown_limit_pct") is not None:
            self.max_drawdown_limit_pct = float(acc["max_drawdown_limit_pct"])
        else:
            self.max_drawdown_limit_pct = self.MAX_DRAWDOWN_LIMIT_PCT

        # Drawdown Type: "STATIC" (FundedNext) o "TRAILING" (FTMO)
        if drawdown_type is not None:
            self.drawdown_type = str(drawdown_type).upper()
        elif self.profile is not None:
            self.drawdown_type = str(getattr(self.profile, "drawdown_type", "STATIC")).upper()
        elif acc.get("drawdown_type") is not None:
            self.drawdown_type = str(acc["drawdown_type"]).upper()
        else:
            self.drawdown_type = "STATIC"

        # Consistency Rule: fracción máxima del profit en 1 día (ej. 0.50 en FTMO, 0.0 en FundedNext)
        if consistency_rule_pct is not None:
            self.consistency_rule_pct = float(consistency_rule_pct)
        elif self.profile is not None:
            self.consistency_rule_pct = float(getattr(self.profile, "consistency_rule_pct", 0.0))
        elif acc.get("consistency_rule_pct") is not None:
            self.consistency_rule_pct = float(acc["consistency_rule_pct"])
        else:
            self.consistency_rule_pct = 0.0

        # Overnight & Weekend
        if allow_overnight_weekend is not None:
            self.allow_overnight_weekend = bool(allow_overnight_weekend)
        elif self.profile is not None:
            self.allow_overnight_weekend = bool(getattr(self.profile, "allow_overnight_weekend", True))
        else:
            self.allow_overnight_weekend = True

        # Min trading days
        if min_trading_days is not None:
            self.min_trading_days = int(min_trading_days)
        elif self.profile is not None:
            self.min_trading_days = int(self.profile.min_trading_days)
        elif acc.get("min_trading_days") is not None:
            self.min_trading_days = int(acc["min_trading_days"])
        else:
            self.min_trading_days = self.MIN_TRADING_DAYS

        # Funded split
        if funded_profit_split is not None:
            self.funded_profit_split = float(funded_profit_split)
        elif self.profile is not None:
            self.funded_profit_split = float(self.profile.funded_profit_split)
        elif acc.get("funded_profit_split") is not None:
            self.funded_profit_split = float(acc["funded_profit_split"])
        else:
            self.funded_profit_split = self.DEFAULT_FUNDED_SPLIT

        # Daily loss limit
        if daily_loss_limit_pct is not None:
            self.daily_loss_limit_pct = float(daily_loss_limit_pct)
        elif self.profile is not None:
            self.daily_loss_limit_pct = float(self.profile.daily_loss_limit_pct)
        elif acc.get("daily_loss_limit_pct") is not None:
            self.daily_loss_limit_pct = float(acc["daily_loss_limit_pct"])
        else:
            self.daily_loss_limit_pct = self.DAILY_LOSS_LIMIT_PCT

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

    def check_consistency_rule(self, phase: str) -> Dict[str, Any]:
        """
        Verifica la regla de consistencia de FTMO (ej. ningún día puede superar el 50% del profit total acumulado).
        Solo aplica si consistency_rule_pct > 0.
        """
        if self.consistency_rule_pct <= 0.0:
            return {"active": False, "ratio": 0.0, "exceeds": False, "max_day_profit": 0.0, "total_profit": 0.0}

        breakdown = self.db.get_daily_pnl_breakdown(phase)
        closed_trades = self.db.get_trades_by_phase(phase, status="CLOSED")
        total_profit = sum(float(t["pnl"]) for t in closed_trades)

        if total_profit <= 0 or not breakdown:
            return {"active": True, "ratio": 0.0, "exceeds": False, "max_day_profit": 0.0, "total_profit": round(total_profit, 2)}

        max_day_pnl = max((float(d["daily_pnl"]) for d in breakdown if float(d["daily_pnl"]) > 0), default=0.0)
        ratio = max_day_pnl / total_profit if total_profit > 0 else 0.0
        exceeds = ratio > self.consistency_rule_pct

        return {
            "active": True,
            "ratio": round(ratio, 4),
            "exceeds": exceeds,
            "max_day_profit": round(max_day_pnl, 2),
            "total_profit": round(total_profit, 2),
        }

    def evaluate_account(
        self,
        floating_pnl: float = 0.0,
        now_server: Optional[datetime] = None,
    ) -> RuleCheckResult:
        """
        Evalúa en tiempo real todas las reglas del desafío (FundedNext o FTMO):
        - Actualiza la equidad flotante (balance + floating_pnl).
        - Verifica Hard Breaches: Daily Loss (4% o 5%) y Max Drawdown (Estático o Trailing).
        - En modo TRAILING (FTMO): el piso de pérdida máxima escala dinámicamente con el High-Water Mark.
        - Verifica Soft Breaches: 40% News Cap (FundedNext), Regla de Consistencia 50% (FTMO), y días mínimos.
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

        # Límite de pérdida diaria
        daily_max_loss_allowance = round(initial_balance * self.daily_loss_limit_pct, 2)
        daily_loss_floor = round(day_start_balance - daily_max_loss_allowance, 2)

        # Cálculo de Max Drawdown: Estático (FundedNext) vs Trailing (FTMO)
        is_trailing = (self.drawdown_type == "TRAILING")
        stored_hwm = float(acc.get("high_water_mark") or initial_balance)
        if stored_hwm < initial_balance:
            stored_hwm = initial_balance

        current_peak = max(stored_hwm, balance, equity)
        if is_trailing:
            high_water_mark = round(current_peak, 2)
            if high_water_mark > stored_hwm:
                self.db.update_account_state(high_water_mark=high_water_mark)
                stored_hwm = high_water_mark
            max_drawdown_amount = round(initial_balance * self.max_drawdown_limit_pct, 2)
            max_loss_floor = round(stored_hwm - max_drawdown_amount, 2)
            self.db.update_account_state(trailing_max_loss_floor=max_loss_floor)
        else:
            high_water_mark = initial_balance
            max_loss_floor = round(initial_balance * (1.0 - self.max_drawdown_limit_pct), 2)

        daily_loss_remaining = round(max(0.0, equity - daily_loss_floor), 2)
        max_loss_remaining = round(max(0.0, equity - max_loss_floor), 2)

        alerts: List[str] = []
        hard_breach = False

        # Si la cuenta ya estaba fallada, mantener el estado
        if status == "FAILED" or phase == self.FAILED:
            if acc.get("fail_reason"):
                alerts.append(f"CUENTA FALLADA: {acc['fail_reason']}")
            hard_breach = True
        else:
            # 1. Verificación de Límite de Pérdida Máxima (Estático o Trailing)
            if equity <= max_loss_floor or balance <= max_loss_floor:
                if is_trailing:
                    reason = (
                        f"Hard Breach: Max Drawdown Limit Trailing ({self.max_drawdown_limit_pct * 100:.0f}%) alcanzado. "
                        f"Equidad (${equity:,.2f}) tocó o perforó el piso móvil de ${max_loss_floor:,.2f} "
                        f"(High-Water Mark: ${stored_hwm:,.2f})."
                    )
                else:
                    reason = (
                        f"Hard Breach: Max Drawdown Limit Estático ({self.max_drawdown_limit_pct * 100:.0f}%) alcanzado. "
                        f"Equidad (${equity:,.2f}) tocó o perforó el piso fijo de ${max_loss_floor:,.2f}."
                    )
                self._fail_account(phase, reason)
                phase = self.FAILED
                status = "FAILED"
                hard_breach = True
                alerts.append(reason)

            # 2. Verificación de Límite de Pérdida Diaria
            elif equity <= daily_loss_floor or balance <= daily_loss_floor:
                reason = (
                    f"Hard Breach: Daily Loss Limit ({self.daily_loss_limit_pct * 100:.0f}% = ${daily_max_loss_allowance:,.2f}) alcanzado. "
                    f"Equidad (${equity:,.2f}) tocó el piso diario de ${daily_loss_floor:,.2f} "
                    f"(Balance inicial del día: ${day_start_balance:,.2f})."
                )
                self._fail_account(phase, reason)
                phase = self.FAILED
                status = "FAILED"
                hard_breach = True
                alerts.append(reason)

        # Evaluación de noticias (40% Cap Rule - relevante para FundedNext)
        news_metrics = self.calculate_news_profit_metrics(phase)
        news_ratio = news_metrics["news_profit_ratio"]
        news_warning = bool(news_metrics["exceeds_40_cap"])
        if news_warning and self.profile and getattr(self.profile, "news_profit_cap_pct", 1.0) < 1.0:
            alerts.append(
                f"SOFT BREACH / ALERTA 40% NEWS CAP: {news_ratio * 100:.1f}% del profit "
                f"(${news_metrics['news_profit']:,.2f} de ${news_metrics['total_profit']:,.2f}) "
                f"proviene de ventanas de noticias de alto impacto (NFP/CPI/FOMC)."
            )

        # Evaluación de consistencia (relevante para FTMO 50% Rule)
        consistency_metrics = self.check_consistency_rule(phase)
        consistency_warning = consistency_metrics["exceeds"]
        if consistency_warning:
            alerts.append(
                f"ALERTA REGLA CONSISTENCIA FTMO ({self.consistency_rule_pct * 100:.0f}%): "
                f"El mejor día (${consistency_metrics['max_day_profit']:,.2f}) representa "
                f"{consistency_metrics['ratio'] * 100:.1f}% del profit total (${consistency_metrics['total_profit']:,.2f}). "
                "Se requiere distribuir el beneficio operando más jornadas para cumplir la regla."
            )

        # Días operativos completados en la fase actual
        trading_days = self.db.get_active_trading_days_count(phase)
        if self.is_trial or phase in (self.CHALLENGE, "TRIAL"):
            min_days_req = self.min_trading_days
        else:
            min_days_req = self.min_trading_days if phase in (self.PHASE_1, self.PHASE_2) else 0

        # Targets por Fase y Promoción Automática (solo sobre balance cerrado y sin Hard Breach)
        profit_target_amount: Optional[float] = None
        profit_target_balance: Optional[float] = None
        current_profit = round(balance - initial_balance, 2)
        target_reached = False
        waiting_min_days = False
        can_pass_phase = False
        real_account_recommendations: List[str] = []

        if not hard_breach:
            if phase == self.SUPERADA:
                profit_target_amount = None
                profit_target_balance = None
                target_reached = True
                can_pass_phase = True

            elif self.is_trial or phase in (self.CHALLENGE, "TRIAL"):
                profit_target_amount = round(initial_balance * self.profit_target_pct, 2)  # $300.00 en $6,000 (+5.0%)
                profit_target_balance = round(initial_balance + profit_target_amount, 2)    # $6,300.00 en $6,000
                if balance >= profit_target_balance:
                    target_reached = True
                    if trading_days >= self.min_trading_days:
                        can_pass_phase = True
                        self._promote_phase(
                            from_phase=phase,
                            to_phase=self.SUPERADA,
                            initial_balance=initial_balance,
                            new_split=0.0,
                        )
                        day_msg = f"{trading_days} días cumplidos"
                        login_label = f"Login #{acc.get('account_login')}" if acc.get('account_login') else "MT5"
                        alerts.append(
                            f"¡CHALLENGE FREE TRIAL SUPERADO! Target +{self.profit_target_pct * 100:.1f}% "
                            f"(${profit_target_amount:,.2f}) alcanzado ({day_msg}). "
                            f"Reto completado con éxito ({login_label})."
                        )
                        return self.evaluate_account(floating_pnl=0.0, now_server=now_server)
                    else:
                        waiting_min_days = True
                        alerts.append(
                            f"Target de Free Trial alcanzado (${balance:,.2f}), pero faltan días operativos: "
                            f"{trading_days}/{self.min_trading_days} días requeridos."
                        )

            elif phase == self.PHASE_1:
                t1_pct = self.profit_target_pct if self.profit_target_pct is not None else self.PHASE_1_TARGET_PCT
                profit_target_amount = round(initial_balance * t1_pct, 2)
                profit_target_balance = round(initial_balance + profit_target_amount, 2)
                if balance >= profit_target_balance:
                    target_reached = True
                    days_ok = trading_days >= self.min_trading_days
                    consistency_ok = not consistency_warning
                    if days_ok and consistency_ok:
                        can_pass_phase = True
                        self._promote_phase(
                            from_phase=self.PHASE_1,
                            to_phase=self.PHASE_2,
                            initial_balance=initial_balance,
                            new_split=0.0,
                        )
                        day_msg = f"{trading_days} días cumplidos" if self.min_trading_days > 0 else "Sin requisito de días mínimos"
                        alerts.append(
                            f"¡FASE 1 SUPERADA! Target +{t1_pct * 100:.1f}% (${profit_target_amount:,.2f}) alcanzado ({day_msg}). "
                            f"Cuenta promovida a FASE 2."
                        )
                        return self.evaluate_account(floating_pnl=0.0, now_server=now_server)
                    elif not days_ok:
                        waiting_min_days = True
                        alerts.append(
                            f"Target de Fase 1 alcanzado (${balance:,.2f}), pero faltan días operativos: "
                            f"{trading_days}/{self.min_trading_days} días requeridos."
                        )
                    elif not consistency_ok:
                        alerts.append(
                            f"Target de Fase 1 alcanzado (${balance:,.2f}), pero se excede la Regla de Consistencia FTMO "
                            f"({self.consistency_rule_pct * 100:.0f}%): mejor día = {consistency_metrics['ratio'] * 100:.1f}%. "
                            "Se requieren días adicionales con ganancias para diluir la concentración."
                        )

            elif phase == self.PHASE_2:
                t2_pct = self.profit_target_phase2_pct if self.profit_target_phase2_pct is not None else self.PHASE_2_TARGET_PCT
                profit_target_amount = round(initial_balance * t2_pct, 2)
                profit_target_balance = round(initial_balance + profit_target_amount, 2)
                if balance >= profit_target_balance:
                    target_reached = True
                    days_ok = trading_days >= self.min_trading_days
                    consistency_ok = not consistency_warning
                    if days_ok and consistency_ok:
                        can_pass_phase = True
                        self._promote_phase(
                            from_phase=self.PHASE_2,
                            to_phase=self.FUNDED,
                            initial_balance=initial_balance,
                            new_split=self.funded_profit_split,
                        )
                        day_msg = f"{trading_days} días cumplidos" if self.min_trading_days > 0 else "Sin requisito de días mínimos"
                        alerts.append(
                            f"¡FASE 2 SUPERADA! Target +{t2_pct * 100:.1f}% (${profit_target_amount:,.2f}) alcanzado ({day_msg}). "
                            f"¡CUENTA FONDEADA OFICIALMENTE! (Profit Split: {self.funded_profit_split * 100:.0f}%)."
                        )
                        return self.evaluate_account(floating_pnl=0.0, now_server=now_server)
                    elif not days_ok:
                        waiting_min_days = True
                        alerts.append(
                            f"Target de Fase 2 alcanzado (${balance:,.2f}), pero faltan días operativos: "
                            f"{trading_days}/{self.min_trading_days} días requeridos."
                        )
                    elif not consistency_ok:
                        alerts.append(
                            f"Target de Fase 2 alcanzado (${balance:,.2f}), pero se excede la Regla de Consistencia FTMO "
                            f"({self.consistency_rule_pct * 100:.0f}%): mejor día = {consistency_metrics['ratio'] * 100:.1f}%. "
                            "Se requieren días adicionales con ganancias para diluir la concentración."
                        )

            elif phase == self.FUNDED:
                profit_target_amount = None
                profit_target_balance = None
                if profit_split < self.funded_profit_split:
                    profit_split = self.funded_profit_split
                    self.db.update_account_state(profit_split=profit_split)
                # Escalado adicional si aplicara
                if current_profit >= initial_balance * 0.10 and profit_split < self.SCALED_FUNDED_SPLIT:
                    profit_split = self.SCALED_FUNDED_SPLIT
                    self.db.update_account_state(profit_split=profit_split)
                    msg = "Profit Split escalado automáticamente por superar +10% de ganancia en cuenta Fondeada."
                    self.db.log_event("PROFIT_SPLIT_SCALE", self.FUNDED, msg)
                    alerts.append(msg)

        # Generar recomendaciones institucionales para cuenta real y prop firm
        if hard_breach:
            pct_dd = self.max_drawdown_limit_pct * 100
            pct_dl = self.daily_loss_limit_pct * 100
            real_account_recommendations.append(
                f"🚨 [CUENTA FALLADA]: Se alcanzó el límite estricto de pérdida (Daily Loss {pct_dl:.0f}% o Max DD {pct_dd:.0f}%). "
                "Detener de inmediato cualquier servicio. En FundedNext, la cuenta queda descalificada; "
                "se debe solicitar un Reset o adquirir una nueva evaluación."
            )
        elif target_reached and waiting_min_days:
            next_phase_str = "RETO SUPERADO" if self.is_trial else ("FASE 2" if phase == self.PHASE_1 else "CUENTA FONDEADA (Split 80%)")
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
            if self.is_trial or phase == self.SUPERADA:
                login_id_str = f"Login #{acc.get('account_login')}" if acc.get('account_login') else "MT5"
                target_val = profit_target_amount if profit_target_amount is not None else round(initial_balance * self.profit_target_pct, 2)
                real_account_recommendations.append(
                    f"🏆 [CHALLENGE FREE TRIAL SUPERADO CON ÉXITO]: Has alcanzado la meta de +${target_val:,.2f} "
                    f"y completado los {min_days_req} días mínimos reglamentarios en tu cuenta de prueba ({login_id_str})."
                )
                real_account_recommendations.append(
                    "🎉 [ESTRATEGIA 100% VALIDADA]: Tu operativa cuantitativa demostró consistencia y control estricto del riesgo. "
                    "Ya estás preparado para operar la cuenta de evaluación oficial FundedNext de $6K o $10K."
                )
            else:
                target_val = profit_target_amount if profit_target_amount is not None else round(initial_balance * (self.profit_target_phase2_pct or self.PHASE_2_TARGET_PCT), 2)
                real_account_recommendations.append(
                    f"🏆 [FASE SUPERADA CON ÉXITO]: Cumpliste tanto el beneficio (${target_val:,.2f}) "
                    f"como los {min_days_req} días mínimos reglamentarios."
                )
                real_account_recommendations.append(
                    "📋 [PASOS EN EL BROKER]: 1. Cierra cualquier posición restante. 2. No abras ninguna otra orden. "
                    "3. En el panel de FundedNext solicita la emisión de credenciales de la siguiente fase o Cuenta Fondeada."
                )
        elif phase == self.SUPERADA:
            login_id_str = f"Login #{acc.get('account_login')}" if acc.get('account_login') else "MT5"
            real_account_recommendations.append(
                f"🏆 [RETO FREE TRIAL 6K COMPLETADO]: Estado oficial: SUPERADO ({login_id_str}). "
                "Todas las reglas fueron respetadas con éxito."
            )
        elif phase == self.FUNDED:
            real_account_recommendations.append(
                f"💎 [CUENTA FONDEADA ACTIVA]: Operando capital institucional con Profit Split al {profit_split * 100:.0f}%."
            )
            real_account_recommendations.append(
                f"🛡️ [PRESERVACIÓN DE CAPITAL]: Tu piso diario es ${daily_loss_floor:,.2f} y el piso inamovible de "
                f"Max Drawdown ({self.max_drawdown_limit_pct * 100:.0f}%) es ${max_loss_floor:,.2f}."
            )
            real_account_recommendations.append(
                "💰 [CALENDARIO DE PAGOS]: Retiros disponibles cada 10 días. Reembolso del 100% de la tarifa pagada ($64.99 USD) al 3er cobro de recompensas."
            )
            max_risk_amount = round(initial_balance * 0.03, 2)
            risk_trade_amount = round(initial_balance * 0.005, 2)
            real_account_recommendations.append(
                f"🛡️ [REGLA FUNDEDNEXT MAX RISK 3%]: El riesgo máximo total simultáneo en mercado no puede superar el 3.0% (${max_risk_amount:,.2f} en ${initial_balance:,.0f}). Tu bot opera en 0.50% (${risk_trade_amount:,.2f}) por trade (factor de seguridad 6x)."
            )
            if profit_split < self.SCALED_FUNDED_SPLIT:
                needed = round(initial_balance * 0.10 - current_profit, 2)
                real_account_recommendations.append(
                    f"📈 [ESCALADO A 90%]: Genera ${max(0.0, needed):,.2f} adicionales (+10% total) para escalar el "
                    f"Profit Split al 90% de forma vitalicia."
                )
        else:
            pct_needed = round(((profit_target_balance - balance) / initial_balance) * 100, 2) if profit_target_balance else 0.0
            phase_label = "CHALLENGE TRIAL" if self.is_trial else phase
            risk_trade_amount = round(initial_balance * 0.005, 2)
            personal_cap_amount = round(initial_balance * float(acc.get("personal_daily_cap_pct", 0.02)), 2)
            max_risk_amount = round(initial_balance * 0.03, 2)
            real_account_recommendations.append(
                f"📊 [PROGRESO DE FASE]: Balance actual: ${balance:,.2f} | Meta: ${profit_target_balance:,.2f} "
                f"(Falta: ${profit_target_balance - balance:,.2f} / {pct_needed}%)."
            )
            real_account_recommendations.append(
                f"📅 [DÍAS OPERATIVOS]: {trading_days}/{min_days_req} días completados en {phase_label}."
            )
            real_account_recommendations.append(
                f"🛡️ [GESTIÓN DE RIESGO]: Mantener riesgo por trade en 0.50% (${risk_trade_amount:,.2f} USD). Respeta el freno personal "
                f"diario (${personal_cap_amount:,.2f} USD), la regla anti-racha (máx. 3 pérdidas) y el límite FundedNext de 3% max risk (${max_risk_amount:,.2f} USD)."
            )
            if is_trailing:
                real_account_recommendations.append(
                    f"📈 [TRAILING DRAWDOWN FTMO]: High-Water Mark pico en ${stored_hwm:,.2f} | Piso móvil en ${max_loss_floor:,.2f} (Margen restante: ${max_loss_remaining:,.2f})."
                )
            if self.consistency_rule_pct > 0.0:
                c_status = "⚠️ PENDIENTE DILUIR" if consistency_warning else "✅ DENTRO DEL LÍMITE"
                real_account_recommendations.append(
                    f"⚖️ [REGLA CONSISTENCIA FTMO {self.consistency_rule_pct * 100:.0f}%]: Concentración del mejor día: {consistency_metrics['ratio'] * 100:.1f}% ({c_status})."
                )
            if not self.allow_overnight_weekend:
                real_account_recommendations.append(
                    "🌙 [REGLA NO-OVERNIGHT FTMO]: Las posiciones deben cerrarse antes de las 16:45 EST (prohibido mantener operaciones overnight y weekend en cuenta estándar)."
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
            drawdown_type=self.drawdown_type,
            high_water_mark=high_water_mark,
            consistency_ratio=consistency_metrics["ratio"],
            consistency_warning=consistency_warning,
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
        reset_trailing_floor = round(initial_balance * (1.0 - self.max_drawdown_limit_pct), 2)
        self.db.update_account_state(
            balance=initial_balance,
            equity=initial_balance,
            day_start_balance=initial_balance,
            current_trading_day=today_str,
            phase=to_phase,
            status="ACTIVE",
            profit_split=new_split,
            high_water_mark=initial_balance,
            trailing_max_loss_floor=reset_trailing_floor,
        )
        self.db.log_event(
            "PHASE_PROMOTION",
            to_phase,
            f"Promoción exitosa de {from_phase} a {to_phase}. Balance restablecido a ${initial_balance:,.2f}.",
        )
