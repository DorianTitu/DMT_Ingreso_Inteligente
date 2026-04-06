"""
Esquemas para ingreso peatonal
"""

from pydantic import BaseModel
from typing import Optional


class RegistroPeaonalRequest(BaseModel):
    """Modelo para guardar un registro de ingreso peatonal completo"""
    nombre: str
    apellido: str
    cedula: str
    departamento: str
    motivo: Optional[str] = None
    imagen_cedula_base64: Optional[str] = None
    imagen_usuario_base64: Optional[str] = None
    hora_ingreso: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "nombre": "Juan",
                "apellido": "Pérez García",
                "cedula": "1234567890",
                "departamento": "Administración",
                "motivo": "Reunión importante",
                "imagen_cedula_base64": "base64_string...",
                "imagen_usuario_base64": "base64_string...",
                "hora_ingreso": "14:30:45"
            }
        }
