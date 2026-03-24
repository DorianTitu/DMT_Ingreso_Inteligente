"""
Módulo de almacenamiento de datos de cédulas
Guarda los datos extraídos en archivos CSV
"""

import os
import csv
from datetime import datetime
from typing import Dict, List, Optional

class DataStorage:
    """Maneja el almacenamiento de datos de cédulas en CSV"""
    
    def __init__(self, storage_path: str):
        """
        Inicializa el almacenamiento con una ruta base
        
        Args:
            storage_path: Ruta donde guardar los archivos
        """
        self.storage_path = storage_path
        self.ensure_directory_exists()
    
    def ensure_directory_exists(self):
        """Crea el directorio si no existe"""
        os.makedirs(self.storage_path, exist_ok=True)
    
    def get_csv_file_path(self) -> str:
        """Retorna la ruta del archivo CSV principal"""
        return os.path.join(self.storage_path, "cedulasReg.csv")
    
    def get_subdirectory_for_date(self) -> str:
        """Retorna subdirectorio con fecha actual"""
        fecha = datetime.now().strftime("%Y-%m-%d")
        subdirectory = os.path.join(self.storage_path, fecha)
        os.makedirs(subdirectory, exist_ok=True)
        return subdirectory
    
    def save_cedula_data(self, cedula_data: Dict, imagen_paths: Optional[Dict] = None) -> Dict:
        """
        Guarda los datos de una cédula en CSV
        
        Args:
            cedula_data: Dict con {nui, apellidos, nombres, tiempo_ocr, ...}
            imagen_paths: Dict con rutas de imágenes {cedula, placa, usuario}
        
        Returns:
            Dict con {success: bool, csv_file: str, error: str (si aplica)}
        """
        try:
            csv_file = self.get_csv_file_path()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Preparar datos para guardar
            row = {
                'timestamp': timestamp,
                'nui': cedula_data.get('nui'),
                'apellidos': cedula_data.get('apellidos'),
                'nombres': cedula_data.get('nombres'),
                'tiempo_ocr_segundos': cedula_data.get('tiempo_ocr'),
                'texto_completo': cedula_data.get('texto_completo', '').replace('\n', ' | '),
                'imagen_cedula': imagen_paths.get('cedula') if imagen_paths else '',
                'imagen_placa': imagen_paths.get('placa') if imagen_paths else '',
                'imagen_usuario': imagen_paths.get('usuario') if imagen_paths else ''
            }
            
            # Verificar si el archivo existe para decidir si escribir encabezados
            file_exists = os.path.isfile(csv_file)
            
            # Escribir datos en CSV
            with open(csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=row.keys())
                
                # Escribir encabezado si es la primera vez
                if not file_exists:
                    writer.writeheader()
                
                # Escribir fila
                writer.writerow(row)
            
            return {
                'success': True,
                'csv_file': csv_file,
                'timestamp': timestamp,
                'registros_guardados': 1
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def save_multiple_cedulas(self, cedulas_list: List[Dict]) -> Dict:
        """
        Guarda múltiples cédulas en CSV
        
        Args:
            cedulas_list: Lista de dicts con datos de cédulas
        
        Returns:
            Dict con resultados
        """
        try:
            csv_file = self.get_csv_file_path()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            file_exists = os.path.isfile(csv_file)
            
            with open(csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                # Usar el primer dict para obtener las claves
                if cedulas_list:
                    first_row = {
                        'timestamp': timestamp,
                        'nui': cedulas_list[0].get('nui'),
                        'apellidos': cedulas_list[0].get('apellidos'),
                        'nombres': cedulas_list[0].get('nombres'),
                        'tiempo_ocr_segundos': cedulas_list[0].get('tiempo_ocr'),
                        'texto_completo': cedulas_list[0].get('texto_completo', '').replace('\n', ' | '),
                        'imagen_cedula': '',
                        'imagen_placa': '',
                        'imagen_usuario': ''
                    }
                    
                    writer = csv.DictWriter(csvfile, fieldnames=first_row.keys())
                    
                    # Escribir encabezado si es necesario
                    if not file_exists:
                        writer.writeheader()
                    
                    # Escribir todas las filas
                    for cedula in cedulas_list:
                        row = {
                            'timestamp': timestamp,
                            'nui': cedula.get('nui'),
                            'apellidos': cedula.get('apellidos'),
                            'nombres': cedula.get('nombres'),
                            'tiempo_ocr_segundos': cedula.get('tiempo_ocr'),
                            'texto_completo': cedula.get('texto_completo', '').replace('\n', ' | '),
                            'imagen_cedula': '',
                            'imagen_placa': '',
                            'imagen_usuario': ''
                        }
                        writer.writerow(row)
            
            return {
                'success': True,
                'csv_file': csv_file,
                'registros_guardados': len(cedulas_list),
                'timestamp': timestamp
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_all_records(self) -> Dict:
        """
        Lee todos los registros del CSV
        
        Returns:
            Dict con {success: bool, records: list, total: int}
        """
        try:
            csv_file = self.get_csv_file_path()
            
            if not os.path.exists(csv_file):
                return {
                    'success': True,
                    'records': [],
                    'total': 0,
                    'mensaje': 'Archivo CSV aún no existe'
                }
            
            records = []
            with open(csv_file, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                records = list(reader)
            
            return {
                'success': True,
                'records': records,
                'total': len(records)
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_storage_info(self) -> Dict:
        """Retorna información sobre el almacenamiento"""
        csv_file = self.get_csv_file_path()
        exists = os.path.exists(csv_file)
        
        info = {
            'storage_path': self.storage_path,
            'csv_file': csv_file,
            'archivo_existe': exists
        }
        
        if exists:
            info['tamaño_bytes'] = os.path.getsize(csv_file)
            # Contar registros
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    info['total_registros'] = len(list(csv.DictReader(f)))
            except:
                info['total_registros'] = 0
        
        return info
