import asyncio
import inspect
import logging
import os
import signal
import socket

from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTTv311


LOGGER = logging.getLogger(__name__)


class MQController:
    """An instance of this class is created and passed to objects
    needing to interact with MQTT.

    Essentially it abstracts all the setup, msg handling and cleanup
    into one place.
    """
    def __init__(self, config):
        self._loop = asyncio.get_event_loop()
        self.subscriptions = []
        self.handlers = []
        self.config = config
        self.host = socket.gethostname()
        self.cleanup_callbacks = set()
        self.stop_event = asyncio.Event()
        self.mqtt = None

    async def connect(self):
        self.mqtt = MQTTClient(f"{socket.gethostname()}.{os.getpid()}")
        self.mqtt.set_auth_credentials(username=self.config["username"],
                                       password=self.config["password"])

        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_message = self.on_message
        self.mqtt.on_disconnect = self.on_disconnect

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
                LOGGER.warn(f"Error trying to connect: {e}. Retrying.")
                await asyncio.sleep(1)

    async def setup(self):
        # Override to do any setup
        pass

    async def run(self):
        """This connects to the mqtt (retrying forever) and waits until
        :func:`ask_exit` is called at which point it exits cleanly.
        """
        await self.connect()

        try:
            await self.setup()
        except Exception as e:
            logger.warning(f"Exception {e} thrown "
                           f"creating {self.__class__}",
                           exc_info=True)

        await self.finish()  # This will wait until the client is signalled

    async def finish(self):
        # This will wait until the client is signalled
        LOGGER.debug(f"Waiting for stop event")
        await self.stop_event.wait()
        LOGGER.debug(f"Stop received, cleaning up")
        for cb in self.cleanup_callbacks:
            res = cb()
            if inspect.isawaitable(res):
                await res

        await self.mqtt.disconnect()  # Disconnect after any last messages sent
        LOGGER.debug(f"client disconnected")

    def add_handler(self, handler):
        '''A handler takes a topic/payload and returns true if it handles the
        topic
        '''
        if handler not in self.handlers:
            self.handlers.append(handler)

    def add_cleanup_callback(self, handler):
        if handler not in self.cleanup_callbacks:
            self.cleanup_callbacks.add(handler)

    async def on_message(self, _client, topic, payload, _qos, _properties):
        handled = False
        tasks = list()

        for h in self.handlers:
            LOGGER.debug(f"handler for {topic} : {h}")
            res = h(topic, payload)
            if inspect.isawaitable(res):
                # it's a async callback
                tasks.append(res)
            else:
                handled |= res

        res_list = await asyncio.gather(*tasks)
        for res in res_list:
            handled |= res
        if not handled:
            LOGGER.warning(f"FYI: Unhandled message {topic} = {payload}")

    def subscribe(self, topic):
        """Subscribes to an MQTT topic (passed directly to MQTT)"""
        if topic not in self.subscriptions:
            self.subscriptions.append(topic)
            if self.mqtt:
                LOGGER.debug(f"Subscribing to {topic}")
                self.mqtt.subscribe(topic)

    def on_connect(self, _client, _flags, _rc, _properties):
        for s in self.subscriptions:
            LOGGER.debug(f"Re-subscribing to {s}")
            self.mqtt.subscribe(s)
        LOGGER.debug('Connected and subscribed')

    def on_disconnect(self, _client, _packet, _exc=None):
        LOGGER.debug('Disconnected')

    def publish(self, topic, payload, retain=True):
        """Publish :param payload: to :param topic:"""
        LOGGER.debug(f"Publishing {topic} = {payload}")
        self.mqtt.publish(topic, payload, qos=2, retain=retain)

    def ask_exit(self):
        """Handle outstanding messages and cleanly disconnect"""
        LOGGER.warning(f"{self} received signal asking to exit")
        self.stop_event.set()

    def handle_exception(self, _loop, context):
        # context["message"] will always be there; but
        # context["exception"] may not
        import traceback
        msg = context.get("exception", context["message"])
        LOGGER.error(f"Caught exception: {msg}", exc_info=True)
        LOGGER.error(traceback.format_tb(msg.__traceback__))
