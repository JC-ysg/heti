"""
Create Test Memory

This script demonstrates how to create a new memory using the OpenMemory client.
It creates a sample memory and prints the result.
"""

from tools.openmemory_client import OpenMemoryClient

def create_sample_memory():
    # Initialize the client
    client = OpenMemoryClient(base_url="http://localhost:8000")
    
    # Create a new memory
    result = client.create_memory(
        user_id="test_user",
        content="This is a test memory created for the Heti MVP demo",
        categories=["test", "demo"],
        metadata={"source": "mvp_demo", "importance": "high"}
    )
    
    # Print the result
    print(f"Memory created with ID: {result['id']}")
    print(result)
    
    # Return the memory ID for potential use in other scripts
    return result['id']

if __name__ == "__main__":
    try:
        memory_id = create_sample_memory()
        print("\nTo update or delete this memory, use the ID above in the other scripts.")
        print("You can view this creation event in the 'Creation Events' tab of Heticontrol.")
        
        # Write the memory ID to a file for easy access by other scripts
        with open("last_memory_id.txt", "w") as f:
            f.write(memory_id)
    except Exception as e:
        print(f"Error creating memory: {str(e)}")
        print("Make sure the OpenMemory backend and MCP server are running.") 