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
        self.m_topic = f"sensor/pir/{host}/{pin}"
        logger.info(f"Setting PIR on pin {pin}: {self.m_topic}")
        self.pir = MotionSensor(pin=pin)
        self.pir.when_motion = self.motion
        self.pir.when_no_motion = self.no_motion
        self.loop = asyncio.get_running_loop()
        self.no_motion()

    def motion(self):
        logger.debug(f"motion on pin {self.m_topic}")
        self.loop.call_soon_threadsafe(self.mqtt.publish,
                                       self.m_topic, True)

    def no_motion(self):
        logger.debug(f"no motion on pin {self.m_topic}")
        self.loop.call_soon_threadsafe(self.mqtt.publish,
                                       self.m_topic, False)
