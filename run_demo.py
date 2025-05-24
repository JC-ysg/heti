"""
Heti Demo Runner

This script provides a guided demo of the Heti system. It walks users through
the steps of testing memory operations and viewing events in the UI.
"""

import os
import sys
import subprocess
import time
import argparse

def print_header(message):
    print("\n" + "=" * 80)
    print(f" {message}")
    print("=" * 80)

def run_cmd(cmd, description=None):
    if description:
        print(f"\n> {description}")
    
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd)

def check_backend_running():
    """Check if the OpenMemory backend is running"""
    try:
        import requests
        response = requests.get("http://localhost:8000/docs", timeout=2)
        return response.status_code == 200
    except:
        return False

def run_demo(skip_memory_ops=False, skip_errors=False):
    print_header("HETI DEMO")
    print("\nThis script will demonstrate the Heti Memory Monitoring System.")
    print("It assumes you have already started:")
    print("  1. The OpenMemory backend (docker-compose in mem0/openmemory/openmemory)")
    print("  2. The MCP server (uvicorn Heti.mcp_server:app --port 8001)")
    print("  3. The Heti Control UI (python heticontrol.py)")
    
    # Check if backend is running
    if not check_backend_running():
        print("\nWARNING: The OpenMemory backend doesn't appear to be running.")
        print("You may need to start it with:")
        print("  cd mem0/openmemory/openmemory")
        print("  docker-compose up -d")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Demo aborted. Please start the backend and try again.")
            return
    
    print("\nPlease ensure you have the Heticontrol UI open and have started the Memory Monitor.")
    input("Press Enter to continue when ready...")
    
    if not skip_memory_ops:
        # Create a memory
        print_header("CREATING A TEST MEMORY")
        run_cmd([sys.executable, "create_test_memory.py"])
        input("\nPress Enter after checking the Creation Events panel in the UI...")
        
        # Update the memory
        print_header("UPDATING THE TEST MEMORY")
        run_cmd([sys.executable, "update_test_memory.py"])
        input("\nPress Enter after checking the Creation Events panel in the UI...")
    
    if not skip_errors:
        # Generate errors
        print_header("GENERATING ERROR EVENTS")
        run_cmd([sys.executable, "generate_error.py"])
        input("\nPress Enter after checking the Error Events panel in the UI...")
    
    if not skip_memory_ops:
        # Delete the memory
        print_header("DELETING THE TEST MEMORY")
        run_cmd([sys.executable, "delete_test_memory.py"])
        input("\nPress Enter after checking the UI for deletion events...")
    
    print_header("DEMO COMPLETE")
    print("\nYou have successfully run through the Heti demo!")
    print("You can continue exploring the UI or run the demo again.")
    print("\nTo shut down the system:")
    print("1. Close the Heticontrol UI")
    print("2. Stop the MCP server (Ctrl+C)")
    print("3. Stop the OpenMemory backend:")
    print("   cd mem0/openmemory/openmemory")
    print("   docker-compose down")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Heti demo")
    parser.add_argument("--skip-memory", action="store_true", help="Skip memory creation/update/deletion steps")
    parser.add_argument("--skip-errors", action="store_true", help="Skip error generation steps")
    
    args = parser.parse_args()
    
    run_demo(
        skip_memory_ops=args.skip_memory,
        skip_errors=args.skip_errors
    ) 