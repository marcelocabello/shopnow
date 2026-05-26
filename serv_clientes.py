import csv
import os
import json
import pika
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, EmailStr
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
        print("✓ Postgres habilitado para servicio de Clientes")
    yield


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


@app.get("/ui", include_in_schema=False)
def clientes_ui():
    return render_service_ui("clientes", "ShopNow Clientes")


@app.get("/", include_in_schema=False)
def clientes_home():
    return {"servicio": "clientes", "ui": "/ui", "docs": "/docs"}

# /home/boomer/ITQ/SOA/ShopNow_PHP/shopnow/var/db_clientes.csv
# /home/boomer/ITQ/SOA/ShopNow/clientes.csv
FILE_NAME = "clientes.csv"
HEADERS = ["id_cliente", "nombre", "correo", "direccion", "telefono", "activo", "rfc", "fecha_registro"]

# Inicializar archivo si no existe
if not storage.postgres_enabled() and not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

# Cliente RabbitMQ global
mq_client = create_rabbitmq_client()

RK_CLIENTE_CREAR = 'clientes.cmd.crear'
RK_CLIENTE_ACTUALIZAR = 'clientes.cmd.actualizar'
RK_CLIENTE_INACTIVAR = 'clientes.cmd.inactivar'

class Cliente(BaseModel):
    id_cliente: int = Field(..., example=101, description="ID numérico único") # type: ignore
    nombre: str = Field(..., min_length=3, example="Juan Pérez") # type: ignore
    correo: str = Field(..., example="juan@ejemplo.com") # type: ignore
    direccion: str = Field(..., example="Calle 123") # type: ignore
    telefono: str = Field(..., example="4421234567") # type: ignore
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

class ClienteV2(BaseModel):
    id_cliente: int
    nombre: str
    correo: str
    direccion: str
    telefono: str
    activo: bool
    rfc: str = ""
    fecha_registro: str = ""

class ClienteRegistroV2(BaseModel):
    nombre: str = Field(..., min_length=3, example="Juan Pérez") # type: ignore
    correo: str = Field(..., example="juan@ejemplo.com") # type: ignore
    direccion: str = Field(..., example="Calle 123") # type: ignore
    telefono: str = Field(..., min_length=10, max_length=10, example="4421234567") # type: ignore
    activo: bool = Field(default=True, example=True) # type: ignore
    rfc: str = Field(default="", example="XAXX010101000") # type: ignore
    fecha_registro: str = Field(default="", example="2026-04-10") # type: ignore

def leer_clientes():
    if storage.postgres_enabled():
        return storage.read_clientes()
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _publicar_comando_cliente(routing_key: str, payload: dict):
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

@app.get("/v1/clientes", tags=["Versionado"], summary="Clientes v1 — 6 campos")
def get_clientes_v1(usuario: str = Depends(verificar_token)):
    """Lista clientes con 6 campos: id_cliente, nombre, correo, direccion, telefono, activo."""
    clientes = leer_clientes()
    return [
        {
            "id_cliente": int(c["id_cliente"]),
            "nombre": c["nombre"],
            "correo": c["correo"],
            "direccion": c["direccion"],
            "telefono": c["telefono"],
            "activo": str(c.get("activo", "True")).lower() in ("true", "1"),
        }
        for c in clientes
    ]

@app.get("/v2/clientes", tags=["Versionado"], summary="Clientes v2 — 8 campos (incluye rfc y fecha_registro)")
def get_clientes_v2(usuario: str = Depends(verificar_token)):
    """Lista clientes con 8 campos: todos los de v1 más rfc y fecha_registro."""
    clientes = leer_clientes()
    return [
        {
            "id_cliente": int(c["id_cliente"]),
            "nombre": c["nombre"],
            "correo": c["correo"],
            "direccion": c["direccion"],
            "telefono": c["telefono"],
            "activo": str(c.get("activo", "True")).lower() in ("true", "1"),
            "rfc": c.get("rfc", ""),
            "fecha_registro": c.get("fecha_registro", ""),
        }
        for c in clientes
    ]

@app.post("/v2/clientes", tags=["Versionado"], summary="Registrar cliente v2 — acepta rfc y fecha_registro", status_code=202)
def registrar_cliente_v2(nuevo: ClienteRegistroV2, usuario: str = Depends(verificar_token)):
    """Registra cliente v2 de forma síncrona (sin RabbitMQ)."""
    payload = {
        "nombre": nuevo.nombre,
        "correo": nuevo.correo,
        "direccion": nuevo.direccion,
        "telefono": nuevo.telefono,
        "activo": nuevo.activo,
        "rfc": nuevo.rfc,
        "fecha_registro": nuevo.fecha_registro,
    }
    if storage.postgres_enabled():
        storage.create_cliente(payload)
    else:
        clientes = leer_clientes()
        siguiente_id = max((int(c["id_cliente"]) for c in clientes), default=100) + 1
        with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                siguiente_id,
                payload["nombre"],
                payload["correo"],
                payload["direccion"],
                payload["telefono"],
                payload["activo"],
                payload["rfc"],
                payload["fecha_registro"],
            ])
    return {
        "mensaje": "Cliente v2 registrado exitosamente",
        "status": "success",
    }


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
def obtener_clientes(usuario: str = Depends(verificar_token)):
    """Retorna el padrón oficial de clientes desde el archivo CSV.
    
    Este endpoint obtiene la lista completa de todos los clientes registrados
    en la base de datos de clientes persistente (archivo CSV).
    
    Returns:
        List[Cliente]: Lista de clientes con todos sus datos.
    """
    clientes = leer_clientes()
    return [
        {
            "id_cliente": int(c.get("id_cliente", 0)),
            "nombre": str(c.get("nombre", "") or ""),
            "correo": str(c.get("correo", "") or ""),
            "direccion": str(c.get("direccion", "") or ""),
            "telefono": str(c.get("telefono", "") or ""),
            "activo": str(c.get("activo", "True")).lower() in ("true", "1", "t", "yes", "y"),
        }
        for c in clientes
    ]

@app.post(
    "/clientes",
    tags=["Operaciones"],
    summary="Registrar nuevo cliente",
    status_code=202,
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
def registrar_cliente(nuevo: ClienteRegistro, usuario: str = Depends(verificar_token)):
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
    payload = {
        "nombre": nuevo.nombre,
        "correo": nuevo.correo,
        "direccion": nuevo.direccion,
        "telefono": nuevo.telefono,
        "activo": nuevo.activo,
        "rfc": "",
        "fecha_registro": "",
    }
    if storage.postgres_enabled():
        storage.create_cliente(payload)
    else:
        clientes = leer_clientes()
        siguiente_id = max((int(c["id_cliente"]) for c in clientes), default=100) + 1
        with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                siguiente_id,
                payload["nombre"],
                payload["correo"],
                payload["direccion"],
                payload["telefono"],
                payload["activo"],
                payload["rfc"],
                payload["fecha_registro"],
            ])
    return {"mensaje": "Cliente registrado exitosamente", "status": "success"}

@app.delete(
    "/clientes/{id_cliente}",
    tags=["Operaciones"],
    summary="Eliminar cliente",
    status_code=202,
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
def eliminar_cliente(id_cliente: int, usuario: str = Depends(verificar_token)):
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
    if storage.postgres_enabled():
        ok = storage.inactivate_cliente(int(id_cliente))
    else:
        clientes = leer_clientes()
        cliente = next((c for c in clientes if int(c["id_cliente"]) == int(id_cliente)), None)
        if cliente:
            cliente["activo"] = "False"
            with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=HEADERS)
                writer.writeheader()
                writer.writerows(clientes)
            ok = True
        else:
            ok = False
    if not ok:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"mensaje": "Cliente inactivado exitosamente", "status": "success"}

@app.patch(
    "/clientes/{id_cliente}",
    tags=["Operaciones"],
    summary="Actualizar cliente parcialmente",
    status_code=202,
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
def actualizar_cliente_parcial(id_cliente: int, update: ClienteUpdate, usuario: str = Depends(verificar_token)):
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
    payload = {
        "id_cliente": id_cliente,
        "nombre": update.nombre,
        "correo": update.correo,
        "direccion": update.direccion,
        "telefono": update.telefono,
        "activo": update.activo,
    }
    if storage.postgres_enabled():
        ok = storage.update_cliente(int(id_cliente), payload)
    else:
        clientes = leer_clientes()
        cliente = next((c for c in clientes if int(c["id_cliente"]) == int(id_cliente)), None)
        if cliente:
            for campo in ["nombre", "correo", "direccion", "telefono", "activo"]:
                if payload.get(campo) is not None:
                    cliente[campo] = payload.get(campo)
            with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=HEADERS)
                writer.writeheader()
                writer.writerows(clientes)
            ok = True
        else:
            ok = False
    if not ok:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"mensaje": "Cliente actualizado exitosamente", "status": "success"}


# ============================================================================
# MANEJADORES DE MENSAJES RABBITMQ
# ============================================================================

def handle_cliente_message(ch, method, properties, body):
    """
    Maneja mensajes de solicitud sobre clientes desde RabbitMQ.
    
    Operaciones soportadas:
    - validate_cliente: Verifica si un cliente existe (request-reply)
    - clientes.cmd.*: Comandos asíncronos de escritura
    """
    try:
        message = json.loads(body)
        print(f"📨 Mensaje recibido en Clientes: {message}")
        
        routing_key = method.routing_key

        if routing_key == ROUTING_KEYS['validate_cliente']:
            reply_to = properties.reply_to
            correlation_id = properties.correlation_id
            id_cliente = message.get('id_cliente')
            existe = storage.cliente_exists(id_cliente) if storage.postgres_enabled() else any(
                int(c['id_cliente']) == id_cliente for c in leer_clientes()
            )
            response = {'existe': existe, 'id_cliente': id_cliente}
            mq_client.channel.basic_publish(
                exchange='',
                routing_key=reply_to,
                body=json.dumps(response),
                properties=pika.BasicProperties(
                    correlation_id=correlation_id
                )
            )
        elif routing_key == RK_CLIENTE_CREAR:
            if storage.postgres_enabled():
                storage.create_cliente(message)
            else:
                clientes = leer_clientes()
                siguiente_id = max((int(c['id_cliente']) for c in clientes), default=100) + 1
                with open(FILE_NAME, "a", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow([
                        siguiente_id,
                        message.get('nombre', ''),
                        message.get('correo', ''),
                        message.get('direccion', ''),
                        message.get('telefono', ''),
                        message.get('activo', True),
                        message.get('rfc', ''),
                        message.get('fecha_registro', ''),
                    ])
        elif routing_key == RK_CLIENTE_ACTUALIZAR:
            id_cliente = message.get('id_cliente')
            if storage.postgres_enabled():
                storage.update_cliente(int(id_cliente), message)
            else:
                clientes = leer_clientes()
                cliente = next((c for c in clientes if int(c['id_cliente']) == int(id_cliente)), None)
                if cliente:
                    for campo in ['nombre', 'correo', 'direccion', 'telefono', 'activo']:
                        if message.get(campo) is not None:
                            cliente[campo] = message.get(campo)
                    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=HEADERS)
                        writer.writeheader()
                        writer.writerows(clientes)
        elif routing_key == RK_CLIENTE_INACTIVAR:
            id_cliente = message.get('id_cliente')
            if storage.postgres_enabled():
                storage.inactivate_cliente(int(id_cliente))
            else:
                clientes = leer_clientes()
                cliente = next((c for c in clientes if int(c['id_cliente']) == int(id_cliente)), None)
                if cliente:
                    cliente['activo'] = "False"
                    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=HEADERS)
                        writer.writeheader()
                        writer.writerows(clientes)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"✓ Operación de clientes procesada para routing_key={routing_key}")
        
    except Exception as e:
        print(f"Error procesando mensaje de clientes: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


# Las funciones de startup y shutdown ahora están en el contexto lifespan
