# Desplegar ShopNow en Render

## Qué cambia frente a ngrok

Con `ngrok`, compartes servicios que siguen corriendo en tu computadora.

Con Render, subes tu proyecto a la nube y Render lo ejecuta por ti. La URL pública ya no depende de que tu máquina siga prendida.

## Opción recomendada para este proyecto

Desplegar 5 servicios web:

1. `shopnow-clientes`
2. `shopnow-productos`
3. `shopnow-pedidos`
4. `shopnow-inventario`
5. `shopnow-gateway`

El gateway concentra las rutas públicas igual que lo hacías con `ngrok`.

## Pasos

1. Sube este repo a GitHub.
2. En Render, entra a `New +`.
3. Elige `Blueprint`.
4. Conecta tu repositorio.
5. Render detectará el archivo `render.yaml`.
6. Revisa los nombres y crea los servicios.
7. Cuando Render termine, abre el servicio `shopnow-gateway`.

## URL para compartir

La URL que compartes será la del gateway:

`https://shopnow-gateway.onrender.com`

Y desde ahí tendrás:

- `/panel`
- `/docs`
- `/clientes/docs`
- `/productos/docs`
- `/pedidos/docs`
- `/inventario/docs`

## Importante sobre RabbitMQ

Tus servicios sí arrancan aunque RabbitMQ no esté disponible, pero varias operaciones asíncronas dependen de él.

Si tu profe solo necesita ver la app y los endpoints básicos, puedes desplegar así.

Si también necesita probar mensajería asíncrona:

1. Consigue un RabbitMQ externo.
2. Configura estas variables en Render para cada microservicio:
   - `RABBITMQ_HOST`
   - `RABBITMQ_PORT`

## Importante sobre las URLs del gateway

En `render.yaml` dejé valores base para:

- `CLIENTES_URL`
- `PRODUCTOS_URL`
- `PEDIDOS_URL`
- `INVENTARIO_URL`

Si Render te asigna URLs distintas, actualízalas en el servicio `shopnow-gateway`.

## Comandos locales equivalentes

Localmente sigues usando:

```bash
uvicorn gateway:app --host 0.0.0.0 --port 8090 --reload
```

En Render se usa:

```bash
uvicorn gateway:app --host 0.0.0.0 --port $PORT
```
