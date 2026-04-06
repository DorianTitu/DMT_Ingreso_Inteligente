"""
Configuración centralizada de la aplicación
Carga variables de entorno y constantes
"""

import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ============ DIRECTORIOS ============
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "dmt_capture_tmp")

# ============ RUTAS DE ALMACENAMIENTO ============
REGISTRO_VEHICULAR_PATH = os.environ.get(
    'REGISTRO_VEHICULAR_PATH',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'registros_vehiculares')
)

REGISTRO_PEATONAL_PATH = os.environ.get(
    'REGISTRO_PEATONAL_PATH',
    r'C:\Users\LENOVO\Documents\Base de datos\DMT_Gestion_Ingreso\Ingreso Peatonal'
)

# ============ API INFO ============
API_TITLE = "Camera Capture API"
API_DESCRIPTION = "API para capturar imágenes de cámaras Dahua ONVIF y guardar registros"
API_VERSION = "1.0.0"

# ============ MESES ============
MESES = {
    1: "01_Enero", 2: "02_Febrero", 3: "03_Marzo", 4: "04_Abril",
    5: "05_Mayo", 6: "06_Junio", 7: "07_Julio", 8: "08_Agosto",
    9: "09_Septiembre", 10: "10_Octubre", 11: "11_Noviembre", 12: "12_Diciembre"
}
