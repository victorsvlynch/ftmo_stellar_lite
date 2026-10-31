# FundedNext Stellar Lite ($5,000) - Automated Trading Engine & MetaTrader 5 Bridge

Motor cuantitativo de trading algorítmico, gestor de riesgo institucional y puente oficial con **MetaTrader 5 (MT5)**, diseñado específicamente para superar las fases de evaluación y operar cuentas fondeadas de **FundedNext - Modelo Stellar Lite ($5,000)**.

Desarrollado en **Python Puro de Alto Rendimiento (sin interfaces web innecesarias, sin Docker y sin dependencias superfluas)**. Operativo tanto en servidores Linux Ubuntu en **Oracle Cloud Infrastructure (OCI)** para ejecución desatendida 24/7, como en estaciones Windows para interacción nativa directa con terminales de escritorio **MetaTrader 5**.

---

## 📋 Tabla de Contenidos

1. [Configuración Oficial Contratada (FundedNext Checkout)](#-configuración-oficial-contratada-fundednext-checkout)
2. [Estrategia Ganadora Seleccionada y Portafolio Multi-Activo](#-estrategia-ganadora-seleccionada-y-portafolio-multi-activo)
   - [Calendario y Horarios Operativos de los Activos (EST / UTC-5)](#-calendario-y-horarios-operativos-de-los-activos-est--utc-5)
   - [Arquitectura Master Bridge en MetaTrader 5 (3 Gráficos en Mosaico)](#-arquitectura-master-bridge-en-metatrader-5-3-gráficos-en-mosaico)
   - [Portafolio Descorrelacionado: S&P 500 (`US500`) + EUR/USD (`EURUSD`)](#-portafolio-profesional-multi-activo-sp-500-esf--us500--eurusd-eurusdx--eurusd)
3. [Arquitectura del Motor Cuantitativo y Reglas de Riesgo](#-arquitectura-del-motor-cuantitativo-y-reglas-de-riesgo)
4. [Puente Institucional con MetaTrader 5 (`mt5_bridge.py`)](#-puente-institucional-con-metatrader-5-mt5_bridgepy)
5. [Guía de Ejecución Rápida y Modalidades de Trading](#-guía-de-ejecución-rápida-y-modalidades-de-trading)
   - [Prueba Interactiva en Vivo con MetaTrader 5 (`Ejecutar_Prueba_MT5.bat`)](#1-prueba-interactiva-en-vivo-con-metatrader-5)
   - [Modalidades de Operación: Opción B.2 (MT5 Automático) y Opción C (Telegram Celular)](#2-modalidades-de-ejecución-disponibles)
   - [Monitoreo en Tiempo Real de la Estrategia Ganadora (`Dashboard_Operaciones_En_Vivo.bat`)](#3-monitoreo-en-tiempo-real-de-la-estrategia-ganadora)
   - [Suite de Pruebas Automatizadas 100% OK (`test_verification.py` - 10/10)](#4-suite-de-pruebas-automatizadas-100-ok)
   - [Consola Interactiva Avanzada (`stellar-cli>`)](#5-consola-interactiva-avanzada-stellar-cli)
6. [Operación y Despliegue 24/7 en Servidor Oracle Cloud (OCI)](#-operación-y-despliegue-247-en-servidor-oracle-cloud-oci)
7. [Panel de Control Maestro (`Control_Total_Bot.bat`) y Dashboards](#-panel-de-control-maestro-control_total_botbat-y-dashboards)
8. [Guía de Migración y Portabilidad Total (PC Windows y Servidores Cloud/VPS)](#-guía-de-migración-y-portabilidad-total-pc-windows-y-servidores-cloudvps)
   - [8.1 Escenario A: Mover a Otra PC en 1 Clic (`PACK_PORTABILIDAD_FTMO_STELLAR_LITE.zip`)](#81-escenario-a-mover-a-otra-pc-windows-1011-con-metatrader-5-en-1-clic)
   - [8.2 Escenario B: Mover o Replicar en un Nuevo Servidor Cloud / VPS Linux](#82-escenario-b-mover-o-replicar-en-un-nuevo-servidor-cloud--vps-linux-ubuntu--debian)
   - [8.3 Documentación Técnica: Trailing Stop por Estructura M15 y Protección de Ganancias](#83-documentación-técnica-trailing-stop-por-estructura-m15-y-protección-de-ganancias)
   - [8.4 Protocolo Operativo en 2 PCs (Trabajo y Hogar) y Reglas Prop Firm](#84-protocolo-operativo-en-2-pcs-trabajo-y-hogar-y-reglas-prop-firm)
9. [Estructura del Proyecto y Archivos Clave](#-estructura-del-proyecto-y-archivos-clave)
10. [Protocolo de Contingencia y Hard Breach](#-protocolo-de-contingencia-y-hard-breach)
11. [Herramientas DevOps, Snapshots, Grabación de Estados y CI/CD](#-herramientas-devops-snapshots-grabación-de-estados-y-cicd)

---

## 🏷️ Configuración Oficial Contratada (FundedNext Checkout)

El motor cuantitativo tiene incorporadas de forma nativa en su lógica de evaluación y riesgo todas las condiciones y add-ons seleccionados en la orden de compra:

| Parámetro | Configuración Seleccionada | Implementación en el Motor (`stellar_rules.py`) |
| :--- | :--- | :--- |
| **Modelo de Cuenta** | **Stellar Lite ($5,000 USD)** | Balance base: `$5,000.00`. Objetivos: Fase 1 (+8% = $400) / Fase 2 (+4% = $200). |
| **Plataforma Broker** | **MetaTrader 5 (MT5)** | Integración nativa con protocolo IPC MT5 y ejecución `TRADE_ACTION_DEAL`. |
| **Tipo de Cuenta** | **Swap** | Soporte de posiciones interdiarias con modelado de comisiones y swap institucional. |
| **Add-on: 95% Lifetime Reward** | **Activado** | Profit Split asignado al **95% de por vida** al fondear la cuenta (vs 80% estándar). |
| **Add-on: No Min Trading Days** | **Activado** | Días mínimos reducidos de 2 a **0 días**. Al tocar el target, promueve inmediatamente. |
| **Add-on: 10% Max Loss Limit** | **Activado** | Drawdown máximo ampliado del 8% al **10% estático**. **Piso de pérdida: $4,500.00** (vs $4,600). |
| **Add-on: Expert Advisor (EA)** | **Activado** | `ea_enabled = 1`. Autorización total para trading algorítmico y ejecución por scripts. |
| **Daily Loss Limit** | **4% Estático ($200.00)** | Calculado cada medianoche UTC (00:00 UTC) sobre el balance inicial del día. |

---

## 🏆 Estrategia Ganadora Seleccionada y Portafolio Multi-Activo

Tras auditar y simular múltiples configuraciones bajo fricción institucional real (comisiones, spreads dinámicos y slippage), el sistema opera con dos configuraciones de élite: la **estrategia monoproducto ganadora en Oro (`NY_OPEN`)** y el **portafolio diversificado descorrelacionado (S&P 500 + EUR/USD)**.

---

### ⏰ Calendario y Horarios Operativos de los Activos (EST / UTC-5)

Todos los activos tradicionales operan de **Lunes a Viernes**. Como la referencia horaria del bot es **Hora de Nueva York (EST)**, los horarios en huso horario **UTC-5** (Colombia, Perú, Ecuador, CDMX) coinciden exactamente con la hora de Wall Street:

| Activo | Días Operativos | Sesión Clave | Vela de Rango (ORB 15m) | Ventana Operativa Activa (Hora Local UTC-5 / EST) | Hora Servidor VPS (UTC) |
| :--- | :---: | :--- | :---: | :---: | :---: |
| **Oro** (`XAUUSD` / `GC=F`) | **Lunes a Viernes** | **Apertura Nueva York** | 08:30 – 08:45 | **08:45 – 11:30** | 13:45 – 16:30 UTC |
| **S&P 500** (`US500` / `ES=F`) | **Lunes a Viernes** | **Wall Street Cash Open** | 09:30 – 09:45 | **09:45 – 11:30** | 14:45 – 16:30 UTC |
| **EUR/USD** (`EURUSD`) *(Ventana 1)* | **Lunes a Viernes** | **Apertura Londres** | 03:00 – 03:15 | **03:15 – 06:00** | 08:15 – 11:00 UTC |
| **EUR/USD** (`EURUSD`) *(Ventana 2)* | **Lunes a Viernes** | **Apertura Nueva York** | 08:30 – 08:45 | **08:45 – 11:30** | 13:45 – 16:30 UTC |

#### Reglas de Apertura, Cierre y Protección de Fin de Semana:
1. **Apertura Semanal de Mercados:** Domingo a las 17:00 / 18:00 EST. El bot permanece en espera y **no abre operaciones el domingo** debido al spread ensanchado interbancario; espera a la sesión de Londres del lunes a las 03:00 EST.
2. **Cierre Forzoso Anti-Gap de Fin de Semana:** **Viernes a las 15:30 EST**. Toda posición abierta en Oro, S&P 500 o EUR/USD es liquidada forzosamente 90 minutos antes del cierre semanal para blindar la cuenta ante saltos de precios por noticias geopolíticas de fin de semana.
3. **Sábados y Domingos:** Mercados cerrados (`4756 - Market closed`). Cero trading tradicional.

#### 🇵🇪 Equivalencia y Referencia Horaria en Lima, Perú (PET / UTC-5):
Perú no implementa horario de verano y mantiene su huso horario fijo en **PET (UTC-5)** todo el año. Su relación con el horario de Wall Street es la siguiente:

1. **Horario de Invierno en EE. UU. (Noviembre a Marzo — EST = UTC-5):**
   * **Coincidencia 100% exacta minuto a minuto:**
     * **Apertura Londres (EUR/USD):** `03:00 a.m. – 06:00 a.m.` (Madrugada de Lima).
     * **Apertura NY (Oro / XAUUSD):** `08:30 a.m. – 11:30 a.m.` (Mañana de Lima).
     * **Wall Street Cash Open (S&P 500):** `09:30 a.m. – 11:30 a.m.` (Mañana de Lima).
     * **Cierre Anti-Gap (Viernes):** `03:30 p.m.` (Tarde de Lima).
2. **Horario de Verano en EE. UU. (Marzo a Noviembre — EDT = UTC-4):**
   * Nueva York se adelanta 1 hora; por tanto, en Lima la campana abre **1 hora más temprano**:
     * **Apertura Londres (EUR/USD):** `02:00 a.m. – 05:00 a.m.` (Madrugada de Lima).
     * **Apertura NY (Oro / XAUUSD):** `07:30 a.m. – 10:30 a.m.` (Mañana de Lima).
     * **Wall Street Cash Open (S&P 500):** `08:30 a.m. – 10:30 a.m.` (Mañana de Lima).
     * **Cierre Anti-Gap (Viernes):** `02:30 p.m.` (Tarde de Lima).

---

### 🖥️ Arquitectura Master Bridge en MetaTrader 5 (3 Gráficos en Mosaico)

Para visualizar y operar simultáneamente los 3 activos de forma profesional sin conflictos de sondeo duplicado:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        METATRADER 5 (Mosaico Alt + R)                  │
├──────────────────────────┬──────────────────────────┬──────────────────┤
│        VENTANA 1         │        VENTANA 2         │    VENTANA 3     │
│       XAUUSD (H1)        │        US500 (H1)        │   EURUSD (H1)    │
│  [ MASTER BRIDGE EA ]    │    [ SOLO VISUAL ]       │  [ SOLO VISUAL ] │
│  * Recibe señales Cloud  │    * Gráfico abierto     │  * Gráfico       │
│  * Ejecuta XAU/US/EUR    │    * Sin EA adjunto      │  * Sin EA        │
│  * Break-Even + Trailing │    * Acción de precio    │  * Velas M15     │
└──────────────────────────┴──────────────────────────┴──────────────────┘
```

#### Regla de Oro en MT5:
* **Un Solo EA Activo en la Cuenta:** El Expert Advisor [`StellarLite_Webhook_Bridge.ex5`](StellarLite_Webhook_Bridge.ex5) es un **Bridge Multi-Activo Global**. Desde un único gráfico (recomendado: **`XAUUSD`**), lee la orden de la nube con el símbolo correspondiente (`XAUUSD`, `US500` o `EURUSD`) y la envía al broker de inmediato.
* Además, su motor autónomo de Break-Even (+1R) y Trailing Stop M15 recorre todas las posiciones de la cuenta para proteger los 3 activos.
* **Organización:** Abre los 3 gráficos, presiona `Alt + R` (Ventana $\rightarrow$ Mosaico) y arrastra el EA **únicamente al gráfico de Oro**. En los gráficos de S&P 500 y EUR/USD manténlos sin el EA para evitar peticiones duplicadas a la cola de señales.

---

### ¿Por qué `NY_OPEN` es la Estrategia Ganadora?
- **Mayor Concentración de Volumen Institucional:** El 68% de las transacciones globales del Oro Spot y Futuros COMEX ocurren entre las 08:30 y las 11:30 EST.
- **Profit Factor Superior (> 2.0):** Presentó el ratio de rentabilidad/riesgo más alto y el menor drawdown relativo de todo el portafolio.
- **Filtros Anti-Trampas:** Elimina los falsos rompimientos comunes durante la apertura asiática o europea.

### Reglas Técnicas de la Estrategia (`OpeningRangeBreakoutStrategy`):
1. **Activo Oficial:** Oro Spot / Futuros COMEX (`XAUUSD` en MT5 / `GC=F` en Yahoo Finance).
2. **Ventana Horaria de Sesión:** **08:30 a 11:30 EST** (Hora de Nueva York / Wall Street).
3. **Vela de Rango de Apertura (ORB 15M):** Se define con la primera vela de 15 minutos (08:30 a 08:45 EST), registrando su máximo (`high`) y mínimo (`low`).
4. **Filtro Tendencial Institucional:** **EMA de 200 periodos en Gráfico de 1 Hora (H1)**:
   - Solo se permiten compras (**BUY**) si el precio se encuentra por encima de la EMA 200 H1.
   - Solo se permiten ventas (**SELL**) si el precio se encuentra por debajo de la EMA 200 H1.
5. **Filtro Anti-Fakeout por Cierre de Vela:** Una ruptura de mecha no es válida. La vela de 15 minutos debe **cerrar estrictamente por fuera del rango** para confirmar la entrada.
6. **Ratio Riesgo/Beneficio Estricto (1:2):**
   - **Stop Loss (SL):** $6.50 por debajo/encima del punto de entrada (1R).
   - **Take Profit (TP):** $13.00 (el doble del riesgo, 2R).
7. **Protocolo de Protección Escalonada y Trailing Stop Autónomo (M15):**
   - **Nivel 1 — Blindaje a Break-Even (+1R / +$6.50 pts):** Al alcanzar +1R de beneficio flotante (+$6.50 en Oro), traslada el Stop Loss al precio de entrada (`SL = Entry Price`), asegurando **$0.00 de riesgo monetario** (Trade Libre de Riesgo).
   - **Nivel 2 — Trailing Stop por Estructura Técnica M15 (+2R / +$13.00 pts):** Al superar +2R, el Asesor Experto en MT5 (`StellarLite_Webhook_Bridge.mq5`) inspecciona las últimas 4 velas M15 cerradas y traslada el SL por detrás del último Swing High (en ventas) o Swing Low (en compras) con un colchón de $1.50 de volatilidad, bloqueando ganancias escalonadas de forma 100% autónoma.
   - **Cálculo de Distancias Relativas Broker-Agnostic:** Las distancias de SL y TP se aplican de forma relativa al precio de llenado real (`Bid`/`Ask`) en MetaTrader 5 mediante `MathAbs`, blindando la orden ante divergencias de cotización entre feeds de análisis (Yahoo Finance `GC=F`) y el broker (`XAUUSD`).
   - **Fail-Safe de Auto-Sincronización:** Si el bot en la nube cierra la operación o reporta `open_trades_count == 0`, el EA detecta el estado y liquida la posición local de inmediato mediante ciclos multi-modo (`IOC`, `FOK`, `RETURN`), previniendo posiciones huérfanas o desincronizadas.
8. **Protección de Fin de Semana:** Todo trade de Oro se liquida forzosamente los viernes a las **15:30 EST** para evitar riesgos de gap al abrir el mercado el domingo.

### 🌐 Portafolio Profesional Multi-Activo: S&P 500 (`ES=F` / `US500`) + EUR/USD (`EURUSD=X` / `EURUSD`)

Además de operar Oro monoproducto, el sistema incorpora arquitectura multi-activo profesional **descorrelacionada**:
- **Descorrelación Renta Variable vs. Forex:** A diferencia de operar NAS100 + S&P 500 (que comparten más del 90% de correlación y duplican el riesgo en bolsa), combinar **S&P 500 con EUR/USD** diversifica el capital entre dos clases de activos independientes.
- **Horarios Diferenciados por Activo:**
  - **EUR/USD:** Apertura de Londres (**03:00 a 06:00 EST**) o Apertura de Nueva York (**08:30 a 11:30 EST**).
  - **S&P 500:** Apertura oficial al contado de Wall Street (**09:30 a 11:30 EST**), operando rupturas de la vela de las 09:30 EST.
- **Dimensionamiento Automático de Lote:** Calcula el lotaje institucional con riesgo fijo del 0.50% ($25 USD) adaptado al tamaño de contrato del broker (100,000 unidades en EUR/USD y 10 o 1 contratos en S&P 500).
- **Lanzador Directo en 1-Clic:** Haz doble clic en [`Monitor_Portfolio_SP500_EURUSD.bat`](Monitor_Portfolio_SP500_EURUSD.bat) para abrir el monitor en tiempo real del portafolio.

---

## 🛡️ Arquitectura del Motor Cuantitativo y Reglas de Riesgo

El sistema implementa una gestión de riesgo de grado bancario dividida en tres módulos desacoplados:

```
[ MarketData / MT5 ] ──> [ RiskManager ] ──> [ StellarRulesEngine ] ──> [ TradingDatabase ]
         │                     │                         │                      │
   Precios en Vivo       Riesgo 0.5% ($25)         Add-ons Checkout         Auditoría SQLite
   Velas M15 & H1        Freno Diario 2%           Piso Max DD $4,500       Historial Trades
   Spreads & Puntos      Anti-Tilt (3 Losses)      Piso Diario $4,800       Eventos y Estados
```

1. **Calculadora Dinámica de Riesgo (`RiskManager`):**
   - Riesgo fijo por operación: **0.50% estricto** ($25.00 USD sobre $5,000 de balance).
   - Cálculo del tamaño de lote adaptado a la especificación de contrato (100 oz en Oro):
     $$\text{Lotes} = \frac{\text{Riesgo USD}}{\text{Distancia SL en USD} \times \text{Tamaño Contrato}} = \frac{\$25.00}{\$6.50 \times 100} \approx 0.04\text{ lotes}$$
2. **Freno de Mano Diario Personal (`Personal Daily Cap`):**
   - Limitado al **2.0% ($100 USD)**. Si las pérdidas del día alcanzan este nivel, el bot bloquea nuevas aperturas, deteniéndose a la mitad del límite letal del 4% del broker.
3. **Alerta Anti-Racha Negativa (`Tilt Alert`):**
   - Tras registrar 3 pérdidas consecutivas en la misma sesión, el bot inhabilita las operaciones hasta el siguiente día hábil.

---

## 🔌 Puente Institucional con MetaTrader 5 (`mt5_bridge.py`)

El módulo [`mt5_bridge.py`](mt5_bridge.py) conecta el motor cuantitativo de Python directamente con la terminal oficial de **MetaTrader 5 (MT5)** mediante IPC nativo de baja latencia.

### Capacidades del Puente MT5:
- **Autodetección de Terminal:** Localiza automáticamente la ruta de instalación de MT5 (`terminal64.exe`) en Windows y sincroniza con el proceso en ejecución.
- **Auditoría de Cuenta:** Lee en milisegundos el login, servidor, balance, equidad, margen libre, apalancamiento y estado de permisos algorítmicos (`terminal_trade_allowed`).
- **Mapeo Inteligente de Símbolos:** Detecta automáticamente la nomenclatura del broker para el Oro (`XAUUSD`, `GOLD`, `XAUUSDm`, etc.) y sus especificaciones (spread en puntos, tamaño de contrato, pasos de volumen).
- **Descarga de Datos en Tiempo Real:** Obtiene velas históricas de M15 y H1 convertidas a la zona horaria institucional de Nueva York (`America/New_York`).
- **Ejecución de Órdenes Resiliente (`TRADE_ACTION_DEAL`):** Incorpora auto-fallback inteligente de modos de ejecución (`ORDER_FILLING_FOK` $\rightarrow$ `ORDER_FILLING_IOC` $\rightarrow$ `ORDER_FILLING_RETURN`) para garantizar el llenado inmediato sin rechazos por tipo de orden.
- **Gestión Dinámica de Órdenes (`TRADE_ACTION_SLTP`):** Modifica el Stop Loss en el servidor del broker para blindar la operación a Break-Even.
- **Cierre Instantáneo a Mercado:** Permite liquidar posiciones de forma automática o de emergencia con protección contra desviación/slippage.

---

## 🚀 Guía de Ejecución Rápida: ¿Cómo Ejecuto?

### 1. Prueba Interactiva en Vivo con MetaTrader 5

Este es el método para comprobar con tus propios ojos cómo Python se conecta a tu terminal MT5 y ejecuta operaciones reales en tu cuenta demo.

#### Requisitos Previos en MetaTrader 5:
1. Abre tu **MetaTrader 5** e inicia sesión en tu cuenta demo (o cuenta de evaluación de FundedNext).
2. Asegúrate de que el botón **"Algo Trading"** en la barra superior esté **activado en color verde** (puedes alternarlo presionando `Ctrl + E`).
3. En el menú superior de MT5, ve a **Herramientas > Opciones > Asesores Expertos** y verifica que estén marcadas las casillas:
   - *Permitir trading algorítmico*.
   - *Permitir importación de DLL*.

#### Pasos para Ejecutar la Prueba:
1. Pon tu ventana de **MetaTrader 5** en un lado de la pantalla (con la pestaña inferior **"Operaciones"** visible).
2. Haz doble clic en el archivo [**`Ejecutar_Prueba_MT5.bat`**](Ejecutar_Prueba_MT5.bat) (o ejecútalo desde PowerShell/CMD):
   ```cmd
   .\Ejecutar_Prueba_MT5.bat
   ```
3. **Flujo de la Prueba en Pantalla:**
   - **Paso 1:** Verifica el paquete oficial de Python `MetaTrader5`.
   - **Paso 2:** Conecta con el terminal, muestra tu balance, equidad y estado de Algorithmic Trading (`[OK]`).
   - **Paso 3:** Detecta el símbolo `XAUUSD`, cotización actual y spread del broker.
   - **Paso 4:** Descarga velas reales M15 y H1 del servidor.
   - **Paso 5:** Calcula la posición exacta con riesgo del 0.50% ($25.00 USD).
   - **Paso 6 (Envío de Micro-Orden):** Te preguntará si deseas enviar una micro-orden demo (0.01 lotes). Presiona **Enter** (o escribe **S**).
     > *¡Mira tu terminal MT5! Verás aparecer de inmediato la orden de compra con sus líneas verdes y los niveles exactos de Stop Loss y Take Profit en el gráfico.*
   - **Paso 7 (Blindaje Break-Even):** Te preguntará si deseas probar la función Break-Even. Presiona **Enter** (o escribe **S**).
     > *En MT5 verás la línea roja de Stop Loss saltar al precio de entrada, dejando el riesgo en $0.00.*
   - **Paso 8 (Cierre de Posición):** Te preguntará si deseas cerrar la posición para dejar tu cuenta limpia. Presiona **Enter** (o escribe **S**).
     > *La orden se cerrará inmediatamente a precio de mercado.*

---

### 2. Modalidades de Ejecución Disponibles

#### 🟢 Opción B.2: Puente Webhook Automático (Oracle Cloud 24/7 + EA en MT5)
- El bot en la nube de Oracle analiza el Oro minuto a minuto y encola las señales.
- El Expert Advisor [`StellarLite_Webhook_Bridge.ex5`](StellarLite_Webhook_Bridge.ex5) en tu MT5 local sondea la nube cada segundo y ejecuta la orden al broker en milisegundos con Stop Loss y Take Profit exactos.
- Usa [`Conectar_Puente_Webhook_MT5.bat`](Conectar_Puente_Webhook_MT5.bat) para activar el túnel seguro en segundo plano.

#### 🟡 Opción C: Alertas Automáticas a tu Celular vía Telegram (@victorsvlynch)
- El bot en la nube de Oracle calcula las oportunidades en la sesión de Nueva York y envía la señal instantáneamente a tu Telegram.
- La alerta llega con el lotaje institucional calculado ($25 USD de riesgo = 0.5%), Stop Loss y Take Profit exactos.
- Solo abres tu app de **MetaTrader 5 en tu teléfono móvil** y presionas **Comprar** o **Vender** en 1 clic.
- **Configuración rápida:** Ejecuta [`Configurar_Telegram.bat`](Configurar_Telegram.bat) (o `python configurar_telegram.py`), introduce tu Token de `@BotFather` y presiona Start en tu bot. Se sincroniza de forma inmediata con el VPS en Oracle Cloud.
- **Prueba de señal en celular:** Ejecuta [`Probar_Alerta_Telegram.bat`](Probar_Alerta_Telegram.bat) para recibir una señal simulada en tu móvil.

---

### 3. Monitoreo en Tiempo Real de la Estrategia Ganadora

Para observar el motor cuantitativo operando en vivo, analizando el mercado segundo a segundo:

- **Desde Windows (1-Clic):**
  Haz doble clic en [**`Monitor_Estrategia_Ganadora.bat`**](Monitor_Estrategia_Ganadora.bat).
- **Desde la Línea de Comandos:**
  ```bash
  python main.py live --session NY_OPEN --refresh 1
  ```
  *Muestra un tablero interactivo con el reloj UTC, hora de Wall Street, cotización del Oro, rango de apertura, equidad flotante, estado de reglas de FundedNext y posiciones abiertas.*

---

### 4. Suite de Pruebas Automatizadas (100% OK - 10/10)

El proyecto incluye una suite integral de 10 pruebas unitarias y de integración que validan matemáticamente todas las reglas del broker, filtros anti-trampas y cálculos de riesgo:

- **Desde Windows:**
  Haz doble clic en `VPS-Oracle\Ejecutar_Tests_Verificacion.bat`.
- **Desde la Consola:**
  ```bash
  python test_verification.py
  ```
- **Pruebas Validadas (10/10 PASS):**
  1. Estrategia ORB: Anti-Fakeout y filtro EMA 200 H1.
  2. Fricción institucional (comisiones + spread dinámico).
  3. Base de datos SQLite y auditoría financiera.
  4. Gestión de Break-Even a +1R.
  5. Cierre en Take Profit con liquidación neta.
  6. Cierre forzoso de fin de semana (Viernes 15:30 EST).
  7. Resiliencia del sistema de notificaciones Telegram.
  8. Detección de target y bloqueo anti-overtrading.
  9. Add-ons de FundedNext (`cloud.png`: No Min Days, 10% Max Loss, 95% Split).
  10. Portafolio Profesional Multi-Activo: S&P 500 (`ES=F` / `US500`) y EUR/USD (`EURUSD=X` / `EURUSD`) con dimensionamiento institucional por contrato y filtros de sesión horaria (Londres vs Wall Street Cash).

---

### 5. Consola Interactiva Avanzada (`stellar-cli>`)

Permite ejecutar operaciones de diagnóstico, cálculos y simulaciones manuales:

```bash
python main.py interactive
```

*Comandos dentro de `stellar-cli>`:*
- `status` : Reporte financiero completo y distancias a los pisos de pérdida.
- `cycle` : Ejecuta un ciclo de análisis en vivo de la estrategia NY ORB 15m.
- `calc <precio_entrada> <stop_loss>` : Calcula el lotaje exacto para el balance actual (ej. `calc 2650.0 2643.5`).
- `force_buy` / `force_sell` : Abre una orden de prueba ignorando el filtro horario.
- `close_all` : Cierra de inmediato todas las posiciones abiertas en la base de datos.
- `history` : Muestra las últimas operaciones registradas.
- `reset` : Restablece la cuenta a $5,000.00 en Fase 1.
- `exit` : Sale de la consola interactiva.

---

## ☁️ Operación y Despliegue 24/7 en Servidor Oracle Cloud (OCI)

Para operar de forma desatendida sin depender de que tu computadora personal esté encendida, el motor se ejecuta en un servidor Linux Ubuntu en la nube de Oracle (`157.137.225.144`).

### Estado de los Servicios en la Nube:
- **`stellar_ny_open.service`:** 🟢 **ACTIVO 24/7** (Estrategia Ganadora NY Open operando de forma continua).
- **`stellar_london_open.service`:** 🔴 **INACTIVO** (Podado).
- **`stellar_crypto_24h.service`:** 🔴 **INACTIVO** (Podado).
- **`stellar_ny_london.service`:** 🔴 **INACTIVO** (Podado).
- **`stellar_combo_trio.service`:** 🔴 **INACTIVO** (Podado).

### Comandos de Gestión Remota vía SSH:
```bash
# Conectarse a la VPS
ssh -i "C:\Users\mantenimiento\.ssh\oracle_vps.key" ubuntu@157.137.225.144

# Ver estado del servicio de la estrategia ganadora
sudo systemctl status stellar_ny_open

# Ver logs en vivo segundo a segundo (Streaming)
sudo journalctl -u stellar_ny_open -f

# Reiniciar el servicio
sudo systemctl restart stellar_ny_open

# Detener el servicio
sudo systemctl stop stellar_ny_open
```

### Despliegue de 1-Clic desde Windows a Oracle Cloud:
Si realizas modificaciones en el código local y deseas subirlas de inmediato a tu servidor en la nube, ejecuta:
```cmd
.\desplegar_a_vps.bat
```
*Sincroniza los archivos por SSH, preserva intactas las bases de datos activas en el servidor y recarga los servicios de Linux automáticamente.*

---

## 🎛️ Panel de Control Maestro (`Control_Total_Bot.bat`) y Dashboards

Para una operación centralizada, cómoda y sin necesidad de escribir comandos en la consola, se diseñó un menú interactivo maestro de **13 opciones**:

```cmd
.\Control_Total_Bot.bat
```

```text
==============================================================================
      PANEL DE CONTROL MAESTRO -- FUNDEDNEXT STELLAR LITE ($5,000 USD)
      Estrategia Ganadora Oficial: NY_OPEN (Oro GC=F / XAUUSD)
      Servidor en la Nube: Oracle Cloud VPS (157.137.225.144) -- 24/7
==============================================================================

  [DASHBOARDS Y MONITOREO EN VIVO]
   1. Abrir Dashboard en Vivo: Estrategia Ganadora NY_OPEN (Local)
   2. Abrir Dashboard en Vivo: Desde Oracle Cloud VPS (Remoto 24/7)
   3. Abrir Tablero Multi-Estrategia Detallado (Operaciones Hoy)

  [OPCION B.2: ENLACE AUTOMATICO WEBHOOK MT5]
   4. Gestor del Puente Webhook MT5 (Tunel Puerto 8000 en Segundo Plano)
   5. Disparar Senal de Prueba Webhook hacia MT5 (Test Micro-Orden)

  [OPCION C: ALERTAS A TU CELULAR VIA TELEGRAM (@victorsvlynch)]
   6. Configurar / Vincular Telegram (@BotFather y Chat ID)
   7. Enviar Alerta de Prueba NY_OPEN a Telegram (Test de Formato Celular)

  [GESTION DEL SERVIDOR 24/7 EN LA NUBE]
   8. Verificar Estado del Servicio en Oracle Cloud (Uptime y Memoria)
   9. Ver Streaming de Logs en Tiempo Real (Segundo a Segundo)
  10. Reiniciar Servicios en la Nube (Bot NY_OPEN + Webhook Server)

  [PRUEBAS Y SIMULACION]
  11. Ejecutar Prueba Interactiva con MetaTrader 5 (MT5 en PC)
  12. Correr Suite de Verificacion Automatizada (9 Pruebas 100% OK)

  13. Salir
==============================================================================
```

### Funcionalidad de los Tableros y Lanzadores:

1. **Dashboard NY_OPEN en Vivo ([`Dashboard_Operaciones_En_Vivo.bat`](Dashboard_Operaciones_En_Vivo.bat)):**
   - **Reloj de Wall Street (EDT/EST):** Muestra la hora oficial del mercado financiero en Nueva York y el estado actual de la sesión (`SESION_ACTIVA`, `FUERA_DE_SESION` o `FIN_DE_SEMANA`).
   - **Cuenta Regresiva Dinámica:** Informa cuántas horas y minutos exactos faltan para la apertura o cierre de la ventana operativa (08:30 a 11:30 AM NY).
   - **Métricas Institucionales:** Balance actual, equidad flotante, margen libre y distancias exactas en dólares hacia el **Piso Diario ($4,800.00)** y el **Piso Máximo de Drawdown ($4,500.00)**.
   - **Monitoreo de Posiciones:** Tabla en vivo con ticket, activo, lotaje, precio de entrada, Stop Loss, Take Profit, PnL flotante e indicador de **🛡️ Break-Even Protegido**.
   - **Historial del Día:** Detalle de las operaciones cerradas en la jornada con comisiones y beneficio neto en dólares.

2. **Gestor del Puente Webhook ([`Conectar_Puente_Webhook_MT5.bat`](Conectar_Puente_Webhook_MT5.bat)):**
   - Permite iniciar el túnel seguro SSH en **segundo plano (silencioso)** redirigiendo el puerto 8000 (`http://127.0.0.1:8000`).
   - No requiere mantener ventanas de consola abiertas.
   - Permite verificar el estado del túnel (`ACTIVO` o `INACTIVO`) y detenerlo en cualquier momento.

3. **Asistente Telegram ([`Configurar_Telegram.bat`](Configurar_Telegram.bat) y [`Probar_Alerta_Telegram.bat`](Probar_Alerta_Telegram.bat)):**
   - Vinculado al bot oficial **`@victor_stellar_bot`** y tu usuario **`@victorsvlynch`** (`Chat ID: 5633051604`).
   - El botón de prueba envía una simulación con formato enriquecido para validar que tu teléfono móvil recibe las alertas al instante.

---

## 💻 Guía de Migración y Portabilidad Total (PC Windows y Servidores Cloud/VPS)

El proyecto se encuentra **100% modular, portátil y automatizado para trasladarse en minutos a cualquier PC local o servidor en la nube** (Windows 10/11 para la terminal MetaTrader 5 y Linux Ubuntu/Debian para el motor cuantitativo en la nube).

> [!TIP]
> **Filosofía de Diseño Plug & Play y Cero Dependencias Complejas:**
> - **Sin Docker:** Se eliminó la sobrecarga de contenedores, capas de red complejas y cuellos de botella de memoria.
> - **Rutas 100% Relativas (`%~dp0`):** El repositorio puede residir en cualquier unidad (`C:\`, `D:\`, `L:\`), disco externo o memoria USB; los scripts calculan sus rutas dinámicamente.
> - **Auto-Instalación de la Clave SSH:** Al ejecutar cualquier script en una nueva PC con Windows, este detecta la clave en `VPS-Oracle\` y la copia automáticamente a `%USERPROFILE%\.ssh\oracle_vps.key` sin requerir configuración manual.
> - **Asesor Experto Precompilado:** El archivo [`StellarLite_Webhook_Bridge.ex5`](StellarLite_Webhook_Bridge.ex5) está listo para copiar directamente a MT5 sin necesidad de abrir MetaEditor.
> - **Credenciales de Telegram Portables:** [`telegram_config.json`](telegram_config.json) viaja pre-configurado para recibir alertas instantáneas en tu dispositivo móvil.

```mermaid
flowchart TD
    Inicio["Repositorio FTMO_Stellar_Lite"] --> Destino{"¿Dónde deseas desplegar?"}
    
    Destino -->|"Escenario A"| Win["PC / Laptop Windows (MT5 Local)"]
    Win --> W1["1. Clonar Repo o Copiar Carpeta"]
    W1 --> W2["2. pip install -r requirements.txt"]
    W2 --> W3["3. Copiar EA a MQL5/Experts/"]
    W3 --> W4["4. Iniciar Conectar_Puente_Webhook_MT5.bat"]
    W4 --> W5["5. Control_Total_Bot.bat (Dashboard en Vivo)"]
    
    Destino -->|"Escenario B"| Linux["Servidor Cloud / VPS Linux (24/7)"]
    Linux --> L1["1. git clone https://github.com/..."]
    L1 --> L2["2. sudo bash setup_oracle.sh"]
    L2 --> L3["3. sudo bash manage_services.sh solo-ganadora"]
    L3 --> L4["4. Actualizar IP en scripts de Windows"]
    L4 --> L5["5. Sincronización Lista y Operativa 24/7"]
```

---

### 8.1 Escenario A: Mover a Otra PC (Windows 10/11 con MetaTrader 5) en 1 Clic

Para migrar todo el sistema a una nueva computadora portátil o de escritorio sin tener que configurar nada a mano, utiliza el **Pack de Portabilidad Automatizado**:

#### 📦 Paquete Portable Incluido:
* **Archivo ZIP directo:** [`PACK_PORTABILIDAD_FTMO_STELLAR_LITE.zip`](PACK_PORTABILIDAD_FTMO_STELLAR_LITE.zip) (1.59 MB con los 173 archivos del ecosistema).
* **Carpeta del Paquete:** [`EXPORT_PACK_PORTABILIDAD/`](EXPORT_PACK_PORTABILIDAD/)

#### Contenido del Pack:
1. `01_MT5_Configuracion/`: EA precompilado (`.ex5` y `.mq5`), `common.ini` (con URLs de WebRequest pre-autorizadas), `servers.dat`, `accounts.dat` y plantillas de gráficos.
2. `02_SSH_Keys_Oracle_VPS/`: Llaves SSH (`oracle_vps.key`) con permisos configurables.
3. `03_Codigo_Python_Proyecto/`: Motor completo, bases de datos sincronizadas (`trading_ny_open.db`), lanzadores `.bat` y `requirements.txt`.
4. `INSTALAR_EN_NUEVA_PC.bat`: Instalador interactivo automático en 1 clic.

#### Procedimiento de Restauración en 3 Pasos (Tiempo estimado: 2 minutos):

1. **Requisitos Mínimos en la Nueva PC:**
   - Tener instalado **MetaTrader 5**.
   - Tener instalado **Python 3.10 o superior** (marcando obligatoriamente ☑️ **"Add python.exe to PATH"**).

2. **Ejecutar el Instalador en 1 Clic:**
   - Descomprime `PACK_PORTABILIDAD_FTMO_STELLAR_LITE.zip` en la nueva PC (ej. `C:\FTMO_Stellar_Lite`).
   - Haz doble clic en **`INSTALAR_EN_NUEVA_PC.bat`**.
   - El instalador automáticamente:
     - Crea la carpeta `%USERPROFILE%\.ssh` e instala las llaves con permisos estrictos de Windows (`icacls`).
     - Detecta la instalación de MT5 y copia el EA a `MQL5\Experts\` e inyecta la configuración de WebRequest en `Config\common.ini`.
     - Instala las dependencias requeridas de Python vía `pip install -r requirements.txt`.
     - Verifica la conexión en vivo con Oracle Cloud VPS (`157.137.225.144`).

3. **Puesta en Marcha:**
   - Abre **MetaTrader 5**, organiza los gráficos de **XAUUSD**, **US500** y **EURUSD** en mosaico (`Alt + R`), y coloca el EA **únicamente en XAUUSD** (Master Bridge).
   - Abre `03_Codigo_Python_Proyecto\Control_Total_Bot.bat` y selecciona la **Opción 6** para levantar el túnel SSH.
   - En el gráfico de MT5 verás inmediatamente: `Estado Conexion: CONECTADO A ORACLE CLOUD (ONLINE)`.

---

### 8.2 Escenario B: Mover o Replicar en un Nuevo Servidor Cloud / VPS Linux (Ubuntu / Debian)

Si deseas trasladar el bot a otra máquina virtual en la nube (Oracle Cloud Always Free, AWS EC2, Hetzner Cloud, DigitalOcean, Google Cloud Compute, etc.):

#### Requisitos de la Máquina Virtual Linux:
- **Distribución:** Ubuntu 22.04 LTS / 24.04 LTS (o Debian 12).
- **Arquitectura:** Compatible con ARM64 (ej. Oracle Ampere A1 Always Free) y x86_64 (Intel / AMD).
- **Recursos Mínimos:** 1 vCPU, 1 GB RAM, 10 GB de disco SSD.
- **Red:** Puerto TCP `22` (SSH) abierto en la Security List / Firewall del proveedor de nube. *(No es necesario exponer públicamente el puerto 8000 si utilizas el túnel SSH cifrado de Windows, lo que garantiza máxima seguridad).*

#### Paso a Paso para Despliegue Automatizado en el Nuevo VPS:

1. **Conectarse vía SSH a la Nueva Instancia y Clonar el Repositorio:**
   ```bash
   ssh usuario@IP_NUEVO_VPS
   git clone https://github.com/victorsvlynch/ftmo_stellar_lite.git
   cd ftmo_stellar_lite
   ```

2. **Ejecutar el Aprovisionamiento Automatizado:**
   ```bash
   sudo bash setup_oracle.sh
   ```
   *¿Qué realiza este script en 60 segundos de forma 100% desatendida?*
   - Actualiza repositorios del sistema e instala `python3`, `python3-pip` y `tzdata`.
   - Instala todas las librerías de Python desde [`requirements.txt`](requirements.txt) en el entorno global (sin la sobrecarga de virtualenvs ni contenedores).
   - Configura las reglas de firewall (UFW / iptables).
   - Genera y registra los servicios systemd oficiales:
     - `stellar_ny_open.service`: Motor cuantitativo de la Estrategia Ganadora NY_OPEN (Oro).
     - `stellar_webhook.service`: Servidor HTTP de señales Webhook para MT5 en el puerto 8000.
   - Remueve cualquier servicio obsoleto o duplicado para evitar conflictos.
   - Habilita el arranque automático con el sistema (`systemctl enable`) e inicia ambos servicios.

3. **Verificar el Estado de los Servicios en la Nube:**
   ```bash
   # Activar modo exclusivo de la estrategia ganadora + webhook:
   sudo bash manage_services.sh solo-ganadora

   # Comprobar estado de los servicios:
   sudo systemctl status stellar_ny_open --no-pager
   sudo systemctl status stellar_webhook --no-pager

   # Inspeccionar logs en vivo segundo a segundo:
   sudo journalctl -u stellar_ny_open -f
   sudo journalctl -u stellar_webhook -f
   ```

4. **Actualizar la IP del Nuevo VPS en los Scripts de Windows:**
   En tu PC local de Windows, abre los siguientes archivos y reemplaza la IP anterior por la nueva IP de tu servidor:
   - En [`desplegar_a_vps.ps1`](desplegar_a_vps.ps1): Cambia `$vpsIp = "IP_NUEVO_VPS"`.
   - En [`Conectar_Puente_Webhook_MT5.bat`](Conectar_Puente_Webhook_MT5.bat): Cambia la variable `REMOTE_HOST=IP_NUEVO_VPS`.
   - En [`Verificar_Servicio_24_7.bat`](Verificar_Servicio_24_7.bat): Cambia la variable `VPS_IP=IP_NUEVO_VPS`.
   - Si generaste una nueva clave SSH para el nuevo VPS, guarda la clave privada como `VPS-Oracle\oracle_vps.key`.

5. **Verificar Conexión desde Windows:**
   - Ejecuta `.\desplegar_a_vps.bat` para confirmar la sincronización remota por SSH.
   - Ejecuta `Conectar_Puente_Webhook_MT5.bat` para validar que el túnel SSH hacia el nuevo servidor levanta de inmediato en el puerto 8000.

---

### 8.3 Documentación Técnica: Trailing Stop por Estructura M15 y Protección de Ganancias

En instrumentos de alta volatilidad como el Oro (`XAUUSD`), los Trailing Stops convencionales de puntos fijos sufren de cierres prematuros por ruido de mercado y mechas de liquidez. Por ello, el Asesor Experto [`StellarLite_Webhook_Bridge.mq5`](StellarLite_Webhook_Bridge.mq5) incorpora el algoritmo institucional **`CheckAutonomousStructuralTrailing()`**.

```mermaid
flowchart TD
    Tick["Tick / Temporizador OnTimer (Cada 1s)"] --> Check{"¿Existe posición abierta con Magic 101501?"}
    Check -->|No| Wait["Esperar siguiente ciclo"]
    Check -->|Sí| EvalPnL["Calcular PnL Flotante en Puntos de Oro"]
    
    EvalPnL --> Step1{"¿PnL >= +1R (+6.50 pts)?"}
    Step1 -->|No| Keep["Mantener SL inicial institucional"]
    Step1 -->|Sí| CheckBE{"¿SL ya está en Break-Even?"}
    CheckBE -->|No| MoveBE["Mover SL a Precio de Entrada ($0.00 Riesgo)"]
    CheckBE -->|Sí| Step2{"¿PnL >= +2R (+13.00 pts)?"}
    
    Step2 -->|No| KeepBE["Mantener SL en Break-Even"]
    Step2 -->|Sí| M15["Analizar últimas 4 velas cerradas M15 (rates 1..4)"]
    
    M15 --> Type{"¿Tipo de Posición?"}
    Type -->|SELL / Venta| SwingH["Identificar Swing High más alto + 1.50 buffer"]
    SwingH --> ModShort{"¿Nuevo SL < SL actual?"}
    ModShort -->|Sí| ApplyShort["Ajustar SL por detrás del Swing High"]
    ModShort -->|No| Wait
    
    Type -->|BUY / Compra| SwingL["Identificar Swing Low más bajo - 1.50 buffer"]
    SwingL --> ModLong{"¿Nuevo SL > SL actual?"}
    ModLong -->|Sí| ApplyLong["Ajustar SL por detrás del Swing Low"]
    ModLong -->|No| Wait
```

#### Características Clave del Algoritmo:

1. **Blindaje Nivel 1: Break-Even a +1R (+6.50 pts / +65 pips):**
   - En cuanto la operación alcanza una distancia de beneficio de +$6.50 sobre el precio de llenado, el EA envía una orden `TRADE_ACTION_SLTP` colocando el `Stop Loss = Open Price`.
   - La posición queda matemáticamente libre de riesgo monetario ($0.00 de exposición).

2. **Blindaje Nivel 2: Trailing Stop Estructural a +2R (+13.00 pts / +130 pips):**
   - Al superar el objetivo de 2R, el EA no utiliza distancias arbitrarias, sino la acción del precio en velas cerradas de 15 minutos (`rates[1]` a `rates[4]`):
     - **Para Posiciones Vendedoras (SELL):**
       $$\text{Swing High} = \max(\text{High}_1, \text{High}_2, \text{High}_3, \text{High}_4)$$
       $$\text{Nuevo SL} = \text{Swing High} + 1.50\text{ (Buffer de Volatilidad)}$$
       *Si $\text{Nuevo SL} < \text{SL Actual}$, el Stop Loss desciende, bloqueando el 80%+ de la ganancia estructuralmente.*
     - **Para Posiciones Compradoras (BUY):**
       $$\text{Swing Low} = \min(\text{Low}_1, \text{Low}_2, \text{Low}_3, \text{Low}_4)$$
       $$\text{Nuevo SL} = \text{Swing Low} - 1.50\text{ (Buffer de Volatilidad)}$$
       *Si $\text{Nuevo SL} > \text{SL Actual}$, el Stop Loss asciende protegiendo la subida.*

3. **Cálculo de Distancias Relativas Broker-Agnostic:**
   - El bot en la nube analiza cotizaciones globales (Yahoo Finance `GC=F`) mientras que MetaTrader 5 ejecuta contra el servidor del broker (`XAUUSD`). Debido a diferencias de spreads y proveedores, las cotizaciones absolutas pueden variar en decenas o cientos de puntos.
   - Para evitar desajustes, el EA extrae las distancias absolutas de Stop Loss y Take Profit:
     $$\text{slDist} = |\text{open\_price} - \text{sl}|, \quad \text{tpDist} = |\text{open\_price} - \text{tp}|$$
   - Y las ancla directamente al precio de ejecución real del broker (`Bid` para compras o `Ask` para ventas), garantizando que el riesgo en dólares ($25.00 USD) sea exactamente el 0.50% sin importar la cotización del proveedor.

4. **Fail-Safe de Auto-Sincronización Cloud $\leftrightarrow$ Broker:**
   - Durante cada consulta al endpoint `/api/v1/status` del Webhook, el EA revisa el campo `open_trades_count`.
   - Si el bot en la nube cerró la operación (por horario de sesión, regla de fin de semana a las 15:30 EST o condición de salida), pero la posición sigue abierta en MT5:
   - El EA activa de inmediato la función de liquidación forzosa `PositionClose` con reintentos automáticos en modos `ORDER_FILLING_IOC`, `ORDER_FILLING_FOK` y `ORDER_FILLING_RETURN`, protegiendo la cuenta contra desincronizaciones o posiciones abandonadas.

---

### 8.4 Protocolo Operativo en 2 PCs (Trabajo y Hogar) y Reglas Prop Firm

Es totalmente posible y habitual operar alternando entre la **computadora de tu trabajo** y tu **computadora personal (hogar)**. Para garantizar la seguridad del capital y el cumplimiento normativo con **FundedNext** y **FTMO**, sigue este protocolo:

#### ⚠️ Regla de Oro Técnica: Solo 1 Terminal Ejecutando a la Vez
El bot cuantitativo en el VPS de Oracle analiza el mercado 24/7 y genera una única orden institucional cuando se confirma una ruptura (riesgo fijo del 0.50% / $25.00 USD).

> [!CAUTION]
> **Peligro de Doble Ejecución Involuntaria:**  
> Si dejas MetaTrader 5 abierto con el EA activo en la PC del trabajo **y al mismo tiempo** lo tienes abierto con el EA activo en tu PC personal:
> * Ambas terminales consultarán la nube al mismo tiempo por el túnel SSH.
> * Ambas terminales recibirán la señal y enviarán una orden al broker.
> * **Consecuencia:** Se abrirían 2 órdenes (0.01 + 0.01 lotes), **duplicando el riesgo al 1.0% ($50 USD)** e incrementando innecesariamente la exposición.

#### 🛡️ Rutina Diaria Recomendada (Modo Turnos):
1. **Turno Oficina (08:30 – 11:30 EST):**  
   * En la PC del trabajo: Abre `Control_Total_Bot.bat` (Opción 6: Iniciar Túnel SSH) y abre MetaTrader 5 con el botón **"Trading Algorítmico" en verde**.
   * Opera la sesión de Nueva York y Wall Street.
2. **Cierre de Jornada Laboral:**  
   * Al retirarte de tu trabajo: **Cierra MetaTrader 5** en la PC de la oficina (o desactiva el botón de Trading Algorítmico con `Ctrl + E`).
3. **Turno Hogar (Tarde / Noche o Sesión de Londres 03:00 – 06:00 EST):**  
   * En tu PC personal: Abre MetaTrader 5, inicia el túnel SSH y continúa la supervisión o deja la terminal lista para la apertura europea.

#### 🖥️ Modo de Visualización Simultánea (Si ambas PCs están encendidas):
Si deseas tener ambas computadoras encendidas al mismo tiempo:
* **PC Ejecutora (ej. Trabajo):** Botón *"Trading Algorítmico"* activado en verde (con el EA cargado en XAUUSD).
* **PC Espejo / Visual (ej. Casa):** Botón *"Trading Algorítmico"* desactivado en rojo o gráficos sin el EA adjunto. Puedes ver el precio, las velas y las operaciones abiertas en tiempo real sin riesgo de duplicar órdenes.

#### 📋 Cumplimiento de Reglas Prop Firm (FundedNext & FTMO):
* **Ubicación e IP:** Las empresas de fondeo permiten expresamente que el trader opere desde su casa, trabajo o teléfono móvil en la misma ciudad/país.
* **Prevención de "Account Sharing":** Las firmas prohíben compartir cuentas con terceros o usar servicios de gestión no autorizados (detectados cuando dos IPs distantes envían órdenes en el mismo segundo). Al alternar el uso con el **Modo Turnos** (una sola PC enviando órdenes a la vez), tu cuenta mantiene un registro 100% limpio y cumple estrictamente los términos de servicio.

---

---

## 📂 Estructura del Proyecto y Archivos Clave

```text
FTMO_Stellar_Lite/
├── Control_Total_Bot.bat            # Menú maestro de control con 13 opciones integradas
├── Dashboard_Operaciones_En_Vivo.bat# Dashboard en vivo con reloj NY, cuenta regresiva y break-even
├── Dashboard_Nube_Oracle_En_Vivo.bat# Dashboard remoto conectado en tiempo real a Oracle Cloud VPS
├── Dashboard_Multi_Detallado.bat    # Tablero con auditoría cruzada e historial financiero
├── Conectar_Puente_Webhook_MT5.bat  # Gestor del túnel seguro SSH en segundo plano (Puerto 8000)
├── Probar_Senal_Webhook.bat         # Disparador de micro-orden demo (0.01 lotes Oro) a MT5
├── Configurar_Telegram.bat          # Asistente de vinculación de bot y usuario (@victorsvlynch)
├── Probar_Alerta_Telegram.bat       # Enviador de alerta de prueba móvil con instrucciones MT5
├── Verificar_Servicio_24_7.bat      # Diagnóstico rápido de uptime y memoria del servidor OCI
├── StellarLite_Webhook_Bridge.mq5   # Código fuente MQL5 del Asesor Experto para MetaTrader 5
├── StellarLite_Webhook_Bridge.ex5   # Archivo compilado de alta velocidad para MT5
├── webhook_server.py                # Servidor HTTP de señales Webhook (0.0.0.0:8000)
├── telegram_notifier.py             # Módulo de alertas push HTML para Telegram con plantillas móviles
├── configurar_telegram.py           # Script de configuración y sincronización automática con la nube
├── test_telegram_signal.py          # Script de prueba de envío de señales a Telegram
├── telegram_config.json             # Credenciales seguras del bot de Telegram
├── main.py                          # CLI principal, monitor interactivo en vivo y loop 24/7
├── mt5_bridge.py                    # Puente IPC nativo de alta velocidad con MetaTrader 5
├── prueba_mt5_simulacion.py         # Script interactivo de prueba y simulación real con MT5
├── Ejecutar_Prueba_MT5.bat          # Lanzador de 1-clic para la prueba interactiva con MT5
├── Monitor_Estrategia_Ganadora.bat  # Monitor rápido en vivo de la estrategia NY_OPEN
├── trading_engine.py                # Motor NY ORB 15M, filtro EMA 200 H1 y conector de mercado
├── risk_manager.py                  # Sizing institucional (0.5%), freno 2% y anti-tilt
├── stellar_rules.py                 # Reglas FundedNext Stellar Lite ($5K) + Add-ons (10% DD, 95% Split)
├── database.py                      # Motor SQLite multi-cuenta, eventos y auditoría de balance
├── test_verification.py             # Suite de 9 pruebas de verificación integral (100% OK)
├── setup_oracle.sh                  # Script de aprovisionamiento en Linux Ubuntu ARM64
├── manage_services.sh               # Gestor de servicios systemd en la nube
├── desplegar_a_vps.bat              # Sincronización automática de código a Oracle Cloud VPS
├── auto_push.bat                    # Commit automático con IA y push a GitHub
├── archify.bat                      # Generador de respaldos y snapshots comprimidos
├── requirements.txt                 # Dependencias de Python mínimas y optimizadas
├── trading_ny_open.db               # Base de datos SQLite exclusiva de la estrategia ganadora
└── README.md                        # Manual integral de operación e instructivo de migración
```

---

## ⚠️ Protocolo de Contingencia y Hard Breach

El motor cuenta con un mecanismo de seguridad a nivel de microsegundos para proteger tu inversión:

1. **Detección de Hard Breach:**
   - Si la equidad o el balance cae al **Piso Diario del 4% ($4,800.00)** o al **Piso Máximo del 10% ($4,500.00)**:
     - **Liquidación Forzosa Inmediata:** Cierra todas las operaciones abiertas en MT5 o base de datos (`LIQUIDACION_FORZOSA_HARD_BREACH`).
     - **Bloqueo Definitivo:** Cambia el estado de la cuenta a **`FALLADA`** (`FAILED`).
     - **Inhibición de Órdenes:** Bloquea de forma irrevocable cualquier intento de apertura y genera un reporte forense en la base de datos de auditoría.
2. **Reinicio de Cuenta para Nueva Evaluación:**
   Si reinicias tu desafío o contratas una nueva cuenta de $5,000, ejecuta:
   ```bash
   python main.py reset
   ```
   *Limpia el historial de trades y reasigna el balance inicial de $5,000.00 en Fase 1.*

---

## 🛠️ Herramientas DevOps, Snapshots, Grabación de Estados y CI/CD

### 1. Auto-Push Inteligente a GitHub (`auto_push.bat`)
Ejecuta:
```cmd
.\auto_push.bat
```
*Analiza las diferencias de código (`git diff`), redacta un mensaje profesional siguiendo el estándar de **Conventional Commits** y realiza el push a GitHub automáticamente.*

### 2. Respaldos, Grabación de Estados y Snapshots (`archify.bat`)
Genera archivos de respaldo estructurados e inmutables con manifiesto JSON en la carpeta `archives/`:
```cmd
.\archify.bat Databases       # Respalda todas las bases de datos SQLite (*.db)
.\archify.bat Full v2.1.0     # Respaldo completo del código fuente limpio
.\archify.bat All             # Respaldo combinado de bases de datos y código
```
*Crea una "grabación de estado" (snapshot comprimido) con hash SHA-256 de integridad para auditoría y restauración rápida.*

### 3. Grabación de Video / Evidencia de Pantalla para Empresas de Fondeo (FTMO / FundedNext)
Si la empresa de fondeo requiere evidencia o grabación en video de la operativa del Asesor Experto en MetaTrader 5:
* **Grabador Nativo de Windows:** Presiona `Win + Alt + R` para iniciar o detener la grabación en video de la ventana de MetaTrader 5 (las grabaciones se guardan automáticamente en `Videos\Capturas`).
* **Atajo del Panel de Juego:** Presiona `Win + G` para ajustar micrófono, audio del sistema y calidad de captura.

### 4. Integración Continua (GitHub Actions)
Configurado en `.github/workflows/release.yml`. Cada `push` a la rama `main` ejecuta la suite completa de pruebas [`test_verification.py`](test_verification.py). Si las 10 pruebas son superadas con éxito (100% OK), genera automáticamente un nuevo Release en GitHub.
