This project allows my Pi's to present sensors onto MQTT.

These are my personal setup notes with hardcoded paths :)

# Prepare to install
```
sudo apt-get --yes install python3-venv

S2M_PATH="/everything/devel/raspi/sensor2mqtt"
# No longer works with site packages???
# python3 -m venv ~/venv-mqtt --system-site-packages
python3 -m venv ~/venv-mqtt
. ~/venv-mqtt/bin/activate
# Now fixed
# Workaround: AttributeError: install_layout ???
# See: https://groups.google.com/g/linux.debian.bugs.dist/c/PHXO3LnqwTQ?pli=1
# SETUPTOOLS_USE_DISTUTILS=stdlib
pip install ${S2M_PATH}
```

# Setup systemd service
```
SYSTEMD_DIR=/home/pi/.config/systemd/user
mkdir -p ${SYSTEMD_DIR}/default.target.wants/
cp -f ${S2M_PATH}/sensor2mqtt.service $SYSTEMD_DIR/sensor2mqtt.service
ln -fs $SYSTEMD_DIR/sensor2mqtt.service $SYSTEMD_DIR/default.target.wants/
systemctl --user daemon-reload 
systemctl --user enable sensor2mqtt

sudo loginctl enable-linger pi
```
# To setup one-wire for temp probes
```
echo "dtoverlay=w1-gpio,gpiopin=3" | sudo tee -a /boot/config.txt
sudo reboot
```
# To setup i2c for light sensor etc
```
echo i2c-dev >> /etc/modules
sed -i -e 's/#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' /boot/config.txt
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
# [tsl2561]
# # i2c-bus = 1
# # i2c-addr = 0x29
# # period = 30
EOF
```

# Start it
Yes, run this as the pi user
```
systemctl --user start sensor2mqtt
```
# And watch
```
journalctl --user-unit sensor2mqtt.service 
```
