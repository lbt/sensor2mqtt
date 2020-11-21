
python3 -m venv ~/venv-mqtt --system-site-packages
. ~/venv-mqtt/bin/activate
pip install toml gmqtt






mkdir -p /home/pi/.config/systemd/user/default.target.wants/
cp /home/pi/heating/temp2mqtt/temp2mqtt.service /home/pi/.config/systemd/user/temp2mqtt.service
ln -s /home/pi/.config/systemd/user/temp2mqtt.service /home/pi/.config/systemd/user/default.target.wants/
systemctl --user daemon-reload 

sudo loginctl enable-linger pi

cat <<EOF > ~/mqtt_sensor.toml
mqtt_host = "apple.dgreaves.com"
username = "mqtt-test"
password = "mqtt-test"
ds18b20-pins = [ 3 ]
debug = false
EOF


systemctl --user start temp2mqtt
