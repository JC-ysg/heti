#!/usr/bin/env python
"""
Error Event Logging Demo

This script demonstrates the error event logging capability
of the Heti Memory Monitor by simulating different error scenarios.
"""

import os
import sys
import time
import json
import uuid
from datetime import datetime, UTC

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Memory Monitor
from agent.memory_monitor import MemoryMonitor

def main():
    """Run the error event logging demonstration."""
    # Create a temporary directory for logs
    log_dir = "examples/logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Create a temporary config file
    config_path = "examples/test_config.yaml"
    
    # Basic config for the test
    config = {
        "polling": {
            "enabled": True,
            "interval_seconds": 1
        },
        "logging": {
            "file_enabled": True,
            "file_path": f"{log_dir}/monitor.log",
            "event_log_path": f"{log_dir}/error_events.jsonl",
            "console_level": "INFO"
        },
        "error": {
            "deduplication_window_seconds": 5  # Short window for demonstration
        }
    }
    
    # Write config to file
    with open(config_path, 'w') as f:
        import yaml
        yaml.dump(config, f)
    
    # Create memory monitor with test config
    monitor = MemoryMonitor(config_path=config_path)
    
    print("Starting Error Logging demonstration")
    
    # Example 1: API Error
    api_error_context = {
        "endpoint": "/api/v1/memories",
        "method": "GET",
        "status_code": 503,
        "response": "Service Unavailable"
    }
    
    print("\n1. Logging API Error:")
    monitor.log_monitor_error(
        "APIError", 
        "Failed to connect to memory service", 
        api_error_context
    )
    print("  Error logged successfully")
    
    # Example 2: Configuration Error
    config_error_context = {
        "parameter": "polling.interval_seconds",
        "value": -10,
        "valid_range": "1-3600"
    }
    
    print("\n2. Logging Configuration Error:")
    monitor.log_monitor_error(
        "ConfigError", 
        "Invalid configuration parameter", 
        config_error_context
    )
    print("  Error logged successfully")
    
    # Example 3: Data Processing Error
    data_error_context = {
        "memory_id": str(uuid.uuid4()),
        "field": "embedding",
        "error_details": "Invalid vector dimensions"
    }
    
    print("\n3. Logging Data Processing Error:")
    monitor.log_monitor_error(
        "DataError", 
        "Failed to process memory data", 
        data_error_context
    )
    print("  Error logged successfully")
    
    # Example 4: Demonstrating deduplication (same as first error)
    print("\n4. Demonstrating error deduplication (repeating API Error):")
    monitor.log_monitor_error(
        "APIError", 
        "Failed to connect to memory service", 
        api_error_context
    )
    print("  This error should be deduplicated and not logged again")
    
    # Example 5: Wait for deduplication window and log again
    print(f"\n5. Waiting {config['error']['deduplication_window_seconds']} seconds for deduplication window to expire...")
    time.sleep(config['error']['deduplication_window_seconds'] + 0.1)
    
    print("   Logging API Error again after deduplication window:")
    monitor.log_monitor_error(
        "APIError", 
        "Failed to connect to memory service", 
        api_error_context
    )
    print("  Error should be logged again")
    
    # Print error log file contents
    print("\nContents of error log file:")
    log_file = f"{log_dir}/error_events.jsonl"
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Parse and pretty print each JSON log entry
                event = json.loads(line)
                print(f"\nLog Entry {i+1}:")
                print(json.dumps(event, indent=2))
    except Exception as e:
        print(f"Error reading log file: {str(e)}")
    
    print("\nError counter:", monitor.event_counters["memory.error"])
    print("\nError Logging demonstration complete")


if __name__ == "__main__":
    main() 