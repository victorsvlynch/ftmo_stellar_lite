# GUÍA RÁPIDA DE INSTALACIÓN Y PORTABILIDAD A OTRA PC
**FundedNext Stellar Lite ($10,000 USD) - Engine Cuantitativo 24/7 & MetaTrader 5 Bridge**

Este paquete contiene **absolutamente todo** lo necesario para migrar y operar el bot desde cualquier otra computadora con Windows en menos de 2 minutos.

---

## 📦 Contenido del Paquete

1. **`01_MT5_Configuracion/`**:
   - `MQL5/Experts/StellarLite_Webhook_Bridge.ex5` y `.mq5` (versión multi-activo compilada).
   - `Config/common.ini` (configuración con permiso de WebRequest pre-autorizado para `http://127.0.0.1:8000` y `http://157.137.225.144:8000`, AlgoTrading y DLLs activadas).
   - `Config/servers.dat` y `settings.ini`.
   - `Profiles/` (perfiles y plantillas de gráficos en mosaico).
2. **`02_SSH_Keys_Oracle_VPS/`**:
   - `oracle_vps.key` y `ssh-key-2026-10-26.key` (llaves privadas RSA para acceso SSH al VPS en Oracle Cloud `157.137.225.144`).
3. **`03_Codigo_Python_Proyecto/`**:
   - Todo el código fuente de Python sincronizado (`risk_manager.py`, `trading_engine.py`, `mt5_bridge.py`, `stellar_rules.py`, `main.py`, etc.).
   - Bases de datos SQLite actualizadas y reseteadas a $10,000.00 USD (`trading_ny_open.db`, etc.).
   - Menú maestro y lanzadores rápidos (`Control_Total_Bot.bat`, `Monitor_Portfolio_SP500_EURUSD.bat`, etc.).

---

## 🎯 Especificaciones de la Cuenta FundedNext ($10,000 USD)

* **Balance Inicial:** `$10,000.00 USD`
* **Target Fase 1:** `+8% ($800.00 USD)` -> Objetivo: `$10,800.00 USD`
* **Target Fase 2:** `+4% ($400.00 USD)` -> Objetivo: `$10,400.00 USD`
* **Pérdida Diaria Máxima:** `4% Estático ($400.00 USD)` -> Piso del día: `$9,600.00 USD`
* **Drawdown Máximo Total:** `8% Estático ($800.00 USD)` -> Piso inamovible: `$9,200.00 USD`
* **Riesgo por Operación:** `0.50% ($50.00 USD)`
* **Exposición Máxima Simultánea:** `3% ($300.00 USD)`
* **Días Mínimos Operativos:** `2 días por fase`
* **Profit Split Fondeada:** `80% (Escalable a 90%)`

---

## 🚀 Pasos de Instalación en la Nueva PC (Menos de 2 minutos)

### Paso 1: Requisitos Previos en la Nueva PC
Asegúrate de tener instalados en la nueva computadora:
1. **MetaTrader 5** (de tu broker o MetaQuotes).
2. **Python 3.10 o superior** (al instalar, asegúrate de marcar la casilla ☑️ **"Add Python to PATH"**).

---

### Paso 2: Instalación Automática en 1 Clic
1. Copia o descomprime este paquete en tu nueva PC (por ejemplo, en `C:\FTMO_Stellar_Lite` o en una unidad secundaria como `L:\Python\FTMO_Stellar_Lite`).
2. Haz **doble clic en `INSTALAR_EN_NUEVA_PC.bat`**.
3. El script automáticamente:
   - Copiará las llaves SSH a `%USERPROFILE%\.ssh` con permisos seguros de Windows (`icacls`).
   - Detectará MetaTrader 5 y copiará el Expert Advisor a `MQL5\Experts`.
   - Instalará la configuración de WebRequest y plantillas.
   - Instalará las librerías necesarias de Python (`pip install -r requirements.txt`).
   - Probará la conexión directa con el VPS de Oracle Cloud.

---

### Paso 3: Operación en la Nueva PC
1. Abre **MetaTrader 5**:
   - Inicia sesión con tu cuenta de FundedNext / MetaQuotes Demo ($10,000 USD).
   - Abre los gráficos de **XAUUSD**, **US500** y **EURUSD** en mosaico (`Alt + R`).
   - Coloca el EA `StellarLite_Webhook_Bridge` en el gráfico de **XAUUSD** (actúa como Master Bridge para los 3 activos).
   - Verifica que el botón **Trading Algorítmico** en la barra superior esté **en verde** (`Ctrl + E`).
2. Abre **`03_Codigo_Python_Proyecto\Control_Total_Bot.bat`**:
   - Selecciona la **Opción 4** para iniciar el Túnel Webhook SSH (`127.0.0.1:8000`).
   - En MT5, el tablero visual cambiará inmediatamente a:  
     `Estado Conexion: CONECTADO A ORACLE CLOUD (ONLINE)`.
3. (Opcional) Selecciona la **Opción 6** (`Ejecutar_Prueba_MT5.bat`) para auditar en vivo la conexión con el broker MT5 y validar el dimensionamiento exacto de lotes.

---

## 🔒 Parámetros del Servidor Cloud
* **IP VPS Oracle:** `157.137.225.144`
* **Usuario:** `ubuntu`
* **Puerto Webhook:** `8000`
* **Ruta de la llave SSH:** `%USERPROFILE%\.ssh\oracle_vps.key`
