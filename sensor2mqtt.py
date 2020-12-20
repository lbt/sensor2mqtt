#!/usr/bin/env python3
import asyncio
import logging

from sensor2mqtt import SensorController

logger = logging.getLogger(__name__)

import toml
config = toml.load("/home/pi/mqtt_sensor.toml")
if "debug" in config and config["debug"]:
    lvl = logging.DEBUG
    modules = ["__main__", "SensorController", "sensor2mqtt.Relays",
               "sensor2mqtt.PIR", "sensor2mqtt.DS18B20s",
               "sensor2mqtt.Switches"]  # , "gmqtt"]
else:
    modules = ["__main__", "SensorController", "sensor2mqtt.Relays",
               "sensor2mqtt.PIR", "sensor2mqtt.DS18B20s",
               "sensor2mqtt.Switches"]
    lvl = logging.INFO

ch = logging.StreamHandler()
ch.setLevel(lvl)
for l in modules:
    logging.getLogger(l).addHandler(ch)
    logging.getLogger(l).setLevel(lvl)
logger.debug(f"Config file loaded:\n{config}")

sensors = SensorController(config)
asyncio.run(sensors.run())
