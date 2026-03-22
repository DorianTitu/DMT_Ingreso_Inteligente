"""
Módulo para organizar y gestionar archivos de imágenes
"""

import os
import shutil
from datetime import datetime

BASE_DIR = "snapshots_camaras"

def crear_directorio_cedula(cedula_numero: str) -> str:
    """
    Crea un directorio para una cédula si no existe
    
    Args:
        cedula_numero: Número de cédula
    
    Returns:
        Ruta del directorio de la cédula
    """
    ruta = os.path.join(BASE_DIR, "cedulas", cedula_numero)
    os.makedirs(ruta, exist_ok=True)
    return ruta

def organizar_imagenes(cedula_numero: str, archivo_temporal_cedula: str, 
                       archivo_temporal_usuario: str, archivo_temporal_placa: str) -> dict:
    """
    Organiza las imágenes capturadas en la carpeta de la cédula
    
    Args:
        cedula_numero: Número de cédula
        archivo_temporal_cedula: Ruta temporal de imagen de cédula
        archivo_temporal_usuario: Ruta temporal de imagen de usuario
        archivo_temporal_placa: Ruta temporal de imagen de placa
    
    Returns:
        dict con rutas finales de las imágenes
    """
    ruta_cedula = crear_directorio_cedula(cedula_numero)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    
    ruta_final_cedula = os.path.join(ruta_cedula, f"cedula_{timestamp}.jpg")
    ruta_final_usuario = os.path.join(ruta_cedula, f"usuario_{timestamp}.jpg")
    ruta_final_placa = os.path.join(ruta_cedula, f"placa_{timestamp}.jpg")
    
    try:
        shutil.move(archivo_temporal_cedula, ruta_final_cedula)
        shutil.move(archivo_temporal_usuario, ruta_final_usuario)
        shutil.move(archivo_temporal_placa, ruta_final_placa)
        
        return {
            "cedula": ruta_final_cedula,
            "usuario": ruta_final_usuario,
            "placa": ruta_final_placa
        }
    except Exception as e:
        print(f"Error organizando imágenes: {e}")
        return None

def limpiar_archivos_temporales(*rutas):
    """Eliminar archivos temporales"""
    for ruta in rutas:
        if ruta and os.path.exists(ruta):
            try:
                os.remove(ruta)
            except:
                pass
