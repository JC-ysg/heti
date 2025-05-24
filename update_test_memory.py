"""
Update Test Memory

This script demonstrates how to update an existing memory using the OpenMemory client.
It reads a memory ID from last_memory_id.txt (created by create_test_memory.py)
or allows you to specify a memory ID as a command-line argument.
"""

import sys
import os
from tools.openmemory_client import OpenMemoryClient

def update_memory(memory_id):
    # Initialize the client
    client = OpenMemoryClient(base_url="http://localhost:8000")
    
    # First get the current memory to show before/after
    try:
        before = client.get_memory(memory_id)
        print("Original memory:")
        print(before)
        print("\n" + "-"*50 + "\n")
    except Exception as e:
        print(f"Could not retrieve original memory: {str(e)}")
        return
    
    # Update the memory
    result = client.update_memory(
        memory_id=memory_id,
        content="This memory has been updated for the Heti MVP demo",
        categories=["test", "demo", "updated"],
        metadata={"source": "mvp_demo", "importance": "high", "status": "updated"}
    )
    
    # Print the result
    print("Memory updated:")
    print(f"Memory ID: {result['id']}")
    print(result)
    
    return result['id']

if __name__ == "__main__":
    memory_id = None
    
    # Check if memory ID is provided as argument
    if len(sys.argv) > 1:
        memory_id = sys.argv[1]
    else:
        # Try to read from file
        if os.path.exists("last_memory_id.txt"):
            with open("last_memory_id.txt", "r") as f:
                memory_id = f.read().strip()
    
    if not memory_id:
        print("Please provide a memory ID as argument, or run create_test_memory.py first.")
        print("Usage: python update_test_memory.py [MEMORY_ID]")
        sys.exit(1)
    
    try:
        update_memory(memory_id)
        print("\nYou can view this update event in Heticontrol by refreshing the 'Creation Events' tab.")
    except Exception as e:
        print(f"Error updating memory: {str(e)}")
        print("Make sure the OpenMemory backend and MCP server are running.") 