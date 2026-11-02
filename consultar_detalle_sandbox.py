# -*- coding: utf-8 -*-
"""
consultar_detalle_sandbox.py
Consulta y muestra el detalle exhaustivo de las operaciones del
Laboratorio Sandbox (3 Cuentas Independientes de $10,000 c/u en Oracle VPS).
"""

import os
import subprocess

def main():
    key_candidates = [
        os.path.expanduser(r"~\.ssh\oracle_vps.key"),
        os.path.expanduser(r"~\.ssh\ssh-key-2026-10-26.key"),
        os.path.abspath(r"VPS-Oracle\oracle_vps.key")
    ]
    key_path = next((k for k in key_candidates if os.path.exists(k)), "")
    
    cmd = [
        "ssh",
        "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "ubuntu@157.137.225.144",
        "cd /home/ubuntu/FTMO_Stellar_Lite && python3 main.py sandbox"
    ]
    try:
        subprocess.run(cmd)
    except Exception as e:
        print(f"[!] Error al conectar con el servidor VPS: {e}")

if __name__ == "__main__":
    main()
