import asyncio
from gpiozero import MotionSensor
import functools

import logging
logger = logging.getLogger(__name__)

class PIR:
    def __init__(self, controller, pin, quiet=10):
        self.controller = controller
        self.quiet = quiet
        self.m_topic = f"sensor/pir/{controller.host}/{pin}"
        logger.info(f"Setting PIR on pin {pin}: {self.m_topic}")
        self.pir = MotionSensor(pin=pin)
        self.pir.when_motion = self.motion
        self.pir.when_no_motion = self.no_motion
        self.loop = asyncio.get_running_loop()
        self.no_motion()

    def motion(self):
        logger.debug(f"motion on pin {self.m_topic}")
        self.loop.call_soon_threadsafe(functools.partial(
            self.controller.publish,
            self.m_topic, True, retain=False))

    def no_motion(self):
        logger.debug(f"no motion on pin {self.m_topic}")
        self.loop.call_soon_threadsafe(functools.partial(
            self.controller.publish,
            self.m_topic, False, retain=False))
