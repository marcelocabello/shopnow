import csv
import os
import json
import pika
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
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
        
        # Declarar y vincular cola para solicitudes de get y descontar
        mq_client.declare_queue('inventario_requests')
        mq_client.bind_queue('inventario_requests', 'servicios', ROUTING_KEYS['get_inventario'])
        mq_client.bind_queue('inventario_requests', 'servicios', ROUTING_KEYS['descontar_inventario'])
        
        # Iniciar consumidor en thread separado
        mq_client.start_consumer_thread('inventario_requests', handle_inventario_message)
        
        print("✓ Servicio de Inventario iniciado y escuchando en RabbitMQ")
    except Exception as e:
        print(f"⚠ Advertencia: Error al conectar a RabbitMQ en startup: {e}")
        print("ℹ El servicio seguirá ejecutándose pero sin soporte de mensajería RabbitMQ")
    
    yield
    
    try:
        mq_client.close()
        print("✓ Servicio de Inventario desconectado de RabbitMQ")
    except Exception as e:
        print(f"Error al desconectar de RabbitMQ: {e}")


app = FastAPI(
    lifespan=lifespan,
    title="Departamento de Inventario",
    description="Servicio encargado de la custodia y control de existencias físicas de productos.\n\n" \
    "Este servicio actúa como el punto central de integración para la validación de stock en los procesos de venta y gestión de pedidos. \n\n" \
    "Ejecutar en puerto **8003** y asegurarse de que los servicios de Pedidos (8002) y Productos (8001) estén activos para su correcto funcionamiento. \n\n" \
    "**Versión RabbitMQ**: Ahora responde a solicitudes a través de un bus de mensajería.",
    version="3.0.0 - RabbitMQ",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)

FILE_NAME = "inventario.csv"
HEADERS = ["id_producto", "cantidad"]

# Inicializar Archivo Oficial si no existe
if not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

# Cliente RabbitMQ global
mq_client = RabbitMQClient(host='localhost', port=5672)

# Contrato de Servicio (Formato Oficial)
class MovimientoInventario(BaseModel):
    id_producto: int = Field(..., example=1) # type: ignore
    cantidad: int = Field(..., gt=0, example=5) # type: ignore

def leer_inventario():
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

@app.get(
    "/inventario",
    tags=["Consultas"],
    summary="Obtener inventario completo",
    status_code=200,
    responses={
        200: {
            "description": "Inventario completo obtenido exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id_producto": 1,
                            "cantidad": 50
                        },
                        {
                            "id_producto": 2,
                            "cantidad": 30
                        }
                    ]
                }
            }
        }
    }
)
def obtener_inventario_completo():
    """Retorna el inventario completo de todos los productos.
    
    Este endpoint obtiene la lista completa del stock disponible de todos
    los productos registrados en la base de datos de inventario persistente.
    
    Returns:
        list: Lista de movimientos de inventario con cantidad por producto.
    """
    return leer_inventario()

@app.get(
    "/inventario/{id_producto}",
    tags=["Consultas"],
    summary="Consultar stock de un producto",
    status_code=200,
    responses={
        200: {
            "description": "Stock del producto obtenido exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "id_producto": 1,
                        "cantidad": 50
                    }
                }
            }
        },
        404: {
            "description": "Producto no registrado en inventario",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Producto no registrado en inventario"
                    }
                }
            }
        }
    }
)
def consultar_stock(id_producto: int):
    """Consulta la cantidad disponible de un producto específico.
    
    Busca y retorna el stock actual de un producto por su ID único.
    
    Args:
        id_producto (int): ID único del producto a consultar.
    
    Returns:
        dict: Diccionario con el ID del producto y cantidad disponible.
    
    Raises:
        HTTPException: Con status 404 si el producto no existe en inventario.
    """
    items = leer_inventario()
    for item in items:
        if int(item['id_producto']) == id_producto:
            return {"id_producto": id_producto, "cantidad": int(item['cantidad'])}
    raise HTTPException(status_code=404, detail="Producto no registrado en inventario")

@app.post(
    "/inventario",
    tags=["Operaciones"],
    summary="Registrar nuevo producto en inventario",
    status_code=201,
    responses={
        201: {
            "description": "Producto registrado en inventario exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Producto registrado en inventario",
                        "id_producto": 1,
                        "cantidad": 100,
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
def registrar_inventario(mov: MovimientoInventario):
    """Registra un nuevo producto en el inventario.
    
    Crea un nuevo registro de inventario para un producto específico con
    la cantidad inicial de existencias.
    
    Args:
        mov (MovimientoInventario): Datos del movimiento de inventario.
            - id_producto: ID del producto a registrar
            - cantidad: Cantidad inicial de existencias (debe ser mayor a 0)
    
    Returns:
        dict: Diccionario con confirmación del registro y datos del producto.
    
    Raises:
        HTTPException: Con status 400 si el producto ya existe en inventario.
    """
    items = leer_inventario()
    
    # Verificar que el producto no exista ya
    if any(int(item['id_producto']) == mov.id_producto for item in items):
        raise HTTPException(status_code=400, detail="El producto ya existe en el inventario")
    
    # Registrar nuevo producto en inventario
    with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([mov.id_producto, mov.cantidad])
    
    return {"mensaje": "Producto registrado en inventario", "id_producto": mov.id_producto, "cantidad": mov.cantidad, "status": "success"}

@app.post(
    "/inventario/descontar",
    tags=["Operaciones"],
    summary="Descontar stock de inventario",
    status_code=200,
    responses={
        200: {
            "description": "Stock descontado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Descuento de inventario aplicado exitosamente",
                        "status": "success"
                    }
                }
            }
        },
        400: {
            "description": "Stock insuficiente en almacén"
        },
        404: {
            "description": "Producto no encontrado en inventario"
        }
    }
)
def descontar_stock(mov: MovimientoInventario):
    """Descuenta stock del inventario tras una venta exitosa.
    
    Reduce la cantidad disponible de un producto en el inventario.
    Se utiliza cuando se completa exitosamente un pedido.
    
    Args:
        mov (MovimientoInventario): Datos del movimiento de descuento.
            - id_producto: ID del producto a descontar
            - cantidad: Cantidad a descontar (debe ser mayor a 0)
    
    Returns:
        dict: Diccionario con confirmación de la operación.
    
    Raises:
        HTTPException: Con status 400 si stock es insuficiente.
        HTTPException: Con status 404 si el producto no existe en inventario.
    """
    items = leer_inventario()
    encontrado = False
    for item in items:
        if int(item['id_producto']) == mov.id_producto:
            nueva_cantidad = int(item['cantidad']) - mov.cantidad
            if nueva_cantidad < 0:
                raise HTTPException(status_code=400, detail="Stock insuficiente en almacén")
            item['cantidad'] = str(nueva_cantidad)
            encontrado = True
            break
    
    if not encontrado:
        raise HTTPException(status_code=404, detail="Producto no encontrado en inventario")
        
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(items)
        
    return {"mensaje": "Descuento de inventario aplicado exitosamente", "status": "success"}

@app.post(
    "/inventario/agregar",
    tags=["Operaciones"],
    summary="Agregar stock al inventario",
    status_code=200,
    responses={
        200: {
            "description": "Stock agregado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Existencias agregadas exitosamente",
                        "id_producto": 1,
                        "nueva_cantidad": 100,
                        "status": "success"
                    }
                }
            }
        },
        404: {
            "description": "Producto no encontrado en inventario"
        }
    }
)
def agregar_stock(mov: MovimientoInventario):
    """Agrega stock al inventario de un producto.
    
    Incrementa la cantidad disponible de un producto en el inventario.
    Se utiliza para registrar compras de mercancía o devoluciones.
    
    Args:
        mov (MovimientoInventario): Datos del movimiento de adición.
            - id_producto: ID del producto a actualizar
            - cantidad: Cantidad a agregar (debe ser mayor a 0)
    
    Returns:
        dict: Diccionario con confirmación de la operación y nueva cantidad.
    
    Raises:
        HTTPException: Con status 404 si el producto no existe en inventario.
    """
    items = leer_inventario()
    encontrado = False
    for item in items:
        if int(item['id_producto']) == mov.id_producto:
            nueva_cantidad = int(item['cantidad']) + mov.cantidad
            item['cantidad'] = str(nueva_cantidad)
            encontrado = True
            break
    
    if not encontrado:
        raise HTTPException(status_code=404, detail="Producto no encontrado en inventario")
        
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(items)
        
    return {"mensaje": "Existencias agregadas exitosamente", "id_producto": mov.id_producto, "nueva_cantidad": nueva_cantidad, "status": "success"}


# ============================================================================
# MANEJADORES DE MENSAJES RABBITMQ
# ============================================================================

def handle_inventario_message(ch, method, properties, body):
    """
    Maneja mensajes de solicitud sobre inventario desde RabbitMQ.
    
    Operaciones soportadas:
    - get_inventario: Obtiene el stock de un producto
    - descontar_inventario: Descuenta stock tras una compra
    """
    try:
        message = json.loads(body)
        print(f"📨 Mensaje recibido en Inventario: {message}")
        
        # Obtener la información de respuesta
        reply_to = properties.reply_to
        correlation_id = properties.correlation_id
        routing_key = method.routing_key
        
        response = None
        
        # Procesar según la routing key
        if 'get' in routing_key:
            # Consultar stock
            id_producto = message.get('id_producto')
            items = leer_inventario()
            for item in items:
                if int(item['id_producto']) == id_producto:
                    response = {'id_producto': id_producto, 'cantidad': int(item['cantidad'])}
                    break
            if not response:
                response = {'id_producto': id_producto, 'cantidad': 0, 'error': 'Producto no en inventario'}
        
        elif 'descontar' in routing_key:
            # Descontar inventario
            id_producto = message.get('id_producto')
            cantidad = message.get('cantidad')
            items = leer_inventario()
            exito = False
            
            for item in items:
                if int(item['id_producto']) == id_producto:
                    nueva_cantidad = int(item['cantidad']) - cantidad
                    if nueva_cantidad < 0:
                        response = {'exito': False, 'error': 'Stock insuficiente', 'id_producto': id_producto}
                    else:
                        item['cantidad'] = str(nueva_cantidad)
                        with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=HEADERS)
                            writer.writeheader()
                            writer.writerows(items)
                        response = {'exito': True, 'id_producto': id_producto, 'nueva_cantidad': nueva_cantidad}
                        exito = True
                    break
            
            if not exito and not response:
                response = {'exito': False, 'error': 'Producto no encontrado', 'id_producto': id_producto}
        
        # Enviar respuesta
        mq_client.channel.basic_publish(
            exchange='',
            routing_key=reply_to,
            body=json.dumps(response or {'error': 'Operación desconocida'}),
            properties=pika.BasicProperties(
                correlation_id=correlation_id
            )
        )
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"✓ Respuesta enviada: {response}")
        
    except Exception as e:
        print(f"Error procesando mensaje de inventario: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag)


# Las funciones de startup y shutdown ahora están en el contexto lifespan

