import csv
import os
import json
import pika
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from rabbitmq_client import RabbitMQClient, ROUTING_KEYS

app = FastAPI(
    title="Departamento de Productos",
    description="Servicio encargado de la custodia y registro oficial del catálogo de productos de la empresa.\n\n" \
    "Este servicio actúa como el punto central de integración para la validación de productos en los procesos de venta y gestión de pedidos. \n\n" \
    "Ejecutar en puerto **8001** y asegurarse de que los servicios de Pedidos (8002) y Clientes (8000) estén activos para su correcto funcionamiento. \n\n" \
    "**Versión RabbitMQ**: Ahora responde a solicitudes a través de un bus de mensajería.",
    version="3.0.0 - RabbitMQ",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)

FILE_NAME = "productos.csv"
HEADERS = ["id_producto", "descripcion", "precio", "activo"]

if not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

# Cliente RabbitMQ global
mq_client = RabbitMQClient(host='localhost', port=5672)

class Producto(BaseModel):
    id_producto: int = Field(..., example=1) # type: ignore
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer") # type: ignore
    precio: float = Field(..., gt=0, example=15000.0) # type: ignore
    activo: bool = Field(..., example=True) # type: ignore

class ProductoRegistro(BaseModel):
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer") # type: ignore
    precio: float = Field(..., gt=0, example=15000.0) # type: ignore
    activo: bool = Field(default=True, example=True) # type: ignore

class ProductoUpdate(BaseModel):
    descripcion: Optional[str] = Field(None, min_length=3, example="Laptop Gamer") # type: ignore
    precio: Optional[float] = Field(None, gt=0, example=15000.0) # type: ignore
    activo: Optional[bool] = Field(None, example=True) # type: ignore

def leer_productos():
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

@app.get(
    "/productos",
    response_model=List[Producto],
    tags=["Consultas"],
    summary="Obtener lista de productos",
    status_code=200,
    responses={
        200: {
            "description": "Lista de productos obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id_producto": 1,
                            "descripcion": "Laptop Gamer",
                            "precio": 15000.0,
                            "activo": True
                        }
                    ]
                }
            }
        }
    }
)
def obtener_productos():
    """**Retorna el catálogo oficial de productos desde el archivo CSV.**
    
    Este endpoint obtiene la lista completa de todos los productos registrados
    en la base de datos de productos persistente (archivo CSV).
    
    **Returns**:

        List[Producto]:
            Lista de productos con todos sus datos (ID, descripción, precio).
    """
    return leer_productos()

@app.post(
    "/productos",
    tags=["Operaciones"],
    summary="Registrar nuevo producto",
    status_code=201,
    responses={
        201: {
            "description": "Producto registrado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Producto guardado exitosamente",
                        "id_producto": 1,
                        "status": "success"
                    }
                }
            }
        },
        422: {
            "description": "Datos de entrada inválidos o formato incorrecto"
        }
    }
)
def registrar_producto(nuevo: ProductoRegistro):
    """**Registra un nuevo producto en el catálogo.**
    
    Crea un nuevo producto con el siguiente flujo:
        1. Valida los datos de entrada según el modelo ProductoRegistro
        2. Genera un ID único autoincremental
        3. Almacena el producto en el archivo CSV
    
    **Args**:

        nuevo (ProductoRegistro): Datos del producto a registrar.
            - descripcion: Descripción del producto (mínimo 3 caracteres)
            - precio: Precio unitario del producto (debe ser mayor a 0)
            - activo (opcional): Estado del producto (por defecto: True)
    
    **Returns**:

        dict:
            Diccionario con mensaje de éxito e ID asignado del producto.
    """
    productos = leer_productos()
    
    # Generar ID autoincremental
    if productos:
        siguiente_id = max(int(p['id_producto']) for p in productos) + 1
    else:
        siguiente_id = 1
    
    with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([siguiente_id, nuevo.descripcion, nuevo.precio, nuevo.activo])
    return {"mensaje": "Producto guardado exitosamente", "id_producto": siguiente_id, "status": "success"}

@app.delete(
    "/productos/{id_producto}",
    tags=["Operaciones"],
    summary="Eliminar producto",
    status_code=200,
    responses={
        200: {
            "description": "Producto eliminado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Producto eliminado exitosamente",
                        "status": "success"
                    }
                }
            }
        },
        404: {
            "description": "Producto no encontrado con el ID especificado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Producto no encontrado"
                    }
                }
            }
        }
    }
)
def eliminar_producto(id_producto: int):
    """**Elimina un producto existente del catálogo.**
    
    Busca y elimina un producto por su ID único, liberando su registro
    del archivo CSV persistente.
    
    **Args**:

        id_producto (int): ID único del producto a eliminar.
    
    **Returns**:

        dict:
            Diccionario con mensaje de confirmación de eliminación.
    
    **Raises**:

        HTTPException:
            Con status 404 si el producto no existe.
    """
    productos = leer_productos()
    producto = next((p for p in productos if int(p['id_producto']) == id_producto), None)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    productos.remove(producto)
    
    # Reescribir el archivo CSV sin el producto eliminado
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(productos)
    
    return {"mensaje": "Producto eliminado exitosamente", "status": "success"}

@app.patch(
    "/productos/{id_producto}",
    tags=["Operaciones"],
    summary="Actualizar producto parcialmente",
    status_code=200,
    responses={
        200: {
            "description": "Producto actualizado parcialmente de forma exitosa",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Producto actualizado parcialmente exitosamente",
                        "status": "success"
                    }
                }
            }
        },
        404: {
            "description": "Producto no encontrado con el ID especificado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Producto no encontrado"
                    }
                }
            }
        },
        422: {
            "description": "Datos de entrada inválidos o formato incorrecto"
        }
    }
)
def actualizar_producto_parcial(id_producto: int, update: ProductoUpdate):
    """**Actualiza parcialmente un producto existente del catálogo.**
    
    Permite actualizar uno o más campos de un producto sin necesidad
    de proporcionar todos los datos. Los campos no proporcionados
    se mantienen sin cambios.
    
    **Args**:

        id_producto (int): ID único del producto a actualizar.
        update (ProductoUpdate): Datos opcionales a actualizar.
            - descripcion (opcional): Nueva descripción (mínimo 3 caracteres)
            - precio (opcional): Nuevo precio (debe ser mayor a 0)
    
    **Returns**:

        dict:
            Diccionario con mensaje de confirmación de actualización.
    
    **Raises**:

        HTTPException:
            Con status 404 si el producto no existe.
    """
    productos = leer_productos()
    producto = next((p for p in productos if int(p['id_producto']) == id_producto), None)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Actualizar campos proporcionados
    if update.descripcion is not None:
        producto['descripcion'] = update.descripcion
    if update.precio is not None:
        producto['precio'] = update.precio
    
    # Reescribir el archivo CSV con los cambios
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(productos)
    
    return {"mensaje": "Producto actualizado parcialmente exitosamente", "status": "success"}


# ============================================================================
# MANEJADORES DE MENSAJES RABBITMQ
# ============================================================================

def handle_producto_message(ch, method, properties, body):
    """
    Maneja mensajes de solicitud sobre productos desde RabbitMQ.
    
    Operaciones soportadas:
    - validate_producto: Verifica si un producto existe
    """
    try:
        message = json.loads(body)
        print(f"📨📨 Mensaje recibido en Productos: {message}")
        print(f"   - reply_to: {properties.reply_to if properties else 'NO_PROPS'}")
        print(f"   - correlation_id: {properties.correlation_id if properties else 'NO_PROPS'}")
        
        # Obtener la información de respuesta
        reply_to = properties.reply_to
        correlation_id = properties.correlation_id
        
        # Procesar la solicitud
        id_producto = message.get('id_producto')
        productos = leer_productos()
        existe = any(int(p['id_producto']) == id_producto for p in productos)
        
        response = {'existe': existe, 'id_producto': id_producto}
        
        print(f"   - Respondiendo a: {reply_to} con correlation_id: {correlation_id}")
        
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
        print(f"✓✓ Respuesta enviada a {reply_to}: {response}")
        
    except Exception as e:
        print(f"❌❌ Error procesando mensaje de productos: {e}")
        import traceback
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag)


@app.on_event("startup")
def startup_event():
    """Evento de inicio: conectar a RabbitMQ y iniciar consumidor"""
    try:
        import pika
        print("▶ Conectando a RabbitMQ...")
        mq_client.connect()
        
        # Declarar exchange
        mq_client.declare_exchange('servicios', exchange_type='direct')
        
        # Declarar y vincular cola para solicitudes de validación
        mq_client.declare_queue('productos_requests')
        mq_client.bind_queue('productos_requests', 'servicios', ROUTING_KEYS['validate_producto'])
        
        # Iniciar consumidor en thread separado
        mq_client.start_consumer_thread('productos_requests', handle_producto_message)
        
        print("✓ Servicio de Productos iniciado y escuchando en RabbitMQ")
    except Exception as e:
        print(f"⚠ Advertencia: Error al conectar a RabbitMQ en startup: {e}")
        print("ℹ El servicio seguirá ejecutándose pero sin soporte de mensajería RabbitMQ")


@app.on_event("shutdown")
def shutdown_event():
    """Evento de cierre: desconectar de RabbitMQ"""
    try:
        mq_client.close()
        print("✓ Servicio de Productos desconectado de RabbitMQ")
    except Exception as e:
        print(f"Error al desconectar de RabbitMQ: {e}")