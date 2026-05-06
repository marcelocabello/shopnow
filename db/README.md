# Base de datos Postgres para ShopNow

Esta carpeta deja lista la estructura para cargar los CSV actuales del proyecto en Postgres.

## Archivos

- `schema.sql`: crea las tablas `clientes`, `productos`, `inventario` y `pedidos`.
- `import_csv.sql`: vacía las tablas e importa los datos desde los CSV del root del proyecto.

## Datos de conexión

Con la información que me compartiste:

- `database`: `shopnow_663n`
- `user`: `shopnow_663n_user`
- `password`: `mJKZ4Bs3pW5XqeK5c5FLIukVy1TUGEII`

Todavía hace falta el `host` de Postgres para conectarnos al servidor real.

## Ejecución

Desde la raíz del proyecto:

```bash
export PGPASSWORD='mJKZ4Bs3pW5XqeK5c5FLIukVy1TUGEII'
psql -h TU_HOST -p 5432 -U shopnow_663n_user -d shopnow_663n -f db/schema.sql
psql -h TU_HOST -p 5432 -U shopnow_663n_user -d shopnow_663n -f db/import_csv.sql
```

## Activar Postgres en la app

Para que los microservicios usen Postgres directamente y ya no dependan de los CSV:

```bash
export SHOPNOW_STORAGE=postgres
export POSTGRES_HOST=TU_HOST
export POSTGRES_PORT=5432
export POSTGRES_DB=shopnow_663n
export POSTGRES_USER=shopnow_663n_user
export POSTGRES_PASSWORD='mJKZ4Bs3pW5XqeK5c5FLIukVy1TUGEII'
```

Después de eso levantas tus servicios normalmente.

## Notas

- `clientes.csv` fue corregido para volver a ser un CSV válido en texto plano.
- `productos.csv` actual solo trae 4 columnas; al importar, `categoria` se rellena con `General`.
- `pedidos` e `inventario` conservan las relaciones por `id_producto` e `id_cliente`.
