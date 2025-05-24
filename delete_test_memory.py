"""
Delete Test Memory

This script demonstrates how to delete an existing memory using the OpenMemory client.
It reads a memory ID from last_memory_id.txt (created by create_test_memory.py)
or allows you to specify a memory ID as a command-line argument.
"""

import sys
import os
from tools.openmemory_client import OpenMemoryClient

def delete_memory(memory_id):
    # Initialize the client
    client = OpenMemoryClient(base_url="http://localhost:8000")
    
    # First get the current memory to show what we're deleting
    try:
        memory = client.get_memory(memory_id)
        print("Memory to delete:")
        print(f"ID: {memory['id']}")
        print(f"Content: {memory['content']}")
        print(f"Categories: {memory.get('categories', [])}")
        print("\n" + "-"*50 + "\n")
    except Exception as e:
        print(f"Could not retrieve memory: {str(e)}")
        return False
    
    # Delete the memory
    try:
        # The OpenMemory client doesn't have a direct delete_memory method in its public API
        # So we'll use a custom request to do this
        response = client._make_request(
            method="DELETE",
            endpoint=f"/api/v1/memories/{memory_id}"
        )
        
        print(f"Memory {memory_id} deleted successfully")
        return True
    except Exception as e:
        print(f"Failed to delete memory: {str(e)}")
        return False

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
        print("Usage: python delete_test_memory.py [MEMORY_ID]")
        sys.exit(1)
    
    try:
        success = delete_memory(memory_id)
        if success:
            print("\nYou can view this deletion event in Heticontrol by refreshing the UI.")
            
            # Remove the memory ID file since it's no longer valid
            if os.path.exists("last_memory_id.txt"):
                os.remove("last_memory_id.txt")
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Make sure the OpenMemory backend and MCP server are running.") 