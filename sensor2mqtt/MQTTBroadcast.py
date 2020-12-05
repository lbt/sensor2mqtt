import sys
import os
import asyncio
import signal
import logging
from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTTv311

from DS18B20s import DS18B20s
from PIR import PIR
logger = logging.getLogger(__name__)


def on_connect(client, flags, rc, properties):
    logger.debug('Connected')


def on_disconnect(client, packet, exc=None):
    logger.debug('Disconnected')


def ask_exit(stop_event):
    logger.warning("Client received signal and exiting")
    stop_event.set()


async def main():
    import socket

    mqtt = MQTTClient(f"{socket.gethostname()}.{os.getpid()}")
    mqtt.set_auth_credentials(username=config["username"],
                              password=config["password"])

    mqtt.on_connect = on_connect
    mqtt.on_disconnect = on_disconnect

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, ask_exit, stop_event)
    loop.add_signal_handler(signal.SIGTERM, ask_exit, stop_event)
    
    mqtt_host = config["mqtt_host"]
    mqtt_version = MQTTv311

    # Connect to the broker
    await mqtt.connect(mqtt_host, version=mqtt_version)

    # Setup our sensors
    if "ds18b20-pins" in config:
        probes = DS18B20s(mqtt, pins=config["ds18b20-pins"])

    if "pir-pins" in config:
        pirs = set()
        for pin in config["pir-pins"]:
            logger.debug(f"Found PIR at pin {pin}")
            pirs.add(PIR(mqtt, pin=pin))

    await stop_event.wait()    # This will wait until the client is signalled
    if probes:
        await probes.stop()     # Tells the probe to stop periodics
    # pirs don't need any async waiting.
    await mqtt.disconnect()  # Disconnect after any last messages sent

if __name__ == "__main__":
    import toml
    config = toml.load("/home/pi/mqtt_sensor.toml")
    if "debug" in config and config["debug"]:
        lvl = logging.DEBUG
        logger.debug(f"Config file loaded:\n{config}")
        modules = ("__main__", "PIR", "DS18B20s", "gmqtt")
    else:
        modules = ("__main__", "PIR", "DS18B20s")
        lvl = logging.INFO

    ch = logging.StreamHandler()
    ch.setLevel(lvl)
    for l in modules:
        logging.getLogger(l).addHandler(ch)
        logging.getLogger(l).setLevel(lvl)


    asyncio.run(main())
