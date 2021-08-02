import logging
from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTTv311
from gpiozero import DigitalOutputDevice

logger = logging.getLogger(__name__)


class Relay:
    def __init__(self, host, pin, inverted):
        self.topic = f"sensor/gpiod/relay/{host}/{pin}"
        self.dod = DigitalOutputDevice(pin=pin, active_high=not inverted,
                                       initial_value=False)


class Relays:
    def __init__(self, controller, pins=None, inverted_pins=None):
        self.controller = controller
        host = controller.host
        self.relays = {}
        if pins:
            for p in pins:
                logger.warning(f"Making Relay for pin {p}")
                # use a string key so we compare to topic string
                r = Relay(host, p, False)
                self.relays[str(p)] = r
                self.controller.publish(r.topic, bool(r.dod.value))
        if inverted_pins:
            for p in inverted_pins:
                logger.warning(f"Making Relay for pin {p}")
                # use a string key so we compare to topic string
                r = Relay(host, p, True)
                self.relays[str(p)] = r
                self.controller.publish(r.topic, bool(r.dod.value))
        controller.subscribe(f"control/relay/{host}/#")
        controller.add_handler(self.handle_message)

    def handle_message(self, topic, payload):
        # control/relay/<host>/<pin>
        if not topic.startswith("control/relay"):
            return False
        topics = topic.split("/")[2:]
        pin = topics[1]
        if pin in self.relays:
            r = self.relays[pin]
            val = (payload.decode("utf-8") == "True")
            logger.debug(f"Setting relay pin {pin} to {val}")
            r.dod.value = val
            self.controller.publish(r.topic, bool(r.dod.value))
        else:
            logger.warn(f"Attempt to control unknown relay on pin {pin}")
        return True
