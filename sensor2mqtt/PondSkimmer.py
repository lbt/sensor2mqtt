import logging
import asyncio

logger = logging.getLogger(__name__)


class PondSkimmer:
    """A PondSkimmer is a sensor2mqtt proxy for a relay on the skimmer.
    It's a normal relay but it adds a timer function
    """
    def __init__(self, controller, skimmer_relay):
        self.controller = controller
        self.controls = "Skimmer"

        self.control_topic = f"named/control/pond/{self.controls}"
        self.relay_control_topic = f"named/control/relay/{skimmer_relay}"

        # An asyncio.TimerHandle
        self.callback = None

        self.controller.subscribe(self.control_topic)
        self.controller.add_handler(self.handle_message)
        self.controller.add_cleanup_callback(self.stop)
        logger.debug(f"Set up skimmer")

    def stop(self):
        if self.callback:
            self.callback.cancel()
        logger.debug(f"Callback cancelled. Exiting")

    def handle_message(self, topic, payload):
        '''Handle the control message to feed the fish'''
        if topic == self.control_topic:
            val = (payload.decode("utf-8") == "True")
            logger.debug(f"Skimmer {val}")
            if self.callback:
                self.callback.cancel()
            if val:
                # Activating the relay turns the pump off as it's NC
                self.controller.publish(self.relay_control_topic, True)
                self.callback = asyncio.get_running_loop().call_later(
                    3600, self.turn_on)
            else:
                self.turn_on()
            return True
        return False

    def turn_on(self):
        logger.debug(f"Skimmer back on")
        self.controller.publish(self.relay_control_topic, False)

    def __repr__(self):
        return f"PondSkimmer"
