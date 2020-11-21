try:
    import sys
    import asyncio
    import os
    import signal
    import socket
    import toml
    from logging import warning, debug
    import logging
    from gmqtt import Client as MQTTClient
    from gmqtt.mqtt.constants import MQTTv311

    from gpiozero import InputDevice
except ModuleNotFoundError as e:
    print(f"{e}\nHave you run\n. ~/venv-mqtt/bin/activate")
    sys.exit(1)


class TemperatureProbe:
    def __init__(self, mqtt, pins, period=10):
        self.mqtt = mqtt
        self.period = period
        self._task = asyncio.create_task(self.run())
        self.pullups = set()
        for p in pins:
            debug(f"Setting pullup for pin {p}")
            self.pullups.add(InputDevice(pin=p, pull_up=True))

    async def run(self):
        # Maybe persist this so we don't have 'New' probes each run
        probes = set()
        try:
            while True:
                notseen_probes = probes.copy()
                for (serial, temp) in self.get_temp():
                    if serial not in probes:
                        debug(f"New probe seen at {serial}")
                        self.mqtt.publish(f'info/w1/temperature/{serial}',
                                          "New", qos=2)
                        probes.add(serial)
                    else:
                        notseen_probes.discard(serial)

                    # Publish anything we find
                    if temp:
                        self.mqtt.publish(f'sensor/w1/temperature/{serial}',
                                          temp, qos=2)
                    else:
                        self.mqtt.publish(f'alert/w1/temperature/{serial}',
                                          "Failed to read temperature",
                                          qos=2)

                # After iterating over all probes warn about any that have gone
                for serial in notseen_probes:
                    debug(f"probe {serial} gone away")
                    self.mqtt.publish(f'alert/w1/temperature/{serial}',
                                      "Gone away", qos=2)
                probes = probes - notseen_probes
                
                await asyncio.sleep(self.period)

        except asyncio.CancelledError:  # This will be raised politely in await
            warning("TemperatureProbe exiting cleanly")

    async def stop(self):
        self._task.cancel()
        await self._task

    def get_temp(self):
        w1_path = "/sys/bus/w1/devices"
        with os.scandir(w1_path) as devices:
            for probe_file in devices:
                if not probe_file.name.startswith("28"):
                    continue
                try:
                    with open(f"{w1_path}/{probe_file.name}/w1_slave", "r") as f:
                        data = f.read()
                    if "YES" in data:
                        (discard, sep, reading) = data.partition(' t=')
                        yield (probe_file.name, float(reading) / float(1000.0))
                    else:
                        yield (probe_file.name, None)
                except Exception as e:
                    warning(f"Exception {e} thrown "
                            "reading {probe_file.name}")
                    yield (probe_file.name, None)


class MyClient:
    def __init__(self, id, mqtt_host,
                 username, password,
                 mqtt_version=MQTTv311):
        self.mqtt = MQTTClient(id)
        self.mqtt.set_auth_credentials(username, password)
        self.mqtt_host = mqtt_host
        self.mqtt_version = mqtt_version
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_disconnect = self.on_disconnect
        self.stop_event = asyncio.Event()
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self.ask_exit)
        loop.add_signal_handler(signal.SIGTERM, self.ask_exit)

    async def connect(self):
        await self.mqtt.connect(self.mqtt_host, version=self.mqtt_version)

    async def disconnect(self):
        await self.mqtt.disconnect()

    def on_connect(self, client, flags, rc, properties):
        debug('Connected')

    def on_disconnect(self, client, packet, exc=None):
        debug('Disconnected')

    def ask_exit(self, *args):
        warning("Client received signal and exiting")
        self.stop_event.set()

    async def until_done(self):
        await self.stop_event.wait()


async def main():
    config = toml.load("/home/pi/mqtt_sensor.toml")
    if config["debug"]:
        logging.basicConfig(level=logging.DEBUG)
    debug(f"Config file loaded:\n{config}")

    client = MyClient(id=socket.gethostname(),
                      mqtt_host=config["mqtt_host"],
                      username=config["username"],
                      password=config["password"],
                      mqtt_version=MQTTv311)
    await client.connect()
    probe = TemperatureProbe(client.mqtt, pins=config["ds18b20-pins"])

    await client.until_done()  # This will wait until the client is signalled
    await probe.stop()         # Tells the probe to stop
    await client.disconnect()  # Disconnect after any last messages sent

if __name__ == "__main__":
    asyncio.run(main())
