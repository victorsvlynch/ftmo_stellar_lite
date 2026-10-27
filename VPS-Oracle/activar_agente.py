#!/usr/bin/env python3
"""
activar_agente.py - Habilita el plugin 'Compute Instance Run Command' en vps-oracle
para que el agente de Oracle Cloud procese la orden de reparacion de claves SSH.
"""

import json
import os
import subprocess
import sys

instance_id = "ocid1.instance.oc1.sa-bogota-1.anrgcljrj6kuzwacc4dj6aua7ps7wgad65mvkjv3j7a2ewhkmr7d37n6amka"

print("[1/3] Consultando configuracion actual de plugins del agente en Oracle...")
res = subprocess.run(
    ["oci", "compute", "instance", "get", "--instance-id", instance_id, "--query", 'data."agent-config"'],
    capture_output=True,
    text=True
)

if res.returncode != 0:
    print("[ERROR] No se pudo obtener la configuracion:")
    print(res.stderr)
    sys.exit(1)

cfg = json.loads(res.stdout) if res.stdout.strip() else {}

plugins = cfg.get("plugins-config", [])
found = False
for p in plugins:
    if p.get("name") == "Compute Instance Run Command":
        p["desired-state"] = "ENABLED"
        found = True
if not found:
    plugins.append({"name": "Compute Instance Run Command", "desired-state": "ENABLED"})

cfg["plugins-config"] = plugins
cfg["is-management-disabled"] = False

config_path = os.path.expanduser("~/agent-config.json")
with open(config_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)

print("[2/3] Activando plugin 'Compute Instance Run Command'...")
update_res = subprocess.run(
    [
        "oci", "compute", "instance", "update",
        "--instance-id", instance_id,
        "--agent-config", f"file://{config_path}",
        "--force"
    ],
    capture_output=True,
    text=True
)

if update_res.returncode == 0:
    print("\n[EXITO] Plugin de ejecucion activado en Oracle Cloud!")
    print("[3/3] Reenviando orden de restauracion de claves SSH...")
    # Reenviar el script de reparacion
    subprocess.run(["python3", os.path.expanduser("~/reparar_clave.py")])
    print("\nEl agente interno procesara la clave en aproximadamente 60 segundos.")
else:
    print("\n[ERROR al actualizar agente]:")
    print(update_res.stderr)
