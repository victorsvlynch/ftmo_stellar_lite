# Diagramas de Arquitectura & Flujo Operativo

Diagramas interactivos de alta fidelidad para el motor cuantitativo **FundedNext / FTMO Stellar Lite ($5,000)**.

---

## 📁 Archivos del Módulo

```text
scripts/diagramas/
├── arquitectura.json        # Definición estructurada de componentes para Archify CLI
├── arquitectura.html        # Render interactivo vectorial 4K generado por Archify
├── render_arquitectura.ps1  # Script PowerShell de validación y compilación
├── render_arquitectura.bat  # Lanzador Batch de 1-clic para Windows
├── secuencia_operativa.mmd  # Diagrama de secuencia Mermaid (Ciclo de trading & riesgos)
├── flujo_trading_orb.html   # Visualizador HTML5 autónomo con Mermaid.js
└── README.md                # Este manual
```

---

## 🎨 1. Diagrama de Arquitectura Interactivo (`arquitectura.html`)

Generado mediante **Archify CLI**:
- **Consolas Locales & Monitoreo:** CLI interactiva (`main.py`) y Tablero Multi-Modalidad en vivo.
- **Núcleo Cuantitativo:** Motor de trading (`run_single_cycle`), Estrategia New York ORB 15m con filtro EMA 200 1H, Gestor de Riesgo (0.5% Sizing, 2% Personal Cap, Tilt Alert 3) y Validador oficial de reglas FundedNext Stellar Lite.
- **Capa de Datos & Notificaciones:** Persistencia SQLite multi-base de datos, auditoría forense con reseteo 00:00 UTC y notificador push en Telegram.
- **Infraestructura Cloud:** Instancia Oracle Cloud Infrastructure (Ubuntu ARM64) con 5 servicios autónomos de `systemd`.
- **DevOps:** GitHub Actions SemVer release y empaquetador Archify.

### ¿Cómo compilar y actualizar el diagrama?
```powershell
# En PowerShell:
.\scripts\diagramas\render_arquitectura.ps1

# O con apertura automática en navegador:
.\scripts\diagramas\render_arquitectura.ps1 -Open

# O mediante el lanzador Batch:
.\scripts\diagramas\render_arquitectura.bat
```

---

## 📊 2. Diagrama de Secuencia y Flujo Operativo (`flujo_trading_orb.html`)

Muestra el flujo de ejecución secuencial en cada ciclo de 60 segundos del bot:
1. **Fase 1 (Gestión de Posiciones Abiertas):** Consulta mark price actual, evalúa equidad contra pisos estrictos (Daily Loss 4% / Max DD 8%), traslada SL a Break-Even al alcanzar +1R y ejecuta liquidaciones.
2. **Fase 2 (Blindaje de Ganancias & Fondeo):** Activa el bloqueo preventivo `TARGET_REACHED_TODAY_SECURED` para evitar sobreoperar, o conmuta a modo Micro-Lote (0.01 lotes) para registrar el día 2/2 mínimo.
3. **Fase 3 (Análisis Técnico & Filtros):** Valida ventana de mercado (08:30-11:30 EST), racha de pérdidas y calcula el rango ORB 15m rechazando mechas falsas mediante confirmación de cierre y filtro EMA 200 1H.
4. **Fase 4 (Ejecución Institucional):** Calcula el lotaje exacto según distancia de SL, registra la operación en SQLite y despacha alerta push inmediata a Telegram.

Para visualizarlo, haz doble clic sobre `scripts/diagramas/flujo_trading_orb.html`.
