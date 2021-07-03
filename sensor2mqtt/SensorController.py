import asyncio
import inspect
import logging
import os
import signal
import socket

from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTTv311


logger = logging.getLogger(__name__)


class SensorController:
    def __init__(self, config):
        self._loop = asyncio.get_event_loop()
        self.subscriptions = []
        self.handlers = []
        self.config = config
        self.host = socket.gethostname()
        self.cleanup_callbacks = set()

    async def connect(self):
        self.mqtt = MQTTClient(f"{socket.gethostname()}.{os.getpid()}")
        self.mqtt.set_auth_credentials(username=self.config["username"],
                                       password=self.config["password"])

        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_message = self.on_message
        self.mqtt.on_disconnect = self.on_disconnect

        self.stop_event = asyncio.Event()
        self._loop.add_signal_handler(signal.SIGINT, self.ask_exit)
        self._loop.add_signal_handler(signal.SIGTERM, self.ask_exit)
        self._loop.set_exception_handler(self.handle_exception)

        mqtt_host = self.config["mqtt_host"]
        mqtt_version = MQTTv311

        # Connect to the broker
        while not self.mqtt.is_connected:
            try:
                await self.mqtt.connect(mqtt_host, version=mqtt_version)
            except Exception as e:
                logger.warn(f"Error trying to connect: {e}. Retrying.")
                await asyncio.sleep(1)

    async def finish(self):
        # This will wait until the client is signalled
        logger.debug(f"Waiting for stop event")
        await self.stop_event.wait()
        logger.debug(f"Stop received, cleaning up")
        for cb in self.cleanup_callbacks:
            res = cb()
            if inspect.isawaitable(res):
                await res

        await self.mqtt.disconnect()  # Disconnect after any last messages sent
        logger.debug(f"client disconnected")

    def add_handler(self, handler):
        if handler not in self.handlers:
            self.handlers.append(handler)

    def add_cleanup_callback(self, handler):
        if handler not in self.cleanup_callbacks:
            self.cleanup_callbacks.add(handler)

    def on_message(self, client, topic, payload, qos, properties):
        for h in self.handlers:
            if h(topic, payload):
                return  # what if a message is interesting to many handlers?
        logger.warning(f"Just in case: Unhandled message {topic} = {payload}")

    def subscribe(self, topic):
        if topic not in self.subscriptions:
            self.subscriptions.append(topic)
            logger.debug(f"Subscribing to {topic}")
            self.mqtt.subscribe(topic)

    def on_connect(self, client, flags, rc, properties):
        for s in self.subscriptions:
            logger.debug(f"Re-subscribing to {s}")
            self.mqtt.subscribe(s)
        logger.debug('Connected and subscribed')

    def on_disconnect(self, client, packet, exc=None):
        logger.debug('Disconnected')

    def publish(self, topic, payload, retain=True):
        logger.debug(f"Publishing {topic} = {payload}")
        self.mqtt.publish(topic, payload, qos=2, retain=True)

    def ask_exit(self):
        logger.warning("Client received signal asking to exit")
        self.stop_event.set()

    def handle_exception(loop, context):
        # context["message"] will always be there; but context["exception"] may not
        msg = context.get("exception", context["message"])
        logger.error(f"Caught exception: {msg}", exc_info=True)
        
