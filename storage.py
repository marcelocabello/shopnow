import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

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
DEFAULT_SSLMODE = os.getenv("POSTGRES_SSLMODE", "prefer")
_COLUMN_CACHE: dict[str, set[str]] = {}


def postgres_enabled() -> bool:
    mode = os.getenv("SHOPNOW_STORAGE", "postgres").lower()
    if mode == "csv":
        raise RuntimeError("El modo CSV ya no está soportado; usa Postgres en Docker")
    return True


def _postgres_settings() -> dict[str, Any]:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme.startswith("postgres"):
            return {
                "host": parsed.hostname or "",
                "port": parsed.port or 5432,
                "dbname": (parsed.path or "").lstrip("/") or DEFAULT_DB,
                "user": unquote(parsed.username or DEFAULT_USER),
                "password": unquote(parsed.password or ""),
                "sslmode": DEFAULT_SSLMODE,
            }

    return {
        "host": os.getenv("POSTGRES_HOST", ""),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DB", DEFAULT_DB),
        "user": os.getenv("POSTGRES_USER", DEFAULT_USER),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "sslmode": DEFAULT_SSLMODE,
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
            # Compatibilidad con BD existente (si el usuario tiene permisos de ALTER).
            try:
                cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS rfc VARCHAR(20)")
                cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS fecha_registro DATE")
                cur.execute("UPDATE clientes SET rfc = '' WHERE rfc IS NULL")
                cur.execute("ALTER TABLE clientes ALTER COLUMN rfc SET DEFAULT ''")

                cur.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS categoria VARCHAR(100)")
                cur.execute("UPDATE productos SET categoria = 'General' WHERE categoria IS NULL")
                cur.execute("ALTER TABLE productos ALTER COLUMN categoria SET DEFAULT 'General'")
                cur.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS descuento_pct NUMERIC(5,2) NOT NULL DEFAULT 0")
                cur.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS precio_unitario NUMERIC(10,2) NOT NULL DEFAULT 0")
                cur.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS total NUMERIC(12,2) NOT NULL DEFAULT 0")
                cur.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS fecha_pedido TIMESTAMP NOT NULL DEFAULT NOW()")
            except Exception:
                conn.rollback()
                cur.execute("SELECT pg_advisory_lock(663001)")
            cur.execute("SELECT pg_advisory_unlock(663001)")


def seed_demo_data_if_enabled() -> None:
    """Inserta datos demo cuando SHOPNOW_SEED_DEMO=true y las tablas estan vacias."""
    if os.getenv("SHOPNOW_SEED_DEMO", "false").strip().lower() not in ("1", "true", "yes", "on"):
        return
    if not postgres_enabled():
        return

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(663002)")
            try:
                cur.execute("SELECT COUNT(*) FROM clientes")
                clientes_count = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM productos")
                productos_count = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM inventario")
                inventario_count = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM pedidos")
                pedidos_count = int(cur.fetchone()[0])
                cliente_cols = _table_columns("clientes")
                producto_cols = _table_columns("productos")
                has_rfc = "rfc" in cliente_cols
                has_fecha = "fecha_registro" in cliente_cols
                has_categoria = "categoria" in producto_cols

                # Clientes
                if clientes_count == 0:
                    for i in range(1, 21):
                        if has_rfc and has_fecha:
                            cur.execute(
                                """
                                INSERT INTO clientes (nombre, correo, direccion, telefono, activo, rfc, fecha_registro)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    f"Cliente Demo {i:02d}",
                                    f"cliente.demo{i:02d}@shopnow.test",
                                    f"Calle Demo #{100+i}, Queretaro",
                                    f"{4420000000 + i:010d}",
                                    True,
                                    f"DEMO{i:02d}0101AAA",
                                    "2026-05-25",
                                ),
                            )
                        else:
                            cur.execute(
                                """
                                INSERT INTO clientes (nombre, correo, direccion, telefono, activo)
                                VALUES (%s, %s, %s, %s, %s)
                                """,
                                (
                                    f"Cliente Demo {i:02d}",
                                    f"cliente.demo{i:02d}@shopnow.test",
                                    f"Calle Demo #{100+i}, Queretaro",
                                    f"{4420000000 + i:010d}",
                                    True,
                                ),
                            )

                # Productos
                if productos_count == 0:
                    for i in range(1, 21):
                        if has_categoria:
                            cur.execute(
                                """
                                INSERT INTO productos (descripcion, precio, activo, categoria)
                                VALUES (%s, %s, %s, %s)
                                """,
                                (
                                    f"Producto Demo {i:02d}",
                                    float(50 + i * 7),
                                    True,
                                    "Demo",
                                ),
                            )
                        else:
                            cur.execute(
                                """
                                INSERT INTO productos (descripcion, precio, activo)
                                VALUES (%s, %s, %s)
                                """,
                                (
                                    f"Producto Demo {i:02d}",
                                    float(50 + i * 7),
                                    True,
                                ),
                            )

                # Inventario (20 registros sobre los primeros 20 productos)
                if inventario_count == 0:
                    cur.execute("SELECT id_producto FROM productos ORDER BY id_producto LIMIT 20")
                    product_rows = cur.fetchall()
                    for idx, (product_id,) in enumerate(product_rows, start=1):
                        cur.execute(
                            """
                            INSERT INTO inventario (id_producto, cantidad)
                            VALUES (%s, %s)
                            ON CONFLICT (id_producto) DO UPDATE SET cantidad = EXCLUDED.cantidad
                            """,
                            (int(product_id), 10 + idx),
                        )

                # Pedidos
                if pedidos_count == 0:
                    cur.execute("SELECT id_cliente FROM clientes ORDER BY id_cliente LIMIT 20")
                    client_rows = [int(row[0]) for row in cur.fetchall()]
                    cur.execute("SELECT id_producto FROM productos ORDER BY id_producto LIMIT 20")
                    product_rows = [int(row[0]) for row in cur.fetchall()]
                    if client_rows and product_rows:
                        for i in range(20):
                            cur.execute(
                                """
                                INSERT INTO pedidos (id_cliente, id_producto, cantidad)
                                VALUES (%s, %s, %s)
                                """,
                                (
                                    client_rows[i % len(client_rows)],
                                    product_rows[i % len(product_rows)],
                                    (i % 5) + 1,
                                ),
                            )
            finally:
                cur.execute("SELECT pg_advisory_unlock(663002)")


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


def _table_columns(table_name: str) -> set[str]:
    cached = _COLUMN_CACHE.get(table_name)
    if cached is not None:
        return cached
    rows = _fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    cols = {str(r["column_name"]) for r in rows}
    _COLUMN_CACHE[table_name] = cols
    return cols


def read_clientes() -> list[dict[str, Any]]:
    cliente_cols = _table_columns("clientes")
    has_rfc = "rfc" in cliente_cols
    has_fecha = "fecha_registro" in cliente_cols
    rfc_select = "rfc" if has_rfc else "''::varchar AS rfc"
    fecha_select = "fecha_registro" if has_fecha else "NULL::date AS fecha_registro"
    rows = _fetch_all(
        f"""
        SELECT id_cliente, nombre, correo, direccion, telefono, activo, {rfc_select}, {fecha_select}
        FROM clientes
        ORDER BY id_cliente
        """
    )
    for row in rows:
        row["nombre"] = row.get("nombre") or ""
        row["correo"] = row.get("correo") or ""
        row["direccion"] = row.get("direccion") or ""
        row["telefono"] = row.get("telefono") or ""
        row["rfc"] = row.get("rfc") or ""
        if row.get("fecha_registro") is not None:
            row["fecha_registro"] = row["fecha_registro"].isoformat()
        else:
            row["fecha_registro"] = ""
    return rows


def cliente_exists(id_cliente: int) -> bool:
    return _fetch_one("SELECT 1 AS ok FROM clientes WHERE id_cliente = %s", (id_cliente,)) is not None


def create_cliente(payload: dict[str, Any]) -> int:
    cliente_cols = _table_columns("clientes")
    has_rfc = "rfc" in cliente_cols
    has_fecha = "fecha_registro" in cliente_cols
    if has_rfc and has_fecha:
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
    else:
        row = _fetch_one(
            """
            INSERT INTO clientes (id_cliente, nombre, correo, direccion, telefono, activo)
            VALUES (
                (SELECT COALESCE(MAX(id_cliente), 100) + 1 FROM clientes),
                %s, %s, %s, %s, %s
            )
            RETURNING id_cliente
            """,
            (
                payload.get("nombre", ""),
                payload.get("correo", ""),
                payload.get("direccion", ""),
                payload.get("telefono", ""),
                payload.get("activo", True),
            ),
        )
    return int(row["id_cliente"])


def update_cliente(id_cliente: int, payload: dict[str, Any]) -> bool:
    cliente_cols = _table_columns("clientes")
    has_rfc = "rfc" in cliente_cols
    has_fecha = "fecha_registro" in cliente_cols
    if has_rfc and has_fecha:
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
    else:
        row = _fetch_one(
            """
            UPDATE clientes
            SET
                nombre = COALESCE(%s, nombre),
                correo = COALESCE(%s, correo),
                direccion = COALESCE(%s, direccion),
                telefono = COALESCE(%s, telefono),
                activo = COALESCE(%s, activo)
            WHERE id_cliente = %s
            RETURNING id_cliente
            """,
            (
                payload.get("nombre"),
                payload.get("correo"),
                payload.get("direccion"),
                payload.get("telefono"),
                payload.get("activo"),
                id_cliente,
            ),
        )
    return row is not None


def inactivate_cliente(id_cliente: int) -> bool:
    return _execute("UPDATE clientes SET activo = FALSE WHERE id_cliente = %s", (id_cliente,)) > 0


def read_productos() -> list[dict[str, Any]]:
    product_cols = _table_columns("productos")
    categoria_select = "categoria" if "categoria" in product_cols else "'General'::varchar AS categoria"
    rows = _fetch_all(
        f"""
        SELECT id_producto, descripcion, precio, activo, {categoria_select}
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
    product_cols = _table_columns("productos")
    if "categoria" in product_cols:
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
    else:
        row = _fetch_one(
            """
            INSERT INTO productos (id_producto, descripcion, precio, activo)
            VALUES (
                (SELECT COALESCE(MAX(id_producto), 0) + 1 FROM productos),
                %s, %s, %s
            )
            RETURNING id_producto
            """,
            (
                payload.get("descripcion", ""),
                payload.get("precio", 0),
                payload.get("activo", True),
            ),
        )
    id_producto = int(row["id_producto"])
    registrar_inventario(id_producto, int(payload.get("stock_inicial", 0) or 0))
    return id_producto


def update_producto(id_producto: int, payload: dict[str, Any]) -> bool:
    product_cols = _table_columns("productos")
    if "categoria" in product_cols:
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
    else:
        row = _fetch_one(
            """
            UPDATE productos
            SET
                descripcion = COALESCE(%s, descripcion),
                precio = COALESCE(%s, precio),
                activo = COALESCE(%s, activo)
            WHERE id_producto = %s
            RETURNING id_producto
            """,
            (
                payload.get("descripcion"),
                payload.get("precio"),
                payload.get("activo"),
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
    row = _fetch_one(
        """
        SELECT exito, nueva_cantidad, error
        FROM sp_descontar_inventario(%s, %s)
        """,
        (id_producto, cantidad),
    )
    if not row:
        return {"exito": False, "error": "Error inesperado en procedimiento", "id_producto": id_producto}
    if not bool(row["exito"]):
        return {
            "exito": False,
            "error": row.get("error") or "No fue posible descontar inventario",
            "id_producto": id_producto,
        }
    return {
        "exito": True,
        "id_producto": id_producto,
        "nueva_cantidad": int(row["nueva_cantidad"]),
    }


def read_pedidos() -> list[dict[str, Any]]:
    cols = _table_columns("pedidos")
    has_descuento = "descuento_pct" in cols
    has_precio = "precio_unitario" in cols
    has_total = "total" in cols
    has_fecha = "fecha_pedido" in cols
    descuento_select = "descuento_pct" if has_descuento else "0::numeric AS descuento_pct"
    precio_select = "precio_unitario" if has_precio else "0::numeric AS precio_unitario"
    total_select = "total" if has_total else "0::numeric AS total"
    fecha_select = "fecha_pedido" if has_fecha else "NOW()::timestamp AS fecha_pedido"
    rows = _fetch_all(
        f"""
        SELECT id_pedido, id_cliente, id_producto, cantidad, {descuento_select}, {precio_select}, {total_select}, {fecha_select}
        FROM pedidos
        ORDER BY id_pedido
        """
    )
    for row in rows:
        row["descuento_pct"] = float(row.get("descuento_pct") or 0)
        row["precio_unitario"] = float(row.get("precio_unitario") or 0)
        row["total"] = float(row.get("total") or 0)
        if row.get("fecha_pedido") is not None and hasattr(row["fecha_pedido"], "isoformat"):
            row["fecha_pedido"] = row["fecha_pedido"].isoformat()
    return rows


def create_pedido(
    id_cliente: int,
    id_producto: int,
    cantidad: int,
    precio_unitario: float = 0,
    descuento_pct: float = 0,
    total: float = 0,
) -> int:
    cols = _table_columns("pedidos")
    if {"descuento_pct", "precio_unitario", "total", "fecha_pedido"}.issubset(cols):
        row = _fetch_one(
            """
            INSERT INTO pedidos (id_cliente, id_producto, cantidad, descuento_pct, precio_unitario, total, fecha_pedido)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id_pedido
            """,
            (id_cliente, id_producto, cantidad, descuento_pct, precio_unitario, total),
        )
    else:
        row = _fetch_one(
            """
            SELECT sp_crear_pedido(%s, %s, %s) AS id_pedido
            """,
            (id_cliente, id_producto, cantidad),
        )
    return int(row["id_pedido"])


def validar_stock(id_producto: int, cantidad: int) -> dict[str, Any]:
    row = _fetch_one(
        """
        SELECT existe_producto, stock_actual, stock_suficiente
        FROM sp_validar_stock(%s, %s)
        """,
        (id_producto, cantidad),
    )
    if not row:
        return {"existe_producto": False, "stock_actual": 0, "stock_suficiente": False}
    return {
        "existe_producto": bool(row["existe_producto"]),
        "stock_actual": int(row["stock_actual"] or 0),
        "stock_suficiente": bool(row["stock_suficiente"]),
    }
