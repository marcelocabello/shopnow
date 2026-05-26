import csv
import os
import json
import pika
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from rabbitmq_client import ROUTING_KEYS, create_rabbitmq_client
from auth import verificar_token, endpoint_login, Token
import storage
from ui_pages import render_service_ui


@asynccontextmanager
async def lifespan(app):
    """Startup/shutdown de Inventario con consumidor RabbitMQ."""
    if storage.postgres_enabled():
        storage.ensure_schema()
        storage.seed_demo_data_if_enabled()
        print("✓ Postgres habilitado para servicio de Inventario")
    try:
        mq_client.connect()
        mq_client.declare_exchange("servicios", "direct")
        mq_client.declare_queue("inventario_requests")
        mq_client.bind_queue("inventario_requests", "servicios", ROUTING_KEYS["get_inventario"])
        mq_client.bind_queue("inventario_requests", "servicios", ROUTING_KEYS["descontar_inventario"])
        mq_client.bind_queue("inventario_requests", "servicios", RK_INVENTARIO_AGREGAR)
        mq_client.bind_queue("inventario_requests", "servicios", RK_INVENTARIO_DESCONTAR)
        mq_client.start_consumer_thread("inventario_requests", handle_inventario_message)
        print("✓ Consumidor RabbitMQ de Inventario activo")
    except Exception as exc:
        print(f"⚠ Inventario sin consumidor RabbitMQ: {exc}")
    yield
    try:
        mq_client.close()
    except Exception:
        pass


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


@app.get("/ui", include_in_schema=False)
def inventario_ui():
    return render_service_ui("inventario", "ShopNow Inventario")


@app.get("/", include_in_schema=False)
def inventario_home():
    return {"servicio": "inventario", "ui": "/ui", "docs": "/docs"}

FILE_NAME = "inventario.csv"
HEADERS = ["id_producto", "cantidad"]

# Inicializar Archivo Oficial si no existe
if not storage.postgres_enabled() and not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

# Cliente RabbitMQ global
mq_client = create_rabbitmq_client()

RK_INVENTARIO_AGREGAR = 'inventario.cmd.agregar'
RK_INVENTARIO_DESCONTAR = 'inventario.cmd.descontar'

# Contrato de Servicio (Formato Oficial)
class MovimientoInventario(BaseModel):
    id_producto: int = Field(..., example=1) # type: ignore
    cantidad: int = Field(..., gt=0, example=5) # type: ignore

def leer_inventario():
    if storage.postgres_enabled():
        return storage.read_inventario()
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _publicar_comando_inventario(routing_key: str, payload: dict):
    mq_client.publish(exchange='servicios', routing_key=routing_key, message=payload)


@app.post("/token", response_model=Token, tags=["Autenticación"], summary="Obtener token JWT")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Genera un JWT Bearer token. Usuarios: admin/admin123, usuario/pass123."""
    return endpoint_login(form_data)

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
def obtener_inventario_completo(usuario: str = Depends(verificar_token)):
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
def consultar_stock(id_producto: int, usuario: str = Depends(verificar_token)):
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
    summary="Operación no permitida: alta de productos",
    status_code=405,
    responses={
        405: {
            "description": "Inventario no da de alta productos",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Inventario no permite altas de productos. Da de alta en /productos y luego ajusta cantidades con /inventario/agregar."
                    }
                }
            }
        }
    }
)
def registrar_inventario(mov: MovimientoInventario, usuario: str = Depends(verificar_token)):
    """Bloquea altas de producto en inventario por política de negocio."""
    raise HTTPException(
        status_code=405,
        detail="Inventario no permite altas de productos. Da de alta en /productos y luego ajusta cantidades con /inventario/agregar.",
    )

@app.post(
    "/inventario/descontar",
    tags=["Operaciones"],
    summary="Operación no permitida: descuento directo",
    status_code=405,
    responses={
        405: {
            "description": "Inventario no permite descuento manual",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Inventario no permite descuento manual. El descuento de existencias se realiza desde /pedidos."
                    }
                }
            }
        }
    }
)
def descontar_stock(mov: MovimientoInventario, usuario: str = Depends(verificar_token)):
    """Bloquea descuentos manuales de inventario por política de negocio."""
    raise HTTPException(
        status_code=405,
        detail="Inventario no permite descuento manual. El descuento de existencias se realiza desde /pedidos.",
    )

@app.post(
    "/inventario/agregar",
    tags=["Operaciones"],
    summary="Agregar stock al inventario",
    status_code=202,
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
def agregar_stock(mov: MovimientoInventario, usuario: str = Depends(verificar_token)):
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
    if storage.postgres_enabled():
        ok = storage.agregar_inventario(mov.id_producto, mov.cantidad)
        nueva = None
        if ok:
            item = storage.get_inventario_item(mov.id_producto)
            nueva = int(item["cantidad"]) if item else None
    else:
        items = leer_inventario()
        item = next((i for i in items if int(i["id_producto"]) == mov.id_producto), None)
        if not item:
            ok = False
            nueva = None
        else:
            item["cantidad"] = int(item["cantidad"]) + mov.cantidad
            nueva = int(item["cantidad"])
            with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=HEADERS)
                writer.writeheader()
                writer.writerows(items)
            ok = True
    if not ok:
        raise HTTPException(status_code=404, detail="Producto no registrado en inventario")
    return {"mensaje": "Existencias agregadas exitosamente", "nueva_cantidad": nueva, "status": "success"}


# ============================================================================
# MANEJADORES DE MENSAJES RABBITMQ
# ============================================================================

def handle_inventario_message(ch, method, properties, body):
    """
    Maneja mensajes de solicitud sobre inventario desde RabbitMQ.
    
    Operaciones soportadas:
    - get_inventario: Obtiene el stock de un producto (request-reply)
    - descontar_inventario: Descuenta stock tras una compra (request-reply)
    - inventario.cmd.*: Comandos asíncronos de escritura
    """
    message = {}
    reply_to = properties.reply_to if properties else None
    correlation_id = properties.correlation_id if properties else None
    routing_key = method.routing_key
    response = None
    try:
        message = json.loads(body)
        print(f"📨 Mensaje recibido en Inventario: {message}")

        # Procesar según la routing key
        if routing_key == ROUTING_KEYS['get_inventario']:
            # Consultar stock
            id_producto = message.get('id_producto')
            items = leer_inventario()
            for item in items:
                if int(item['id_producto']) == id_producto:
                    response = {'id_producto': id_producto, 'cantidad': int(item['cantidad'])}
                    break
            if not response:
                response = {'id_producto': id_producto, 'cantidad': 0, 'error': 'Producto no en inventario'}

        elif routing_key == ROUTING_KEYS['descontar_inventario']:
            # Descontar inventario
            id_producto = message.get('id_producto')
            cantidad = message.get('cantidad')
            if storage.postgres_enabled():
                response = storage.descontar_inventario(int(id_producto), int(cantidad))
            else:
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

        elif routing_key == RK_INVENTARIO_DESCONTAR:
            id_producto = int(message.get('id_producto'))
            cantidad = int(message.get('cantidad'))
            if storage.postgres_enabled():
                resultado = storage.descontar_inventario(id_producto, cantidad)
                if not resultado.get('exito'):
                    raise ValueError(resultado.get('error'))
            else:
                items = leer_inventario()
                actualizado = False
                for item in items:
                    if int(item['id_producto']) == id_producto:
                        nueva_cantidad = int(item['cantidad']) - cantidad
                        if nueva_cantidad >= 0:
                            item['cantidad'] = str(nueva_cantidad)
                            with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                                writer = csv.DictWriter(f, fieldnames=HEADERS)
                                writer.writeheader()
                                writer.writerows(items)
                        actualizado = True
                        break
                if not actualizado:
                    raise ValueError(f"Producto {id_producto} no encontrado en inventario")

        elif routing_key == RK_INVENTARIO_AGREGAR:
            id_producto = int(message.get('id_producto'))
            cantidad = int(message.get('cantidad'))
            if storage.postgres_enabled():
                if not storage.agregar_inventario(id_producto, cantidad):
                    raise ValueError(f"Producto {id_producto} no encontrado en inventario")
            else:
                items = leer_inventario()
                actualizado = False
                for item in items:
                    if int(item['id_producto']) == id_producto:
                        item['cantidad'] = str(int(item['cantidad']) + cantidad)
                        with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=HEADERS)
                            writer.writeheader()
                            writer.writerows(items)
                        actualizado = True
                        break
                if not actualizado:
                    raise ValueError(f"Producto {id_producto} no encontrado en inventario")

        # Enviar respuesta solo para operaciones request-reply
        if reply_to and correlation_id and response is not None:
            mq_client.channel.basic_publish(
                exchange='',
                routing_key=reply_to,
                body=json.dumps(response),
                properties=pika.BasicProperties(
                    correlation_id=correlation_id
                )
            )

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"✓ Operación de inventario procesada para routing_key={routing_key}")

    except Exception as e:
        # Evita el ciclo infinito de requeue en request-reply:
        # siempre responde error al caller y ACK del mensaje.
        print(f"Error procesando mensaje de inventario: {e}")
        if reply_to and correlation_id:
            fallback_id_producto = message.get('id_producto') if isinstance(message, dict) else None
            error_response = {
                "exito": False,
                "error": f"Error interno inventario: {e}",
                "id_producto": fallback_id_producto,
            }
            try:
                mq_client.channel.basic_publish(
                    exchange='',
                    routing_key=reply_to,
                    body=json.dumps(error_response),
                    properties=pika.BasicProperties(correlation_id=correlation_id),
                )
            except Exception as pub_exc:
                print(f"Error enviando respuesta fallback de inventario: {pub_exc}")
        ch.basic_ack(delivery_tag=method.delivery_tag)


# Las funciones de startup y shutdown ahora están en el contexto lifespan
