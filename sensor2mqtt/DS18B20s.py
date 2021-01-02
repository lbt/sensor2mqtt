import asyncio
import os
import logging

from gpiozero import InputDevice
logger = logging.getLogger(__name__)


class DS18B20s:
    def __init__(self, mqtt, pins, period=10):
        self.mqtt = mqtt
        self.period = period
        self._task = asyncio.create_task(self.run())
        self.pullups = set()
        for p in pins:
            logger.debug(f"Setting pullup for pin {p}")
            self.pullups.add(InputDevice(pin=p, pull_up=True))

    async def run(self):
        # Maybe persist this so we don't have 'New' probes each run
        probes = set()
        try:
            while True:
                notseen_probes = probes.copy()
                async for (serial, temp) in self.get_temp():
                    if serial not in probes:
                        logger.info(f"New probe seen at {serial}")
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
                        logger.warning(f"probe {serial} failed to read")
                        self.mqtt.publish(f'alert/w1/temperature/{serial}',
                                          "Failed to read temperature",
                                          qos=2)

                # After iterating over all probes warn about any that have gone
                for serial in notseen_probes:
                    logger.warning(f"probe {serial} gone away")
                    self.mqtt.publish(f'alert/w1/temperature/{serial}',
                                      "Gone away", qos=2)
                probes = probes - notseen_probes

                await asyncio.sleep(self.period)

        except asyncio.CancelledError:  # This will be raised politely in await
            logger.debug("DS18B20s exiting cleanly")

    async def stop(self):
        self._task.cancel()
        await self._task

    async def get_temp(self):
        w1_path = "/sys/bus/w1/devices"
        with os.scandir(w1_path) as devices:
            for probe_file in devices:
                if not probe_file.name.startswith("28"):
                    continue
                try:
                    # Hopefully the conversion is triggered on open
                    # and async.sleeping for a second will avoid blocking
                    # in the read()
                    with open(f"{w1_path}/{probe_file.name}/w1_slave",
                              "r") as f:
                        await asyncio.sleep(1)
                        data = f.read()
                    if "YES" in data:
                        (discard, sep, reading) = data.partition(' t=')
                        yield (probe_file.name, float(reading) / float(1000.0))
                    else:
                        yield (probe_file.name, None)
                except Exception as e:
                    logger.warning(f"Exception {e} thrown "
                                   f"reading {probe_file.name}")
                    yield (probe_file.name, None)


