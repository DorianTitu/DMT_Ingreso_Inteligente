"""
Módulo de captura de cámaras ONVIF-Dahua
"""

from .camara_placa_entrada_vehicular import capture_camera1
from .camara_usuario_entrada_vehicular import capture_camera3
from .camara_cedula_entrada_vehicular import (
    capture_camera250, 
    extraer_datos_cedula,
    capturar_y_extraer_cedula
)

__all__ = [
    'capture_camera1', 
    'capture_camera3', 
    'capture_camera250',
    'extraer_datos_cedula',
    'capturar_y_extraer_cedula'
]
