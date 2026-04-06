"""
Esquemas para ingreso vehicular
"""

from pydantic import BaseModel
from typing import Optional


class RegistroVehicularRequest(BaseModel):
    """Modelo para guardar un registro vehicular completo"""
    nombres: str
    apellidos: str
    cedula: str
    departamento: str
    motivo: str
    imagen_cedula_base64: Optional[str] = None
    imagen_usuario_base64: Optional[str] = None
    imagen_placa_base64: Optional[str] = None
    hora_ingreso: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "nombres": "Juan",
                "apellidos": "Pérez",
                "cedula": "1234567890",
                "departamento": "Administración",
                "motivo": "Visita",
                "imagen_cedula_base64": "base64_string...",
                "imagen_usuario_base64": "base64_string...",
                "imagen_placa_base64": "base64_string...",
                "hora_ingreso": "14:30:45"
            }
        }
