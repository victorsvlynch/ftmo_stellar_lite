#!/usr/bin/env python3
"""
auto_push.py - Asistente Interactivo de Git Commit y Push con Convenciones SemVer.
Genera mensajes basados en Conventional Commits para disparar GitHub Actions SemVer Release.
"""

import subprocess
import os
import sys

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    os.chdir(repo_root)

    print("============================================================")
    print(" 🚀 AUTO-PUSH CLI: FTMO Stellar Lite ($5,000)")
    print("============================================================")
    print("📦 Añadiendo cambios con 'git add .'...")
    subprocess.run(["git", "add", "."], check=True)
    
    result = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
    diff = result.stdout.strip()
    
    if not diff:
        print("⚠️  No hay cambios nuevos pendientes para subir a GitHub.")
        return
        
    prompt = f"""Eres un desarrollador cuantitativo experto en Python y cuentas de fondeo (FundedNext/FTMO).
Escribe un único mensaje de commit usando el estándar de "Conventional Commits" basado en el siguiente 'git diff'.

Tipos permitidos:
- feat: (nuevas características, reglas de trading, endpoints, dashboards)
- fix: (solución de bugs, cálculos de lotaje o fricción, drawdown)
- refactor: (limpieza y organización de código sin cambiar comportamiento)
- chore: (mantenimiento de scripts, diagramas, CI/CD, dependencias)

REGLAS ESTRICTAS:
1. Devuelve ÚNICAMENTE el mensaje del commit en una sola línea. Sin explicaciones, ni saludos, ni comillas, ni markdown.
2. El mensaje DEBE estar en idioma Español.
3. Sé conciso pero informativo (ej: feat: blindaje anti-sobreoperacion y modo micro-lote).

DIFF DE CÓDIGO:
{diff[:25000]}
"""

    print("🧠 Copia el siguiente texto y pégalo en el chat de la IA para generar el mensaje de commit:\n")
    print("-" * 60)
    print(prompt)
    print("-" * 60)
    
    commit_msg = input("\n📝 Pega aquí el mensaje generado por la IA (o escribe el tuyo propio) y presiona Enter: ").strip()
    
    if not commit_msg:
        print("❌ Operación cancelada. No se ingresó ningún mensaje.")
        return
        
    commit_msg = commit_msg.strip('`').strip('"').strip("'").replace('\n', ' ')
    
    try:
        print(f"\n🚀 Haciendo Commit y Push a GitHub con el mensaje: '{commit_msg}'...")
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push"], check=True)
        
        print("\n✅ ¡ÉXITO! El código fue subido a GitHub.")
        print("🤖 GitHub Actions (.github/workflows/release.yml) ahora detectará el prefijo y creará el Release SemVer automáticamente.")
        
    except Exception as e:
        print(f"❌ Error al subir a Git: {e}")

if __name__ == "__main__":
    main()
