# Testing

Comprehensive test suite using pytest with CI/CD via GitHub Actions.

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=fingerprinting --cov=audio_utils --cov-report=html

# Run specific test file
python -m pytest tests/test_mqtt_client.py -v
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                 # Shared fixtures
├── test_storage_config.py      # Database config tests (13 tests)
├── test_mqtt_client.py         # MQTT client tests (15 tests)
└── test_audio_utils.py         # Audio utilities tests (18 tests)
```

## Test Coverage

**Total: 46 test cases** covering:

### Database Configuration (`test_storage_config.py`)
- Memory, PostgreSQL, MySQL configuration
- Environment variable overrides
- YAML config file loading
- Config validation and defaults

### MQTT Client (`test_mqtt_client.py`)
- Publisher initialization and config parsing
- System details publishing (with retain flag)
- Running status publishing (retained)
- Version publishing (retained)
- Event publishing to single `/event` topic
- Last song publishing to `/event/last_song`
- Fallback logic for metadata.song → song_name
- Connection state and error handling

### Audio Utilities (`test_audio_utils.py`)
- Audio file info extraction (ffprobe)
- Format conversion detection (44.1kHz mono WAV)
- YAML metadata scaffold creation
- Metadata and debounce field support
- Audio file discovery (recursive/non-recursive)
- Overwrite protection and error handling

## Shared Fixtures (`conftest.py`)

Available pytest fixtures:

- **`temp_dir`** - Temporary directory for test files
- **`sample_audio_file`** - 44.1kHz mono WAV (optimal format)
- **`sample_audio_file_16khz`** - 16kHz mono WAV (non-optimal)
- **`sample_yaml_metadata`** - Sample YAML metadata file
- **`mock_mqtt_config`** - Mock MQTT configuration dict
- **`memory_db_config`** - In-memory database config

## Running Tests

### All Tests
```bash
python -m pytest
```

### Specific Test File
```bash
python -m pytest tests/test_mqtt_client.py
```

### Specific Test Function
```bash
python -m pytest tests/test_mqtt_client.py::test_publish_event_single_topic
```

### Verbose Output
```bash
python -m pytest -v
python -m pytest -vv  # Extra verbose
```

### With Coverage Report
```bash
# Terminal output
python -m pytest --cov=fingerprinting --cov=audio_utils --cov-report=term-missing

# HTML report (open in browser)
python -m pytest --cov=fingerprinting --cov=audio_utils --cov-report=html
open htmlcov/index.html
```

### Stop on First Failure
```bash
python -m pytest -x
```

### Run Tests Matching Pattern
```bash
python -m pytest -k "mqtt"     # Run tests with "mqtt" in name
python -m pytest -k "not slow" # Skip tests marked as slow
```

## Continuous Integration

### GitHub Actions Workflow

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`

**Configuration:** `.github/workflows/test.yml`

**Test Matrix:**
- Python 3.11
- Python 3.12
- Python 3.13

**Steps:**
1. Checkout code
2. Setup Python (with version matrix)
3. Cache pip dependencies
4. Install system dependencies (ffmpeg, portaudio)
5. Install Python dependencies
6. Apply PyDejavu patches
7. Run pytest with coverage
8. Upload coverage to Codecov

### Viewing CI Results

Check CI status:
- In GitHub pull requests
- Under "Actions" tab in repository
- Badge in README (add if desired)

## Writing New Tests

### Basic Test Structure

```python
import pytest

def test_my_feature():
    """Test my feature does X."""
    result = my_function()
    assert result == expected_value
```

### Using Fixtures

```python
def test_with_temp_dir(temp_dir):
    """Test using temporary directory."""
    file_path = temp_dir / "test.txt"
    file_path.write_text("content")
    assert file_path.exists()
```

### Using Mock Objects

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test using mocked dependencies."""
    with patch('module.external_call') as mock_call:
        mock_call.return_value = "mocked"
        result = function_using_external_call()
        assert result == "mocked"
        mock_call.assert_called_once()
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    """Test doubling numbers."""
    assert double(input) == expected
```

## Test Dependencies

Defined in `requirements-dev.txt`:

- **pytest** (8.3.4) - Testing framework
- **pytest-cov** (6.0.0) - Coverage plugin
- **pytest-mock** (3.14.0) - Mocking utilities

## Mocking Strategy

Tests use mocks for:

- **MQTT**: Mock `paho.mqtt.client` to avoid broker connection
- **Audio**: Use synthetic WAV files from fixtures
- **Database**: Use in-memory configs for speed
- **File I/O**: Use pytest's `tmp_path` fixture

Benefits:
- Tests run fast (no external services)
- Deterministic results
- No network dependencies
- Parallel execution safe

## Coverage Goals

- Core modules: **80%+** coverage
- Critical paths: **90%+** coverage
- Integration tests optional for CI

Current coverage areas:
- ✅ Database configuration
- ✅ MQTT client
- ✅ Audio utilities
- 🔄 Fingerprint engine (integration tests)
- 🔄 Real-time recognizer (integration tests)

## Troubleshooting

### Tests Failing Locally

**Missing dependencies:**
```bash
pip install -r requirements-dev.txt
```

**PyDejavu patches not applied:**
```bash
python scripts/apply_patches.py
```

**FFmpeg not installed:**
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt-get install ffmpeg

# Windows
# Download from ffmpeg.org
```

### CI Failing

**Check workflow logs:**
- Go to GitHub Actions tab
- Click on failed workflow run
- Expand failed step to see error

**Common issues:**
- Dependency version conflicts
- System dependency missing
- Test environment differences

### Slow Tests

**Profile test execution:**
```bash
pytest --durations=10  # Show 10 slowest tests
```

**Run only fast tests:**
```bash
pytest -m "not slow"  # Skip tests marked @pytest.mark.slow
```

## Best Practices

1. **Write tests first** (TDD) when adding new features
2. **Keep tests fast** - use mocks for external services
3. **Test edge cases** - empty inputs, errors, boundaries
4. **Use descriptive names** - `test_publish_event_with_metadata`
5. **One assertion per test** - when possible
6. **Clean up** - fixtures handle cleanup automatically
7. **Run tests before commit** - catch issues early

## Integration Tests

For tests requiring real services (database, MQTT broker):

```python
@pytest.mark.integration
def test_with_real_postgres():
    """Test with real PostgreSQL connection."""
    # Skip in CI if service not available
    pytest.skip("Requires PostgreSQL")
```

Run integration tests separately:
```bash
python -m pytest -m integration
```

Skip integration tests in CI:
```bash
python -m pytest -m "not integration"
```

## See Also

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
