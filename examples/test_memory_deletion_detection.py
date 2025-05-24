#!/usr/bin/env python
"""
Memory Deletion Detection Demo

This script demonstrates the memory deletion detection capability
of the Heti Memory Monitor by simulating memory creation and deletion.

It uses a mock OpenMemory client to simulate API responses.
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

class MockOpenMemoryClient:
    """Mock OpenMemory client for demonstration purposes."""
    
    def __init__(self):
        """Initialize with some test memories."""
        self.memories = {}
        
        # Create some test memories
        for i in range(5):
            memory_id = str(uuid.uuid4())
            self.memories[memory_id] = {
                "id": memory_id,
                "user_id": "test-user",
                "app_id": "test-app",
                "content": f"Test memory content {i}",
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "categories": ["test"]
            }
    
    def list_memories(self, **kwargs):
        """Mock implementation of list_memories."""
        return {
            "items": list(self.memories.values()),
            "total": len(self.memories),
            "page": 1,
            "size": 10,
            "pages": 1
        }
    
    def get_memory(self, memory_id):
        """Mock implementation of get_memory."""
        if memory_id in self.memories:
            return self.memories[memory_id]
        else:
            raise ValueError("Memory not found")
    
    def delete_memory(self, memory_id):
        """Delete a memory from the mock storage."""
        if memory_id in self.memories:
            del self.memories[memory_id]
            return {"success": True}
        else:
            raise ValueError("Memory not found")


def main():
    """Run the memory deletion detection demo."""
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
            "event_log_path": f"{log_dir}/memory_events.jsonl",
            "console_level": "INFO"
        }
    }
    
    # Write config to file
    with open(config_path, 'w') as f:
        import yaml
        yaml.dump(config, f)
    
    # Create mock client
    mock_client = MockOpenMemoryClient()
    
    # Create memory monitor with test config
    monitor = MemoryMonitor(config_path=config_path)
    monitor.client = mock_client
    
    print("Starting Memory Monitor demonstration")
    print(f"Initial memories: {len(mock_client.memories)}")
    
    # Start the monitor
    monitor.start()
    
    # Wait for initial poll to complete
    time.sleep(2)
    
    print(f"Known memory IDs: {len(monitor.known_memory_ids)}")
    
    # Pick a memory to delete
    memory_to_delete = next(iter(mock_client.memories.keys()))
    
    print(f"Deleting memory: {memory_to_delete}")
    
    # Delete the memory
    mock_client.delete_memory(memory_to_delete)
    
    # Run the deletion detection
    print("Running deletion detection...")
    deletion_events = monitor.poll_memory_deletions()
    
    print(f"Detected {len(deletion_events)} deletion events")
    
    # Print the detected events
    for event in deletion_events:
        print("\nDetected deletion event:")
        print(json.dumps(event, indent=2))
    
    # Verify memory was removed from known_memory_ids
    print(f"\nMemory {memory_to_delete} removed from known_memory_ids: {memory_to_delete not in monitor.known_memory_ids}")
    
    # Print event counters
    print("\nEvent counters:")
    for event_type, count in monitor.event_counters.items():
        print(f"  {event_type}: {count}")
    
    # Stop the monitor
    monitor.stop()
    print("\nMemory Monitor demonstration complete")


if __name__ == "__main__":
    main() 