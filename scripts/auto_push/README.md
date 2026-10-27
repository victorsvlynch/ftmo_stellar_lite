# Automatización de Git, Versionado SemVer y Respaldos (Archify)

Módulo integral de DevOps y respaldos para el motor algorítmico **FundedNext / FTMO Stellar Lite ($5,000)**.

---

## 📁 Estructura del Módulo

```text
scripts/auto_push/
├── auto_push.bat     # Ejecutor Batch para Windows (1-clic)
├── auto_push.ps1     # Script PowerShell con IA (Gemini API) para Conventional Commits
├── auto_push.py      # CLI Interactivo en Python
├── archify.bat       # Ejecutor Batch para respaldos y empaquetado
├── archify.ps1       # Script PowerShell para snapshots limpios y backup de SQLite
├── api_keys.txt      # Claves de Google Gemini API para generación de mensajes
└── README.md         # Este manual de uso
```

---

## 🚀 1. Auto-Push con Inteligencia Artificial (Conventional Commits)

El script `auto_push.ps1` (o su lanzador `auto_push.bat`):
1. Ejecuta `git add .` para preparar todos los cambios.
2. Analiza el `git diff --cached` mediante la API de **Google Gemini** (`gemini-2.5-flash-lite` / `gemini-2.5-flash`).
3. Genera un mensaje conciso en español siguiendo la convención de **Conventional Commits**:
   - `feat:` Nuevas características, reglas de trading o módulos.
   - `fix:` Correcciones de bugs, cálculos de lotaje o liquidaciones.
   - `refactor:` Limpieza y reestructuración de código sin alterar comportamiento.
   - `chore:` Mantenimiento de dependencias, scripts o CI/CD.
4. Hace `git commit -m "..."` y `git push origin main`.
5. **Disparo en GitHub Actions:** Al subir a la rama `main`, `.github/workflows/release.yml` detecta el prefijo, incrementa la versión SemVer correspondiente (patch, minor, major) y crea el GitHub Release automáticamente con su changelog.

### Uso:
```powershell
# Ejecución interactiva automática con IA:
.\scripts\auto_push\auto_push.ps1

# O con mensaje manual:
.\scripts\auto_push\auto_push.ps1 "feat: blindaje anti-sobreoperacion y modo micro-lote"

# O mediante el archivo Batch:
.\scripts\auto_push\auto_push.bat
```

---

## 📦 2. Archify: Empaquetado y Respaldos

Herramienta de compresión de alta fidelidad que genera archivos `.zip` dentro de la carpeta `archives/` con metadatos completos y un `manifest.json` incorporado.

### Modos Soportados:

1. **`Databases` (Por defecto):**
   - Respalda todas las bases de datos de SQLite activas (`trading_ny_open.db`, `trading_crypto_24h.db`, etc.) con su historial de órdenes y eventos de auditoría.
   ```powershell
   .\scripts\auto_push\archify.ps1 -Mode Databases
   ```

2. **`Full` (Snapshot de Código Fuente):**
   - Genera un snapshot completo del código fuente limpio, excluyendo `.git`, `archives`, `__pycache__`, entornos virtuales y claves SSH privadas.
   ```powershell
   .\scripts\auto_push\archify.ps1 -Mode Full -Tag "v1.1.0"
   ```

3. **`All` (Ambos):**
   - Genera tanto el respaldo de bases de datos como el snapshot del código en archivos separados.
   ```powershell
   .\scripts\auto_push\archify.ps1 -Mode All
   ```

4. **Modo Simulación (`-DryRun`):**
   - Inspecciona qué archivos se incluirían sin crear el archivo en disco.
   ```powershell
   .\scripts\auto_push\archify.ps1 -Mode Full -DryRun
   ```
