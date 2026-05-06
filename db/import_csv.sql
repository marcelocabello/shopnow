\set ON_ERROR_STOP on

BEGIN;

TRUNCATE TABLE pedidos, inventario, clientes, productos RESTART IDENTITY CASCADE;

CREATE TEMP TABLE stg_clientes (
    id_cliente INTEGER,
    nombre TEXT,
    correo TEXT,
    direccion TEXT,
    telefono TEXT,
    activo TEXT,
    rfc TEXT,
    fecha_registro TEXT
);

CREATE TEMP TABLE stg_productos (
    id_producto INTEGER,
    descripcion TEXT,
    precio NUMERIC(10,2),
    activo TEXT
);

CREATE TEMP TABLE stg_inventario (
    id_producto INTEGER,
    cantidad INTEGER
);

CREATE TEMP TABLE stg_pedidos (
    id_pedido INTEGER,
    id_cliente INTEGER,
    id_producto INTEGER,
    cantidad INTEGER
);

\copy stg_clientes FROM './clientes.csv' WITH (FORMAT csv, HEADER true)
\copy stg_productos FROM './productos.csv' WITH (FORMAT csv, HEADER true)
\copy stg_inventario FROM './inventario.csv' WITH (FORMAT csv, HEADER true)
\copy stg_pedidos FROM './pedidos.csv' WITH (FORMAT csv, HEADER true)

INSERT INTO clientes (id_cliente, nombre, correo, direccion, telefono, activo, rfc, fecha_registro)
SELECT
    id_cliente,
    nombre,
    correo,
    direccion,
    telefono,
    COALESCE(NULLIF(LOWER(activo), ''), 'true') IN ('true', '1', 't', 'yes'),
    COALESCE(rfc, ''),
    NULLIF(fecha_registro, '')::DATE
FROM stg_clientes
ORDER BY id_cliente;

INSERT INTO productos (id_producto, descripcion, precio, activo, categoria)
SELECT
    id_producto,
    descripcion,
    precio,
    COALESCE(NULLIF(LOWER(activo), ''), 'true') IN ('true', '1', 't', 'yes'),
    'General'
FROM stg_productos
ORDER BY id_producto;

INSERT INTO inventario (id_producto, cantidad)
SELECT id_producto, cantidad
FROM stg_inventario
ORDER BY id_producto;

INSERT INTO pedidos (id_pedido, id_cliente, id_producto, cantidad)
SELECT id_pedido, id_cliente, id_producto, cantidad
FROM stg_pedidos
ORDER BY id_pedido;

SELECT setval(pg_get_serial_sequence('clientes', 'id_cliente'), COALESCE((SELECT MAX(id_cliente) FROM clientes), 1), true);
SELECT setval(pg_get_serial_sequence('productos', 'id_producto'), COALESCE((SELECT MAX(id_producto) FROM productos), 1), true);
SELECT setval(pg_get_serial_sequence('pedidos', 'id_pedido'), COALESCE((SELECT MAX(id_pedido) FROM pedidos), 1), true);

COMMIT;
