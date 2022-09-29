This project allows my Pi's to present sensors onto MQTT.

These are my personal setup notes with hardcoded paths :)

# Prepare to install
```
sudo apt-get --yes install python3-venv

S2M_PATH="/everything/devel/raspi/sensor2mqtt"
python3 -m venv ~/venv-mqtt --system-site-packages
. ~/venv-mqtt/bin/activate
# Workaround: AttributeError: install_layout ???
# See: https://groups.google.com/g/linux.debian.bugs.dist/c/PHXO3LnqwTQ?pli=1
SETUPTOOLS_USE_DISTUTILS=stdlib
pip install ${S2M_PATH}
```

# Setup systemd service
```
SYSTEMD_DIR=/home/pi/.config/systemd/user
mkdir -p ${SYSTEMD_DIR}/default.target.wants/
cp ${S2M_PATH}/sensor2mqtt.service $SYSTEMD_DIR/sensor2mqtt.service
ln -s $SYSTEMD_DIR/sensor2mqtt.service $SYSTEMD_DIR/default.target.wants/
systemctl --user daemon-reload 

sudo loginctl enable-linger pi
```
# To setup one-wire for temp probes
```
echo "dtoverlay=w1-gpio,gpiopin=3" | sudo tee -a /boot/config.txt
sudo reboot
```

# Configure
Add in any sensors on this Pi
```
cat <<EOF > ~/mqtt_sensor.toml
mqtt_host = "mqtt.dgreaves.com"
username = "mqtt-test"
password = "mqtt-test"
debug = false
# ds18b20-pins = [ 3 ]
# relay-pins = [ 27 ]
# relay-inverted-pins = [17, 27, 22]
# switch-pins = [10, 9, 11]
# pir-pins = [ 17 ]
EOF
```

# Start it
Yes, run this as the pi user
```
systemctl --user enable sensor2mqtt
systemctl --user start sensor2mqtt
```
# And watch
```
journalctl --user-unit sensor2mqtt.service 
```
