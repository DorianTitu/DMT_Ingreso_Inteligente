"""
Módulo de OCR con EasyOCR para extracción de datos de cédula ecuatoriana
"""

import re
import easyocr

class CedulaOCR:
    def __init__(self):
        """Inicializar EasyOCR (lazy loading)"""
        self.reader = None
    
    def _inicializar_ocr(self):
        """Inicializar OCR la primera vez que se use"""
        if self.reader is None:
            print("Iniciando EasyOCR...")
            self.reader = easyocr.Reader(['es', 'en'], gpu=False)
            print("EasyOCR listo")
    
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
            
            # EasyOCR devuelve lista de [bbox, text, confidence]
            resultado = self.reader.readtext(ruta_imagen, detail=1)
            texto_completo = ""
            
            for deteccion in resultado:
                text = deteccion[1]
                confidence = deteccion[2]
                # Solo agregar si tiene confianza > 0.3
                if confidence > 0.3:
                    texto_completo += text + "\n"
            
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
        Extrae NUI de la cédula ecuatoriana
        Patrón: 10 dígitos, comienza con 0 o 1, segundo dígito es 1-9 (no cero)
        Ejemplo: 1754756920, 0123456789, etc
        """
        print("[DEBUG] Buscando NUI...")
        
        # Patrón 1: "NUI:1754..." o "NUI.1754..." (con etiqueta NUI)
        patron_nui_etiqueta = r'NUI[:\s\.]*([01][1-9]\d{8})'
        match = re.search(patron_nui_etiqueta, texto, re.IGNORECASE)
        if match:
            nui = match.group(1)
            print(f"[DEBUG] NUI encontrado con etiqueta: {nui}")
            return nui
        
        # Patrón 2: búsqueda genérica de [01][1-9]xxxxxxxx (10 dígitos válidos)
        patron_generico = r'([01][1-9]\d{8})'
        matches = re.findall(patron_generico, texto)
        print(f"[DEBUG] Coincidencias encontradas: {matches}")
        
        if matches:
            # Tomar el primer NUI válido
            nui = matches[0]
            print(f"[DEBUG] NUI encontrado: {nui}")
            return nui
        
        print("[DEBUG] No se encontró NUI válido")
        print(f"[DEBUG] Texto completo:\n{texto}")
        return None
    
    def _extraer_nombres(self, texto: str) -> str:
        """
        Extrae nombres (1-3 palabras después de NOMBRES)
        """
        # Buscar la palabra NOMBRES y obtener lo que viene después
        match = re.search(
            r'NOMBRES?\s+([A-Z][A-Z\s]*?)(?=NACIONALIDAD|FECHA DE|SEXO|APELLIDOS|CONDICIÓN|\n\n)',
            texto,
            re.IGNORECASE | re.DOTALL
        )
        
        if match:
            nombres = match.group(1).strip()
            # Limpiar espacios múltiples y tomar máximo 3 palabras
            nombres = ' '.join(nombres.split()[:3])
            if nombres:
                return nombres
        
        return None
    
    def _extraer_apellidos(self, texto: str) -> str:
        """
        Extrae apellidos (1-2 palabras después de APELLIDOS)
        """
        # Buscar la palabra APELLIDOS y obtener lo que viene después
        match = re.search(
            r'APELLIDOS?\s+([A-Z][A-Z\s]*?)(?=CONDICIÓN|CALLE|NACIONALIDAD|FECHA DE|SEXO|\n\n)',
            texto,
            re.IGNORECASE | re.DOTALL
        )
        
        if match:
            apellidos = match.group(1).strip()
            # Limpiar espacios múltiples y tomar máximo 2 palabras
            apellidos = ' '.join(apellidos.split()[:2])
            if apellidos:
                return apellidos
        
        return None

# Instancia global
ocr_processor = CedulaOCR()
