import pika
import os
from pika import (
    exceptions,
    PlainCredentials,
    ConnectionParameters,
    BlockingConnection,
    BasicProperties,
    DeliveryMode
)
import json
import uuid
from typing import Callable, Dict, Any, Optional
import threading
import time


def create_rabbitmq_client(default_host: str = 'localhost', default_port: int = 5672):
    """Crea un cliente RabbitMQ configurable por variables de entorno."""
    host = os.getenv("RABBITMQ_HOST", default_host)
    port = int(os.getenv("RABBITMQ_PORT", str(default_port)))
    return RabbitMQClient(host=host, port=port)

class RabbitMQClient:
    """Client para comunicación entre servicios a través de RabbitMQ."""
    
    def __init__(self, host='rabbitmq', port=5672):
        """
        Inicializa el cliente de RabbitMQ.
        
        Args:
            host: Dirección del servidor RabbitMQ (default: 'rabbitmq' para Docker)
            port: Puerto de RabbitMQ (default: 5672)
        """
        self.host = host
        self.port = port
        self.connection: Optional[Any] = None
        self.channel: Optional[Any] = None
        self.reply_queue: Optional[str] = None
        self.callbacks: Dict[str, Callable] = {}
        self.channel_lock = threading.Lock()  # Para sincronizar acceso al canal
        
    def connect(self):
        """Establece conexión con RabbitMQ."""
        try:
            credentials = PlainCredentials('guest', 'guest')
            parameters = ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                connection_attempts=10,
                retry_delay=1,
                heartbeat=0,  # Disable heartbeat which can cause StreamLostError
                blocked_connection_timeout=300
            )
            self.connection = BlockingConnection(parameters)
            self.channel = self.connection.channel()
            print(f"✓ Conectado a RabbitMQ en {self.host}:{self.port}")
        except exceptions.AMQPConnectionError as e:
            print(f"✗ Error conectando a RabbitMQ: {e}")
            raise
    
    def declare_queue(self, queue_name: str, durable: bool = True):
        """
        Declara una cola en RabbitMQ.
        
        Args:
            queue_name: Nombre de la cola
            durable: Si la cola persiste después de reiniciar RabbitMQ
        """
        self.channel.queue_declare(queue=queue_name, durable=durable)
    
    def declare_exchange(self, exchange_name: str, exchange_type: str = 'direct', durable: bool = True):
        """
        Declara un exchange en RabbitMQ.
        
        Args:
            exchange_name: Nombre del exchange
            exchange_type: Tipo de exchange (direct, topic, fanout)
            durable: Si persiste después de reiniciar
        """
        self.channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=exchange_type,
            durable=durable
        )
    
    def bind_queue(self, queue_name: str, exchange_name: str, routing_key: str):
        """
        Vincula una cola a un exchange con una routing key.
        
        Args:
            queue_name: Nombre de la cola
            exchange_name: Nombre del exchange
            routing_key: Clave de enrutamiento
        """
        self.channel.queue_bind(
            queue=queue_name,
            exchange=exchange_name,
            routing_key=routing_key
        )
    
    def publish(self, exchange: str, routing_key: str, message: Dict[str, Any]):
        """
        Publica un mensaje a un exchange.
        
        Args:
            exchange: Nombre del exchange
            routing_key: Clave de enrutamiento
            message: Diccionario con el mensaje
        """
        publish_connection = None
        try:
            credentials = PlainCredentials('guest', 'guest')
            parameters = ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                connection_attempts=3,
                retry_delay=0.5,
                heartbeat=0,
                blocked_connection_timeout=300
            )
            publish_connection = BlockingConnection(parameters)
            publish_channel = publish_connection.channel()
            publish_channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=BasicProperties(
                    delivery_mode=DeliveryMode.Persistent
                )
            )
        finally:
            if publish_connection and not publish_connection.is_closed:
                publish_connection.close()
    
    def request_reply(self, exchange: str, routing_key: str, message: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        """
        Patrón Request-Reply: envía un mensaje y espera respuesta.
        
        Args:
            exchange: Exchange donde enviar
            routing_key: Routing key del servicio destino
            message: Mensaje a enviar
            timeout: Segundos a esperar respuesta (default: 30)
        
        Returns:
            Diccionario con la respuesta o None si timeout
        """
        rr_connection = None
        try:
            # Crear una conexión completamente separada para request-reply
            credentials = PlainCredentials('guest', 'guest')
            parameters = ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                connection_attempts=3,
                retry_delay=0.5,
                heartbeat=0,
                blocked_connection_timeout=300
            )
            rr_connection = BlockingConnection(parameters)
            rr_channel = rr_connection.channel()
            
            # ID único para esta solicitud
            correlation_id = str(uuid.uuid4())
            
            # Declarar cola temporal exclusiva
            result = rr_channel.queue_declare(queue='', exclusive=True)
            reply_queue = result.method.queue
            
            print(f"📤 Request: {routing_key}")
            
            # Enviar request
            rr_channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=BasicProperties(
                    reply_to=reply_queue,
                    correlation_id=correlation_id,
                    delivery_mode=DeliveryMode.Persistent
                )
            )
            
            # Esperar respuesta con timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                method, properties, body = rr_channel.basic_get(queue=reply_queue, auto_ack=False)
                
                if method:
                    # Verificar correlation_id
                    if properties and properties.correlation_id == correlation_id:
                        response = json.loads(body)
                        rr_channel.basic_ack(delivery_tag=method.delivery_tag)
                        print(f"📥 Response OK")
                        return response
                    else:
                        # No es nuestra respuesta
                        rr_channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                
                time.sleep(0.05)
            
            print(f"⏱ Timeout para {routing_key}")
            return None
        
        except Exception as e:
            print(f"❌ Error request_reply: {e}")
            return None
        finally:
            # Cerrar conexión separada
            try:
                if rr_connection and not rr_connection.is_closed:
                    rr_connection.close()
            except:
                pass
    
    def consume(self, queue_name: str, callback: Callable, auto_ack: bool = False):
        """
        Comienza a consumir mensajes de una cola.
        
        Args:
            queue_name: Nombre de la cola
            callback: Función callback(channel, method, properties, body)
            auto_ack: Reconocimiento automático de mensajes
        """
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=auto_ack
        )
        
        try:
            print(f"🔄 Escuchando mensajes en cola: {queue_name}")
            self.channel.start_consuming()
        except KeyboardInterrupt:
            print(f"⏹ Deteniendo consumidor de {queue_name}")
            self.channel.stop_consuming()
    
    def start_consumer_thread(self, queue_name: str, callback: Callable, auto_ack: bool = False):
        """
        Inicia un consumidor en un thread separado.
        
        Args:
            queue_name: Nombre de la cola
            callback: Función callback
            auto_ack: Reconocimiento automático
        
        Returns:
            Thread del consumidor
        """
        thread = threading.Thread(
            target=self.consume,
            args=(queue_name, callback, auto_ack)
        )
        thread.daemon = True
        thread.start()
        return thread
    
    def close(self):
        """Cierra la conexión con RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            print("✓ Desconectado de RabbitMQ")


# Queues y exchanges definidos
# =============================

EXCHANGES = {
    'servicios': 'direct'
}

QUEUES = {
    'productos_requests': 'request.productos',
    'productos_responses': 'response.productos',
    'clientes_requests': 'request.clientes',
    'clientes_responses': 'response.clientes',
    'inventario_requests': 'request.inventario',
    'inventario_responses': 'response.inventario',
}

ROUTING_KEYS = {
    'validate_producto': 'productos.validate',
    'get_inventario': 'inventario.get',
    'descontar_inventario': 'inventario.descontar',
    'validate_cliente': 'clientes.validate',
    'crear_pedido': 'pedidos.crear',
}
