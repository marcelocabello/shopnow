from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List

app = FastAPI(title="Departamento de Productos - ShopNow",
    description="Servicio encargado de la custodia y registro oficial de los productos de la empresa.",
    version="1.0.0",
    contact={
        "name": "Arturo Barajas, Profesor de SOA - TecNM Querétaro",
    }
)

class Producto(BaseModel):
    id_producto: int = Field(..., example=1)
    nombre: str = Field(..., min_length=3, example="Laptop Gamer")
    precio: float = Field(..., gt=0, example=15000.0)
    stock: int = Field(..., ge=0, example=10)

db_productos = []

@app.get("/productos", response_model=List[Producto], tags=["Consultas"])
def obtener_productos():
    return db_productos

@app.post("/productos", tags=["Operaciones"])
def registrar_producto(nuevo_p: Producto):
    for p in db_productos:
        if p.id_producto == nuevo_p.id_producto:
            raise HTTPException(status_code=400, detail="El ID del producto ya existe")
    db_productos.append(nuevo_p)
    return {"mensaje": "Producto agregado al catálogo"}
