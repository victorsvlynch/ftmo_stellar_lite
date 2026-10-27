#!/usr/bin/env python3
"""
reparar_clave.py - Script para ejecutar dentro de Oracle Cloud Shell.
Reinyecta la clave pública oficial de forma desatendida y repara permisos en vps-oracle.
"""

import json
import os
import subprocess
import sys

pubkey = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC3Lspu+7uohHaP7n2lCaEFa6ZlbXhA7cxSuQyJl6/QEfbTXjaCY5ku6RWhiw9xhGq7xSFUxwbgDY5zcf58BAcMzfEUrTnqm1UVuxJ+3f3PQQVZS1cjZquW53CCcJo40HzthoatFwNjDNzzUmo2CJG8oxr0vYYKJf69K/l8pKHAkwo+UelVnJeqSoJ5poq4IOC3yxSUTw/ahxbiOvuxtuYvdZ3qOamKz7g45jKBkkjvviCValu5vgsHf7YmS00yLEajFu3xN6CBPVLTKAtxU6nj3pAJQOQDrOM+M3Oznts3A56lSwsC3ypqh7n+vUzm9B3KwF/8ovJeuneB/a/g/TyP ssh-key-2026-10-22"

remote_script = f"""mkdir -p /home/ubuntu/.ssh
echo "{pubkey}" > /home/ubuntu/.ssh/authorized_keys
chown -R ubuntu:ubuntu /home/ubuntu
chmod 755 /home/ubuntu
chmod 700 /home/ubuntu/.ssh
chmod 600 /home/ubuntu/.ssh/authorized_keys
systemctl restart ssh
"""

content = {
    "source": {
        "sourceType": "TEXT",
        "text": remote_script
    }
}

content_file = os.path.expanduser("~/content.json")
with open(content_file, "w", encoding="utf-8") as f:
    json.dump(content, f)

tenancy = os.environ.get("OCI_TENANCY")
if not tenancy:
    print("[ERROR] Variable OCI_TENANCY no encontrada en Cloud Shell.")
    sys.exit(1)

instance_id = "ocid1.instance.oc1.sa-bogota-1.anrgcljrj6kuzwacc4dj6aua7ps7wgad65mvkjv3j7a2ewhkmr7d37n6amka"

cmd = [
    "oci", "instance-agent", "command", "create",
    "--compartment-id", tenancy,
    "--target", json.dumps({"instanceId": instance_id}),
    "--content", f"file://{content_file}",
    "--timeout-in-seconds", "600",
    "--display-name", "Restore-Ubuntu-Key"
]

print("[*] Enviando comando de reparacion a la maquina virtual...")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode == 0:
    print("\n[EXITO] Clave publica reinyectada y permisos corregidos!")
    print(res.stdout)
    print("\nEspera 15 segundos y prueba abrir la sesion en MobaXterm o con Control_Servicios.bat.")
else:
    print("\n[ERROR]")
    print(res.stderr)
    sys.exit(res.returncode)
