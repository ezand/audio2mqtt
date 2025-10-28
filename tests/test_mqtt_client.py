"""Tests for MQTT client module."""

import json
from unittest.mock import Mock, patch, MagicMock

import pytest

from fingerprinting.mqtt_client import MQTTPublisher


@pytest.fixture
def mqtt_publisher():
    """Create an MQTT publisher instance for testing."""
    with patch('fingerprinting.mqtt_client.mqtt.Client'):
        publisher = MQTTPublisher(
            broker='localhost',
            port=1883,
            topic_prefix='test_audio',
            qos=1,
            retain=False
        )
        publisher.connected = True  # Simulate connected state
        return publisher


def test_mqtt_publisher_init():
    """Test MQTTPublisher initialization."""
    with patch('fingerprinting.mqtt_client.mqtt.Client') as mock_client:
        publisher = MQTTPublisher(
            broker='test_broker',
            port=1234,
            username='test_user',
            password='test_pass',
            topic_prefix='test_prefix',
            qos=2,
            retain=True
        )

        assert publisher.broker == 'test_broker'
        assert publisher.port == 1234
        assert publisher.topic_prefix == 'test_prefix'
        assert publisher.qos == 2
        assert publisher.retain == True
        assert publisher.connected == False


def test_mqtt_publisher_from_config(mock_mqtt_config):
    """Test creating MQTTPublisher from config."""
    with patch('fingerprinting.mqtt_client.mqtt.Client'):
        publisher = MQTTPublisher.from_config(mock_mqtt_config)

        assert publisher is not None
        assert publisher.broker == 'localhost'
        assert publisher.port == 1883
        assert publisher.topic_prefix == 'test_audio'


def test_mqtt_publisher_from_config_no_mqtt():
    """Test from_config returns None when MQTT not configured."""
    config = {}
    publisher = MQTTPublisher.from_config(config)

    assert publisher is None


def test_publish_system_details(mqtt_publisher):
    """Test publishing system details."""
    details = {
        'version': '1.0.0',
        'platform': 'darwin',
        'sample_rate': 44100
    }

    with patch.object(mqtt_publisher.client, 'publish') as mock_publish:
        mock_publish.return_value = Mock(rc=0)  # MQTT_ERR_SUCCESS

        result = mqtt_publisher.publish_system_details(details, retain=True)

        assert result == True
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args

        assert call_args.kwargs['topic'] == 'test_audio/system/details'
        assert call_args.kwargs['retain'] == True
        assert call_args.kwargs['qos'] == 1

        # Verify payload is valid JSON
        payload = json.loads(call_args.kwargs['payload'])
        assert payload['version'] == '1.0.0'
        assert payload['platform'] == 'darwin'


def test_publish_system_details_default_retain(mqtt_publisher):
    """Test publishing system details with default retain=False."""
    details = {'version': '1.0.0'}

    with patch.object(mqtt_publisher.client, 'publish') as mock_publish:
        mock_publish.return_value = Mock(rc=0)

        mqtt_publisher.publish_system_details(details)

        call_args = mock_publish.call_args
        assert call_args.kwargs['retain'] == False


def test_publish_running_status(mqtt_publisher):
    """Test publishing running status."""
    with patch.object(mqtt_publisher.client, 'publish') as mock_publish:
        mock_publish.return_value = Mock(rc=0)

        result = mqtt_publisher.publish_running_status("on")

        assert result == True
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args

        assert call_args.kwargs['topic'] == 'test_audio/system/running'
        assert call_args.kwargs['payload'] == 'on'
        assert call_args.kwargs['retain'] == True  # Should always be retained


def test_publish_version(mqtt_publisher):
    """Test publishing version."""
    with patch.object(mqtt_publisher.client, 'publish') as mock_publish:
        mock_publish.return_value = Mock(rc=0)

        result = mqtt_publisher.publish_version("abc123")

        assert result == True
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args

        assert call_args.kwargs['topic'] == 'test_audio/system/version'
        assert call_args.kwargs['payload'] == 'abc123'
        assert call_args.kwargs['retain'] == True


def test_publish_event_single_topic(mqtt_publisher):
    """Test that events are published to single topic."""
    event = {
        'song_name': 'test_song',
        'confidence': 0.85,
        'timestamp': '2025-10-27 12:00:00',
        'metadata': {'game': 'Test Game', 'song': 'Test Song'},
        'offset': 0,
        'hashes_matched_in_input': 100,
        'input_total_hashes': 120
    }

    with patch.object(mqtt_publisher.client, 'publish') as mock_publish:
        mock_publish.return_value = Mock(rc=0)

        result = mqtt_publisher.publish_event(event)

        assert result == True
        # Should publish twice: once to /event, once to /event/last_song
        assert mock_publish.call_count == 2

        # Check first call (main event)
        first_call = mock_publish.call_args_list[0]
        assert first_call.kwargs['topic'] == 'test_audio/event'

        payload = json.loads(first_call.kwargs['payload'])
        assert payload['song_name'] == 'test_song'
        assert payload['confidence'] == 0.85


def test_publish_event_last_song(mqtt_publisher):
    """Test that last_song is published with song name from metadata."""
    event = {
        'song_name': 'test_song_id',
        'confidence': 0.85,
        'timestamp': '2025-10-27 12:00:00',
        'metadata': {'game': 'Test Game', 'song': 'Beautiful Song Name'},
        'offset': 0,
        'hashes_matched_in_input': 100,
        'input_total_hashes': 120
    }

    with patch.object(mqtt_publisher.client, 'publish') as mock_publish:
        mock_publish.return_value = Mock(rc=0)

        mqtt_publisher.publish_event(event)

        # Check second call (last_song)
        second_call = mock_publish.call_args_list[1]
        assert second_call.kwargs['topic'] == 'test_audio/event/last_song'
        assert second_call.kwargs['payload'] == 'Beautiful Song Name'
        assert second_call.kwargs['retain'] == True


def test_publish_event_last_song_fallback(mqtt_publisher):
    """Test that last_song falls back to song_name if metadata.song missing."""
    event = {
        'song_name': 'fallback_song_name',
        'confidence': 0.85,
        'timestamp': '2025-10-27 12:00:00',
        'metadata': {'game': 'Test Game'},  # No 'song' key
        'offset': 0,
        'hashes_matched_in_input': 100,
        'input_total_hashes': 120
    }

    with patch.object(mqtt_publisher.client, 'publish') as mock_publish:
        mock_publish.return_value = Mock(rc=0)

        mqtt_publisher.publish_event(event)

        # Check second call uses fallback
        second_call = mock_publish.call_args_list[1]
        assert second_call.kwargs['payload'] == 'fallback_song_name'


def test_publish_when_not_connected(mqtt_publisher):
    """Test that publish methods return False when not connected."""
    mqtt_publisher.connected = False

    assert mqtt_publisher.publish_system_details({'test': 'data'}) == False
    assert mqtt_publisher.publish_running_status('on') == False
    assert mqtt_publisher.publish_version('1.0.0') == False
    assert mqtt_publisher.publish_event({'song_name': 'test'}) == False


def test_connect_waits_for_connection():
    """Test that connect() waits for async connection to complete."""
    with patch('fingerprinting.mqtt_client.mqtt.Client') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        publisher = MQTTPublisher(broker='localhost', port=1883, topic_prefix='test')

        # Simulate connection callback setting connected flag after delay
        def connect_side_effect(*args, **kwargs):
            pass

        mock_client.connect.side_effect = connect_side_effect

        with patch('time.sleep'):  # Speed up test by mocking sleep
            # Simulate connection succeeds after first check
            publisher.connected = False
            with patch.object(publisher, 'connected', False):
                result = publisher.connect()
                # Without actual callback, connected stays False
                assert result == False


def test_disconnect(mqtt_publisher):
    """Test disconnect stops loop and disconnects client."""
    with patch.object(mqtt_publisher.client, 'loop_stop') as mock_loop_stop, \
         patch.object(mqtt_publisher.client, 'disconnect') as mock_disconnect:

        mqtt_publisher.disconnect()

        mock_loop_stop.assert_called_once()
        mock_disconnect.assert_called_once()
