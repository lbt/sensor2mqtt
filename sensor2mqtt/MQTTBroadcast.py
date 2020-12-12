import sys
import os
import asyncio
import signal
import logging
import socket
        
from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTTv311

from DS18B20s import DS18B20s
from PIR import PIR
from Relays import Relays
logger = logging.getLogger(__name__)


class SensorController:
    def __init__(self):
        self.subscriptions = []
        self.handlers = []

    async def run(self):
        self.mqtt = MQTTClient(f"{socket.gethostname()}.{os.getpid()}")
        self.mqtt.set_auth_credentials(username=config["username"],
                                  password=config["password"])

        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_message = self.on_message
        self.mqtt.on_disconnect = self.on_disconnect

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, self.ask_exit, stop_event)
        loop.add_signal_handler(signal.SIGTERM, self.ask_exit, stop_event)

        mqtt_host = config["mqtt_host"]
        mqtt_version = MQTTv311

        # Connect to the broker
        await self.mqtt.connect(mqtt_host, version=mqtt_version)

        # Setup our sensors
        if "ds18b20-pins" in config:
            probes = DS18B20s(self.mqtt, pins=config["ds18b20-pins"])
        else:
            probes = None

        if "pir-pins" in config:
            pirs = set()
            for pin in config["pir-pins"]:
                logger.debug(f"Found PIR at pin {pin}")
                pirs.add(PIR(self.mqtt, pin=pin))
        else:
            pirs = None                

        if "relay-pins" in config:
            relays = Relays(self, config["relay-pins"])

        await stop_event.wait()    # This will wait until the client is signalled
        if probes:
            await probes.stop()     # Tells the probe to stop periodics
        # pirs don't need any async waiting.
        await self.mqtt.disconnect()  # Disconnect after any last messages sent

    def add_handler(self, handler):
        if not handler in self.handlers:
            self.handlers.append(handler)

    def on_message(self, client, topic, payload, qos, properties):
        for h in self.handlers:
            if h(topic, payload):
                return
        logger.warn(f"Unhandled message {topic} = {payload}")

    def subscribe(self, topic):
        if not topic in self.subscriptions:
            self.subscriptions.append(topic)
            logger.debug(f"Subscribing to {topic}")
            self.mqtt.subscribe(topic)

    def on_connect(self, client, flags, rc, properties):
        for s in self.subscriptions:
            logger.debug(f"Re-subscribing to {topic}")
            self.mqtt.subscribe(s)
        logger.debug('Connected and subscribed')

    def on_disconnect(self, client, packet, exc=None):
        logger.debug('Disconnected')

    def publish(self, topic, payload):
        logger.debug(f"Publishing {topic} = {payload}")
        self.mqtt.publish(topic, payload, qos=2)

    def ask_exit(self, stop_event):
        logger.warning("Client received signal and exiting")
        stop_event.set()


if __name__ == "__main__":
    import toml
    config = toml.load("/home/pi/mqtt_sensor.toml")
    if "debug" in config and config["debug"]:
        lvl = logging.DEBUG
        logger.debug(f"Config file loaded:\n{config}")
        modules = ("__main__", "PIR", "DS18B20s")  #, "gmqtt")
    else:
        modules = ("__main__", "PIR", "DS18B20s")
        lvl = logging.INFO

    ch = logging.StreamHandler()
    ch.setLevel(lvl)
    for l in modules:
        logging.getLogger(l).addHandler(ch)
        logging.getLogger(l).setLevel(lvl)

    sensors = SensorController()
    asyncio.run(sensors.run())
