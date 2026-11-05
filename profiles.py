"""
profiles.py - Gestor Institucional de Perfiles de Trading FundedNext.
Permite administrar y conmutar sin conflicto entre múltiples cuentas y modelos:
1. Stellar 10K Demo (Stellar Lite 2-Step $10,000 USD)
2. Stellar 6K Trial (Free Trial Challenge $6,000 USD - MT5 / Swap)
3. Soporte para crear, clonar, editar o cambiar perfiles sin borrar el historial.
"""

import os
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger("TradingProfiles")

PROFILES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json")


@dataclass
class TradingProfile:
    """Definición canónica de un perfil de cuenta / desafío FundedNext."""
    id: str                                  # Clave única: 'stellar_10k_demo', 'stellar_6k_trial'
    name: str                                # Nombre visible: 'Stellar 10K Demo', 'Stellar 6K Trial'
    account_type: str                        # 'Stellar Lite 2-Step' | 'Free Trial Challenge'
    platform: str = "MT5"                    # Plataforma oficial: MT5
    account_mode: str = "SWAP"               # Tipo de cuenta: Swap
    initial_balance: float = 10000.0         # Capital base ($10,000 o $6,000)
    profit_target_pct: float = 0.08          # Target fase 1 o challenge (+8% o +5%)
    profit_target_phase2_pct: Optional[float] = 0.04  # Target fase 2 (+4% para 2-step, None para trial)
    daily_loss_limit_pct: float = 0.04       # Límite pérdida diaria (4% en 10K, 5% en 6K)
    max_drawdown_limit_pct: float = 0.08     # Límite drawdown total (8% en 10K, 10% en 6K)
    min_trading_days: int = 2                # Días mínimos requeridos (2 en 10K, 3 en 6K)
    max_open_risk_pct: float = 0.03          # Regla FundedNext Max Risk At Any Time (3.0%)
    default_risk_per_trade_pct: float = 0.005 # Riesgo institucional por trade (0.50%)
    personal_daily_cap_pct: float = 0.02     # Freno de mano personal (2.0% en 10K, 2.5% en 6K)
    db_file: str = "trading_history.db"      # Archivo SQLite independiente
    login_id: Optional[int] = None           # Login MT5 (ej. 35338849 en 6K trial)
    server: str = "FundedNext-Demo"          # Servidor del broker
    is_trial: bool = False                   # True para Free Trial Challenge (1-step)
    ea_enabled: bool = True                  # Permiso EA
    allow_overnight_weekend: bool = True     # Overnight y fin de semana permitido
    news_profit_cap_pct: float = 0.40        # Regla 40% ganancia en noticias
    funded_profit_split: float = 0.80        # Split al fondear (80%)
    scaled_funded_split: float = 0.90        # Split escalado (90%)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""
    magic_number: int = 505001               # Magic Number MT5 exclusivo para aislar ejecuciones
    allowed_symbols: List[str] = field(default_factory=lambda: ["XAUUSD", "EURUSD", "US500", "USDJPY"])

    # Propiedades calculadas útiles
    @property
    def target_amount_fase1(self) -> float:
        return round(self.initial_balance * self.profit_target_pct, 2)

    @property
    def target_balance_fase1(self) -> float:
        return round(self.initial_balance + self.target_amount_fase1, 2)

    @property
    def target_amount_fase2(self) -> Optional[float]:
        if self.profit_target_phase2_pct is None:
            return None
        return round(self.initial_balance * self.profit_target_phase2_pct, 2)

    @property
    def target_balance_fase2(self) -> Optional[float]:
        if self.target_amount_fase2 is None:
            return None
        return round(self.initial_balance + self.target_amount_fase2, 2)

    @property
    def daily_loss_amount(self) -> float:
        return round(self.initial_balance * self.daily_loss_limit_pct, 2)

    @property
    def max_loss_amount(self) -> float:
        return round(self.initial_balance * self.max_drawdown_limit_pct, 2)

    @property
    def max_loss_floor(self) -> float:
        return round(self.initial_balance * (1.0 - self.max_drawdown_limit_pct), 2)

    @property
    def max_open_risk_amount(self) -> float:
        return round(self.initial_balance * self.max_open_risk_pct, 2)

    @property
    def risk_amount_per_trade(self) -> float:
        return round(self.initial_balance * self.default_risk_per_trade_pct, 2)

    @property
    def personal_daily_cap_amount(self) -> float:
        return round(self.initial_balance * self.personal_daily_cap_pct, 2)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingProfile":
        # Filtrar campos desconocidos para robustez
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def get_default_profiles() -> Dict[str, TradingProfile]:
    """Retorna los perfiles oficiales configurados por defecto."""
    return {
        "stellar_10k_demo": TradingProfile(
            id="stellar_10k_demo",
            name="Stellar 10K Demo",
            account_type="Stellar Lite 2-Step (Evaluation)",
            platform="MT5",
            account_mode="SWAP",
            initial_balance=10000.0,
            profit_target_pct=0.08,             # +8% Fase 1 ($800) -> Meta: $10,800
            profit_target_phase2_pct=0.04,      # +4% Fase 2 ($400) -> Meta: $10,400
            daily_loss_limit_pct=0.04,          # 4% ($400) límite de pérdida diaria
            max_drawdown_limit_pct=0.08,        # 8% ($800) piso fijo en $9,200
            min_trading_days=2,                 # 2 días mínimos por fase
            max_open_risk_pct=0.03,             # 3% riesgo máximo simultáneo ($300)
            default_risk_per_trade_pct=0.005,   # 0.50% por operación ($50)
            personal_daily_cap_pct=0.02,        # 2.0% freno de mano personal ($200)
            db_file="trading_history.db",
            login_id=None,
            server="FundedNext-Demo",
            is_trial=False,
            ea_enabled=True,
            news_profit_cap_pct=0.40,
            funded_profit_split=0.80,
            scaled_funded_split=0.90,
            notes="Evaluación Oficial 2-Step FundedNext Stellar Lite $10,000 USD (cloud.png).",
        ),
        "stellar_6k_trial": TradingProfile(
            id="stellar_6k_trial",
            name="Stellar 6K Trial",
            account_type="Free Trial Challenge (CFDs)",
            platform="MT5",
            account_mode="SWAP",
            initial_balance=6000.0,             # $6,000 USD (1-trial.png / 2-trial.png)
            profit_target_pct=0.05,             # +5.0% Target = $300 en $6K -> Meta: $6,300 (2-trial.png)
            profit_target_phase2_pct=None,      # 1 sola fase / Challenge Free Trial
            daily_loss_limit_pct=0.05,          # 5.0% ($300) límite de pérdida diaria (2-trial.png)
            max_drawdown_limit_pct=0.10,        # 10.0% ($600) piso fijo en $5,400 (2-trial.png)
            min_trading_days=3,                 # 3 días mínimos requeridos (2-trial.png)
            max_open_risk_pct=0.03,             # 3% riesgo máximo simultáneo ($180)
            default_risk_per_trade_pct=0.005,   # 0.50% por trade ($30)
            personal_daily_cap_pct=0.025,       # 2.5% freno de mano personal ($150) -> 50% de margen seguro
            db_file="trading_stellar_6k_trial.db",
            login_id=35338849,                  # Login ID oficial visible en 2-trial.png
            server="FundedNext-Demo",
            is_trial=True,
            ea_enabled=True,
            news_profit_cap_pct=0.40,
            funded_profit_split=0.80,
            scaled_funded_split=0.90,
            notes="Free Trial $6K Challenge MT5 Swap - Login 35338849 (1-trial.png / 2-trial.png).",
        ),
        "ftmo_10k_challenge": TradingProfile(
            id="ftmo_10k_challenge",
            name="FTMO 10K Challenge",
            account_type="FTMO Challenge 2-Step",
            platform="MT5",
            account_mode="SWAP",
            initial_balance=10000.0,            # $10,000 USD (€89 EUR - Plan 10K FTMO.png)
            profit_target_pct=0.10,             # +10.0% Fase 1 ($1,000) -> Meta: $11,000
            profit_target_phase2_pct=0.05,      # +5.0% Fase 2 ($500) -> Meta: $10,500
            daily_loss_limit_pct=0.05,          # 5.0% ($500) límite de pérdida diaria
            max_drawdown_limit_pct=0.10,        # 10.0% ($1,000) drawdown máximo total -> piso fijo $9,000
            min_trading_days=4,                 # 4 días mínimos por fase (Plan 10K FTMO.png)
            max_open_risk_pct=0.03,             # 3% riesgo máximo simultáneo ($300)
            default_risk_per_trade_pct=0.005,   # 0.50% por operación ($50)
            personal_daily_cap_pct=0.025,       # 2.5% freno de mano personal ($250) -> factor 2x vs 5% diario
            db_file="trading_ftmo_10k.db",
            login_id=None,
            server="FTMO-Demo",
            is_trial=False,
            ea_enabled=True,
            allow_overnight_weekend=True,
            news_profit_cap_pct=1.0,            # Sin restricción de 40% News Cap en FTMO
            funded_profit_split=0.80,           # Hasta 90% (80% inicial escalable a 90%)
            scaled_funded_split=0.90,
            notes="Evaluación Oficial 2-Step FTMO Challenge $10,000 USD (€89 EUR) - Plan 10K FTMO.png.",
        ),
    }


class ProfileManager:
    """
    Administrador centralizado de perfiles de trading.
    Carga, almacena y permite alternar sin riesgo entre perfiles independientes.
    """

    def __init__(self, config_path: str = PROFILES_FILE) -> None:
        self.config_path = config_path
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """Crea el archivo profiles.json si no existe con los perfiles predeterminados."""
        if not os.path.exists(self.config_path):
            defaults = get_default_profiles()
            data = {
                "active_profile_id": "stellar_10k_demo",
                "profiles": {pid: prof.to_dict() for pid, prof in defaults.items()},
                "last_switched_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_raw_config(data)
            logger.info(f"[*] Archivo de perfiles inicializado en: {self.config_path}")
        else:
            # Asegurar que ambos perfiles predeterminados existan en el JSON
            data = self._load_raw_config()
            defaults = get_default_profiles()
            updated = False
            for pid, prof in defaults.items():
                if pid not in data.get("profiles", {}):
                    if "profiles" not in data:
                        data["profiles"] = {}
                    data["profiles"][pid] = prof.to_dict()
                    updated = True
            if updated:
                self._save_raw_config(data)

    def _load_raw_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error al leer {self.config_path}: {e}. Usando configuración por defecto.")
            defaults = get_default_profiles()
            return {
                "active_profile_id": "stellar_10k_demo",
                "profiles": {pid: prof.to_dict() for pid, prof in defaults.items()},
                "last_switched_at": datetime.now(timezone.utc).isoformat(),
            }

    def _save_raw_config(self, data: Dict[str, Any]) -> None:
        data["last_switched_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def list_profiles(self) -> List[TradingProfile]:
        """Retorna la lista de todos los perfiles registrados."""
        data = self._load_raw_config()
        profiles = []
        for pid, pdata in data.get("profiles", {}).items():
            try:
                profiles.append(TradingProfile.from_dict(pdata))
            except Exception as exc:
                logger.error(f"Error cargando perfil {pid}: {exc}")
        return profiles

    def get_profile(self, profile_id: str) -> Optional[TradingProfile]:
        """Obtiene un perfil específico por su ID."""
        data = self._load_raw_config()
        pdata = data.get("profiles", {}).get(profile_id)
        if pdata:
            return TradingProfile.from_dict(pdata)
        return None

    def get_active_profile_id(self) -> str:
        """Retorna el ID del perfil actualmente activo."""
        data = self._load_raw_config()
        return data.get("active_profile_id", "stellar_10k_demo")

    def get_active_profile(self) -> TradingProfile:
        """Retorna la instancia del perfil activo."""
        active_id = self.get_active_profile_id()
        prof = self.get_profile(active_id)
        if prof is None:
            # Fallback a stellar_10k_demo
            defaults = get_default_profiles()
            return defaults["stellar_10k_demo"]
        return prof

    def set_active_profile(self, profile_id: str) -> TradingProfile:
        """
        Cambia el perfil activo globalmente.
        Valida que el perfil exista antes de conmutar.
        """
        data = self._load_raw_config()
        if profile_id not in data.get("profiles", {}):
            raise KeyError(
                f"El perfil '{profile_id}' no existe. "
                f"Perfiles disponibles: {list(data.get('profiles', {}).keys())}"
            )
        data["active_profile_id"] = profile_id
        self._save_raw_config(data)
        logger.info(f"[*] Perfil activo cambiado a: {profile_id}")
        return TradingProfile.from_dict(data["profiles"][profile_id])

    def save_profile(self, profile: TradingProfile) -> None:
        """Guarda o actualiza un perfil."""
        data = self._load_raw_config()
        if "profiles" not in data:
            data["profiles"] = {}
        data["profiles"][profile.id] = profile.to_dict()
        self._save_raw_config(data)

    def delete_profile(self, profile_id: str) -> bool:
        """
        Elimina un perfil personalizado.
        Protege los perfiles estándar del sistema ('stellar_10k_demo' y 'stellar_6k_trial').
        """
        if profile_id in ("stellar_10k_demo", "stellar_6k_trial", "ftmo_10k_challenge"):
            raise ValueError(f"No se permite eliminar los perfiles predeterminados del sistema ({profile_id}).")

        data = self._load_raw_config()
        if profile_id == data.get("active_profile_id"):
            raise ValueError("No se puede eliminar el perfil actualmente activo. Conmute a otro perfil primero.")

        if profile_id in data.get("profiles", {}):
            del data["profiles"][profile_id]
            self._save_raw_config(data)
            return True
        return False

    def sync_profile_db(self, profile: TradingProfile) -> Any:
        """
        Garantiza que la base de datos asociada al perfil esté inicializada y sincronizada
        con sus parámetros específicos (capital inicial, metas y límites de pérdida).
        """
        from database import TradingDatabase
        db = TradingDatabase(profile.db_file, profile=profile)
        acc = db.get_account_state()

        # Si el balance inicial en BD no coincide con el perfil o faltan campos, sincronizar
        update_fields: Dict[str, Any] = {}
        if acc.get("profile_id") != profile.id:
            update_fields["profile_id"] = profile.id
        if acc.get("daily_loss_limit_pct") != profile.daily_loss_limit_pct:
            update_fields["daily_loss_limit_pct"] = profile.daily_loss_limit_pct
        if acc.get("profit_target_pct") != profile.profit_target_pct:
            update_fields["profit_target_pct"] = profile.profit_target_pct
        if acc.get("max_drawdown_limit_pct") != profile.max_drawdown_limit_pct:
            update_fields["max_drawdown_limit_pct"] = profile.max_drawdown_limit_pct
        if acc.get("min_trading_days") != profile.min_trading_days:
            update_fields["min_trading_days"] = profile.min_trading_days
        if acc.get("is_trial") != (1 if profile.is_trial else 0):
            update_fields["is_trial"] = 1 if profile.is_trial else 0
        if profile.login_id and acc.get("account_login") != profile.login_id:
            update_fields["account_login"] = profile.login_id

        if update_fields:
            db.update_account_state(**update_fields)

        return db


# Instancia única para importación directa
profile_manager = ProfileManager()


def print_profiles_table(active_id: Optional[str] = None) -> None:
    """Imprime una tabla formateada en consola con todos los perfiles disponibles."""
    if active_id is None:
        active_id = profile_manager.get_active_profile_id()

    profiles = profile_manager.list_profiles()
    sep = "=" * 98
    subsep = "-" * 98

    print(f"\n{sep}")
    print("                    ADMINISTRADOR DE PERFILES - FUNDEDNEXT PROP TRADING")
    print(sep)
    header = f" {'#':<2} {'ID':<18} {'NOMBRE':<18} {'CAPITAL':<11} {'TARGET':<8} {'DAILY':<7} {'MAX DD':<7} {'DÍAS':<7} {'LOGIN MT5':<10} {'ESTADO'}"
    print(header)
    print(subsep)

    for idx, p in enumerate(profiles, start=1):
        is_active = (p.id == active_id)
        status_tag = ">>> [ACTIVO]" if is_active else ""
        login_tag = str(p.login_id) if p.login_id else "---"
        target_tag = f"+{p.profit_target_pct * 100:.0f}%"
        daily_tag = f"-{p.daily_loss_limit_pct * 100:.0f}%"
        max_dd_tag = f"-{p.max_drawdown_limit_pct * 100:.0f}%"
        min_days_tag = f"{p.min_trading_days} d"
        bal_tag = f"${p.initial_balance:,.0f}"

        print(
            f" {idx:<2} {p.id:<18} {p.name:<18} {bal_tag:<11} {target_tag:<8} "
            f"{daily_tag:<7} {max_dd_tag:<7} {min_days_tag:<7} {login_tag:<10} {status_tag}"
        )
    print(f"{sep}\n")


def print_profile_card(profile: TradingProfile) -> None:
    """Imprime una ficha detallada del perfil con todos sus límites y especificaciones."""
    sep = "=" * 78
    subsep = "-" * 78
    print(f"\n{sep}")
    print(f"   FICHA TÉCNICA DEL PERFIL: {profile.name.upper()} ({profile.id})")
    print(sep)
    print(f" • Modelo de Cuenta       : {profile.account_type}")
    print(f" • Plataforma Broker      : {profile.platform} ({profile.account_mode})")
    print(f" • Capital Base           : ${profile.initial_balance:,.2f} USD")
    login_str = f"#{profile.login_id}" if profile.login_id else "No asignado (Configurable)"
    print(f" • Login MT5 Asignado     : {login_str}")
    print(f" • Servidor Broker        : {profile.server}")
    print(f" • Base de Datos SQLite   : {profile.db_file}")
    print(f" • Magic Number MT5       : {profile.magic_number}")
    print(f" • Activos Autorizados    : {', '.join(profile.allowed_symbols)}")
    print(subsep)
    print(" [OBJETIVOS Y REGLAS DE EVALUACIÓN]")
    if profile.is_trial:
        print(f" • Target Challenge       : +{profile.profit_target_pct * 100:.1f}% (${profile.target_amount_fase1:,.2f}) -> Meta: ${profile.target_balance_fase1:,.2f}")
        print(" • Fases de Evaluación    : 1 Sola Fase (Free Trial Challenge)")
    else:
        print(f" • Target Fase 1          : +{profile.profit_target_pct * 100:.1f}% (${profile.target_amount_fase1:,.2f}) -> Meta: ${profile.target_balance_fase1:,.2f}")
        if profile.profit_target_phase2_pct:
            print(f" • Target Fase 2          : +{profile.profit_target_phase2_pct * 100:.1f}% (${profile.target_amount_fase2:,.2f}) -> Meta: ${profile.target_balance_fase2:,.2f}")
        print(f" • Profit Split Fondeada  : {profile.funded_profit_split * 100:.0f}% (Escalable al {profile.scaled_funded_split * 100:.0f}%)")

    print(f" • Días Mínimos Operativos: {profile.min_trading_days} Días")
    print(subsep)
    print(" [LÍMITES INSTITUCIONALES DE RIESGO]")
    print(
        f" • Límite Pérdida Diaria  : {profile.daily_loss_limit_pct * 100:.1f}% "
        f"(${profile.daily_loss_amount:,.2f} sobre balance al inicio de jornada UTC)"
    )
    print(
        f" • Límite Drawdown Total  : {profile.max_drawdown_limit_pct * 100:.1f}% "
        f"(${profile.max_loss_amount:,.2f} estático -> Piso Fijo: ${profile.max_loss_floor:,.2f})"
    )
    print(
        f" • Regla Max Open Risk 3% : 3.0% (${profile.max_open_risk_amount:,.2f} USD "
        f"máximo riesgo simultáneo en mercado)"
    )
    print(
        f" • Freno de Mano Personal : -{profile.personal_daily_cap_pct * 100:.1f}% "
        f"(${profile.personal_daily_cap_amount:,.2f} USD para 100% margen de seguridad)"
    )
    print(
        f" • Riesgo por Operación   : {profile.default_risk_per_trade_pct * 100:.2f}% "
        f"(${profile.risk_amount_per_trade:,.2f} USD por trade institucional)"
    )
    print(f" • Regla Profit Noticias  : Máximo {profile.news_profit_cap_pct * 100:.0f}% de ganancias durante eventos NFP/CPI/FOMC")
    if profile.notes:
        print(subsep)
        print(f" • Notas Oficiales        : {profile.notes}")
    print(f"{sep}\n")

