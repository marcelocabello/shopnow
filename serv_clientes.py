import csv
import os
import json
import pika
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from rabbitmq_client import RabbitMQClient, ROUTING_KEYS


@asynccontextmanager
async def lifespan(app):
    """Maneja el startup y shutdown de la aplicación con RabbitMQ"""
    try:
        import pika
        print("▶ Conectando a RabbitMQ...")
        mq_client.connect()
        
        # Declarar exchange
        mq_client.declare_exchange('servicios', exchange_type='direct')
        
        # Declarar y vincular cola para solicitudes de validación
        mq_client.declare_queue('clientes_requests')
        mq_client.bind_queue('clientes_requests', 'servicios', ROUTING_KEYS['validate_cliente'])
        
        # Iniciar consumidor en thread separado
        mq_client.start_consumer_thread('clientes_requests', handle_cliente_message)
        
        print("✓ Servicio de Clientes iniciado y escuchando en RabbitMQ")
    except Exception as e:
        print(f"⚠ Advertencia: Error al conectar a RabbitMQ en startup: {e}")
        print("ℹ El servicio seguirá ejecutándose pero sin soporte de mensajería RabbitMQ")
    
    yield
    
    try:
        mq_client.close()
        print("✓ Servicio de Clientes desconectado de RabbitMQ")
    except Exception as e:
        print(f"Error al desconectar de RabbitMQ: {e}")


app = FastAPI(
    lifespan=lifespan,
    title="Departamento de Clientes",
    description="Servicio encargado de la custodia y registro oficial de los clientes de la empresa. \n\n" \
    "Este servicio actúa como el punto central de integración para la validación de clientes en los procesos de venta y atención al cliente. \n\n" \
    "Ejecutar en puerto **8010** y asegurarse de que los servicios de Pedidos (8002) y Productos (8001) estén activos para su correcto funcionamiento. \n\n" \
    "**Versión RabbitMQ**: Ahora responde a solicitudes a través de un bus de mensajería.",
    version="3.0.0 - RabbitMQ",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)

# /home/boomer/ITQ/SOA/ShopNow_PHP/shopnow/var/db_clientes.csv
# /home/boomer/ITQ/SOA/ShopNow/clientes.csv
FILE_NAME = "clientes.csv"
HEADERS = ["id_cliente", "nombre", "correo", "direccion", "telefono", "activo"]

# Inicializar archivo si no existe
if not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

# Cliente RabbitMQ global
mq_client = RabbitMQClient(host='localhost', port=5672)

class Cliente(BaseModel):
    id_cliente: int = Field(..., example=101, description="ID numérico único") # type: ignore
    nombre: str = Field(..., min_length=3, example="Juan Pérez") # type: ignore
    correo: EmailStr = Field(..., example="juan@ejemplo.com") # type: ignore
    direccion: str = Field(..., example="Calle 123") # type: ignore
    telefono: str = Field(..., min_length=10, max_length=10, example="4421234567") # type: ignore
    activo: bool = Field(..., example=True) # type: ignore

class ClienteRegistro(BaseModel):
    nombre: str = Field(..., min_length=3, example="Juan Pérez") # type: ignore
    correo: EmailStr = Field(..., example="juan@ejemplo.com") # type: ignore
    direccion: str = Field(..., example="Calle 123") # type: ignore
    telefono: str = Field(..., min_length=10, max_length=10, example="4421234567") # type: ignore
    activo: bool = Field(..., example=True) # type: ignore

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=3, example="Juan Pérez") # type: ignore
    correo: Optional[EmailStr] = Field(None, example="juan@ejemplo.com") # type: ignore
    direccion: Optional[str] = Field(None, example="Calle 123") # type: ignore
    telefono: Optional[str] = Field(None, min_length=10, max_length=10, example="4421234567") # type: ignore
    activo: Optional[bool] = Field(None, example=True) # type: ignore

def leer_clientes():
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

@app.get(
    "/clientes",
    response_model=List[Cliente],
    tags=["Consultas"],
    summary="Obtener lista de clientes",
    status_code=200,
    responses={
        200: {
            "description": "Lista de clientes obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id_cliente": 101,
                            "nombre": "Juan Pérez",
                            "correo": "juan@ejemplo.com",
                            "direccion": "Calle 123",
                            "telefono": "4421234567",
                            "activo": "True"
                        }
                    ]
                }
            }
        }
    }
)
def obtener_clientes():
    """Retorna el padrón oficial de clientes desde el archivo CSV.
    
    Este endpoint obtiene la lista completa de todos los clientes registrados
    en la base de datos de clientes persistente (archivo CSV).
    
    Returns:
        List[Cliente]: Lista de clientes con todos sus datos.
    """
    return leer_clientes()

@app.post(
    "/clientes",
    tags=["Operaciones"],
    summary="Registrar nuevo cliente",
    status_code=201,
    responses={
        201: {
            "description": "Cliente registrado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Cliente registrado en el archivo CSV",
                        "id_cliente": 1
                    }
                }
            }
        },
        422: {
            "description": "Datos de entrada inválidos o formato incorrecto"
        }
    }
)
def registrar_cliente(nuevo: ClienteRegistro):
    """Registra un nuevo cliente en la base de datos.
    
    Crea un nuevo cliente con el siguiente flujo:
    1. Valida los datos de entrada según el modelo ClienteRegistro
    2. Genera un ID único autoincremental
    3. Almacena el cliente en el archivo CSV
    
    Args:
        nuevo (ClienteRegistro): Datos del cliente a registrar.
            - nombre: Nombre del cliente (mínimo 3 caracteres)
            - correo: Email válido del cliente
            - direccion: Dirección del cliente
            - telefono: Teléfono de contacto
    
    Returns:
        dict: Diccionario con mensaje de éxito e ID asignado del cliente.
    """
    clientes = leer_clientes()
    
    # Generar ID autoincremental
    if clientes:
        siguiente_id = max(int(c['id_cliente']) for c in clientes) + 1
    else:
        siguiente_id = 1
    
    with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([siguiente_id, nuevo.nombre, nuevo.correo, nuevo.direccion, nuevo.telefono, nuevo.activo])
    return {"mensaje": "Cliente registrado en el archivo CSV", "id_cliente": siguiente_id, "status": "success"}

@app.delete(
    "/clientes/{id_cliente}",
    tags=["Operaciones"],
    summary="Eliminar cliente",
    status_code=200,
    responses={
        200: {
            "description": "Cliente eliminado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Cliente eliminado exitosamente",
                        "status": "success"
                    }
                }
            }
        },
        404: {
            "description": "Cliente no encontrado con el ID especificado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Cliente no encontrado"
                    }
                }
            }
        }
    }
)
def eliminar_cliente(id_cliente: int):
    """Elimina un cliente existente de la base de datos.
    
    Busca y elimina un cliente por su ID único, liberando su registro
    del archivo CSV persistente.
    
    Args:
        id_cliente (int): ID único del cliente a eliminar.
    
    Returns:
        dict: Diccionario con mensaje de confirmación de eliminación.
    
    Raises:
        HTTPException: Con status 404 si el cliente no existe.
    """
    clientes = leer_clientes()
    cliente = next((c for c in clientes if int(c['id_cliente']) == id_cliente), None)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # clientes.remove(cliente)
    cliente['activo'] = "False"  # Marcar como inactivo en lugar de eliminar físicamente
    
    # Reescribir el archivo CSV sin el cliente eliminado
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(clientes)
    
    return {"mensaje": "Cliente eliminado (inactivado) exitosamente", "status": "success"}

@app.patch(
    "/clientes/{id_cliente}",
    tags=["Operaciones"],
    summary="Actualizar cliente parcialmente",
    status_code=200,
    responses={
        200: {
            "description": "Cliente actualizado parcialmente de forma exitosa",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Cliente actualizado parcialmente exitosamente",
                        "status": "success"
                    }
                }
            }
        },
        404: {
            "description": "Cliente no encontrado con el ID especificado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Cliente no encontrado"
                    }
                }
            }
        },
        422: {
            "description": "Datos de entrada inválidos o formato incorrecto"
        }
    }
)
def actualizar_cliente_parcial(id_cliente: int, update: ClienteUpdate):
    """Actualiza parcialmente un cliente existente.
    
    Permite actualizar uno o más campos de un cliente sin necesidad
    de proporcionar todos los datos. Los campos no proporcionados
    se mantienen sin cambios.
    
    Args:
        id_cliente (int): ID único del cliente a actualizar.
        update (ClienteUpdate): Datos opcionales a actualizar.
            - nombre (opcional): Nuevo nombre (mínimo 3 caracteres)
            - correo (opcional): Nuevo email válido
            - direccion (opcional): Nueva dirección
            - telefono (opcional): Nuevo teléfono de contacto
            - activo (opcional): Nuevo estado de actividad del cliente
    
    Returns:
        dict: Diccionario con mensaje de confirmación de actualización.
    
    Raises:
        HTTPException: Con status 404 si el cliente no existe.
    """
    clientes = leer_clientes()
    cliente = next((c for c in clientes if int(c['id_cliente']) == id_cliente), None)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Actualizar campos proporcionados
    if update.nombre is not None:
        cliente['nombre'] = update.nombre
    if update.correo is not None:
        cliente['correo'] = update.correo
    if update.direccion is not None:
        cliente['direccion'] = update.direccion
    if update.telefono is not None:
        cliente['telefono'] = update.telefono
    if update.activo is not None:
        cliente['activo'] = update.activo
    
    # Reescribir el archivo CSV con los cambios
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(clientes)
    
    return {"mensaje": "Cliente actualizado parcialmente exitosamente", "status": "success"}


# ============================================================================
# MANEJADORES DE MENSAJES RABBITMQ
# ============================================================================

def handle_cliente_message(ch, method, properties, body):
    """
    Maneja mensajes de solicitud sobre clientes desde RabbitMQ.
    
    Operaciones soportadas:
    - validate_cliente: Verifica si un cliente existe
    """
    try:
        message = json.loads(body)
        print(f"📨 Mensaje recibido en Clientes: {message}")
        
        # Obtener la información de respuesta
        reply_to = properties.reply_to
        correlation_id = properties.correlation_id
        
        # Procesar la solicitud
        id_cliente = message.get('id_cliente')
        clientes = leer_clientes()
        existe = any(int(c['id_cliente']) == id_cliente for c in clientes)
        
        response = {'existe': existe, 'id_cliente': id_cliente}
        
        # Enviar respuesta
        mq_client.channel.basic_publish(
            exchange='',
            routing_key=reply_to,
            body=json.dumps(response),
            properties=pika.BasicProperties(
                correlation_id=correlation_id
            )
        )
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"✓ Respuesta enviada: {response}")
        
    except Exception as e:
        print(f"Error procesando mensaje de clientes: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag)


# Las funciones de startup y shutdown ahora están en el contexto lifespan

