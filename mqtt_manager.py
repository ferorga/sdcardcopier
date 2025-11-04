
import json
import paho.mqtt.client as mqtt

class MQTTManager:
    def __init__(self, config_file="mqtt_settings.json", message_callback=None):
        self.config = self.load_config(config_file)
        self.client_connected = False
        self.message_queue = {}  # To store payloads of messages received from topics
        self.client = self.create_mqtt_instance()
        self.message_callback = message_callback

    def load_config(self, config_file):
        with open(config_file, "r") as f:
            config = json.load(f)
        return config

    def on_message(self, client, userdata, message):
        print(f"Message received from topic {message.topic}: {str(message.payload.decode('utf-8'))}")
        # Store the payload in the message queue
        self.message_queue[message.topic] = message.payload.decode("utf-8")
        # Call the message callback if available
        if self.message_callback:
            self.message_callback(message.topic, message.payload.decode("utf-8"))

    def on_connect(self, client, userdata, flags, rc):
        self.client_connected = True
        print("Connected MQTT")
        # Subscribe to all topics specified in the config file
        for topic in self.config["subscribed_topics"]:
            self.client.subscribe(topic)

    def create_mqtt_instance(self):
        print(f"Creating new instance")
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "NAS")
        client.username_pw_set(self.config["mqtt_username"], self.config["mqtt_password"])
        print(f"Connecting to broker")
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.connect(self.config["mqtt_host"], self.config["mqtt_port"])
        client.loop_start()
        return client

    def publish_message(self, topic, payload):
        self.client.publish(topic=topic, payload=payload, qos=0, retain=False)

    def stop(self):
        print("Stopping MQTT")
        self.client.disconnect()
