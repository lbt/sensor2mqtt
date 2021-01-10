import asyncio
import logging
from gpiozero import DigitalInputDevice

import logging
logger = logging.getLogger(__name__)

class Switch:
    def __init__(self, host, pin, controller):
        self.topic = f"sensor/switch/{host}/{pin}"
        logger.info(f"Making Switch on pin {pin}: {self.topic}")
        self.controller = controller
        self.loop = asyncio.get_running_loop()
        self.did = DigitalInputDevice(pin=pin)
        self.did.when_activated = self.changed
        self.did.when_deactivated = self.changed
        self.changed()

    def changed(self):
        # Called from a gpiozero thread
        logger.debug(f"switch {self.topic} "
                     f"{'closed' if self.did.value else 'opened'}")
        self.loop.call_soon_threadsafe(self.controller.publish,
                                       self.topic, bool(self.did.value))


class Switches:
    def __init__(self, controller, pins):
        self.controller = controller
        host = controller.host
        self.switchs = {}
        for p in pins:
            logger.debug(f"Making Switch for pin {p}")
            # use a string key so we compare to topic string
            self.switchs[str(p)] = Switch(host, p, controller)
