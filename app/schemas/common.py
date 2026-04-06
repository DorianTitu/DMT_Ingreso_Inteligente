"""
Esquemas comunes compartidos entre módulos
"""

from pydantic import BaseModel
from typing import Optional


class HoraSalidaRequest(BaseModel):
    """Modelo para actualizar hora de salida por ticket"""
    ticket: str
    hora_salida: Optional[str] = None


class CedulaOCRRequest(BaseModel):
    """Modelo para extraer datos OCR desde una imagen de cédula en base64"""
    imagen_cedula_base64: str


class ActualizarRegistroVehicularRequest(BaseModel):
    """Modelo para actualizar datos de un registro vehicular"""
    ticket: str
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    cedula: Optional[str] = None
    departamento: Optional[str] = None
    motivo: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticket": "TICKET_000042",
                "nombres": "Juan",
                "apellidos": "Pérez",
                "departamento": "Administración",
                "motivo": "Visita"
            }
        }


class ActualizarRegistroPeaonalRequest(BaseModel):
    """Modelo para actualizar datos de un registro peatonal"""
    ticket: str
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    cedula: Optional[str] = None
    departamento: Optional[str] = None
    motivo: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticket": "TICKET_000042",
                "nombre": "Juan",
                "apellido": "Pérez García",
                "departamento": "Administración",
                "motivo": "Reunión importante"
            }
        }
