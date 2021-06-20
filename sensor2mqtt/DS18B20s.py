import asyncio
import os
import logging

from gpiozero import InputDevice
logger = logging.getLogger(__name__)


class DS18B20s:
    def __init__(self, controller, pins, period=30):
        self.controller = controller
        self.period = period
        self.pullups = set()
        for p in pins:
            logger.debug(f"Setting pullup for pin {p}")
            self.pullups.add(InputDevice(pin=p, pull_up=True))
        self._task = asyncio.create_task(self.run())
        controller.add_cleanup_callback(self.stop)

    async def run(self):
        # Maybe persist this so we don't have 'New' probes each run
        probes = dict()
        try:
            while True:
                # Make a list of probes we've not seen by starting
                # with all of them and removing probes from this set
                # when we see them
                notseen_probes = set(probes.keys())
                async for (serial, temp) in self.get_temp():

                    # We've seen the probe - even if it's failed to
                    # read and discard doesn't care if it's new
                    notseen_probes.discard(serial)

                    if temp is None:
                        logger.warning(f"probe {serial} failed to read")
                        self.controller.publish(
                            f'alert/w1/temperature/{serial}',
                            "Failed to read temperature",
                            retain=False)
                        continue

                    if serial not in probes:
                        logger.info(f"New probe seen at {serial}")
                        self.controller.publish(
                            f'info/w1/temperature/{serial}',
                            "New", retain=False)
                        probes[serial] = None  # No old temp

                    # Publish anything we find as a float
                    if probes[serial] != temp:
                        self.controller.publish(
                            f'sensor/w1/temperature/{serial}',
                            float(temp) / float(1000.0))
                    else:
                        logger.debug(f"Probe {serial} unchanged at {temp}")

                    # Store the temp as the old temp
                    probes[serial] = temp

                # After iterating over all probes warn about any that have gone
                for serial in notseen_probes:
                    logger.warning(f"probe {serial} gone away")
                    self.controller.publish(f'alert/w1/temperature/{serial}',
                                            "Gone away", retain=False)

                    del probes[serial]

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
                    path = f"{w1_path}/{probe_file.name}/w1_slave"
                    with open(path, "r") as f:
                        await asyncio.sleep(1)
                        data = f.read()
                    if "YES" in data:
                        (discard, sep, reading) = data.partition(' t=')
                        yield (probe_file.name, reading.rstrip())
                    else:
                        yield (probe_file.name, None)
                except Exception as e:
                    logger.warning(f"Exception '{e}' thrown "
                                   f"reading {path}")
                    yield (probe_file.name, None)


