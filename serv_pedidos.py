import csv
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List
from rabbitmq_client import RabbitMQClient, ROUTING_KEYS
import json

app = FastAPI(
    title="Coordinador de Pedidos",
    description="Servicio encargado de la coordinación y gestión de pedidos de venta, con validación de clientes e inventario. \n\n" \
    "Este servicio actúa como el punto central de integración entre los departamentos de Clientes, Productos e Inventario para garantizar la correcta ejecución de las ventas. \n\n" \
    "Ejecutar en puerto **8002** y asegurarse de que los servicios de Clientes (8000), Productos (8001) e Inventario (8003) estén activos para su correcto funcionamiento. \n\n" \
    "**Versión RabbitMQ**: Ahora se comunica a través de un bus de mensajería.",
    version="3.0.0 - RabbitMQ",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)

FILE_NAME = "pedidos.csv"
HEADERS = ["id_pedido", "id_cliente", "id_producto", "cantidad"]

if not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

# Cliente RabbitMQ global
mq_client = RabbitMQClient(host='localhost', port=5672)

class Pedido(BaseModel):
    id_pedido: int = Field(..., example=501)  # type: ignore
    id_cliente: int = Field(..., example=101) # type: ignore
    id_producto: int = Field(..., example=1) # type: ignore
    cantidad: int = Field(..., gt=0, example=2) # type: ignore

class PedidoRegistro(BaseModel):
    id_cliente: int = Field(..., example=101) # type: ignore
    id_producto: int = Field(..., example=1) # type: ignore
    cantidad: int = Field(..., gt=0, example=2) # type: ignore

def leer_pedidos():
    """Lee todos los pedidos del archivo CSV."""
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

@app.get(
    "/pedidos",
    response_model=List[Pedido],
    tags=["Consultas"],
    summary="Obtener lista de pedidos",
    status_code=200,
    responses={
        200: {
            "description": "Lista de pedidos obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id_pedido": 501,
                            "id_cliente": 101,
                            "id_producto": 1,
                            "cantidad": 2
                        }
                    ]
                }
            }
        }
    }
)
def obtener_pedidos():
    """Retorna el registro oficial de pedidos desde el archivo CSV.
    
    Este endpoint obtiene la lista completa de todos los pedidos registrados
    en la base de datos de pedidos persistente (archivo CSV).
    
    Returns:
        List[Pedido]: Lista de pedidos con todos sus datos.
    """
    return leer_pedidos()

@app.post(
    "/pedidos",
    tags=["Operaciones"],
    summary="Crear nuevo pedido",
    status_code=201,
    responses={
        201: {
            "description": "Pedido creado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Venta completada y stock descontado",
                        "id_pedido": 501,
                        "status": "success"
                    }
                }
            }
        },
        400: {
            "description": "Datos inválidos: cliente no existe, producto no existe, inventario insuficiente"
        },
        503: {
            "description": "Servicios de catálogo o inventario no disponibles"
        }
    }
)
def crear_pedido(p: PedidoRegistro):
    """Crea un nuevo pedido con validación integrada a través de RabbitMQ.
    
    Ejecuta el siguiente flujo de validación usando mensajería:
    1. Consulta el servicio de productos para verificar que el producto existe
    2. Verifica que hay inventario suficiente para completar el pedido
    3. Valida que el cliente existe en el padrón oficial
    4. Si todo es válido: descuenta el inventario y persiste el pedido
    
    Args:
        p (PedidoRegistro): Datos del pedido a crear.
            - id_cliente: ID del cliente que realiza el pedido
            - id_producto: ID del producto a ordenar
            - cantidad: Cantidad de unidades a ordenar (debe ser mayor a 0)
    
    Returns:
        dict: Diccionario con mensaje de éxito e ID asignado del pedido.
    
    Raises:
        HTTPException: Con status 400 si hay problemas de validación.
        HTTPException: Con status 503 si no hay disponibilidad de servicios.
    """
    try:
        # PASO 1a: Validar que el producto existe (a través de RabbitMQ)
        response = mq_client.request_reply(
            exchange='servicios',
            routing_key=ROUTING_KEYS['validate_producto'],
            message={'id_producto': p.id_producto}
        )
        
        if response is None:
            raise HTTPException(status_code=503, detail="Timeout esperando validación de producto")
        if not response.get('existe'):
            raise HTTPException(status_code=400, detail="Producto no existe en el catálogo")
        
        # PASO 1b: Consultar inventario disponible (a través de RabbitMQ)
        response = mq_client.request_reply(
            exchange='servicios',
            routing_key=ROUTING_KEYS['get_inventario'],
            message={'id_producto': p.id_producto}
        )
        
        if response is None:
            raise HTTPException(status_code=503, detail="Timeout esperando consulta de inventario")
        if not response or response.get('cantidad') == 0:
            raise HTTPException(status_code=400, detail="Producto sin registro de inventario")
        
        stock_actual = response.get('cantidad', 0)
        if stock_actual <= 0 or p.cantidad > stock_actual:
            raise HTTPException(status_code=400, detail="Inventario insuficiente para completar el pedido")
        
        # PASO 2: Validar que el cliente existe (a través de RabbitMQ)
        response = mq_client.request_reply(
            exchange='servicios',
            routing_key=ROUTING_KEYS['validate_cliente'],
            message={'id_cliente': p.id_cliente}
        )
        
        if response is None:
            raise HTTPException(status_code=503, detail="Timeout esperando validación de cliente")
        if not response.get('existe'):
            raise HTTPException(status_code=400, detail="El cliente no existe en el padrón oficial")
        
        # PASO 3: Descontar inventario (a través de RabbitMQ)
        response = mq_client.request_reply(
            exchange='servicios',
            routing_key=ROUTING_KEYS['descontar_inventario'],
            message={'id_producto': p.id_producto, 'cantidad': p.cantidad}
        )
        
        if response is None:
            raise HTTPException(status_code=503, detail="Timeout esperando descuento de inventario")
        if not response.get('exito'):
            raise HTTPException(status_code=503, detail="Error al descontar inventario")
        
        # PASO 4: Persistir pedido localmente
        pedidos = leer_pedidos()
        if pedidos and len(pedidos) > 0:
            siguiente_id = max(int(ped['id_pedido']) for ped in pedidos) + 1
        else:
            siguiente_id = 1
        
        with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([siguiente_id, p.id_cliente, p.id_producto, p.cantidad])
        
        return {"mensaje": "Venta completada y stock descontado", "id_pedido": siguiente_id, "status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en crear_pedido: {e}")
        raise HTTPException(status_code=503, detail="Error de comunicación con servicios (RabbitMQ)")


@app.on_event("startup")
def startup_event():
    """Evento de inicio: conectar a RabbitMQ"""
    try:
        print("▶ Conectando a RabbitMQ...")
        mq_client.connect()
        # Declarar el exchange
        mq_client.declare_exchange('servicios', exchange_type='direct')
        print("✓ Servicio de Pedidos iniciado y conectado a RabbitMQ")
    except Exception as e:
        print(f"⚠ Advertencia: Error al conectar a RabbitMQ en startup: {e}")
        print("ℹ El servicio seguirá ejecutándose pero sin soporte de mensajería RabbitMQ")


@app.on_event("shutdown")
def shutdown_event():
    """Evento de cierre: desconectar de RabbitMQ"""
    try:
        mq_client.close()
        print("✓ Servicio de Pedidos desconectado de RabbitMQ")
    except Exception as e:
        print(f"Error al desconectar de RabbitMQ: {e}")