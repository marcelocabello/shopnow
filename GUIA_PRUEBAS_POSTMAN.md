# Guía de Pruebas Paso a Paso — ShopNow

## Antes de empezar: levantar todo

```bash
cd /home/olecram/Documentos/SOA/shopnow/ShopNow
bash shopnow.sh start
```

Espera ~10 segundos. Con eso levantas el flujo de microservicios Python y RabbitMQ.

Verifica en el navegador que abren:
- http://localhost:8010/docs — Clientes
- http://localhost:8001/docs — Productos
- http://localhost:8002/docs — Pedidos
- http://localhost:15672 — RabbitMQ (guest / guest)

Importante:
- `bash shopnow.sh start` sirve para probar autenticación, versionado y operaciones de escritura asíncronas con RabbitMQ.
- El flujo de pedidos usa el inventario Python consumidor de RabbitMQ.
- El inventario Java se prueba aparte como servicio REST en el puerto `8003` para cubrir el requisito de "otro lenguaje".

> **El inventario Java** no lo levanta el script. Para probar la parte Java por separado:
> ```bash
> bash java.sh start
> ```
>
> Alternativa manual (si quieres ejecutarlo sin script):
> ```bash
> pkill -f "uvicorn serv_inventario:app"
> cd java-inventario
> JAVA_HOME=/home/olecram/.jdk/jdk-25 /home/olecram/.jdk/jdk-25/bin/java -jar target/inventario-java-1.0.0.jar > /tmp/inventario.log 2>&1 &
> ```

Después de eso, verifica:
- http://localhost:8003/docs — Inventario (Java)

---

## BLOQUE 1 — Autenticación JWT

### 1.1 Obtener token (POST /token)

| Campo | Valor |
|-------|-------|
| Método | POST |
| URL | `http://localhost:8010/token` |
| Body | `form-data` |
| username | `admin` |
| password | `admin123` |

**Respuesta esperada (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```
**Guarda el `access_token`** — lo usarás en todos los requests siguientes.

---

### 1.2 Acceso sin token (debe dar 401)

| Campo | Valor |
|-------|-------|
| Método | GET |
| URL | `http://localhost:8010/v1/clientes` |
| Authorization | *(vacío, sin nada)* |

**Respuesta esperada (401):**
```json
{ "detail": "Not authenticated" }
```

---

### 1.3 Token inválido (debe dar 401)

| Campo | Valor |
|-------|-------|
| Método | GET |
| URL | `http://localhost:8010/v1/clientes` |
| Authorization | `Bearer token_invalido_xyz` |

**Respuesta esperada (401):**
```json
{ "detail": "Invalid authentication credentials" }
```

> A partir de aquí **todos los requests llevan**:
> ```
> Authorization: Bearer <tu_token>
> ```

---

## BLOQUE 2 — Versionado de API (v1 vs v2)

### 2.1 GET /v1/clientes

| Campo | Valor |
|-------|-------|
| Método | GET |
| URL | `http://localhost:8010/v1/clientes` |
| Authorization | `Bearer <token>` |

**Respuesta esperada (200) — 6 campos por cliente:**
```json
[
  {
    "id_cliente": 1,
    "nombre": "Cliente 1",
    "correo": "cliente1@example.com",
    "direccion": "Calle 1",
    "telefono": "4420000001",
    "activo": true
  }
]
```
Nota: NO tiene `rfc` ni `fecha_registro`.

---

### 2.2 GET /v2/clientes

| Campo | Valor |
|-------|-------|
| Método | GET |
| URL | `http://localhost:8010/v2/clientes` |
| Authorization | `Bearer <token>` |

**Respuesta esperada (200) — 8 campos por cliente:**
```json
[
  {
    "id_cliente": 1,
    "nombre": "Cliente 1",
    "correo": "cliente1@example.com",
    "direccion": "Calle 1",
    "telefono": "4420000001",
    "activo": true,
    "rfc": "RFC123456789",
    "fecha_registro": "2026-01-01"
  }
]
```
Nota: v2 **agrega** `rfc` y `fecha_registro`.

---

### 2.3 GET /v1/productos

| Campo | Valor |
|-------|-------|
| Método | GET |
| URL | `http://localhost:8001/v1/productos` |
| Authorization | `Bearer <token>` |

**Respuesta esperada (200) — 4 campos:**
```json
[
  { "id_producto": 1, "descripcion": "Producto 1", "precio": 100.0, "activo": true }
]
```

---

### 2.4 GET /v2/productos

| Campo | Valor |
|-------|-------|
| Método | GET |
| URL | `http://localhost:8001/v2/productos` |
| Authorization | `Bearer <token>` |

**Respuesta esperada (200) — 5 campos:**
```json
[
  { "id_producto": 1, "descripcion": "Producto 1", "precio": 100.0, "activo": true, "categoria": "General" }
]
```
Nota: v2 **agrega** `categoria`.

---

## BLOQUE 3 — Crear datos de prueba

### 3.1 Crear cliente de prueba (POST /v2/clientes)

| Campo | Valor |
|-------|-------|
| Método | POST |
| URL | `http://localhost:8010/v2/clientes` |
| Authorization | `Bearer <token>` |
| Content-Type | `application/json` |

**Body:**
```json
{
  "nombre": "Cliente Test",
  "correo": "test@example.com",
  "direccion": "Calle Test 123",
  "telefono": "4420000000",
  "activo": true,
  "rfc": "XAXX010101000",
  "fecha_registro": "2026-04-10"
}
```

**Respuesta esperada (202):**
```json
{
  "mensaje": "Cliente v2 encolado exitosamente",
  "status": "queued",
  "nota": "Se procesará automáticamente por RabbitMQ"
}
```
Luego de unos segundos, valida con `GET /v2/clientes` que el registro ya exista.

---

### 3.2 Crear producto de prueba (POST /v2/productos)

| Campo | Valor |
|-------|-------|
| Método | POST |
| URL | `http://localhost:8001/v2/productos` |
| Authorization | `Bearer <token>` |
| Content-Type | `application/json` |

**Body:**
```json
{
  "descripcion": "Laptop Prueba SOA",
  "precio": 5000.00,
  "activo": true,
  "categoria": "ELECTRONICA"
}
```

**Respuesta esperada (202):**
```json
{
  "mensaje": "Producto v2 encolado exitosamente",
  "status": "queued",
  "nota": "Se procesará automáticamente por RabbitMQ"
}
```
Luego de unos segundos, valida con `GET /v2/productos` y toma el `id_producto` real creado.

### 3.3 Preparar inventario para pruebas de pedidos

Este paso es para el flujo Python + RabbitMQ, no para el servicio Java.

Si tu inventario Python está corriendo en `8003` (o `8004` cuando `8003` lo ocupa Java), registra existencias ahí antes de probar pedidos.
Si estás usando el inventario Java en `8003`, termina primero esa prueba y vuelve al escenario Python para esta sección.

Ejemplo para inventario Python:

| Campo | Valor |
|-------|-------|
| Método | POST |
| URL | `http://localhost:8003/inventario` (o `http://localhost:8004/inventario`) |
| Authorization | `Bearer <token>` |
| Content-Type | `application/json` |

**Body:**
```json
{ "id_producto": 1, "cantidad": 100 }
```

**Respuesta esperada (202):**
```json
{
  "mensaje": "Solicitud de registro encolada",
  "status": "queued",
  "nota": "Se procesará automáticamente por RabbitMQ"
}
```

---

## BLOQUE 4 — Pedido Automático (Asíncrono)

### 4.1 POST /pedidos (encola automáticamente)

| Campo | Valor |
|-------|-------|
| Método | POST |
| URL | `http://localhost:8002/pedidos` |
| Authorization | `Bearer <token>` |
| Content-Type | `application/json` |

**Body:**
```json
{
  "id_cliente": 101,
  "id_producto": 1,
  "cantidad": 1
}
```

**Respuesta esperada (202):**
```json
{
  "mensaje": "Pedido encolado exitosamente",
  "status": "queued",
  "nota": "Se procesará cuando todos los servicios estén disponibles"
}
```

> Qué pasa: ahora **siempre se encola** en RabbitMQ. El consumidor lo procesa en segundo plano.
> Si un servicio dependiente está caído, el mensaje se re-encola y espera hasta que vuelva.

---

## BLOQUE 5 — Verificación de RabbitMQ y Reintentos

Este bloque es el más visual. Abre el dashboard en **http://localhost:15672** (guest / guest) antes de enviarlo.

### 5.1 POST /pedidos (flujo recomendado)

| Campo | Valor |
|-------|-------|
| Método | POST |
| URL | `http://localhost:8002/pedidos` |
| Authorization | `Bearer <token>` |
| Content-Type | `application/json` |

**Body:**
```json
{
  "id_cliente": 101,
  "id_producto": 1,
  "cantidad": 1
}
```

**Respuesta esperada (202):**
```json
{
  "mensaje": "Pedido encolado exitosamente",
  "status": "queued",
  "nota": "Se procesara automaticamente cuando todos los servicios esten disponibles"
}
```

### 5.2 Observar en RabbitMQ Dashboard

1. Ve a **http://localhost:15672**
2. Login: `guest` / `guest`
3. Click en la pestaña **Queues**
4. Busca la cola `pedidos_requests`
5. Verás el mensaje encolado (Ready: 1)
6. Espera 3-5 segundos y recarga → el mensaje desaparece al procesarse

### 5.3 Verificar que el pedido se creó (GET /pedidos)

| Campo | Valor |
|-------|-------|
| Método | GET |
| URL | `http://localhost:8002/pedidos` |
| Authorization | `Bearer <token>` |

**Respuesta:** aparece un nuevo pedido con el `id_cliente` e `id_producto` enviados, procesado desde la cola.

### 5.4 Probar el requeue real si un servicio se cae

Este es el check fuerte del requisito asíncrono.

1. Deja abiertos RabbitMQ y Pedidos.
2. Detén temporalmente Clientes:

```bash
pkill -f "uvicorn serv_clientes:app"
```

3. Envía otra vez `POST /pedidos`.
4. La respuesta HTTP debe seguir siendo `202`.
5. Haz `GET /pedidos`: el total **no debe aumentar todavía**.
6. Levanta Clientes otra vez:

```bash
cd /home/olecram/Documentos/SOA/shopnow/ShopNow
source .venv2/bin/activate
uvicorn serv_clientes:app --port 8010 --reload
```

7. Espera unos segundos.
8. Repite `GET /pedidos`: ahora sí debe aparecer el pedido pendiente.

Eso prueba que el mensaje se quedó encolado y se reprocesó después.

### 5.5 Nota de diseño

No hay endpoint especial para encolar.
El endpoint oficial y único para crear pedidos es `POST /pedidos`, y ese endpoint
ya encola automáticamente en RabbitMQ.

---

## BLOQUE 6 — Inventario Java (Puerto 8003)

> **Diferencia clave:** este servicio está escrito en **Java 25 + Spring Boot 3.5**.
> **También requiere autenticación JWT**. Usa el mismo header:
> `Authorization: Bearer <token>`

Precondición para este bloque:
- haber detenido el inventario Python en `8003`
- haber levantado el inventario Java en `8003`
- obtener un token con `POST /token` en `http://localhost:8003/token` o reutilizar uno válido emitido por otro servicio

### 6.1 GET /inventario — lista completa

| Campo | Valor |
|-------|-------|
| Método | GET |
| URL | `http://localhost:8003/inventario` |
| Authorization | `Bearer <token>` |

**Respuesta esperada (200):** `[]` o lista de productos.

---

### 6.2 POST /inventario — registrar producto

| Campo | Valor |
|-------|-------|
| Método | POST |
| URL | `http://localhost:8003/inventario` |
| Authorization | `Bearer <token>` |
| Content-Type | `application/json` |

**Body:**
```json
{ "id_producto": 23, "cantidad": 100 }
```

**Respuesta esperada (201):**
```json
{
  "status": "success",
  "mensaje": "Producto registrado en inventario",
  "id_producto": 23,
  "cantidad": 100
}
```

---

### 6.3 GET /inventario/23 — consultar por ID

| Campo | Valor |
|-------|-------|
| Método | GET |
| URL | `http://localhost:8003/inventario/23` |
| Authorization | `Bearer <token>` |

**Respuesta esperada (200):**
```json
{ "id_producto": 23, "cantidad": 100 }
```

---

### 6.4 GET /inventario/999 — producto inexistente

Usa el mismo header `Authorization: Bearer <token>`.

**Respuesta esperada (404):**
```json
{ "detail": "Producto no registrado en inventario" }
```

---

### 6.5 POST /inventario — duplicado (error)

Usa el mismo header `Authorization: Bearer <token>`.

Vuelve a enviar el mismo body de 6.2.

**Respuesta esperada (400):**
```json
{ "detail": "Producto ya registrado en inventario" }
```

---

### 6.6 POST /inventario — cantidad 0 (error)

Usa el mismo header `Authorization: Bearer <token>`.

**Body:**
```json
{ "id_producto": 99, "cantidad": 0 }
```

**Respuesta esperada (400):**
```json
{ "detail": "cantidad debe ser mayor a 0" }
```

---

### 6.7 POST /inventario/agregar — sumar stock

| Campo | Valor |
|-------|-------|
| Método | POST |
| URL | `http://localhost:8003/inventario/agregar` |
| Authorization | `Bearer <token>` |
| Content-Type | `application/json` |

**Body:**
```json
{ "id_producto": 23, "cantidad": 50 }
```

**Respuesta esperada (200):**
```json
{
  "status": "success",
  "mensaje": "Inventario actualizado exitosamente",
  "id_producto": 23,
  "cantidad_agregada": 50
}
```

Haz GET /inventario/23 → debe mostrar `"cantidad": 150`.

---

### 6.8 POST /inventario/descontar — restar stock

| Campo | Valor |
|-------|-------|
| Método | POST |
| URL | `http://localhost:8003/inventario/descontar` |
| Authorization | `Bearer <token>` |
| Content-Type | `application/json` |

**Body:**
```json
{ "id_producto": 23, "cantidad": 30 }
```

**Respuesta esperada (200):**
```json
{
  "status": "success",
  "mensaje": "Inventario descontado exitosamente",
  "id_producto": 23,
  "cantidad_descontada": 30
}
```

Haz GET /inventario/23 → debe mostrar `"cantidad": 120`.

---

### 6.9 POST /inventario/descontar — stock insuficiente (error)

Usa el mismo header `Authorization: Bearer <token>`.

**Body:**
```json
{ "id_producto": 23, "cantidad": 9999 }
```

**Respuesta esperada (400):**
```json
{ "detail": "Inventario insuficiente" }
```

---

### 6.10 POST /inventario/descontar — producto no existe (error)

Usa el mismo header `Authorization: Bearer <token>`.

**Body:**
```json
{ "id_producto": 999, "cantidad": 5 }
```

**Respuesta esperada (404):**
```json
{ "detail": "Producto no registrado en inventario" }
```

---

## Para detener todo

```bash
bash shopnow.sh stop
```

Detiene los 4 servicios Python y el contenedor de RabbitMQ.
