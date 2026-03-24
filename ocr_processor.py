"""
Módulo OCR - Extrae NUI, nombres, apellidos de cédula ecuatoriana
"""
import re
import easyocr
import os
from PIL import Image
import tempfile

class CedulaOCR:
    def __init__(self):
        self.reader = None
    
    def _inicializar_ocr(self):
        if self.reader is None:
            print("Iniciando EasyOCR (optimizado)...")
            # Máximas optimizaciones para macOS
            self.reader = easyocr.Reader(
                ['es'],  # Solo español = MÁS RÁPIDO
                gpu=False,
                model_storage_directory='/tmp/easyocr_models',
                user_network_directory='/tmp/easyocr_user',
                verbose=False,  # No imprimir debug
                quantize=True   # Usar modelos cuantificados = MÁS RÁPIDO
            )
            print("EasyOCR listo (español solamente)")
    
    def _recortar_imagen(self, ruta_imagen: str, recorte_arriba: float = 0.17, recorte_izquierda: float = 0.2) -> str:
        """
        Recorta la imagen eliminando todo el marco
        Luego REDUCE el tamaño para OCR más rápido
        """
        try:
            # Abrir imagen
            img = Image.open(ruta_imagen)
            ancho, alto = img.size
            
            print(f"[RECORTE] Imagen original: {ancho}x{alto}")
            
            # Calcular coordenadas de recorte
            top = int(alto * recorte_arriba)
            left = int(ancho * recorte_izquierda)
            right = ancho
            bottom = alto
            
            # Realizar recorte
            img_recortada = img.crop((left, top, right, bottom))
            
            # OPTIMIZACIÓN: Reducir tamaño a 50% para OCR más rápido
            # (Sigue siendo legible pero procesa 75% más rápido)
            nuevo_ancho = img_recortada.width // 2
            nuevo_alto = img_recortada.height // 2
            img_recortada = img_recortada.resize((nuevo_ancho, nuevo_alto), Image.Resampling.LANCZOS)
            
            print(f"[RECORTE] Imagen redimensionada: {nuevo_ancho}x{nuevo_alto} para OCR rápido")
            
            # Guardar imagen procesada
            img_recortada.save(ruta_imagen, quality=85)
            
            return ruta_imagen
            
        except Exception as e:
            print(f"Error recortando imagen: {e}")
            import traceback
            traceback.print_exc()
            return ruta_imagen
    
    def extraer_datos_cedula(self, ruta_imagen: str) -> dict:
        try:
            self._inicializar_ocr()
            
            print("[OCR] Iniciando procesamiento...")
            
            # Recortar imagen antes del OCR
            ruta_imagen_recortada = self._recortar_imagen(ruta_imagen)
            
            # OCR MAXIMAMENTE OPTIMIZADO PARA macOS
            print("[OCR] Ejecutando readtext...")
            resultado = self.reader.readtext(
                ruta_imagen_recortada, 
                detail=1,
                batch_size=4,      # Mejor para macOS
                workers=4,         # Más workers = más rápido
                add_margin=0.1,    # Reducir cálculos
                paragraph=False,   # Desactivar análisis de párrafos
                rotation_info=None  # No analizar rotación
            )
            
            print("[OCR] Procesamiento completado, extrayendo texto...")
            
            texto_completo = ""
            
            # Filtrar por confianza más moderada (0.4)
            for deteccion in resultado:
                text = deteccion[1]
                confidence = deteccion[2]
                if confidence > 0.4:
                    texto_completo += text + "\n"
            
            print(f"[OCR TEXT]:\n{texto_completo}\n")
            
            nui = self._extraer_nui(texto_completo)
            nombres = self._extraer_nombres(texto_completo)
            apellidos = self._extraer_apellidos(texto_completo)
            
            return {
                "nui": nui,
                "nombres": nombres,
                "apellidos": apellidos
            }
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return {"nui": None, "nombres": None, "apellidos": None, "error": str(e)}
    
    def _extraer_nui(self, texto: str) -> str:
        match = re.search(r'NUI[:\s\.]*([01][1-9]\d{8})', texto, re.IGNORECASE)
        if match:
            return match.group(1)
        matches = re.findall(r'([01][1-9]\d{8})', texto)
        return matches[0] if matches else None
    
    def _extraer_nombres(self, texto: str) -> str:
        """
        Extrae nombres (1-2 palabras) después de la etiqueta NOMBRES
        Ejemplo: "NOMBRES MARTÍN ALEXANDER" -> "MARTÍN ALEXANDER"
        """
        texto_upper = texto.upper()
        
        # Buscar la etiqueta NOMBRES o NOMBRE
        match = re.search(r'NOMBRE[S]?\s+([A-Z][A-ZÁ-Ú\s\-]{3,})', texto_upper)
        if not match:
            return None
        
        # Extraer texto después de NOMBRES
        texto_nombres = match.group(1).strip()
        
        # Capturar 1-2 palabras (evitar palabras muy cortas)
        palabras = []
        for palabra in texto_nombres.split():
            # Saltar palabras de etiquetas siguientes
            if palabra in {'NACIONALIDAD', 'SEXO', 'FECHA', 'CONDICION', 'CIUDADANIA', 'LUGAR', 'NACIMIENTO'}:
                break
            if len(palabra) >= 3 and palabra not in {'NNA', 'NAC', 'DEL', 'LA', 'LOS'}:
                palabras.append(palabra)
            if len(palabras) == 2:  # Máximo 2 nombres
                break
        
        resultado = ' '.join(palabras)
        return resultado if len(resultado) >= 4 else None
    
    def _extraer_apellidos(self, texto: str) -> str:
        """
        Extrae apellidos (1-2 palabras) después de la etiqueta APELLIDOS
        Ejemplo: "APELLIDOS SIMBAÑA LIMA" -> "SIMBAÑA LIMA"
        """
        texto_upper = texto.upper()
        
        # Buscar la etiqueta APELLIDOS o APELLIDO
        match = re.search(r'APELLIDO[S]?\s+([A-Z][A-ZÁ-Ú\s\-]{3,})', texto_upper)
        if not match:
            return None
        
        # Extraer texto después de APELLIDOS
        texto_apellidos = match.group(1).strip()
        
        # Capturar 1-2 palabras
        palabras = []
        for palabra in texto_apellidos.split():
            # Saltar palabras de etiquetas siguientes
            if palabra in {'NOMBRES', 'NACIONALIDAD', 'SEXO', 'FECHA', 'CONDICION', 'CIUDADANIA', 'LUGAR', 'NACIMIENTO'}:
                break
            if len(palabra) >= 3 and palabra not in {'NNA', 'NAC', 'DEL', 'LA', 'LOS', 'SIMBA'}:
                palabras.append(palabra)
            if len(palabras) == 2:  # Máximo 2 apellidos
                break
        
        resultado = ' '.join(palabras)
        return resultado if len(resultado) >= 4 else None
    
    def _limpiar(self, texto: str, max_palabras: int) -> str:
        malas = {'REPUBLICA', 'DEL', 'ECUADOR', 'DIRECCION', 'CIVIL', 'IDENTIFICACION', 'CEDULA', 'IDENTIDAD', 'INSTITUCION', 'ECUATORIANA', 'ULA', 'FECHA', 'HOMBRE', 'MUJER'}
        palabras = [p for p in texto.split() if len(p) >= 2 and p.upper() not in malas]
        resultado = ' '.join(palabras[:max_palabras])
        return resultado if len(resultado) > 2 else None

ocr_processor = CedulaOCR()
