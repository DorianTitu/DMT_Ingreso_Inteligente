"""
Módulo de OCR con PaddleOCR para extracción de datos de cédula
"""

import re
from paddleocr import PaddleOCR

class CedulaOCR:
    def __init__(self):
        """Inicializar PaddleOCR (lazy loading)"""
        self.ocr = None
    
    def _inicializar_ocr(self):
        """Inicializar OCR la primera vez que se use"""
        if self.ocr is None:
            print("Iniciando PaddleOCR...")
            self.ocr = PaddleOCR(use_angle_cls=True, lang='es')
            print("PaddleOCR listo")
    
    def extraer_numero_cedula(self, ruta_imagen: str) -> str:
        """
        Extrae el número de cédula de una imagen
        
        Args:
            ruta_imagen: Ruta a la imagen de la cédula
        
        Returns:
            Número de cédula extraído (string de 10 dígitos)
        """
        try:
            self._inicializar_ocr()
            
            resultado = self.ocr.ocr(ruta_imagen, cls=True)
            texto_completo = ""
            
            for linea in resultado:
                for palabra in linea:
                    texto_completo += palabra[1] + " "
            
            # Buscar patrón de cédula ecuatoriana (10 dígitos)
            cedulas = re.findall(r'\b\d{10}\b', texto_completo)
            
            if cedulas:
                return cedulas[0]
            
            return None
        except Exception as e:
            print(f"Error en OCR: {e}")
            return None

# Instancia global
ocr_processor = CedulaOCR()
