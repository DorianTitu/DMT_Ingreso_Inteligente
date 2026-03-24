"""
Captura de Camera250 (192.168.1.250)
Protocolo: RTSP
Modelo: Dahua
Incluye extracción de datos de cédula mediante OCR
"""

import subprocess
import os
import re
import time
import tempfile
from datetime import datetime
from PIL import Image
import easyocr

def capture_camera250(output_dir: str = "snapshots_camaras") -> dict:
    """
    Captura foto de Camera250 (cedula entrada vehicular)
    
    Args:
        output_dir: Directorio donde guardar la foto
    
    Returns:
        dict con estado de la captura {'success': bool, 'file': str, 'size': int}
    """
    # Configuración
    ip = "192.168.1.250"
    user = "admin"
    password = "DMT_1990"
    rtsp_url = f"rtsp://{user}:{password}@{ip}:554/"
    
    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"camara_cedula_entrada_vehicular_{timestamp}.jpg")
    
    # Comando ffmpeg para capturar desde RTSP
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
        
        # Validar captura exitosa
        if result.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            file_size = os.path.getsize(output_file)
            return {
                'success': True,
                'file': output_file,
                'size': file_size,
                'camera': 'Camera250 (Cedula)',
                'ip': ip
            }
        else:
            # Eliminar archivo si la captura no fue exitosa
            if os.path.exists(output_file):
                os.remove(output_file)
            return {
                'success': False,
                'file': None,
                'size': None,
                'camera': 'Camera250 (Cedula)',
                'ip': ip,
                'error': f'Exit code: {result.returncode}'
            }
    except subprocess.TimeoutExpired:
        if os.path.exists(output_file):
            os.remove(output_file)
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camera250 (Cedula)',
            'ip': ip,
            'error': 'Timeout'
        }
    except Exception as e:
        if os.path.exists(output_file):
            os.remove(output_file)
        return {
            'success': False,
            'file': None,
            'size': None,
            'camera': 'Camera250 (Cedula)',
            'ip': ip,
            'error': str(e)
        }


# ============ FUNCIONES OCR PARA EXTRACCIÓN DE CÉDULA ============

# Variable global para mantener el reader de OCR en memoria
_ocr_reader = None

def _inicializar_ocr():
    """Inicializa el reader de OCR (se mantiene en memoria)"""
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(
            ['es'],  # Solo español para más velocidad
            gpu=False,
            verbose=False
        )
    return _ocr_reader

def _recortar_imagen_cedula(ruta_imagen: str) -> str:
    """
    Recorta la imagen de cédula eliminando márgenes
    Reduce el tamaño para aceleración de OCR
    
    Args:
        ruta_imagen: Ruta del archivo de imagen
    
    Returns:
        str: Ruta de la imagen procesada
    """
    try:
        img = Image.open(ruta_imagen)
        ancho, alto = img.size
        
        # Recortar márgenes (17% arriba, 20% izquierda)
        top = int(alto * 0.17)
        left = int(ancho * 0.2)
        right = ancho
        bottom = alto
        
        img_recortada = img.crop((left, top, right, bottom))
        
        # Reducir tamaño a 50% para OCR más rápido
        nuevo_ancho = img_recortada.width // 2
        nuevo_alto = img_recortada.height // 2
        img_recortada = img_recortada.resize(
            (nuevo_ancho, nuevo_alto), 
            Image.Resampling.LANCZOS
        )
        
        img_recortada.save(ruta_imagen, quality=85)
        return ruta_imagen
        
    except Exception as e:
        print(f"Error recortando imagen: {e}")
        return ruta_imagen

def extraer_datos_cedula(ruta_imagen: str) -> dict:
    """
    Extrae datos de cédula ecuatoriana (NUI, apellidos, nombres) mediante OCR
    Usa patrones específicos para cédulas del Ecuador
    
    Args:
        ruta_imagen: Ruta del archivo de imagen de cédula (ya procesada/recortada)
    
    Returns:
        dict con los datos extraídos: {
            'success': bool,
            'nui': str,
            'apellidos': str,
            'nombres': str,
            'tiempo_ocr': float,
            'error': str (si aplica)
        }
    """
    try:
        if not os.path.exists(ruta_imagen):
            return {
                'success': False,
                'error': f'Archivo no encontrado: {ruta_imagen}'
            }
        
        # Inicializar OCR
        reader = _inicializar_ocr()
        
        # Medir tiempo de OCR
        tiempo_inicio = time.time()
        
        # Ejecutar OCR directamente
        resultados = reader.readtext(ruta_imagen, detail=1)
        
        tiempo_ocr = time.time() - tiempo_inicio
        
        # Extraer texto con confianza > 0.4
        texto_completo = ""
        for deteccion in resultados:
            if deteccion[2] > 0.4:  # Confianza > 0.4
                texto_completo += deteccion[1] + "\n"
        
        # ===== EXTRACCIÓN DE NUI (OPTIMIZADA) =====
        nui = None
        
        # Patrón 1: "No " o "No." seguido de dígitos (más común)
        patron_no = r'No\.?\s+(\d{9,13}(?:-\d)?)'
        match = re.search(patron_no, texto_completo)
        if match:
            nui = match.group(1).strip()
        
        # Patrón 2: "CÉDULA DE\n" seguido de dígitos
        if not nui:
            patron_cedula = r'CÉDULA\s+DE\s+(?:No\s+)?(\d{9,13}(?:-\d)?)'
            match = re.search(patron_cedula, texto_completo, re.IGNORECASE | re.MULTILINE)
            if match:
                nui = match.group(1).strip()
        
        # Patrón 3: Números aislados de 10-11 dígitos (rango típico ecuatoriano)
        if not nui:
            matches = re.findall(r'\b(\d{10,11})\b', texto_completo)
            if matches:
                nui = matches[0]
        
        # Patrón 4: "NUI." (última opción, frecuentemente al final)
        if not nui:
            patron_nui = r'NUI\.?\s*(\d{9,13}(?:-\d)?)'
            match = re.search(patron_nui, texto_completo, re.IGNORECASE)
            if match:
                nui = match.group(1).strip()
        
        # Limpiar NUI
        if nui:
            nui = nui.replace(' ', '').replace('-', '').strip()
            if not re.match(r'^\d{8,13}$', nui):
                nui = None
        
        # ===== EXTRACCIÓN DE APELLIDOS (OPTIMIZADA) =====
        apellidos = None
        
        # Patrón: Busca "APELLIDOS" y captura TODO hasta "NOMBRES"
        patron_apellidos = r'APELL?IDOS?\s*\n([\s\S]*?)(?=NOMBRES?)'
        match = re.search(patron_apellidos, texto_completo, re.IGNORECASE | re.MULTILINE)
        
        if match:
            texto_apellidos = match.group(1).strip()
            
            # Eliminar líneas que son etiquetas/labels (CONDICIÓN, CIUDADANÍA, etc.)
            lineas = texto_apellidos.split('\n')
            lineas_filtradas = []
            
            for linea in lineas:
                linea_limpia = linea.strip()
                # Ignorar líneas que contienen palabras clave de labels
                if linea_limpia and not re.search(
                    r'CONDICIÓN|CIUDADAN|EXTRANJERO|ECUATORIAN',
                    linea_limpia,
                    re.IGNORECASE
                ):
                    lineas_filtradas.append(linea_limpia)
            
            # Unir líneas filtradas
            if lineas_filtradas:
                apellidos = ' '.join(lineas_filtradas)
                # Limitar a máximo 2 palabras (para cédula ecuatoriana)
                palabras = apellidos.split()
                if len(palabras) > 2:
                    apellidos = ' '.join(palabras[:2])
        
        # ===== EXTRACCIÓN DE NOMBRES (OPTIMIZADA) =====
        nombres = None
        
        # Patrón: Busca "NOMBRES" y captura TODO hasta NACIONALIDAD, FECHA o final
        patron_nombres = r'NOMBRES?\s*\n([\s\S]*?)(?=NACIONALIDAD|FECHA|LUGAR|CONDICIÓN|AUTOIDENTICACION|$)'
        match = re.search(patron_nombres, texto_completo, re.IGNORECASE | re.MULTILINE)
        
        if match:
            texto_nombres = match.group(1).strip()
            
            # Limpiar líneas en blanco y espacios extras
            lineas = texto_nombres.split('\n')
            lineas_filtradas = []
            
            for linea in lineas:
                linea_limpia = linea.strip()
                # Solo aceptar líneas que empiezan con letra mayúscula (nombres)
                if linea_limpia and re.match(r'^[A-ZÁÉÍÓÚÑ]', linea_limpia):
                    lineas_filtradas.append(linea_limpia)
            
            # Unir líneas y limpiar
            if lineas_filtradas:
                nombres = ' '.join(lineas_filtradas)
                # Limpiar espacios extras
                nombres = ' '.join(nombres.split())
                # Limitar a máximo 3 palabras (para cédula ecuatoriana)
                palabras = nombres.split()
                if len(palabras) > 3:
                    nombres = ' '.join(palabras[:3])
        
        return {
            'success': True,
            'nui': nui,
            'apellidos': apellidos,
            'nombres': nombres,
            'tiempo_ocr': round(tiempo_ocr, 2),
            'texto_completo': texto_completo
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'tiempo_ocr': 0
        }

def capturar_y_extraer_cedula(output_dir: str = "snapshots_camaras") -> dict:
    """
    Ejecuta la captura de cédula Y extrae automáticamente
    los datos mediante OCR en una sola llamada
    
    Flujo optimizado:
    1. Captura imagen de Camera250
    2. Recorta imagen inmediatamente (preprocesamiento)
    3. Extrae datos con OCR de imagen recortada
    
    Args:
        output_dir: Directorio de salida
    
    Returns:
        dict con resultado de captura + datos de cédula
    """
    try:
        # PASO 1: Capturar la imagen
        resultado_captura = capture_camera250(output_dir)
        
        if not resultado_captura['success']:
            return {
                'success': False,
                'error': 'Fallo en captura de imagen',
                'captura': resultado_captura
            }
        
        # PASO 2: Recortar imagen inmediatamente (ANTES del OCR)
        archivo_imagen = resultado_captura['file']
        print(f"[CAPTURA] Imagen capturada: {archivo_imagen}")
        
        print(f"[RECORTE] Procesando imagen para OCR...")
        _recortar_imagen_cedula(archivo_imagen)
        print(f"[RECORTE] ✅ Imagen recortada y optimizada")
        
        # PASO 3: Extraer datos de cédula (OCR en imagen recortada)
        print(f"[OCR] Iniciando extracción de datos...")
        resultado_ocr = extraer_datos_cedula(archivo_imagen)
        
        if resultado_ocr['success']:
            print(f"[OCR] ✅ Datos extraídos exitosamente")
        
        return {
            'success': resultado_ocr['success'],
            'captura': {
                'file': resultado_captura['file'],
                'size': resultado_captura['size'],
                'camera': resultado_captura['camera'],
                'ip': resultado_captura['ip']
            },
            'cedula': {
                'nui': resultado_ocr.get('nui'),
                'apellidos': resultado_ocr.get('apellidos'),
                'nombres': resultado_ocr.get('nombres'),
                'tiempo_ocr': resultado_ocr.get('tiempo_ocr'),
                'texto_completo': resultado_ocr.get('texto_completo')
            } if resultado_ocr['success'] else None,
            'error': resultado_ocr.get('error')
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Error en captura y extracción: {str(e)}'
        }
