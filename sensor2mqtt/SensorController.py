import os
import asyncio
import signal
import logging
import socket

from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTTv311

from .DS18B20s import DS18B20s
from .PIR import PIR
from .Relays import Relays
from .Switches import Switches

logger = logging.getLogger(__name__)


class SensorController:
    def __init__(self, config):
        self.subscriptions = []
        self.handlers = []
        self.config = config

    async def run(self):
        self.mqtt = MQTTClient(f"{socket.gethostname()}.{os.getpid()}")
        self.mqtt.set_auth_credentials(username=self.config["username"],
                                       password=self.config["password"])

        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_message = self.on_message
        self.mqtt.on_disconnect = self.on_disconnect

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, self.ask_exit, stop_event)
        loop.add_signal_handler(signal.SIGTERM, self.ask_exit, stop_event)

        mqtt_host = self.config["mqtt_host"]
        mqtt_version = MQTTv311

        # Connect to the broker
        while not self.mqtt.is_connected:
            try:
                await self.mqtt.connect(mqtt_host, version=mqtt_version)
            except Exception as e:
                logger.warn(f"Error trying to connect: {e}. Retrying.")
                await asyncio.sleep(1)

        # Setup our sensors
        if "ds18b20-pins" in self.config:
            logger.warning(f"Found probe")
            probes = DS18B20s(self.mqtt, pins=self.config["ds18b20-pins"])
        else:
            probes = None

        if "pir-pins" in self.config:
            pirs = set()
            for pin in self.config["pir-pins"]:
                logger.warning(f"Found PIR at pin {pin}")
                pirs.add(PIR(self.mqtt, pin=pin))

        # Gather all our objects into collections so they persist for
        # the duration of the scope
        if "relay-pins" in self.config:
            relays = Relays(self, self.config["relay-pins"])

        if "relay-inverted-pins" in self.config:
            irelays = Relays(self, self.config["relay-inverted-pins"], True)

        if "switch-pins" in self.config:
            switches = Switches(self, self.config["switch-pins"])

        await stop_event.wait()    # This will wait until the client is signalled
        logger.debug(f"stop received")
        if probes:
            await probes.stop()     # Tells the probe to stop periodics
        # pirs don't need any async waiting.
        await self.mqtt.disconnect()  # Disconnect after any last messages sent
        logger.debug(f"client disconnected")

    def add_handler(self, handler):
        if handler not in self.handlers:
            self.handlers.append(handler)

    def on_message(self, client, topic, payload, qos, properties):
        for h in self.handlers:
            if h(topic, payload):
                return
        logger.warning(f"Unhandled message {topic} = {payload}")

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

    def publish(self, topic, payload):
        logger.debug(f"Publishing {topic} = {payload}")
        self.mqtt.publish(topic, payload, qos=2, retain=True)

    def ask_exit(self, stop_event):
        logger.warning("Client received signal and exiting")
        stop_event.set()
