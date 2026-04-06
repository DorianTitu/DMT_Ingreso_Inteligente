"""
Servicio de lógica de ingreso peatonal
Orquesta captura, OCR y persistencia de peatones
"""

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from app.schemas.peatonal import RegistroPeaonalRequest
from app.schemas.common import ActualizarRegistroPeaonalRequest


class ServicioPeatonal:
    """Servicio para gestionar registros de peatones"""
    
    def __init__(self, registro_manager):
        """
        Inicializa el servicio con el gestor de registros
        
        Args:
            registro_manager: Instancia de RegistroPeatonal
        """
        self.registro_manager = registro_manager
    
    def guardar_registro(self, registro: RegistroPeaonalRequest) -> JSONResponse:
        """Guarda un registro completo de ingreso peatonal"""
        if self.registro_manager is None:
            raise HTTPException(
                status_code=500,
                detail="El sistema de registro de peatones no está inicializado"
            )
        
        try:
            # Preparar datos
            datos = {
                'nombre': registro.nombre,
                'apellido': registro.apellido,
                'cedula': registro.cedula,
                'departamento': registro.departamento,
                'motivo': registro.motivo,
                'imagen_cedula_base64': registro.imagen_cedula_base64,
                'imagen_usuario_base64': registro.imagen_usuario_base64,
                'hora_ingreso': registro.hora_ingreso
            }
            
            # Guardar registro
            resultado = self.registro_manager.guardar_registro(datos)
            
            if resultado.get('success'):
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "numero_ticket": resultado['numero_ticket'],
                        "codigo_ticket": f"TICKET_{resultado['numero_ticket']:06d}",
                        "ruta_ticket": resultado['ruta_ticket'],
                        "imagenes_guardadas": resultado['imagenes'],
                        "mensaje": resultado['mensaje']
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error al guardar registro peatonal: {resultado.get('error', 'Desconocido')}"
                )
        
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando registro peatonal: {str(e)}"
            )
    
    def obtener_todos_tickets(self) -> JSONResponse:
        """Lista todos los tickets del Excel maestro de peatones"""
        if self.registro_manager is None:
            raise HTTPException(
                status_code=500,
                detail="El sistema de registro de peatones no está inicializado"
            )

        resultado = self.registro_manager.obtener_todos_tickets()
        if not resultado.get('success'):
            raise HTTPException(
                status_code=500,
                detail=f"Error leyendo tickets peatonales: {resultado.get('error', 'Desconocido')}"
            )

        return JSONResponse(
            status_code=200,
            content={
                'success': True,
                'total': resultado.get('cantidad', 0),
                'tickets': resultado.get('tickets', []),
            }
        )
    
    def obtener_fotos_ticket(self, ticket: str) -> JSONResponse:
        """Obtiene fotos guardadas para un ticket de peatón"""
        if self.registro_manager is None:
            raise HTTPException(
                status_code=500,
                detail="El sistema de registro de peatones no está inicializado"
            )

        resultado = self.registro_manager.obtener_fotos_por_ticket(ticket)
        if not resultado.get('success'):
            detalle = resultado.get('error', 'Desconocido')
            status_code = 404 if 'No se encontró carpeta' in detalle else 400
            raise HTTPException(status_code=status_code, detail=detalle)

        return JSONResponse(status_code=200, content=resultado)
    
    def obtener_informacion_completa_ticket(self, ticket: str) -> JSONResponse:
        """Obtiene toda la información del ticket peatonal + fotos"""
        if self.registro_manager is None:
            raise HTTPException(
                status_code=500,
                detail="El sistema de registro de peatones no está inicializado"
            )
        
        try:
            # Obtener todos los tickets para buscar el específico
            resultado_tickets = self.registro_manager.obtener_todos_tickets()
            if not resultado_tickets.get('success'):
                raise HTTPException(
                    status_code=500,
                    detail=f"Error leyendo tickets peatonales: {resultado_tickets.get('error', 'Desconocido')}"
                )
            
            # Buscar el ticket específico
            tickets = resultado_tickets.get('tickets', [])
            ticket_encontrado = None
            
            # Normalizar la búsqueda del ticket
            ticket_limpio = ticket.strip().replace('TICKET_', '')
            
            for t in tickets:
                ticket_val = str(t.get('ticket', '')).strip()
                # Si el ticket del registro es "TICKET_000060", comparamos correctamente
                if ticket_val == ticket or \
                   ticket_val.replace('TICKET_', '') == ticket_limpio:
                    ticket_encontrado = t
                    break
            
            if not ticket_encontrado:
                raise HTTPException(
                    status_code=404,
                    detail=f"No se encontró el ticket peatonal {ticket}"
                )
            
            # Procesar persona (ya viene separada)
            nombre = ticket_encontrado.get('nombre', '')
            apellido = ticket_encontrado.get('apellido', '')
            
            # Obtener fotos
            resultado_fotos = self.registro_manager.obtener_fotos_por_ticket(ticket)
            
            if resultado_fotos.get('success'):
                fotos = resultado_fotos.get('fotos', [])
            else:
                fotos = []
            
            return JSONResponse(
                status_code=200,
                content={
                    'success': True,
                    'ticket': ticket,
                    'informacion': {
                        'ticket': ticket_encontrado.get('ticket'),
                        'nombre': nombre,
                        'apellido': apellido,
                        'cedula': ticket_encontrado.get('cedula'),
                        'departamento': ticket_encontrado.get('departamento'),
                        'motivo': ticket_encontrado.get('motivo'),
                        'ingreso': ticket_encontrado.get('ingreso'),
                        'salida': ticket_encontrado.get('salida_estado'),
                        'fecha_registro': ticket_encontrado.get('fecha_registro')
                    },
                    'fotos': fotos,
                    'mensaje': f"Información completa del ticket peatonal {ticket}"
                }
            )
        
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo información del ticket peatonal: {str(e)}"
            )
    
    def actualizar_hora_salida(self, ticket: str, hora_salida: Optional[str] = None) -> JSONResponse:
        """Actualiza hora de salida de un peatón por ticket"""
        if self.registro_manager is None:
            raise HTTPException(
                status_code=500,
                detail="El sistema de registro de peatones no está inicializado"
            )

        resultado = self.registro_manager.actualizar_hora_salida_por_ticket(
            ticket,
            hora_salida
        )

        if not resultado.get('success'):
            detalle = resultado.get('error', 'Desconocido')
            status_code = 404 if 'No se encontró el ticket' in detalle else 400
            raise HTTPException(status_code=status_code, detail=detalle)

        return JSONResponse(
            status_code=200,
            content={
                'success': True,
                'ticket': resultado.get('ticket'),
                'hora_salida': resultado.get('hora_salida'),
                'mensaje': resultado.get('mensaje')
            }
        )
    
    def actualizar_registro(self, actualizacion: ActualizarRegistroPeaonalRequest) -> JSONResponse:
        """Actualiza datos de un registro peatonal existente"""
        if self.registro_manager is None:
            raise HTTPException(
                status_code=500,
                detail="El sistema de registro de peatones no está inicializado"
            )
        
        try:
            # Preparar datos a actualizar (solo los que no son None)
            datos_actualizacion = {}
            
            if actualizacion.nombre is not None:
                datos_actualizacion['nombre'] = actualizacion.nombre
            if actualizacion.apellido is not None:
                datos_actualizacion['apellido'] = actualizacion.apellido
            if actualizacion.cedula is not None:
                datos_actualizacion['cedula'] = actualizacion.cedula
            if actualizacion.departamento is not None:
                datos_actualizacion['departamento'] = actualizacion.departamento
            if actualizacion.motivo is not None:
                datos_actualizacion['motivo'] = actualizacion.motivo
            
            # Actualizar registro
            resultado = self.registro_manager.actualizar_registro_por_ticket(
                actualizacion.ticket,
                datos_actualizacion
            )
            
            if resultado.get('success'):
                return JSONResponse(
                    status_code=200,
                    content={
                        'success': True,
                        'ticket': resultado.get('ticket'),
                        'datos_actualizados': resultado.get('datos_actualizados', {}),
                        'mensaje': f"Registro peatonal {actualizacion.ticket} actualizado exitosamente"
                    }
                )
            else:
                detalle = resultado.get('error', 'Desconocido')
                status_code = 404 if 'No se encontró' in detalle else 400
                raise HTTPException(status_code=status_code, detail=detalle)
        
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error actualizando registro peatonal: {str(e)}"
            )
