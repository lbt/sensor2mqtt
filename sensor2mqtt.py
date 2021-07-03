#!/usr/bin/env python3
import asyncio
import logging

from sensor2mqtt import SensorController

logger = logging.getLogger(__name__)

import toml
config = toml.load("/home/pi/mqtt_sensor.toml")
if "debug" in config and config["debug"]:
    lvl = logging.DEBUG
else:
    lvl = logging.INFO
modules = ["__main__",
           "gmqtt",
           "baker",
           "sensor2mqtt.SensorController",
           "sensor2mqtt.DS18B20s",
           "sensor2mqtt.Heating",
           "sensor2mqtt.PIR",
           "sensor2mqtt.PondSkimmer",
           "sensor2mqtt.Relays",
           "sensor2mqtt.Switches"]

ch = logging.StreamHandler()
ch.setLevel(lvl)
ch.setFormatter(logging.Formatter("%(name)s : %(message)s"))
for l in modules:
    logging.getLogger(l).addHandler(ch)
    logging.getLogger(l).setLevel(lvl)
logger.debug(f"Config file loaded:\n{config}")


async def main():
    sensor_controller = SensorController(config)
    await sensor_controller.connect()

    # Gather all our objects into collections so they persist for
    # the duration of the scope

    try:
        persistent_objects = set()
        if "ds18b20-pins" in config:
            from sensor2mqtt.DS18B20s import DS18B20s
            persistent_objects.add(
                DS18B20s(sensor_controller, pins=config["ds18b20-pins"]))

        if "pir-pins" in config:
            from sensor2mqtt.PIR import PIR
            for pin in config["pir-pins"]:
                logger.warning(f"Found PIR at pin {pin}")
                persistent_objects.add(
                    PIR(sensor_controller, pin=pin))

        if "relay-pins" in config:
            from sensor2mqtt.Relays import Relays
            persistent_objects.add(
                Relays(sensor_controller, config["relay-pins"]))

        if "relay-inverted-pins" in config:
            from sensor2mqtt.Relays import Relays
            persistent_objects.add(
                Relays(sensor_controller, config["relay-inverted-pins"], True))

        if "switch-pins" in config:
            from sensor2mqtt.Switches import Switches
            persistent_objects.add(
                Switches(sensor_controller, config["switch-pins"]))

        if "heating" in config:
            import os
            import django
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heating.settings')
            django.setup()
            from sensor2mqtt.Heating import HeatingRelayManager
            heating = HeatingRelayManager(sensor_controller, config["heating"])
            await heating.init()
            persistent_objects.add(heating)

        if "skimmer" in config:
            from sensor2mqtt.PondSkimmer import PondSkimmer
            persistent_objects.add(PondSkimmer(
                sensor_controller, config["skimmer"]))

    except Exception as e:
        logger.warning(f"Exception {e} whilst setting up")

    await sensor_controller.finish()
    logger.warning(f"All done. Exiting")


asyncio.run(main())
