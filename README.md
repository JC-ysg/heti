# Heti - Memory Monitoring System

Heti is a comprehensive system for monitoring, logging, and visualizing memory operations in the OpenMemory platform. It provides real-time detection of memory creation, updates, deletions, and errors with a user-friendly graphical interface.

## Features

- **Real-time Memory Monitoring**: Detect memory operations as they happen
- **Event Logging**: Detailed logging of all memory events
- **Error Detection**: Capture and display error events with detailed information
- **User Interface**: Visual display of memory events with filtering and details
- **Configurable**: Easily adjust settings through YAML configuration
- **API Connection Status**: Real-time detection and display of OpenMemory API availability
- **Robust Startup**: Comprehensive validation and auto-configuration system
- **Troubleshooting**: Built-in diagnostics and guidance for common issues

## Project Structure

- `/agent`: Core monitoring functionality
- `/tools`: API clients and utilities
- `/ui`: User interface components
- `/config`: Configuration files
- `/logs`: Log files
- `/tests`: Test files
- `/Heti`: Backend server implementations

## Quick Start

### Recommended: Using the Launcher

The simplest way to start Heti is using the launcher script:

```bash
python start_heti.py
```

This launcher will:
1. Check if Docker is installed and running
2. Verify all required configuration is present (creating if needed)
3. Start the OpenMemory backend containers if they're not running
4. Wait for the API to be responsive
5. Launch the Heti Control Panel UI

For additional options:
```bash
python start_heti.py --help
```

### Manual Startup (Advanced)

If you prefer to start components manually:

#### 1. Start the Backend

```bash
cd mem0/openmemory/openmemory
docker-compose up -d
```

#### 2. Start the MCP Server

```bash
python -m uvicorn Heti.mcp_server:app --port 8001 --reload
```

#### 3. Launch the UI

```bash
python heticontrol.py
```

The UI will automatically check and display the connection status to the OpenMemory API.

### 4. Start the Memory Monitor

Within the UI, go to the Memory Monitor tab and click "Start Memory Monitor".

For detailed usage instructions, see [MVP Demo Guide](.cursor/mvp_demo_guide.mdc).

## Troubleshooting

If you encounter issues:

1. Use the "Troubleshoot" button in the UI for comprehensive diagnostics
2. Check the logs in the `logs/` directory, especially `heti_startup.log`
3. Ensure Docker is running and ports 8000/8001 are available
4. Verify the configuration in `config/memory_monitor.yaml`

For detailed troubleshooting, see [UI Connection Validation](.cursor/ui_connection_validation.mdc).

## Requirements

- Python 3.8+
- Docker and Docker Compose
- Required Python packages:
  - tkinter
  - yaml
  - asyncio
  - datetime
  - json
  - logging
  - threading
  - uuid
  - requests

## Configuration

The system is configured through YAML files located in the `/config` directory:

- `memory_monitor.yaml`: Configuration for the Memory Monitor

## User Interface

### Connection Status Indicator

The Heti Control Panel displays the connection status to the OpenMemory API backend:

- **Connected**: Green checkmark indicates successful connection
- **Not Connected**: Red X indicates connection failure with detailed error message
- **Retry Connection**: Button to manually retry connection when the API is unavailable
- **Troubleshoot**: Button to open the diagnostics dialog with detailed information

For connection status validation details, see [UI Connection Validation](.cursor/ui_connection_validation.mdc).

## Development

### Running Tests

```bash
python -m pytest tests/test_memory_monitor.py
python -m pytest tests/test_openmemory_client.py
```

### Documentation

- [Memory Monitor Validation](.cursor/memory_monitor_validation.mdc)
- [Memory Monitor Specification](.cursor/memory_monitor_spec.mdc)
- [Project Structure Review](.cursor/structure_review.mdc)
- [UI Connection Validation](.cursor/ui_connection_validation.mdc)

## License

This project is licensed under the terms of the MIT license. 