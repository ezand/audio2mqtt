"""MQTT client for publishing audio recognition events."""

import json
import logging
import os
import uuid
from typing import Dict, Optional, Any

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False


class MQTTPublisher:
    """MQTT client for publishing audio recognition events."""

    def __init__(self,
                 broker: str = "localhost",
                 port: int = 1883,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 topic_prefix: str = "audio2mqtt",
                 client_id: str = f"audio2mqtt_listener_{str(uuid.uuid4())}",
                 keepalive: int = 60,
                 qos: int = 1,
                 retain: bool = False):
        """Initialize MQTT publisher.

        Args:
            broker: MQTT broker hostname/IP.
            port: MQTT broker port.
            username: MQTT username (optional).
            password: MQTT password (optional).
            topic_prefix: Prefix for all MQTT topics.
            client_id: MQTT client ID.
            keepalive: Connection keepalive interval in seconds.
            qos: Quality of Service level (0, 1, or 2).
            retain: Whether to retain published messages.
        """
        if not MQTT_AVAILABLE:
            raise ImportError("paho-mqtt is required for MQTT publishing. Install with: pip install paho-mqtt")

        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.topic_prefix = topic_prefix
        self.qos = qos
        self.retain = retain
        self.connected = False

        # Create MQTT client
        self.client = mqtt.Client(client_id=client_id)

        # Set authentication if provided
        if username and password:
            self.client.username_pw_set(username, password)

        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        # Setup logging
        self.logger = logging.getLogger(__name__)

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.connected = True
            self.logger.info(f"Connected to MQTT broker {self.broker}:{self.port}")
        else:
            self.connected = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            error_msg = error_messages.get(rc, f"Connection refused - unknown error ({rc})")
            self.logger.error(f"Failed to connect to MQTT broker: {error_msg}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        self.connected = False
        if rc != 0:
            self.logger.warning(f"Unexpected disconnection from MQTT broker (rc={rc})")
        else:
            self.logger.info("Disconnected from MQTT broker")

    def _on_publish(self, client, userdata, mid):
        """Callback for when a message is published."""
        self.logger.debug(f"Message published (mid={mid})")

    def connect(self) -> bool:
        """Connect to MQTT broker.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()

            # Wait for async connection to complete (with timeout)
            import time
            timeout = 5.0
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)

            return self.connected
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()

    def publish_system_details(self, details: Dict[str, Any], retain: bool = False) -> bool:
        """Publish system details to MQTT.

        Args:
            details: System details dictionary.
            retain: Whether to retain the message (default: False).

        Returns:
            True if publish successful, False otherwise.
        """
        if not self.connected:
            self.logger.warning("Not connected to MQTT broker, skipping system details publish")
            return False

        try:
            topic = f"{self.topic_prefix}/system/details"
            payload_json = json.dumps(details, ensure_ascii=False)

            result = self.client.publish(
                topic=topic,
                payload=payload_json,
                qos=self.qos,
                retain=retain
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"Published system details to {topic}")
                return True
            else:
                self.logger.error(f"Failed to publish system details to {topic}: {result.rc}")
                return False

        except Exception as e:
            self.logger.error(f"Error publishing system details: {e}")
            return False

    def publish_running_status(self, status: str) -> bool:
        """Publish running status to MQTT.

        Args:
            status: Status string ("on" or "off").

        Returns:
            True if publish successful, False otherwise.
        """
        if not self.connected:
            self.logger.warning("Not connected to MQTT broker, skipping running status publish")
            return False

        try:
            topic = f"{self.topic_prefix}/system/running"

            result = self.client.publish(
                topic=topic,
                payload=status,
                qos=self.qos,
                retain=True  # Retain so status survives broker restarts
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"Published running status to {topic}: {status}")
                return True
            else:
                self.logger.error(f"Failed to publish running status to {topic}: {result.rc}")
                return False

        except Exception as e:
            self.logger.error(f"Error publishing running status: {e}")
            return False

    def publish_event(self, event: Dict[str, Any]) -> bool:
        """Publish audio recognition event to MQTT.

        Args:
            event: Event dictionary with keys like 'song_name', 'confidence', 'metadata', etc.

        Returns:
            True if publish successful, False otherwise.
        """
        if not self.connected:
            self.logger.warning("Not connected to MQTT broker, skipping publish")
            return False

        try:
            # Extract song name for topic
            song_name = event.get('song_name', 'unknown')

            # Construct topic: audio2mqtt/event/{song_name}
            topic = f"{self.topic_prefix}/event/{song_name}"

            # Prepare payload with all event data
            payload = {
                'song_name': song_name,
                'confidence': event.get('confidence', 0.0),
                'timestamp': event.get('timestamp'),
                'metadata': event.get('metadata', {}),
                'offset': event.get('offset', 0),
                'hashes_matched': event.get('hashes_matched_in_input', 0),
                'total_hashes': event.get('input_total_hashes', 0)
            }

            # Serialize to JSON
            payload_json = json.dumps(payload, ensure_ascii=False)

            # Publish
            result = self.client.publish(
                topic=topic,
                payload=payload_json,
                qos=self.qos,
                retain=self.retain
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(f"Published event to {topic}: {song_name} ({payload['confidence']:.2f})")
                return True
            else:
                self.logger.error(f"Failed to publish to {topic}: {result.rc}")
                return False

        except Exception as e:
            self.logger.error(f"Error publishing event: {e}")
            return False

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> Optional['MQTTPublisher']:
        """Create MQTT publisher from configuration dictionary.

        Args:
            config: Configuration dictionary with MQTT settings.

        Returns:
            MQTTPublisher instance or None if MQTT not configured.
        """
        if not MQTT_AVAILABLE:
            logging.warning("paho-mqtt not installed, MQTT publishing disabled")
            return None

        mqtt_config = config.get('mqtt', {})
        if not mqtt_config:
            logging.info("MQTT not configured, publishing disabled")
            return None

        # Environment variable overrides
        broker = os.getenv('MQTT_BROKER', mqtt_config.get('broker', 'localhost'))
        port = int(os.getenv('MQTT_PORT', mqtt_config.get('port', 1883)))
        username = os.getenv('MQTT_USERNAME', mqtt_config.get('username'))
        password = os.getenv('MQTT_PASSWORD', mqtt_config.get('password'))

        # Generate client_id from prefix + UUID
        client_id_prefix = mqtt_config.get('client_id_prefix', 'audio2mqtt_listener')
        client_id = f"{client_id_prefix}_{uuid.uuid4()}"

        return cls(
            broker=broker,
            port=port,
            username=username,
            password=password,
            topic_prefix=mqtt_config.get('topic_prefix', 'audio_events'),
            client_id=client_id,
            keepalive=mqtt_config.get('keepalive', 60),
            qos=mqtt_config.get('qos', 1),
            retain=mqtt_config.get('retain', False)
        )
