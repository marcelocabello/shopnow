import csv
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

app = FastAPI(
    title="Departamento de Productos",
    description="Servicio encargado de la custodia y registro oficial del catálogo de productos de la empresa.",
    version="2.0.0",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)

FILE_NAME = "productos.csv"
HEADERS = ["id_producto", "descripcion", "precio"]

if not os.path.exists(FILE_NAME):
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADERS)

class Producto(BaseModel):
    id_producto: int = Field(..., example=1) # type: ignore
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer") # type: ignore
    precio: float = Field(..., gt=0, example=15000.0) # type: ignore

class ProductoRegistro(BaseModel):
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer") # type: ignore
    precio: float = Field(..., gt=0, example=15000.0) # type: ignore

class ProductoUpdate(BaseModel):
    descripcion: Optional[str] = Field(None, min_length=3, example="Laptop Gamer") # type: ignore
    precio: Optional[float] = Field(None, gt=0, example=15000.0) # type: ignore

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
                            "precio": 15000.0
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
        csv.writer(f).writerow([siguiente_id, nuevo.descripcion, nuevo.precio])
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