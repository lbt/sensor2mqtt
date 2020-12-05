import asyncio
import socket
import logging
from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTTv311
from gpiozero import MotionSensor

import logging
logger = logging.getLogger(__name__)

class PIR:
    def __init__(self, mqtt, pin, quiet=10):
        self.mqtt = mqtt
        self.quiet = quiet
        host = socket.gethostname()
        self.m_chan = f"sensor/pir/{host}/{pin}"
        logger.info(f"Setting PIR on pin {pin}: {self.m_chan}")
        self.pir = MotionSensor(pin=pin, pull_up=True)
        self.pir.when_motion = self.motion
        self.pir.when_no_motion = self.no_motion
        self.loop = asyncio.get_running_loop()
        self.no_motion()

    def motion(self):
        self.loop.call_soon_threadsafe(self.mqtt.publish,
                                       self.m_chan, True)

    def no_motion(self):
        self.loop.call_soon_threadsafe(self.mqtt.publish,
                                       self.m_chan, False)
