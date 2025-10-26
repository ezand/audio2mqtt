# MQTT Integration

This guide covers MQTT integration for publishing audio recognition events to an MQTT broker.

## Overview

When audio events are detected, they can be automatically published to MQTT topics with full metadata. This enables integration with home automation systems (Home Assistant, Node-RED), monitoring dashboards, and custom applications.

## Features

- **Automatic publishing** - Events published on detection
- **Rich metadata** - Includes confidence, metadata fields, hash counts
- **Flexible topics** - Configurable topic prefix and per-song topics
- **QoS support** - Configurable quality of service levels
- **Authentication** - Username/password support
- **Graceful degradation** - Works without MQTT if not configured

## Configuration

MQTT is configured in your config file (e.g., `dev-config.yaml`):

```yaml
mqtt:
  # MQTT broker connection
  broker: localhost
  port: 1883

  # Authentication (optional)
  username: mosquitto
  password: mosquitto

  # Topic configuration
  topic_prefix: audio_events

  # Connection settings
  client_id_prefix: audio2mqtt_listener_
  keepalive: 60

  # QoS level (0, 1, or 2)
  qos: 1

  # Retain messages
  retain: false
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `broker` | string | `localhost` | MQTT broker hostname/IP |
| `port` | int | `1883` | MQTT broker port |
| `username` | string | - | Authentication username (optional) |
| `password` | string | - | Authentication password (optional) |
| `topic_prefix` | string | `audio_events` | Prefix for all topics |
| `client_id_prefix` | string | `audio2mqtt_listener_` | Client ID prefix (UUID appended) |
| `keepalive` | int | `60` | Connection keepalive (seconds) |
| `qos` | int | `1` | Quality of Service (0, 1, or 2) |
| `retain` | bool | `false` | Retain published messages |

### Environment Variables

You can override configuration with environment variables:

```bash
export MQTT_BROKER=192.168.1.100
export MQTT_PORT=1883
export MQTT_USERNAME=myuser
export MQTT_PASSWORD=mypass
```

## Topic Structure

Events are published to topics following this pattern:

```
{topic_prefix}/event/{song_name}
```

**Examples:**
- `audio_events/event/super_mario_world_overworld`
- `audio_events/event/super_mario_world_underground`
- `audio_events/event/zelda_item_fanfare`

This structure allows you to:
- Subscribe to all events: `audio_events/event/#`
- Subscribe to specific songs: `audio_events/event/super_mario_world_overworld`
- Filter by prefix: `audio_events/event/super_mario_world_+`

## Message Format

Messages are published as JSON with the following structure:

```json
{
  "song_name": "super_mario_world_overworld",
  "confidence": 0.87,
  "timestamp": "2025-10-26 15:30:45",
  "metadata": {
    "game": "Super Mario World",
    "song": "Overworld",
    "console": "SNES",
    "year": 1990
  },
  "offset": -1.23,
  "hashes_matched": 145,
  "total_hashes": 167
}
```

### Message Fields

| Field | Type | Description |
|-------|------|-------------|
| `song_name` | string | Unique song identifier |
| `confidence` | float | Match confidence (0.0-1.0) |
| `timestamp` | string | Detection timestamp (ISO format) |
| `metadata` | object | Flexible metadata fields (JSONB) |
| `offset` | float | Time offset in matched audio (seconds) |
| `hashes_matched` | int | Number of matching fingerprint hashes |
| `total_hashes` | int | Total hashes in reference fingerprint |

**Note**: The `metadata` field is flexible and contains whatever fields you defined in your YAML metadata files.

## Usage

### Enable MQTT

MQTT is automatically enabled when you use a config file:

```bash
# MQTT enabled (if configured in file)
python listen.py --config dev-config.yaml

# MQTT disabled (no config file)
python listen.py --db-type postgresql
```

### Output Example

When MQTT is enabled, you'll see connection info on startup:

```
Loading config from: dev-config.yaml
Method: Fingerprinting (Dejavu)
Using database type: postgresql
MQTT publishing: enabled
Connected to MQTT broker: localhost:1883
Found 45 registered fingerprints in database

Listening to: BlackHole 2ch
Method: Fingerprinting
Sample rate: 44100 Hz
[...]
```

Each detection is published automatically:

```
[2025-10-26 15:30:45] Event detected: super_mario_world_overworld (game: Super Mario World, song: Overworld) (confidence: 0.87)
```

### Testing MQTT

Subscribe to events with `mosquitto_sub`:

```bash
# Subscribe to all events
mosquitto_sub -h localhost -t "audio_events/event/#" -v

# Subscribe to specific song
mosquitto_sub -h localhost -t "audio_events/event/super_mario_world_overworld" -v

# With authentication
mosquitto_sub -h localhost -u mosquitto -P mosquitto -t "audio_events/event/#" -v
```

## MQTT Broker Setup

### Mosquitto (Docker)

Add Mosquitto to your `docker-compose.yml`:

```yaml
services:
  postgres:
    # ... existing postgres service ...

  mosquitto:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto_data:/mosquitto/data
      - mosquitto_log:/mosquitto/log
    restart: unless-stopped

volumes:
  postgres_data:
  mosquitto_data:
  mosquitto_log:
```

Create `mosquitto.conf`:

```conf
listener 1883
allow_anonymous true

# Or with authentication:
# listener 1883
# allow_anonymous false
# password_file /mosquitto/config/password.txt
```

Start broker:

```bash
docker-compose up -d mosquitto
```

### Other MQTT Brokers

audio2mqtt works with any MQTT broker:

- **Home Assistant** - Built-in MQTT broker
- **AWS IoT Core** - Cloud MQTT service
- **HiveMQ** - Enterprise MQTT broker
- **EMQ X** - Scalable MQTT broker

Just configure the `broker` and `port` in your config file.

## Integration Examples

### Home Assistant

Subscribe to audio events in Home Assistant:

```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "Last Audio Event"
      state_topic: "audio_events/event/+"
      value_template: "{{ value_json.metadata.game }}: {{ value_json.metadata.song }}"
      json_attributes_topic: "audio_events/event/+"
      json_attributes_template: "{{ value_json | tojson }}"

  binary_sensor:
    - name: "Mario Overworld Playing"
      state_topic: "audio_events/event/super_mario_world_overworld"
      payload_on: "ON"
      value_template: >
        {% if value_json.confidence > 0.8 %}ON{% else %}OFF{% endif %}
      off_delay: 5
```

### Node-RED

Create a flow to process events:

1. **MQTT In** node: Subscribe to `audio_events/event/#`
2. **JSON** node: Parse payload
3. **Switch** node: Route by `msg.payload.metadata.game`
4. **Function** nodes: Custom logic per game
5. **MQTT Out** / **HTTP Request**: Trigger actions

### Python Client

Process events in Python:

```python
import paho.mqtt.client as mqtt
import json

def on_message(client, userdata, msg):
    event = json.loads(msg.payload)
    print(f"Detected: {event['metadata']['game']} - {event['metadata']['song']}")
    print(f"Confidence: {event['confidence']:.2f}")

    # Your custom logic here
    if event['confidence'] > 0.8:
        trigger_action(event)

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("audio_events/event/#")
client.loop_forever()
```

## Troubleshooting

### Connection Failed

**Issue**: `Failed to connect to MQTT broker`

**Solutions**:
- Verify broker is running: `mosquitto -v` or `docker ps`
- Check broker address/port in config
- Test connection: `mosquitto_sub -h localhost -t test`
- Check firewall rules

### Authentication Failed

**Issue**: `Connection refused - bad username or password`

**Solutions**:
- Verify username/password in config
- Check broker authentication settings
- Test credentials: `mosquitto_sub -h localhost -u user -P pass -t test`

### Messages Not Received

**Issue**: Published but not received by subscribers

**Check**:
- Topic subscription pattern matches published topics
- QoS level compatibility between publisher/subscriber
- Broker logs: `docker logs mosquitto`
- Test with `mosquitto_sub` to isolate issue

### MQTT Disabled

**Issue**: `MQTT publishing: disabled (no config file)`

**Solution**: Use `--config` flag to load MQTT settings:
```bash
python listen.py --config dev-config.yaml
```

## Performance Considerations

### Message Rate

Detection events are debounced (default 1 second), so maximum message rate is ~1 msg/sec per song.

### QoS Levels

- **QoS 0** (at most once): Fastest, may lose messages
- **QoS 1** (at least once): Reliable, may duplicate (recommended)
- **QoS 2** (exactly once): Most reliable, slower

### Retain Flag

Set `retain: true` to keep last event for each song:
- Subscribers see last event immediately on connect
- Useful for status dashboards
- Increases broker memory usage

## Security

### Authentication

Always use authentication in production:

```yaml
mqtt:
  username: secure_user
  password: strong_password_here
```

### TLS/SSL

For encrypted connections, use port 8883 and configure your broker for TLS.

### Network Security

- Run broker on private network
- Use firewall rules to restrict access
- Consider VPN for remote access

## Next Steps

- **[Fingerprinting Guide](fingerprinting.md)** - Learn about metadata and fingerprint generation
- **[Audio Device Setup](setup.md)** - Configure audio capture
- **[Home Assistant Integration](https://www.home-assistant.io/integrations/mqtt/)** - Connect to home automation
