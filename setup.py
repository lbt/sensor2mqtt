from distutils.core import setup

setup(
    name='sensor2mqtt',
    version='0.1dev',
    packages=['sensor2mqtt',],
    scripts=['bin/broadcast_temps.py'],
    license='GPLv3',
    long_description="""
    Sends MQTT messagesa about the 1-wire temperature probes on a system
    """
    install_requires=[
        "toml",
        "gmqtt",
        "gpiozero",
        "RPi.GPIO",
    ],
)
