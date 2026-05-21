import os
from pathlib import Path
from typing import Any

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover - handled at runtime if dependency missing
    psycopg2 = None
    RealDictCursor = None


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"
DEFAULT_DB = "shopnow_663n"
DEFAULT_USER = "shopnow_663n_user"


def postgres_enabled() -> bool:
    mode = os.getenv("SHOPNOW_STORAGE", "postgres").lower()
    if mode == "csv":
        raise RuntimeError("El modo CSV ya no está soportado; usa Postgres en Docker")
    return True


def _postgres_settings() -> dict[str, Any]:
    return {
        "host": os.getenv("POSTGRES_HOST", ""),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DB", DEFAULT_DB),
        "user": os.getenv("POSTGRES_USER", DEFAULT_USER),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }


def _connect():
    if psycopg2 is None:
        raise RuntimeError("Falta instalar psycopg2-binary para usar Postgres")
    settings = _postgres_settings()
    if not settings["host"]:
        raise RuntimeError("Falta definir POSTGRES_HOST para usar Postgres")
    if not settings["password"]:
        raise RuntimeError("Falta definir POSTGRES_PASSWORD para usar Postgres")
    return psycopg2.connect(**settings)


def ensure_schema() -> None:
    if not postgres_enabled():
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            # Evita carreras cuando múltiples microservicios arrancan al mismo tiempo.
            cur.execute("SELECT pg_advisory_lock(663001)")
            cur.execute("SELECT to_regclass('public.clientes')")
            if cur.fetchone()[0] is None:
                cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            cur.execute("SELECT pg_advisory_unlock(663001)")


def _fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]


def _fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None


def _execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount


def read_clientes() -> list[dict[str, Any]]:
    rows = _fetch_all(
        """
        SELECT id_cliente, nombre, correo, direccion, telefono, activo, rfc, fecha_registro
        FROM clientes
        ORDER BY id_cliente
        """
    )
    for row in rows:
        if row.get("fecha_registro") is not None:
            row["fecha_registro"] = row["fecha_registro"].isoformat()
        else:
            row["fecha_registro"] = ""
    return rows


def cliente_exists(id_cliente: int) -> bool:
    return _fetch_one("SELECT 1 AS ok FROM clientes WHERE id_cliente = %s", (id_cliente,)) is not None


def create_cliente(payload: dict[str, Any]) -> int:
    row = _fetch_one(
        """
        INSERT INTO clientes (id_cliente, nombre, correo, direccion, telefono, activo, rfc, fecha_registro)
        VALUES (
            (SELECT COALESCE(MAX(id_cliente), 100) + 1 FROM clientes),
            %s, %s, %s, %s, %s, %s, NULLIF(%s, '')::date
        )
        RETURNING id_cliente
        """,
        (
            payload.get("nombre", ""),
            payload.get("correo", ""),
            payload.get("direccion", ""),
            payload.get("telefono", ""),
            payload.get("activo", True),
            payload.get("rfc", ""),
            payload.get("fecha_registro", ""),
        ),
    )
    return int(row["id_cliente"])


def update_cliente(id_cliente: int, payload: dict[str, Any]) -> bool:
    row = _fetch_one(
        """
        UPDATE clientes
        SET
            nombre = COALESCE(%s, nombre),
            correo = COALESCE(%s, correo),
            direccion = COALESCE(%s, direccion),
            telefono = COALESCE(%s, telefono),
            activo = COALESCE(%s, activo),
            rfc = COALESCE(%s, rfc),
            fecha_registro = COALESCE(NULLIF(%s, '')::date, fecha_registro)
        WHERE id_cliente = %s
        RETURNING id_cliente
        """,
        (
            payload.get("nombre"),
            payload.get("correo"),
            payload.get("direccion"),
            payload.get("telefono"),
            payload.get("activo"),
            payload.get("rfc"),
            payload.get("fecha_registro"),
            id_cliente,
        ),
    )
    return row is not None


def inactivate_cliente(id_cliente: int) -> bool:
    return _execute("UPDATE clientes SET activo = FALSE WHERE id_cliente = %s", (id_cliente,)) > 0


def read_productos() -> list[dict[str, Any]]:
    rows = _fetch_all(
        """
        SELECT id_producto, descripcion, precio, activo, categoria
        FROM productos
        ORDER BY id_producto
        """
    )
    for row in rows:
        row["precio"] = float(row["precio"])
    return rows


def producto_exists(id_producto: int) -> bool:
    return _fetch_one("SELECT 1 AS ok FROM productos WHERE id_producto = %s", (id_producto,)) is not None


def create_producto(payload: dict[str, Any]) -> int:
    row = _fetch_one(
        """
        INSERT INTO productos (id_producto, descripcion, precio, activo, categoria)
        VALUES (
            (SELECT COALESCE(MAX(id_producto), 0) + 1 FROM productos),
            %s, %s, %s, %s
        )
        RETURNING id_producto
        """,
        (
            payload.get("descripcion", ""),
            payload.get("precio", 0),
            payload.get("activo", True),
            payload.get("categoria", ""),
        ),
    )
    return int(row["id_producto"])


def update_producto(id_producto: int, payload: dict[str, Any]) -> bool:
    row = _fetch_one(
        """
        UPDATE productos
        SET
            descripcion = COALESCE(%s, descripcion),
            precio = COALESCE(%s, precio),
            activo = COALESCE(%s, activo),
            categoria = COALESCE(%s, categoria)
        WHERE id_producto = %s
        RETURNING id_producto
        """,
        (
            payload.get("descripcion"),
            payload.get("precio"),
            payload.get("activo"),
            payload.get("categoria"),
            id_producto,
        ),
    )
    return row is not None


def delete_producto(id_producto: int) -> bool:
    return _execute("DELETE FROM productos WHERE id_producto = %s", (id_producto,)) > 0


def read_inventario() -> list[dict[str, Any]]:
    return _fetch_all(
        """
        SELECT id_producto, cantidad
        FROM inventario
        ORDER BY id_producto
        """
    )


def get_inventario_item(id_producto: int) -> dict[str, Any] | None:
    return _fetch_one(
        "SELECT id_producto, cantidad FROM inventario WHERE id_producto = %s",
        (id_producto,),
    )


def registrar_inventario(id_producto: int, cantidad: int) -> bool:
    return _execute(
        """
        INSERT INTO inventario (id_producto, cantidad)
        VALUES (%s, %s)
        ON CONFLICT (id_producto) DO NOTHING
        """,
        (id_producto, cantidad),
    ) > 0


def agregar_inventario(id_producto: int, cantidad: int) -> bool:
    row = _fetch_one(
        """
        UPDATE inventario
        SET cantidad = cantidad + %s
        WHERE id_producto = %s
        RETURNING id_producto
        """,
        (cantidad, id_producto),
    )
    return row is not None


def descontar_inventario(id_producto: int, cantidad: int) -> dict[str, Any]:
    item = get_inventario_item(id_producto)
    if item is None:
        return {"exito": False, "error": "Producto no encontrado", "id_producto": id_producto}

    stock_actual = int(item["cantidad"])
    if stock_actual < cantidad:
        return {"exito": False, "error": "Stock insuficiente", "id_producto": id_producto}

    row = _fetch_one(
        """
        UPDATE inventario
        SET cantidad = cantidad - %s
        WHERE id_producto = %s
        RETURNING cantidad
        """,
        (cantidad, id_producto),
    )
    return {
        "exito": True,
        "id_producto": id_producto,
        "nueva_cantidad": int(row["cantidad"]),
    }


def read_pedidos() -> list[dict[str, Any]]:
    return _fetch_all(
        """
        SELECT id_pedido, id_cliente, id_producto, cantidad
        FROM pedidos
        ORDER BY id_pedido
        """
    )


def create_pedido(id_cliente: int, id_producto: int, cantidad: int) -> int:
    row = _fetch_one(
        """
        INSERT INTO pedidos (id_pedido, id_cliente, id_producto, cantidad)
        VALUES (
            (SELECT COALESCE(MAX(id_pedido), 500) + 1 FROM pedidos),
            %s, %s, %s
        )
        RETURNING id_pedido
        """,
        (id_cliente, id_producto, cantidad),
    )
    return int(row["id_pedido"])
