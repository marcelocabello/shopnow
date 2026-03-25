import pika
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
        
    def connect(self):
        """Establece conexión con RabbitMQ."""
        try:
            credentials = PlainCredentials('guest', 'guest')
            parameters = ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                connection_attempts=10,
                retry_delay=1
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
        message_json = json.dumps(message)
        self.channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=message_json,
            properties=BasicProperties(
                delivery_mode=DeliveryMode.Persistent
            )
        )
    
    def request_reply(self, exchange: str, routing_key: str, message: Dict[str, Any], timeout: int = 5) -> Dict[str, Any]:
        """
        Patrón Request-Reply: envía un mensaje y espera respuesta.
        
        Args:
            exchange: Exchange donde enviar
            routing_key: Routing key del servicio destino
            message: Mensaje a enviar
            timeout: Segundos a esperar respuesta (default: 5)
        
        Returns:
            Diccionario con la respuesta o None si timeout
        """
        # Crear cola de respuesta si no existe
        if not self.reply_queue:
            result = self.channel.queue_declare(queue='', exclusive=True)
            self.reply_queue = result.method.queue
        
        # ID único para correlacionar request-reply
        correlation_id = str(uuid.uuid4())
        
        # Agregar información de respuesta al mensaje
        message['reply_to'] = self.reply_queue
        message['correlation_id'] = correlation_id
        
        # Variable para almacenar respuesta
        response = None
        
        def response_callback(ch, method, properties, body):
            nonlocal response
            # Verificar que es la respuesta correcta
            if properties.correlation_id == correlation_id:
                response = json.loads(body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
        
        # Suscribirse a la cola de respuesta
        self.channel.basic_consume(
            queue=self.reply_queue,
            on_message_callback=response_callback,
            auto_ack=False
        )
        
        # Enviar request
        self.publish(exchange, routing_key, message)
        
        # Esperar respuesta con timeout
        start_time = time.time()
        while response is None:
            if time.time() - start_time > timeout:
                print(f"⏱ Timeout esperando respuesta con correlation_id: {correlation_id}")
                self.channel.stop_consuming()
                return None
            
            try:
                self.channel.connection.process_data_events(time_limit=0.1)
            except Exception as e:
                print(f"Error procesando eventos: {e}")
                self.channel.stop_consuming()
                return None
        
        # Detener consumidor temporal
        self.channel.stop_consuming()
        
        return response
    
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
}
