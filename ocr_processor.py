"""
Módulo de OCR con PaddleOCR para extracción de datos de cédula ecuatoriana
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
    
    def extraer_datos_cedula(self, ruta_imagen: str) -> dict:
        """
        Extrae datos de cédula ecuatoriana
        
        Args:
            ruta_imagen: Ruta a la imagen de la cédula
        
        Returns:
            dict con: nui, nombres, apellidos
        """
        try:
            self._inicializar_ocr()
            
            resultado = self.ocr.ocr(ruta_imagen, cls=True)
            texto_completo = ""
            
            for linea in resultado:
                for palabra in linea:
                    texto_completo += palabra[1] + "\n"
            
            print(f"Texto extraído:\n{texto_completo}\n")
            
            # Extraer NUI (10 dígitos, comienza con 0 o 1, segundo dígito no es 0)
            nui = self._extraer_nui(texto_completo)
            
            # Extraer nombres (1-2 palabras, después de "NOMBRES")
            nombres = self._extraer_nombres(texto_completo)
            
            # Extraer apellidos (1-2 palabras, después de "APELLIDOS")
            apellidos = self._extraer_apellidos(texto_completo)
            
            return {
                "nui": nui,
                "nombres": nombres,
                "apellidos": apellidos
            }
        except Exception as e:
            print(f"Error en OCR: {e}")
            return {
                "nui": None,
                "nombres": None,
                "apellidos": None,
                "error": str(e)
            }
    
    def _extraer_nui(self, texto: str) -> str:
        """
        Extrae NUI de la cédula
        Patrón: 10 dígitos, comienza con 0 o 1, segundo dígito no es 0
        """
        # Buscar números de 10 dígitos que cumplan el patrón
        numeros = re.findall(r'\b[01][\d]{9}\b', texto)
        
        for numero in numeros:
            # Verificar que segundo dígito no sea 0
            if numero[1] != '0':
                return numero
        
        return None
    
    def _extraer_nombres(self, texto: str) -> str:
        """
        Extrae nombres (1-2 palabras después de NOMBRES)
        """
        # Buscar la palabra NOMBRES y obtener lo que viene después
        match = re.search(r'NOMBRES\s+([A-Z][A-Z\s]*?)(?=NACIONALIDAD|FECHA DE|SEXO|\n\n)', texto, re.IGNORECASE)
        
        if match:
            nombres = match.group(1).strip()
            # Tomar máximo 2 palabras
            palabras = nombres.split()[:2]
            return ' '.join(palabras)
        
        return None
    
    def _extraer_apellidos(self, texto: str) -> str:
        """
        Extrae apellidos (1-2 palabras después de APELLIDOS)
        """
        # Buscar la palabra APELLIDOS y obtener lo que viene después
        match = re.search(r'APELLIDOS\s+([A-Z][A-Z\s]*?)(?=CONDICIÓN|CALLE|\n\n)', texto, re.IGNORECASE)
        
        if match:
            apellidos = match.group(1).strip()
            # Tomar máximo 2 palabras
            palabras = apellidos.split()[:2]
            return ' '.join(palabras)
        
        return None

# Instancia global
ocr_processor = CedulaOCR()
