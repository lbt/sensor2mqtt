
sudo -i
mkdir /everything
echo "elm:/everything /everything nfs4 rw 0 0" >> /etc/fstab
mount /everything
exit

ln -s /everything/devel/raspi/heating ~/


echo "dtoverlay=w1-gpio,gpiopin=3" | sudo tee -a /boot/config.txt
sudo reboot


sudo apt-get --yes install python3-venv

python3 -m venv ~/venv-mqtt --system-site-packages
. ~/venv-mqtt/bin/activate
pip install toml gmqtt gpiozero rpi.gpio


mkdir -p /home/pi/.config/systemd/user/default.target.wants/
cp /home/pi/heating/sensor2mqtt/sensor2mqtt.service /home/pi/.config/systemd/user/sensor2mqtt.service
ln -s /home/pi/.config/systemd/user/sensor2mqtt.service /home/pi/.config/systemd/user/default.target.wants/
systemctl --user daemon-reload 

sudo loginctl enable-linger pi

cat <<EOF > ~/mqtt_sensor.toml
mqtt_host = "mqtt.dgreaves.com"
username = "mqtt-test"
password = "mqtt-test"
ds18b20-pins = [ 3 ]
debug = false
EOF


systemctl --user start sensor2mqtt

journalctl --user-unit sensor2mqtt.service 
