"""
Modelos de base de datos
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database.config import Base

class Persona(Base):
    __tablename__ = "personas"
    
    id = Column(Integer, primary_key=True, index=True)
    cedula_numero = Column(String(20), unique=True, index=True, nullable=False)
    fecha_primera_captura = Column(DateTime, default=datetime.utcnow)
    
    capturas = relationship("Captura", back_populates="persona", cascade="all, delete-orphan")

class Captura(Base):
    __tablename__ = "capturas"
    
    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    ruta_imagen_cedula = Column(String(255), nullable=True)
    ruta_imagen_usuario = Column(String(255), nullable=True)
    ruta_imagen_placa = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    persona = relationship("Persona", back_populates="capturas")
