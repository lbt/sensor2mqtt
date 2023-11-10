import asyncio
import os
import logging
import time

from smbus2 import SMBus

try:
    from typing import Optional, Tuple, Union
except ImportError:
    pass


logger = logging.getLogger(__name__)

class TSL2561Sensor:
    # *************************************************
    # ******* MACHINE VARIABLES (DO NOT TOUCH) ********
    # *************************************************
    VISIBLE = 2  # channel 0 - channel 1
    INFRARED = 1  # channel 1
    FULLSPECTRUM = 0  # channel 0

    ADDR = 0x29 # Can be 0x29 0x39 or something else
    #READBIT = 0x01
    COMMAND_BIT = 0x80
    CLEAR_BIT = 0x40  # Clears any pending interrupt (write 1 to clear)
    WORD_BIT = 0x20  # 1 = read/write word (rather than byte)
    BLOCK_BIT = 0x10  # 1 = using block read/write
    ENABLE_POWERON = 0x03
    ENABLE_POWEROFF = 0x00
    #ENABLE_AEN = 0x02
    #ENABLE_AIEN = 0x10
    #CONTROL_RESET = 0x80

    #LUX_DF = 408.0
    #LUX_COEFB = 1.64  # CH0 coefficient
    #LUX_COEFC = 0.59  # CH1 coefficient A
    #LUX_COEFD = 0.86  # CH2 coefficient B

    REGISTER_CONTROL = 0x00
    REGISTER_TIMING = 0x01
    REGISTER_THRESHHOLDL_LOW = 0x02
    REGISTER_THRESHHOLDL_HIGH = 0x03
    REGISTER_THRESHHOLDH_LOW = 0x04
    REGISTER_THRESHHOLDH_HIGH = 0x05
    REGISTER_INTERRUPT = 0x06
    REGISTER_ID = 0x0A
    REGISTER_CHAN0_LOW = 0x0C
    REGISTER_CHAN0_HIGH = 0x0D
    REGISTER_CHAN1_LOW = 0x0E
    REGISTER_CHAN1_HIGH = 0x0F
    # *****************************************
    # ******* END OF MACHINE VARIABLES ********
    # *****************************************

    # Integration time
    # The integration time can be set between 14 and 400ms,
    # and the longer the integration time the more light the
    # sensor is able to integrate, making it more sensitive in
    # low light
    INTEGRATIONTIME_14MS = 0x00 # shortest integration time (bright light)
    INTEGRATIONTIME_100MS = 0x01
    INTEGRATIONTIME_400MS = 0x02
    INTEGRATION_TIME_VALUE = {
        INTEGRATIONTIME_14MS: 14.,
        INTEGRATIONTIME_100MS: 100.,
        INTEGRATIONTIME_400MS: 400.,
    }
    MAX_INTEGRATION_TIME_VALUE = 400.

    # Gain
    # The gain can be set to one of the following values
    # (though the last value, MAX, has limited use in the
    # real world given the extreme amount of gain applied):
    # GAIN_LOW: Sets the gain to 1x (bright light)
    # GAIN_HIGH: Sets the gain to 16x (low light)
    GAIN_LOW = 0x00
    GAIN_HIGH = 0x10
    GAIN_VALUE = {
        GAIN_LOW: 1,
        GAIN_HIGH: 16,
    }
    MAX_GAIN = 16


    def __init__(
            self,
            i2c_bus=1,
            sensor_address=ADDR,
            integration=INTEGRATIONTIME_100MS,
            gain=GAIN_LOW
    ):
        self.bus = SMBus(i2c_bus)
        self.sensor_address = sensor_address
        self.integration_time = integration
        self.gain = gain
        self.set_timing(self.integration_time)
        self.set_gain(self.gain)
        self.disable()  # to be sure

    def enable(self):
        self.bus.write_byte_data(
            self.sensor_address,
            self.COMMAND_BIT | self.REGISTER_CONTROL,
            self.ENABLE_POWERON
        )

    def disable(self):
        self.bus.write_byte_data(
            self.sensor_address,
            self.COMMAND_BIT | self.REGISTER_CONTROL,
            self.ENABLE_POWEROFF
        )

    @property
    def chip_id(self) -> Tuple[int, int]:
        """A tuple containing the part number and the revision number."""
        self.enable()
        chip_id = self.bus.read_word_data(self.sensor_address,
                                          self.COMMAND_BIT | self.REGISTER_ID)
        partno = (chip_id >> 4) & 0x0F
        revno = chip_id & 0x0F
        return (partno, revno)

    def set_timing(self, integration):
        self.enable()
        self.integration_time = integration
        self.bus.write_byte_data(
            self.sensor_address,
            self.COMMAND_BIT | self.REGISTER_TIMING,
            self.integration_time | self.gain
        )
        self.disable()

    def get_timing(self):
        return self.INTEGRATION_TIME_VALUE.get(
            self.integration_time,
            self.MAX_INTEGRATION_TIME_VALUE)

    def set_gain(self, gain):
        self.enable()
        self.gain = gain
        self.bus.write_byte_data(
            self.sensor_address,
            self.COMMAND_BIT | self.REGISTER_CONTROL,
            self.integration_time | self.gain
        )
        self.disable()

    def get_gain(self):
        return self.GAIN_VALUE.get(self.gain, 1)

    # The luminosity data needs to be scaled to take into account
    # internal gain and exposure time
    def get_scale(self):
        return ((self.MAX_INTEGRATION_TIME_VALUE/self.get_timing()) *
                (self.MAX_GAIN / self.get_gain()))

    def _get_luminosity_data(self):
        # get the data and scale it
        full = self.bus.read_word_data(
            self.sensor_address, self.COMMAND_BIT | self.REGISTER_CHAN0_LOW
        ) * self.get_scale()
        ir = self.bus.read_word_data(
            self.sensor_address, self.COMMAND_BIT | self.REGISTER_CHAN1_LOW
        ) * self.get_scale()
        return full, ir

    def get_luminosity_data(self):
        self.enable()
        # Wait X ms for ADC to complete with 10ms of slack
        time.sleep(0.001*self.get_timing() + 0.01)
        full, ir = self._get_luminosity_data()
        self.disable()
        return full, ir

    async def aget_luminosity_data(self):
        self.enable()
        # Wait X ms for ADC to complete with 10ms of slack
        await asyncio.sleep(0.001*self.get_timing() + 0.01)
        full, ir = self._get_luminosity_data()
        self.disable()
        return full, ir

    def calculate_lux(self, full, ir):
        # Check for overflow conditions first
        if (full == 0xFFFF) | (ir == 0xFFFF):
            return 0

        if full == 0:
            return 0

        ratio = ir/full

        if 0 < ratio <= 0.50:
            return 0.0304 * full - 0.062 * ir * ((ratio)**1.4)
        if 0.50 < ratio <= 0.61:
            return 0.0224 * full - 0.031 * ir
        if 0.61 < ratio <= 0.80:
            return 0.0128 * full - 0.0153 * ir
        if 0.80 < ratio <= 1.30:
            return 0.00146 * full - 0.00112 * ir
        return 0

    def get_lux(self):
        full, ir = self.get_luminosity_data()
        return self.calculate_lux(full, ir)

    async def aget_lux(self):
        full, ir = await self.aget_luminosity_data()
        return self.calculate_lux(full, ir)

    def get_luminosity(self, channel):
        full, ir = self.get_luminosity_data()
        if channel == self.VISIBLE:
            # Reads all and subtracts out ir to give just the visible!
            return full - ir
        if channel == self.FULLSPECTRUM:
            # Reads two byte value from channel 0 (visible + infrared)
            return full
        if channel == self.INFRARED:
            # Reads two byte value from channel 1 (infrared)
            return ir
        # unknown channel!
        return 0

    def get_current(self, format=''):
        full, ir = self.get_luminosity_data()
        lux = self.calculate_lux(full, ir)  # convert raw values to lux
        output = {
            'lux': lux,
            'full': full,
            'ir': ir,
            'gain': self.get_gain(),
            'integration_time': self.get_timing()
        }
        if format == 'json':
            import json
            return json.dumps(output)
        return output

    def test(self, int_time=INTEGRATIONTIME_100MS, gain=GAIN_LOW):
        self.set_gain(gain)
        self.set_timing(int_time)
        full_test, ir_test = self.get_luminosity_data()
        lux_test = self.calculate_lux(full_test, ir_test)
        print(f'Lux = {lux_test:.0f}  full = {full_test} ir = {ir_test} '
              f'Integration time = {self.get_timing()} '
              f'Gain = {self.get_gain()}')

class TSL2561:
    def __init__(self, controller, i2c_bus=1, i2c_addr=0x29, period=30):
        self.controller = controller
        self.topic = f"sensor/i2c/lux/{controller.host}/{i2c_bus}/{i2c_addr}"
        self.period = period

        self._task = asyncio.create_task(self.run())
        controller.add_cleanup_callback(self.stop)

        self.sensor = TSL2561Sensor(
            i2c_bus=i2c_bus,
            sensor_address=i2c_addr,
            integration=TSL2561Sensor.INTEGRATIONTIME_100MS,
            gain=TSL2561Sensor.GAIN_HIGH)

    async def run(self):
        try:
            while True:
                lux = await self.sensor.aget_lux()
                logger.debug("TSL2561: {}", lux)
                self.controller.publish(
                    self.topic, int(lux))
                await asyncio.sleep(self.period)
        except asyncio.CancelledError:  # This will be raised politely in await
            logger.debug("TSL2561 exiting cleanly")

    async def stop(self):
        self._task.cancel()
        await self._task
