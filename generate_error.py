"""
Generate Error Events

This script demonstrates how to generate various error events that will be
captured by the Memory Monitor and displayed in the Error Events tab.
"""

from tools.openmemory_client import OpenMemoryClient
import uuid
import time

def generate_errors():
    # Initialize the client
    client = OpenMemoryClient(base_url="http://localhost:8000")
    
    print("Generating various error events for demonstration...\n")
    
    # 1. Try to get a non-existent memory (404 Not Found)
    try:
        print("1. Attempting to get non-existent memory...")
        non_existent_id = str(uuid.uuid4())
        result = client.get_memory(non_existent_id)
    except Exception as e:
        print(f"  Error generated: {str(e)}")
    
    time.sleep(1)  # Small delay between errors
    
    # 2. Try to create a memory with invalid data (400 Bad Request)
    try:
        print("\n2. Attempting to create memory with invalid data...")
        result = client.create_memory(
            user_id="", # Empty user_id will fail validation
            content="This should fail",
            categories=["test"],
            metadata={}
        )
    except Exception as e:
        print(f"  Error generated: {str(e)}")
    
    time.sleep(1)
    
    # 3. Try to update a non-existent memory (404 Not Found)
    try:
        print("\n3. Attempting to update non-existent memory...")
        non_existent_id = str(uuid.uuid4())
        result = client.update_memory(
            memory_id=non_existent_id,
            content="This should fail",
            categories=["test"],
            metadata={}
        )
    except Exception as e:
        print(f"  Error generated: {str(e)}")
    
    time.sleep(1)
    
    # 4. Try to filter with invalid query (400 Bad Request)
    try:
        print("\n4. Attempting to filter with invalid query...")
        result = client.filter_memories(
            filter_query={"invalid": {"operator": "nonexistent", "value": "test"}}
        )
    except Exception as e:
        print(f"  Error generated: {str(e)}")
    
    print("\nAll error events generated. Go to the 'Error Events' tab in Heticontrol to see them.")
    print("You may need to click 'Refresh Events' if auto-refresh is disabled.")

if __name__ == "__main__":
    try:
        generate_errors()
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        print("Make sure the OpenMemory backend and MCP server are running.") 