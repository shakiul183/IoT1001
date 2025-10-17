#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json, time, sys
from datetime import datetime

try:
    import RPi.GPIO as GPIO
    REAL_GPIO = True
except:
    REAL_GPIO = False
    class GPIOEmu:
        BCM = 'BCM'; OUT = 'OUT'; HIGH = 1; LOW = 0
        _state = {}
        def setmode(self, m): pass
        def setup(self, pin, mode): self._state[pin] = 0
        def output(self, pin, val): self._state[pin] = 1 if val else 0
        def input(self, pin): return self._state.get(pin,0)
        def cleanup(self): pass
    GPIO = GPIOEmu()

# ---------- CONFIG ----------
BROKER = "13.234.21.33"  # AWS public IP
PORT   = 1883
CLIENT_ID = "Pi001"
TOPIC_CONTROL = "myiot/device/control"
TOPIC_STATUS  = "myiot/device/status"
PIN_LIST = [17,18,27,22]  # Pi pins to control

# ---------- GPIO SETUP ----------
GPIO.setmode(GPIO.BCM)
for p in PIN_LIST:
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, GPIO.LOW)

def read_all_pins():
    return {str(p): GPIO.input(p) for p in PIN_LIST}

def publish_state(client):
    payload = {
        "device_id": CLIENT_ID,
        "timestamp": datetime.utcnow().isoformat(),
        "pins": read_all_pins()
    }
    client.publish(TOPIC_STATUS, json.dumps(payload), qos=1)
    print("[Pi] Published state:", payload)

# ---------- MQTT CALLBACKS ----------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Pi] Connected to broker")
        client.subscribe(TOPIC_CONTROL, qos=1)
        publish_state(client)
    else:
        print("[Pi] Connect failed, rc=", rc)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception as e:
        print("[Pi] Invalid JSON:", e)
        return

    device = data.get("device_id", CLIENT_ID)
    pin = data.get("pin")
    cmd = data.get("command","").upper()

    if device != CLIENT_ID: return
    if pin is None or int(pin) not in PIN_LIST: return
    pin = int(pin)

    if cmd == "ON": GPIO.output(pin, GPIO.HIGH)
    elif cmd == "OFF": GPIO.output(pin, GPIO.LOW)
    else: return

    publish_state(client)

def on_disconnect(client, userdata, rc):
    print("[Pi] Disconnected, rc=", rc)

# ---------- MQTT CLIENT ----------
client = mqtt.Client(CLIENT_ID, protocol=mqtt.MQTTv311)
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

try:
    client.connect(BROKER, PORT, keepalive=60)
except Exception as e:
    print("[Pi] Connection failed:", e)
    GPIO.cleanup()
    sys.exit(1)

client.loop_start()

try:
    while True:
        publish_state(client)
        time.sleep(30)
except KeyboardInterrupt:
    print("\n[Pi] Stopping...")
finally:
    client.loop_stop()
    GPIO.cleanup()
