import csv
import os
import json
import pika
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import List, Optional
from rabbitmq_client import ROUTING_KEYS, create_rabbitmq_client
from auth import verificar_token, endpoint_login, Token
import storage
from ui_pages import render_service_ui


@asynccontextmanager
async def lifespan(app):
    """Startup/shutdown sin dependencia de RabbitMQ."""
    if storage.postgres_enabled():
        storage.ensure_schema()
        storage.seed_demo_data_if_enabled()
        print("✓ Postgres habilitado para servicio de Productos")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Departamento de Productos",
    description="Servicio encargado de la custodia y registro oficial del catálogo de productos de la empresa.\n\n" \
    "Este servicio actúa como el punto central de integración para la validación de productos en los procesos de venta y gestión de pedidos. \n\n" \
    "Ejecutar en puerto **8001** y asegurarse de que los servicios de Pedidos (8002) y Clientes (8010) estén activos para su correcto funcionamiento. \n\n" \
    "**Versión RabbitMQ**: Ahora responde a solicitudes a través de un bus de mensajería.",
    version="3.0.0 - RabbitMQ",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)


@app.get("/ui", include_in_schema=False)
def productos_ui():
    return render_service_ui("productos", "ShopNow Productos")


@app.get("/", include_in_schema=False)
def productos_home():
    return {"servicio": "productos", "ui": "/ui", "docs": "/docs"}

FILE_NAME = "productos.csv"
HEADERS = ["id_producto", "descripcion", "precio", "activo", "categoria"]

if not storage.postgres_enabled() and not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

# Cliente RabbitMQ global
mq_client = create_rabbitmq_client()

RK_PRODUCTO_CREAR = 'productos.cmd.crear'
RK_PRODUCTO_ACTUALIZAR = 'productos.cmd.actualizar'
RK_PRODUCTO_ELIMINAR = 'productos.cmd.eliminar'

class Producto(BaseModel):
    id_producto: int = Field(..., example=1) # type: ignore
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer") # type: ignore
    precio: float = Field(..., gt=0, example=15000.0) # type: ignore
    activo: bool = Field(..., example=True) # type: ignore

class ProductoRegistro(BaseModel):
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer") # type: ignore
    precio: float = Field(..., gt=0, example=15000.0) # type: ignore
    activo: bool = Field(default=True, example=True) # type: ignore
    stock_inicial: int = Field(default=0, ge=0, example=0) # type: ignore

class ProductoUpdate(BaseModel):
    descripcion: Optional[str] = Field(None, min_length=3, example="Laptop Gamer") # type: ignore
    precio: Optional[float] = Field(None, gt=0, example=15000.0) # type: ignore
    activo: Optional[bool] = Field(None, example=True) # type: ignore

class ProductoV2(BaseModel):
    id_producto: int
    descripcion: str
    costo_unitario: float
    activo: bool

class ProductoRegistroV2(BaseModel):
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer") # type: ignore
    costo_unitario: float = Field(..., gt=0, example=15000.0) # type: ignore
    activo: bool = Field(default=True, example=True) # type: ignore

def leer_productos():
    if storage.postgres_enabled():
        return storage.read_productos()
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _publicar_comando_producto(routing_key: str, payload: dict):
    mq_client.publish(exchange='servicios', routing_key=routing_key, message=payload)

# ============================================================================
# AUTENTICACIÓN
# ============================================================================

@app.post("/token", response_model=Token, tags=["Autenticación"], summary="Obtener token JWT")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Genera un JWT Bearer token. Usuarios: admin/admin123, usuario/pass123."""
    return endpoint_login(form_data)


# ============================================================================
# ENDPOINTS VERSIONADOS
# ============================================================================

@app.get("/v1/productos", tags=["Versionado"], summary="Productos v1 — 4 campos")
def get_productos_v1(usuario: str = Depends(verificar_token)):
    """Lista productos con 4 campos: id_producto, descripcion, precio, activo."""
    productos = leer_productos()
    return [
        {
            "id_producto": int(p["id_producto"]),
            "descripcion": p["descripcion"],
            "precio": float(p["precio"]),
            "activo": str(p.get("activo", "True")).lower() in ("true", "1"),
        }
        for p in productos
    ]

@app.get("/v2/productos", tags=["Versionado"], summary="Productos v2 — reemplaza precio por costo_unitario")
def get_productos_v2(usuario: str = Depends(verificar_token)):
    """Lista productos v2 con contrato evolucionado: costo_unitario."""
    productos = leer_productos()
    return [
        {
            "id_producto": int(p["id_producto"]),
            "descripcion": p["descripcion"],
            "costo_unitario": float(p["precio"]),
            "activo": str(p.get("activo", "True")).lower() in ("true", "1"),
        }
        for p in productos
    ]

@app.post("/v2/productos", tags=["Versionado"], summary="Registrar producto v2 — usa costo_unitario", status_code=202)
def registrar_producto_v2(nuevo: ProductoRegistroV2, usuario: str = Depends(verificar_token)):
    """Registra producto v2 mapeando costo_unitario al precio interno."""
    payload = {
        "descripcion": nuevo.descripcion,
        "precio": nuevo.costo_unitario,
        "activo": nuevo.activo,
        "categoria": "",
    }
    if storage.postgres_enabled():
        storage.create_producto(payload)
    else:
        productos = leer_productos()
        siguiente_id = max((int(p["id_producto"]) for p in productos), default=0) + 1
        with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                siguiente_id,
                payload["descripcion"],
                payload["precio"],
                payload["activo"],
                "",
            ])
    return {
        "mensaje": "Producto v2 registrado exitosamente",
        "status": "success",
    }

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
def obtener_productos(usuario: str = Depends(verificar_token)):
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
    status_code=202,
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
def registrar_producto(nuevo: ProductoRegistro, usuario: str = Depends(verificar_token)):
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
    payload = {
        "descripcion": nuevo.descripcion,
        "precio": nuevo.precio,
        "activo": nuevo.activo,
        "categoria": "",
        "stock_inicial": nuevo.stock_inicial,
    }
    if storage.postgres_enabled():
        storage.create_producto(payload)
    else:
        productos = leer_productos()
        siguiente_id = max((int(p["id_producto"]) for p in productos), default=0) + 1
        with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                siguiente_id,
                payload["descripcion"],
                payload["precio"],
                payload["activo"],
                payload["categoria"],
            ])
    return {"mensaje": "Producto registrado exitosamente", "status": "success"}

@app.delete(
    "/productos/{id_producto}",
    tags=["Operaciones"],
    summary="Eliminar producto",
    status_code=202,
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
def eliminar_producto(id_producto: int, usuario: str = Depends(verificar_token)):
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
    if storage.postgres_enabled():
        ok = storage.delete_producto(int(id_producto))
    else:
        productos = leer_productos()
        producto = next((p for p in productos if int(p["id_producto"]) == int(id_producto)), None)
        if producto:
            productos.remove(producto)
            with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=HEADERS)
                writer.writeheader()
                writer.writerows(productos)
            ok = True
        else:
            ok = False
    if not ok:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"mensaje": "Producto eliminado exitosamente", "status": "success"}

@app.patch(
    "/productos/{id_producto}",
    tags=["Operaciones"],
    summary="Actualizar producto parcialmente",
    status_code=202,
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
def actualizar_producto_parcial(id_producto: int, update: ProductoUpdate, usuario: str = Depends(verificar_token)):
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
    payload = {
        "id_producto": id_producto,
        "descripcion": update.descripcion,
        "precio": update.precio,
        "activo": update.activo,
    }
    if storage.postgres_enabled():
        ok = storage.update_producto(int(id_producto), payload)
    else:
        productos = leer_productos()
        producto = next((p for p in productos if int(p["id_producto"]) == int(id_producto)), None)
        if producto:
            for campo in ["descripcion", "precio", "activo"]:
                if payload.get(campo) is not None:
                    producto[campo] = payload.get(campo)
            with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=HEADERS)
                writer.writeheader()
                writer.writerows(productos)
            ok = True
        else:
            ok = False
    if not ok:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"mensaje": "Producto actualizado exitosamente", "status": "success"}


# ============================================================================
# MANEJADORES DE MENSAJES RABBITMQ
# ============================================================================

def handle_producto_message(ch, method, properties, body):
    """
    Maneja mensajes de solicitud sobre productos desde RabbitMQ.
    
    Operaciones soportadas:
    - validate_producto: Verifica si un producto existe (request-reply)
    - productos.cmd.*: Comandos asíncronos de escritura
    """
    try:
        message = json.loads(body)
        print(f"📨📨 Mensaje recibido en Productos: {message}")
        print(f"   - reply_to: {properties.reply_to if properties else 'NO_PROPS'}")
        print(f"   - correlation_id: {properties.correlation_id if properties else 'NO_PROPS'}")
        
        routing_key = method.routing_key

        if routing_key == ROUTING_KEYS['validate_producto']:
            reply_to = properties.reply_to
            correlation_id = properties.correlation_id
            id_producto = message.get('id_producto')
            existe = storage.producto_exists(id_producto) if storage.postgres_enabled() else any(
                int(p['id_producto']) == id_producto for p in leer_productos()
            )
            response = {'existe': existe, 'id_producto': id_producto}
            print(f"   - Respondiendo a: {reply_to} con correlation_id: {correlation_id}")
            mq_client.channel.basic_publish(
                exchange='',
                routing_key=reply_to,
                body=json.dumps(response),
                properties=pika.BasicProperties(
                    correlation_id=correlation_id
                )
            )
        elif routing_key == RK_PRODUCTO_CREAR:
            if storage.postgres_enabled():
                storage.create_producto(message)
            else:
                productos = leer_productos()
                siguiente_id = max((int(p['id_producto']) for p in productos), default=0) + 1
                with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow([
                        siguiente_id,
                        message.get('descripcion', ''),
                        message.get('precio', 0),
                        message.get('activo', True),
                        message.get('categoria', ''),
                    ])
        elif routing_key == RK_PRODUCTO_ACTUALIZAR:
            id_producto = message.get('id_producto')
            if storage.postgres_enabled():
                storage.update_producto(int(id_producto), message)
            else:
                productos = leer_productos()
                producto = next((p for p in productos if int(p['id_producto']) == int(id_producto)), None)
                if producto:
                    for campo in ['descripcion', 'precio', 'activo']:
                        if message.get(campo) is not None:
                            producto[campo] = message.get(campo)
                    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=HEADERS)
                        writer.writeheader()
                        writer.writerows(productos)
        elif routing_key == RK_PRODUCTO_ELIMINAR:
            id_producto = message.get('id_producto')
            if storage.postgres_enabled():
                storage.delete_producto(int(id_producto))
            else:
                productos = leer_productos()
                producto = next((p for p in productos if int(p['id_producto']) == int(id_producto)), None)
                if producto:
                    productos.remove(producto)
                    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=HEADERS)
                        writer.writeheader()
                        writer.writerows(productos)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"✓✓ Operación de productos procesada para routing_key={routing_key}")
        
    except Exception as e:
        print(f"❌❌ Error procesando mensaje de productos: {e}")
        import traceback
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


# Las funciones de startup y shutdown ahora están en el contexto lifespan
