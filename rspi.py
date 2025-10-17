#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json, time, sys
from datetime import datetime

# Try to import RPi.GPIO; if not available we emulate (useful for development)
try:
    import RPi.GPIO as GPIO
    REAL_GPIO = True
except Exception:
    REAL_GPIO = False
    class GPIOEmu:
        BCM = 'BCM'
        OUT = 'OUT'
        LOW = 0
        HIGH = 1
        _state = {}
        def setmode(self, m): pass
        def setup(self, pin, mode): self._state[pin] = 0
        def output(self, pin, v): self._state[pin] = 1 if v else 0
        def input(self, pin): return self._state.get(pin,0)
        def cleanup(self): pass
    GPIO = GPIOEmu()

# ---------- CONFIG ----------
BROKER = "13.234.21.33"   # <- change to your AWS public IP (1883)
PORT = 1883
CLIENT_ID = "Pi001"        # keep same as dashboard DEVICE_ID
TOPIC_CONTROL = "myiot/device/control"
TOPIC_STATUS  = "myiot/device/status"

# pins to control (BCM numbers)
PIN_LIST = [17, 18, 27, 22]   # change to your pins

# ---------- GPIO SETUP ----------
GPIO.setmode(GPIO.BCM)
for p in PIN_LIST:
    try:
        GPIO.setup(p, GPIO.OUT)
        GPIO.output(p, GPIO.LOW)
    except Exception as e:
        print("GPIO setup error:", e)

def read_all_pins():
    d = {}
    for p in PIN_LIST:
        try:
            d[str(p)] = 1 if GPIO.input(p) else 0
        except Exception:
            d[str(p)] = 0
    return d

def publish_state(client):
    payload = {
        "device_id": CLIENT_ID,
        "timestamp": datetime.utcnow().isoformat(),
        "pins": read_all_pins()
    }
    client.publish(TOPIC_STATUS, json.dumps(payload), qos=1)
    print("[Pi] Published state:", payload)

# ---------- MQTT callbacks ----------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Pi] Connected to broker")
        client.subscribe(TOPIC_CONTROL, qos=1)
        # publish initial state
        publish_state(client)
    else:
        print("[Pi] Connect failed, rc=", rc)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception as e:
        print("[Pi] Invalid JSON in control:", e, msg.payload)
        return

    # simple validations
    device = data.get("device_id", CLIENT_ID)
    pin = data.get("pin")
    cmd = data.get("command", "").upper()

    print(f"[Pi] Control message: device={device} pin={pin} cmd={cmd}")

    # if dashboard may control multiple devices, check device id (optional)
    if device != CLIENT_ID:
        print("[Pi] Message for other device id:", device)
        return

    if pin is None or int(pin) not in PIN_LIST:
        print("[Pi] Ignoring invalid pin:", pin)
        return

    pin = int(pin)
    if cmd == "ON":
        GPIO.output(pin, GPIO.HIGH)
    elif cmd == "OFF":
        GPIO.output(pin, GPIO.LOW)
    else:
        print("[Pi] Unknown command:", cmd)
        return

    # immediately publish new state
    publish_state(client)

def on_publish(client, userdata, mid):
    pass

def on_disconnect(client, userdata, rc):
    print("[Pi] Disconnected, rc=", rc)

# ---------- MQTT client ----------
client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
client.on_connect = on_connect
client.on_message = on_message
client.on_publish = on_publish
client.on_disconnect = on_disconnect

print("[Pi] Connecting to broker", BROKER, "port", PORT)
try:
    client.connect(BROKER, PORT, keepalive=60)
except Exception as e:
    print("[Pi] Connection failed:", e)
    GPIO.cleanup()
    sys.exit(1)

client.loop_start()

# periodic heartbeat (publish state every 30s) so dashboard can get updates
try:
    while True:
        publish_state(client)
        time.sleep(30)
except KeyboardInterrupt:
    print("\n[Pi] Stopping...")
finally:
    client.loop_stop()
    GPIO.cleanup()
