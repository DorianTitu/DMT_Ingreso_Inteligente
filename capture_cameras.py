#!/usr/bin/env python3
"""
Sistema de captura de cámaras ONVIF-Dahua
Captura fotos de múltiples cámaras y las guarda con timestamp

Cámaras soportadas:
- Camera1 (192.168.1.108): HTTP snapshot + autenticación digest
- Camera3 (192.168.1.223): RTSP
- Camera250 (192.168.1.250): RTSP
"""

import subprocess
import os
from datetime import datetime

# ============ CONFIGURACIÓN ============
OUTPUT_DIR = "snapshots_camaras"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

CAMERAS = {
    "camara_placa_entrada_vehicular": {
        "ip": "192.168.1.108",
        "tipo": "http",
        "user": "admin",
        "password": "dmt_2390",
        "url": "http://{ip}/cgi-bin/snapshot.cgi"
    },
    "camara_usuario_entrada_vehicular": {
        "ip": "192.168.1.223",
        "tipo": "rtsp",
        "user": "admin",
        "password": "DMT_1990",
        "url": "rtsp://{user}:{password}@{ip}:554/"
    },
    "camara_cedula_entrada_vehicular": {
        "ip": "192.168.1.250",
        "tipo": "rtsp",
        "user": "admin",
        "password": "DMT_1990",
        "url": "rtsp://{user}:{password}@{ip}:554/"
    }
}

# ============ FUNCIONES ============
def create_output_dir():
    """Crea la carpeta de salida si no existe"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def capture_http(ip, user, password, url, output_file):
    """Captura vía HTTP con curl"""
    cmd = [
        'curl',
        '--digest',
        '-u', f'{user}:{password}',
        '-s',
        '-o', output_file,
        '-w', '%{http_code}',
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
        http_code = result.stdout.strip()
        
        if http_code == '200' and os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            return True, os.path.getsize(output_file)
        return False, None
    except:
        return False, None

def capture_rtsp(user, password, ip, output_file):
    """Captura vía RTSP con ffmpeg"""
    rtsp_url = f"rtsp://{user}:{password}@{ip}:554/"
    cmd = [
        'ffmpeg',
        '-rtsp_transport', 'tcp',
        '-i', rtsp_url,
        '-vframes', '1',
        '-q:v', '5',
        '-y',
        output_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        if result.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            return True, os.path.getsize(output_file)
        return False, None
    except:
        return False, None

def capture_camera(name, config):
    """Captura foto de una cámara"""
    ip = config["ip"]
    output_file = f"{OUTPUT_DIR}/{name}_{TIMESTAMP}.jpg"
    
    print(f"{name} ({ip})...", end=" ", flush=True)
    
    if config["tipo"] == "http":
        url = config["url"].format(ip=ip)
        success, size = capture_http(ip, config["user"], config["password"], url, output_file)
    else:  # rtsp
        success, size = capture_rtsp(config["user"], config["password"], ip, output_file)
    
    if success:
        print(f"OK ({size:,} bytes)")
        return True
    else:
        print(f"ERRO")
        # Eliminar archivo si no fue exitosa la captura
        if os.path.exists(output_file):
            os.remove(output_file)
        return False

def main():
    """Función principal"""
    print("=" * 50)
    print("CAPTURA DE CAMARAS ONVIF-DAHUA")
    print("=" * 50 + "\n")
    
    create_output_dir()
    
    success_count = 0
    total_count = len(CAMERAS)
    
    for name, config in CAMERAS.items():
        if capture_camera(name, config):
            success_count += 1
    
    print(f"\n{'=' * 50}")
    print(f"Captura completada: {success_count}/{total_count} camaras")
    print(f"Fotos guardadas en: {OUTPUT_DIR}/")
    print(f"{'=' * 50}\n")

if __name__ == "__main__":
    main()
