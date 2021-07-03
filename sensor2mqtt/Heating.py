import logging
from django.apps import apps
from asgiref.sync import sync_to_async
from baker.models import ZoneControl
from baker.mqtt import DjangoMQTTPublish
logger = logging.getLogger(__name__)


class ZoneValveRelay:
    """A ZoneValve is a sensor2mqtt proxy for a relay on a zone valve.
    The interface it provides should be used to control that relay as
    it is also connected to the heating relay. This ensures the
    heating is only on when at least one zone valve is open.

    """
    def __init__(self, mgr, zone):
        self.mgr = mgr
        self.controls = zone.controls
        # control_topic is what we respond to (unused; there's a wildcard)
        self.control_topic = f"named/control/heating/zone/{zone.controls}"
        # announce_topic is what we announce our state on (after
        # confirmation by switch)
        self.announce_topic = f"named/sensor/heating/zone/{zone.controls}"
        # heating_topic is used to control the heating relay (via the
        # mgr)
        self.heating_topic = f"named/control/relay/{zone.heating_relay.controls}"

        # If we don't have a valve relay then fake it
        if zone.valve_relay is None:
            self.has_valve_relay = False
            self.valve_topic = ""
        else:
            self.has_valve_relay = True
            # valve_topic is used to control our valve
            self.valve_topic = f"named/control/relay/{zone.valve_relay.controls}"

        # If we have a switch then subscribe to the switch_topic to
        # hear when we're active
        if zone.valve_switch is None:
            self.has_valve_switch = False
            self.switch_topic = ""
        else:
            if not self.has_valve_relay:
                raise Exception("Can't have a valve switch without a relay")
            self.has_valve_switch = False
            self.switch_topic = ("named/sensor/switch"
                                 f"/{zone.valve_switch.operatedby}")
        self.state = None
        self.setState(False)  # Force a publish

    def setState(self, v):
        '''Ask the valve relay to change if needed.
        If we have no switch then fake a response as if it worked
        returns True if it changes state
        '''
        old = self.state
        if v == old:
            return False
        self.state = v
        if self.has_valve_relay:
            self.mgr.controller.publish(self.valve_topic, v)
        if not self.has_valve_switch:
            self.switchChanged(v)  # Fake a switch responding
        return True

    def switchChanged(self, v):
        ''' When the zone switch turns on/off, ask the heating to turn
        on/off and announce our state finally changing
        '''
        if v != self.state:
            logger.critical("Switch changed state and doesn't agree with"
                            " internal state")
        self.mgr.setHeatingFor(self, v)
        self.mgr.controller.publish(self.announce_topic, v)

    def __repr__(self):
        return f"ZoneValveRelay({self.controls})"


class ZoneOccupancy:
    """This is where Zone occupancy lives. It doesn't persist.
    """
    def __init__(self, mgr, zone):
        self.control_topic = f"named/control/occupancy/zone/{zone.controls}"
        self.announce_topic = f"named/sensor/occupancy/zone/{zone.controls}"
        self.state = ZoneControl.Occupied.MAYBE
        self.until = None
        self.mgr = mgr

    def occupiedUntil(self, v, until):
        old = self.state
        if v == old:
            return False
        else:
            self.state = v
            self.mgr.setFor(self, v)
            self.mgr.controller.publish(self.announce_topic, v)
            return True

    @property
    def occupied(self):
        return self.state


class HeatingRelayManager:
    """This is a logical interface to the heating system and zonevalve
    relays.  It notes who wants the heating on and keeps it on as long
    as someone wants it.

    It actually turns the heating on when the Switch for the valve (if
    present) says it is open.

    It has multiple zones and listens for and sends mqtt messages
    about them. Each zone owns a zone relay and provides a virtual
    occupancy sensor.

    """
    def __init__(self, controller, config):
        self.controller = controller
        self.heating_users = {}  # keyed on a heating topic
        self.zones_by_controls = {}
        self.zones_by_switches = {}
        controller.add_cleanup_callback(self.stop)

    async def init(self):
        zones = await sync_to_async(list)(
            ZoneControl.objects.all().select_related("heating_relay",
                                                     "valve_relay",
                                                     "valve_switch"))
        for zone in zones:
            logger.warning(f"Making Zone {zone}")
            zv = ZoneValveRelay(self, zone)
            # Lookup zv by control message key
            self.zones_by_controls[zone.controls] = zv
            # Lookup zv by switch message key if it has one
            if zone.valve_switch is not None:
                self.zones_by_switches[zone.valve_switch.operatedby] = zv
                self.controller.subscribe(zv.switch_topic)
        self.controller.subscribe(f"named/control/heating/zone/#")
        self.controller.add_handler(self.handle_message)

    def stop(self):
        logger.debug(f"Heating. Stopping django publisher thread")
        pub = DjangoMQTTPublish.getPublisherThread()
        pub.ask_exit()
        pub.join()

    def setHeatingFor(self, user, v):
        heating = user.heating_topic
        if heating not in self.heating_users:
            users = set()
            self.heating_users[heating] = users
        else:
            users = self.heating_users[heating]
        logger.debug(f"Heating users pre  {users}")
        if v:
            users.add(user)
            self.set_heating(heating, True)
        else:
            users.discard(user)
            if len(users) == 0:
                self.set_heating(heating, False)
        logger.debug(f"Heating users post {users}")

    def set_heating(self, heating_topic, v):
        self.controller.publish(heating_topic, v)

    def handle_message(self, topic, payload):
        '''Handle the control message to turn a zone on/off
        or to set occupancy for a zone.
        Listen for sensor messages from our switches
        '''
        topics = topic.split("/")
        if topics[0] != "named":
            return False
        if topics[2:4] == ["heating", "zone"]:
            return self.handle_zone(topics, payload)
        if topics[2] == "switch":
            return self.handle_switch(topics, payload)

    def handle_zone(self, topics, payload):
        kind = topics[1]  # We should handle alerts one day
        controls = topics[4]
        if kind != "control":
            logger.critical(f"Unhandled {kind} message for zone {controls}")
            return True
        if controls not in self.zones_by_controls:
            logger.warn(f"Attempt to control unknown zone: {controls}")
            return False
        zv = self.zones_by_controls[controls]
        val = (payload.decode("utf-8") == "True")
        logger.debug(f"Setting zone {controls} to {val}")
        zv.setState(val)
        return True

    def handle_switch(self, topics, payload):
        kind = topics[1]  # We could handle alerts somehow?? disable the zone?
        operatedby = topics[3]
        if operatedby not in self.zones_by_switches:
            return False  # Some switches we're just not interested in
        zv = self.zones_by_switches[operatedby]
        val = (payload.decode("utf-8") == "True")
        logger.debug(f"Zone switch for {operatedby} changed")
        zv.switchChanged(val)
        return True
