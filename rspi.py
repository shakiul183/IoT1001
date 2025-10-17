import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import time

BROKER = "YOUR_AWS_PUBLIC_IP"  # Example: "13.233.166.78"
PORT = 1883
TOPIC = "rpi/gpio/#"

pins = [17, 27, 22]

GPIO.setmode(GPIO.BCM)
for pin in pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

def on_connect(client, userdata, flags, rc):
    print(f"[RPi] Connected with result code {rc}")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode().strip()
    print(f"[RPi] Topic: {topic} | Message: {payload}")

    if topic.startswith("rpi/gpio/"):
        pin = int(topic.split("/")[-1])
        if payload == "ON":
            GPIO.output(pin, GPIO.HIGH)
        else:
            GPIO.output(pin, GPIO.LOW)

client = mqtt.Client("RPi_Client")
client.on_connect = on_connect
client.on_message = on_message

try:
    print(f"[RPi] Connecting to {BROKER}:{PORT}")
    client.connect(BROKER, PORT, 60)
    client.loop_forever()
except KeyboardInterrupt:
    GPIO.cleanup()
    print("GPIO cleaned up.")
