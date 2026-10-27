#!/usr/bin/env python3
"""
verificar_estado.py - Revisa si el comando se ejecutó y obtiene el comando de consola serie.
"""

import json
import os
import subprocess

cmd_id = "ocid1.instanceagentcommand.oc1.sa-bogota-1.amaaaaaaj6kuzwaaeg7z4c4pbmgxrve2jiuofivig37k2sj6tyonufmelo2a"
instance_id = "ocid1.instance.oc1.sa-bogota-1.anrgcljrj6kuzwacc4dj6aua7ps7wgad65mvkjv3j7a2ewhkmr7d37n6amka"

print("[*] Consultando estado de ejecucion en el agente de Oracle Cloud...")
check_cmd = [
    "oci", "instance-agent", "command-execution", "get",
    "--command-id", cmd_id,
    "--instance-id", instance_id
]
res = subprocess.run(check_cmd, capture_output=True, text=True)
if res.returncode == 0:
    data = json.loads(res.stdout)
    status = data.get("data", {}).get("lifecycle-state")
    print(f"Estado del comando: {status}")
    print(json.dumps(data, indent=2))
else:
    print("Error consultando ejecucion:")
    print(res.stderr)
