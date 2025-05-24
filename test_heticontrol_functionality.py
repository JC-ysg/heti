#!/usr/bin/env python3
"""
Test script to verify the functionality of the enhanced heticontrol.py.
This script simulates a user workflow using the various features of heticontrol.py.
"""

import os
import sys
import time
import subprocess
import json
from heticontrol import OpenMemoryClient

def print_header(message):
    print("\n" + "=" * 80)
    print(f" {message}")
    print("=" * 80)

def create_test_memory():
    """Create a test memory using the test script"""
    print_header("CREATING TEST MEMORY")
    
    try:
        # Initialize client with correct base URL
        client = OpenMemoryClient(base_url="http://localhost:8765")
        
        # Create memory with correct parameters
        memory = client.create_memory(
            user_id="default_user",
            text="Test memory content",
            infer=True,
            app="heti"
        )
        
        if memory and 'id' in memory:
            print(f"✅ Successfully created test memory with ID: {memory['id']}")
            return memory['id']
        else:
            print("❌ Error creating test memory: No memory ID returned")
    except Exception as e:
        print(f"❌ Error creating test memory: {str(e)}")
    
    return None

def update_test_memory(memory_id):
    """Update a test memory using the test script"""
    if not memory_id:
        print("❌ No memory ID provided for update")
        return False
    
    print_header(f"UPDATING MEMORY {memory_id}")
    
    try:
        # Initialize client with correct base URL
        client = OpenMemoryClient(base_url="http://localhost:8765")
        
        # Update memory with correct parameters
        memory = client.update_memory(
            memory_id=memory_id,
            content="Updated test memory content",
            metadata={"updated": True}
        )
        
        if memory and 'id' in memory:
            print(f"✅ Successfully updated test memory with ID: {memory['id']}")
            return True
        else:
            print("❌ Error updating test memory: No memory ID returned")
    except Exception as e:
        print(f"❌ Error updating test memory: {str(e)}")
    
    return False

def delete_test_memory(memory_id):
    """Delete a test memory using the test script"""
    if not memory_id:
        print("❌ No memory ID provided for deletion")
        return False
    
    print_header(f"DELETING MEMORY {memory_id}")
    
    try:
        # Initialize client with correct base URL
        client = OpenMemoryClient(base_url="http://localhost:8765")
        
        # Delete memory using _make_request
        response = client._make_request(
            method="DELETE",
            endpoint=f"/api/v1/memories/{memory_id}"
        )
        
        print("✅ Successfully deleted test memory")
        return True
    except Exception as e:
        print(f"❌ Error deleting test memory: {str(e)}")
    
    return False

def generate_error():
    """Generate a test error using the error script"""
    print_header("GENERATING TEST ERROR")
    
    try:
        result = subprocess.run(
            ["python", "generate_error.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ Successfully generated test error")
            return True
        else:
            print(f"❌ Error running generate_error.py: {result.stderr}")
    except Exception as e:
        print(f"❌ Error running generate_error.py: {str(e)}")
    
    return False

def check_memory_events_log():
    """Check the memory events log for events"""
    print_header("CHECKING MEMORY EVENTS LOG")
    
    log_file = "logs/memory_events/memory_events.jsonl"
    if not os.path.exists(log_file):
        print(f"❌ Memory events log file not found: {log_file}")
        return False
    
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        
        print(f"Found {len(lines)} events in log file")
        
        # Count events by type
        event_counts = {}
        for line in lines:
            try:
                event = json.loads(line.strip())
                event_type = event.get("event_type", "unknown")
                if event_type not in event_counts:
                    event_counts[event_type] = 0
                event_counts[event_type] += 1
            except json.JSONDecodeError:
                pass
        
        print("\nEvent counts by type:")
        for event_type, count in event_counts.items():
            print(f"  - {event_type}: {count}")
        
        # Check if we have events of each type
        required_event_types = ["creation", "update", "deletion", "error"]
        missing_types = [t for t in required_event_types if t not in event_counts]
        
        if missing_types:
            print(f"❌ Missing events of types: {', '.join(missing_types)}")
            return False
        else:
            print("✅ Found events of all required types")
            return True
    except Exception as e:
        print(f"❌ Error reading events log: {str(e)}")
        return False

def run_tests():
    """Run a series of tests to verify heticontrol.py functionality"""
    print_header("HETICONTROL FUNCTIONALITY TESTS")
    
    # 1. Create a test memory
    memory_id = create_test_memory()
    
    # Wait a moment for the memory monitor to detect the creation
    print("Waiting for memory monitor to detect creation...")
    time.sleep(2)
    
    # 2. Update the test memory
    if memory_id:
        update_success = update_test_memory(memory_id)
        
        # Wait a moment for the memory monitor to detect the update
        print("Waiting for memory monitor to detect update...")
        time.sleep(2)
        
        # 3. Delete the test memory
        if update_success:
            delete_success = delete_test_memory(memory_id)
            
            # Wait a moment for the memory monitor to detect the deletion
            print("Waiting for memory monitor to detect deletion...")
            time.sleep(2)
    
    # 4. Generate a test error
    generate_error()
    
    # Wait a moment for the memory monitor to detect the error
    print("Waiting for memory monitor to detect error...")
    time.sleep(2)
    
    # 5. Check the memory events log
    check_memory_events_log()
    
    print_header("FUNCTIONALITY TESTS COMPLETE")
    print("heticontrol.py should now show all event types in their respective tabs.")
    print("Please check the UI to verify that:")
    print("1. Creation Events tab shows the test memory creation")
    print("2. Update Events tab shows the test memory update")
    print("3. Deletion Events tab shows the test memory deletion")
    print("4. Error Events tab shows the test error")
    print("\nManual verification steps:")
    print("1. Try clicking the 'Start Backend' button (if not already started)")
    print("2. Try clicking the 'Start Monitor' button (if not already started)")
    print("3. Try using the memory operation buttons to create, update, delete memories directly from the UI")
    print("4. Check if status indicators update correctly")

if __name__ == "__main__":
    run_tests() 