# FundedNext Stellar Lite ($5,000) - Automated Trading Engine & Risk Manager

Motor cuantitativo de trading algorítmico y gestor de riesgo institucional diseñado específicamente para superar y gestionar cuentas de fondeo **FundedNext - Modelo Stellar Lite ($5,000)**. 

Desarrollado en **Python Puro (Sin Streamlit, sin interfaces web, sin Docker y sin venv)**, optimizado para ejecutarse como un servicio desatendido 24/7 en servidores Linux Ubuntu (arquitecturas ARM64 y x86_64) en **Oracle Cloud Infrastructure (OCI)** con persistencia local en **SQLite**.

---

## 📋 Tabla de Contenidos
1. [Reglas Oficiales FundedNext Stellar Lite Implementadas](#-reglas-oficiales-fundednext-stellar-lite-implementadas)
2. [Gestión de Riesgo Avanzada e Institucional](#-gestión-de-riesgo-avanzada-e-institucional)
3. [Estrategia Principal: New York ORB 15m](#-estrategia-principal-new-york-orb-15m)
4. [Estructura del Proyecto](#-estructura-del-proyecto)
5. [Guía de Instalación y Despliegue en Oracle Cloud (OCI)](#-guía-de-instalación-y-despliegue-en-oracle-cloud-oci)
6. [Manual de Comandos CLI (`main.py`)](#-manual-de-comandos-cli-mainpy)
7. [Administración del Servicio 24/7 con `systemd`](#-administración-del-servicio-247-con-systemd)
8. [Monitoreo en Vivo desde una PC con Windows](#-monitoreo-en-vivo-desde-una-pc-con-windows)
9. [Ciclo de Vida: ¿Qué pasa si la cuenta falla o logra el objetivo?](#-ciclo-de-vida-qué-pasa-si-la-cuenta-falla-o-logra-el-objetivo)

---

## ⚖️ Reglas Oficiales FundedNext Stellar Lite Implementadas

| Regla | Parámetro Oficial | Comportamiento del Motor |
| :--- | :--- | :--- |
| **Fase 1 Target** | **+8% ($400 sobre $5,000)** | Al alcanzar $5,400 con 2 días mínimos, promueve automáticamente a Fase 2. |
| **Fase 2 Target** | **+4% ($200 sobre $5,000)** | Al alcanzar $5,200 con 2 días mínimos, promueve automáticamente a Cuenta Fondeada. |
| **Cuenta Fondeada** | **Sin target de ganancia** | Profit Split inicial del **80%**. Escala al **90%** tras acumular +10% de beneficio. |
| **Daily Loss Limit** | **4% Estático ($200 en $5K)** | Piso calculado cada día a las 00:00 UTC sobre el balance inicial del día. Si la equidad lo toca, **falla la cuenta**. |
| **Max Drawdown** | **8% Estático ($400 en $5K)** | **Piso fijo e inamovible en $4,600.00**. Si la equidad o balance cae a este nivel, **falla la cuenta**. |
| **Días Mínimos** | **2 días por fase** | No permite avanzar de fase hasta completar al menos 2 jornadas con operaciones cerradas. |
| **Filtro de Noticias** | **40% News Profit Cap** | Alerta si más del 40% del profit acumulado proviene de ventanas de alto impacto (NFP, CPI, FOMC). |
| **Overnight & Weekend** | **Permitido** | No fuerza cierres artificiales al finalizar el día o la semana. |

---

## 🛡️ Gestión de Riesgo Avanzada e Institucional

1. **Calculadora Dinámica de Posición (`Position Sizing Calculator`):**
   - Calcula el tamaño exacto del lote basándose en el porcentaje de riesgo por operación (ej. 0.5% = $25 USD en cuenta de $5K) y la distancia en pips/puntos hasta el Stop Loss.
   - Aplica especificaciones de contrato institucionales (Oro XAU/USD 100 oz/lote, Forex 100k unidades/lote, Cripto 1 unidad/lote).
2. **Freno de Mano Personal (`Personal Daily Loss Cap`):**
   - Configurado por defecto al **2.0%** ($100 USD). Si las pérdidas del día alcanzan este nivel, el bot bloquea nuevas operaciones para proteger la cuenta y quedar muy lejos del 4% letal del broker.
3. **Filtro por Sesión de Mercado:**
   - Restringe la apertura de operaciones únicamente a ventanas de máxima liquidez: Apertura de Nueva York (**08:30 - 11:30 EST**), sesión de Londres, o modo 24H para criptoactivos.
4. **Alerta de Racha Negativa (`Tilt Alert`):**
   - Bloquea temporalmente nuevas aperturas durante el resto de la jornada si se registran **3 pérdidas consecutivas en el día**.

---

## 📈 Estrategias y Modalidades Operativas (5 Estrategias Independientes)

El sistema soporta 5 modalidades cuantitativas con gestión de riesgo independiente, bases de datos SQLite separadas y servicios systemd autónomos:

1. **Estrategia 1 - `NY_OPEN` (Apertura Wall Street):**
   - **Activo:** Oro XAU/USD (`GC=F` vía `yfinance`).
   - **Horario:** 08:30 a 11:30 EST (América/New_York).
   - **Referencia ORB:** Vela de apertura de las 08:30 a 08:45 EST.
   - **Servicio Systemd:** `stellar_ny_open.service` | **Base de Datos:** `trading_ny_open.db`.

2. **Estrategia 2 - `LONDON_OPEN` (Apertura Londres):**
   - **Activo:** Oro XAU/USD (`GC=F` vía `yfinance`).
   - **Horario:** 03:00 a 06:00 EST (08:00 a 11:00 London Time).
   - **Referencia ORB:** Vela de apertura de Londres de las 03:00 a 03:15 EST.
   - **Servicio Systemd:** `stellar_london_open.service` | **Base de Datos:** `trading_london_open.db`.

3. **Estrategia 3 - `CRYPTO_24H` (Cripto Continuo 24/7):**
   - **Activo:** Bitcoin (`BTC/USDT` vía `ccxt`/Binance).
   - **Horario:** Operación continua 24 horas, 7 días a la semana.
   - **Referencia ORB:** Rango dinámico de consolidación 15m.
   - **Servicio Systemd:** `stellar_crypto_24h.service` | **Base de Datos:** `trading_crypto_24h.db`.

4. **Estrategia 4 - `NY_OPEN + LONDON` (Combo Dual):**
   - **Activo:** Oro XAU/USD (`GC=F` vía `yfinance`).
   - **Horario:** Ventanas de apertura combinadas (03:00-06:00 EST y 08:30-11:30 EST).
   - **Referencia ORB:** Vela de las 03:00 EST en Londres y vela de las 08:30 EST en Nueva York.
   - **Servicio Systemd:** `stellar_ny_london.service` | **Base de Datos:** `trading_ny_london.db`.

5. **Estrategia 5 - `NY_OPEN + LONDON + CRYPTO_24H` (Combo Trío Multi-Activo 24/7):**
   - **Activos:** Oro (`GC=F`) + Bitcoin (`BTC/USDT`).
   - **Horario:** 24/7 continuo con asignación inteligente por sesión:
     * Oro (`GC=F`): Apertura Londres (03:00-06:00 EST) y Apertura NY (08:30-11:30 EST).
     * Cripto (`BTC/USDT`): Continuo 24/7.
   - **Servicio Systemd:** `stellar_combo_trio.service` | **Base de Datos:** `trading_combo_trio.db`.

---

## 📂 Estructura del Proyecto

```text
/home/ubuntu/FTMO_Stellar_Lite/
├── main.py                   # Entrypoint CLI, tablero multi-modalidad, loop 24/7 y reportes
├── database.py               # Motor de persistencia SQLite multi-base de datos y auditoría
├── stellar_rules.py          # Reglas oficiales FundedNext Stellar Lite (Hard/Soft breaches)
├── risk_manager.py           # Gestor de lotaje, filtro multi-sesión, freno 2% y Tilt Alert
├── trading_engine.py         # Conectores y motor OpeningRangeBreakoutStrategy multi-sesión
├── setup_oracle.sh           # Aprovisionamiento OCI y despliegue de los 5 servicios systemd
├── manage_services.sh        # Gestor central de inicio/parada/reinicio de las 5 estrategias
├── trading_ny_open.db        # Base de datos Estrategia 1 (NY Open)
├── trading_london_open.db    # Base de datos Estrategia 2 (London Open)
├── trading_crypto_24h.db     # Base de datos Estrategia 3 (Crypto 24/7)
├── trading_ny_london.db      # Base de datos Estrategia 4 (Combo Dual)
├── trading_combo_trio.db     # Base de datos Estrategia 5 (Combo Trío 24/7)
└── README.md                 # Este manual de instrucciones
```

---

## 🚀 Guía de Instalación y Despliegue en Oracle Cloud (OCI)

### Paso 1: Subir archivos a la VPS
Mediante el navegador SFTP de **MobaXterm**, arrastra la carpeta `FTMO_Stellar_Lite` al directorio `/home/ubuntu/`.

### Paso 2: Limpiar saltos de línea Windows (CRLF a LF) y dar permisos
En la consola de Ubuntu ejecuta:
```bash
cd /home/ubuntu/FTMO_Stellar_Lite
sed -i 's/\r$//' *.sh *.py *.txt
chmod +x setup_oracle.sh main.py
```

### Paso 3: Ejecutar el script automatizado
```bash
sudo ./setup_oracle.sh
```
El script instalará automáticamente `python3-pip`, las librerías compatibles con ARM64/Python 3.8, abrirá el puerto `8501` y configurará el servicio `fundednext_bot.service` para correr 24/7.

---

## 💻 Manual de Comandos CLI (`main.py`)

Todos los comandos se ejecutan dentro del directorio `/home/ubuntu/FTMO_Stellar_Lite`:

### 1. Consultar Reporte de Estado Financiero y de Riesgo
- **Reporte estático puntual:**
  ```bash
  python3 main.py status
  ```
- **Monitor dinámico EN VIVO (segundo a segundo):**
  ```bash
  python3 main.py live --refresh 1
  ```
  *(Mantiene la pantalla actualizada en tiempo real con el precio de mercado, reloj UTC, equidad flotante y posiciones abiertas).*
- **Tablero Multi-Modalidad Detallado EN VIVO (5 Estrategias con Operaciones Abiertas y Cerradas):**
  ```bash
  python3 main.py multi-detail
  # O bien mediante el gestor central en OCI:
  ./manage_services.sh detail
  ```

### 2. Consola Interactiva (`stellar-cli>`)
Abre una terminal interactiva para gestión manual:
```bash
python3 main.py interactive
```
*Comandos disponibles dentro de `stellar-cli>`:*
- `status` : Muestra el reporte completo formateado.
- `cycle` : Ejecuta un ciclo de análisis en vivo de la estrategia NY ORB 15m.
- `calc <precio_entrada> <stop_loss>` : Calcula el lotaje exacto para el balance actual (ej. `calc 2650.0 2642.5`).
- `force_buy` / `force_sell` : Abre una orden de prueba ignorando el filtro horario.
- `close_all` : Cierra de inmediato todas las posiciones abiertas a precio de mercado.
- `history` : Muestra las últimas 15 operaciones en la base de datos SQLite.
- `events` : Muestra el log de eventos de auditoría y transiciones de fase.
- `reset` : Restablece la cuenta a $5,000.00 en Fase 1.
- `exit` : Sale de la consola interactiva.

### 3. Simulación Rápida de Prueba (Demo Cycle)
Abre un trade simulado de Oro, simula el alcance del Take Profit 1:2, actualiza el balance en SQLite y muestra el reporte:
```bash
python3 main.py simulate
```

### 4. Reinicio de Cuenta a Fase 1
Limpia el historial de pruebas y restablece el balance a $5,000.00:
```bash
python3 main.py reset
```

### 5. Parámetros Personalizables de Ejecución
Puedes arrancar el motor con diferentes activos o configuraciones:
```bash
# Operar Cripto (BTC/USDT) con riesgo del 1% y sesión 24H:
python3 main.py run --symbol BTC/USDT --provider ccxt --risk 0.01 --personal-cap 0.02 --session ALL --interval 30

# Operar Oro (XAU/USD) con riesgo del 0.5% y sesión de Apertura NY:
python3 main.py run --symbol GC=F --provider yfinance --risk 0.005 --personal-cap 0.02 --session NY_OPEN --interval 60
```

---

## ⚙️ Administración del Servicio 24/7 con `systemd`

El bot opera de forma continua sin depender de que tu sesión SSH o tu PC estén encendidos:

- **Ver estado del servicio:**
  ```bash
  sudo systemctl status fundednext_bot.service
  ```
- **Ver logs en tiempo real (streaming en vivo):**
  ```bash
  sudo journalctl -u fundednext_bot.service -f
  ```
- **Reiniciar el bot:**
  ```bash
  sudo systemctl restart fundednext_bot.service
  ```
- **Detener el bot:**
  ```bash
  sudo systemctl stop fundednext_bot.service
  ```
- **Iniciar el bot:**
  ```bash
  sudo systemctl start fundednext_bot.service
  ```

---

## 🖥️ Monitoreo y Control desde Windows (Scripts .BAT de 1-Clic)

En la carpeta `L:\VPS-Oracle\` dispones de un ecosistema completo de accesos directos configurados para Oracle Cloud (`157.137.225.144`):

### 1. Centro de Control Total (`Control_Servicios.bat`)
Menú interactivo para:
- Consultar el **Status Consolidado** de las 5 estrategias y servicios systemd.
- Iniciar, detener o reiniciar los **5 servicios independientes** en el VPS.
- Ver **logs en vivo combinados** o **filtrar logs por estrategia individual (1 a 5)**.
- Abrir el **Tablero en Vivo Multi-Modalidad**.
- Reiniciar todas las cuentas a $5,000.00 en caso de nueva evaluación.

### 2. Monitores en Vivo por Estrategia
- `Monitor_Consolidado_Todas.bat` / `Monitorear_Bot.bat` : Tablero interactivo con las 5 modalidades en tiempo real.
- `Monitor_1_NY_Open.bat` : Monitor exclusivo Modalidad 1 (NY_OPEN 08:30-11:30 EST | Oro `GC=F`).
- `Monitor_2_London_Open.bat` : Monitor exclusivo Modalidad 2 (LONDON_OPEN 03:00-06:00 EST | Oro `GC=F`).
- `Monitor_3_Crypto_24H.bat` : Monitor exclusivo Modalidad 3 (CRYPTO_24H 24/7 | Bitcoin `BTC/USDT`).
- `Monitor_4_Combo_Dual.bat` : Monitor exclusivo Modalidad 4 (NY_OPEN + LONDON | Oro `GC=F`).
- `Monitor_5_Combo_Trio.bat` : Monitor exclusivo Modalidad 5 (NY + LONDON + CRYPTO | Multi-Activo).

### 3. Streaming de Logs en Tiempo Real
- `Logs_En_Vivo.bat` : Transmisión en tiempo real de todos los servicios activos (`stellar_*`).
- `Logs_1_NY_Open.bat` a `Logs_5_Combo_Trio.bat` : Transmisión de logs individuales por servicio.

### 4. Scripts Locales en `L:\Python\FTMO_Stellar_Lite\`
- `Ejecutar_Multi_Detallado_En_Vivo.bat` : **NUEVO** - Tablero detallado en vivo segundo a segundo con todas las operaciones abiertas y cerradas del día por cada modalidad.
- `Ejecutar_Multi_Status.bat` : Consulta instantánea de balance, equidad y drawdowns de las 5 cuentas locales.
- `Ejecutar_Consolidado_En_Vivo.bat` : Tablero visual en vivo local (vista compacta).
- `Ejecutar_Consola_Interactiva.bat` : CLI para testear órdenes, calcular lotajes y forzar trades.
- `Ejecutar_Tests_Verificacion.bat` : Corre la suite de verificación automatizada (100% OK).

---

## 🔄 Ciclo de Vida: ¿Qué pasa si la cuenta falla o logra el objetivo?

### Si LOGRA EL OBJETIVO (Aprobación y Promoción):
1. **Fase 1 (+8% = $5,400.00 y 2 días mínimos):**
   - El motor registra el éxito en SQLite y **promueve automáticamente a `FASE_2`**.
   - Restablece el balance base de evaluación a $5,000.00 y fija el nuevo objetivo a +4% ($5,200.00).
2. **Fase 2 (+4% = $5,200.00 y 2 días mínimos):**
   - El motor promueve automáticamente la cuenta a **`FONDEADA`**.
   - Asigna el **Profit Split inicial del 80%** y elimina los targets obligatorios de beneficio.
3. **Cuenta Fondeada:**
   - Al acumular **+10% de beneficio** en la cuenta fondeada, escala el **Profit Split del 80% al 90%**.

### Si FALLA LA CUENTA (Hard Breach):
1. Si la equidad o el balance toca el **Piso Diario del 4% ($4,800)** o el **Piso Máximo del 8% ($4,600)**:
   - **Liquidación Forzosa Inmediata:** Cierra todas las operaciones abiertas en milisegundos (`LIQUIDACION_FORZOSA_HARD_BREACH`).
   - **Bloqueo de Emergencia:** Cambia el estado a **`FALLADA`** (`status: 'FAILED'`).
   - **Inhibición Total:** El motor bloquea la apertura de cualquier nueva orden y registra en auditoría la causa forense exacta.
2. Para reiniciar la cuenta a Fase 1 tras adquirir una nueva evaluación, solo ejecuta:
   ```bash
   python3 main.py reset
   ```


---

## 🛠️ DevOps, Diagramas de Arquitectura & Respaldos (Archify)

El repositorio incorpora la misma arquitectura de automatización profesional de proyectos de grado institucional:

### 1. Diagramas de Arquitectura & Flujo Operativo (scripts/diagramas/)
- **Renderizado Interactivo 4K (rquitectura.html):** Generado mediante **Archify CLI** a partir de rquitectura.json, visualizando los componentes de trading, reglas de riesgo, bases de datos y la nube de Oracle.
  `powershell
  .\scripts\diagramas\render_arquitectura.bat
  # O en PowerShell:
  .\scripts\diagramas\render_arquitectura.ps1 -Open
  `
- **Diagrama de Secuencia y Flujo (lujo_trading_orb.html):** Diagrama interactivo Mermaid.js que detalla el ciclo completo de análisis, gestión de break-even, filtros anti-fakeout y notificaciones push.

### 2. Auto-Push con IA & Conventional Commits (scripts/auto_push/)
- Analiza automáticamente el git diff mediante la API de **Google Gemini**, redacta un mensaje en español con el estándar de Conventional Commits (eat:, ix:, 
efactor:, chore:) y sube los cambios a GitHub.
  `cmd
  auto_push.bat
  `

### 3. Respaldos y Snapshots con Archify (scripts/auto_push/archify.bat)
- Empaqueta copias de seguridad de alta compresión en la carpeta rchives/ con manifiesto JSON de auditoría:
  - **Modo Databases (por defecto):** Respalda todas las bases de datos SQLite (*.db).
  - **Modo Full:** Genera un snapshot completo del código fuente limpio (excluyendo claves, caches y temporales).
  - **Modo All:** Genera ambos respaldos.
  `cmd
  archify.bat Databases
  archify.bat Full v1.2.0
  `

### 4. GitHub Actions CI/CD (.github/workflows/release.yml)
- Al realizar push a la rama main, GitHub Actions:
  1. Instala el entorno Python y dependencias.
  2. Ejecuta la suite de pruebas automatizada 	est_verification.py.
  3. Si todas las pruebas pasan (100% OK), incrementa la versión SemVer y crea un nuevo **GitHub Release** con su changelog detallado.
