#!/bin/bash
.  /home/pi/venv-mqtt/bin/activate
exec python3 /home/pi/heating/temp2mqtt/temp2mqtt/temp2mqtt.py 
