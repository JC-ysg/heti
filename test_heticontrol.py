#!/usr/bin/env python3
"""
Test script to verify heticontrol.py functionality.
This script checks if all required components for heticontrol.py are working correctly.
"""

import os
import sys
import importlib
import subprocess
import json
from pathlib import Path

def print_header(message):
    print("\n" + "=" * 80)
    print(f" {message}")
    print("=" * 80)

def check_python_environment():
    print_header("PYTHON ENVIRONMENT")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Current directory: {os.getcwd()}")
    
    # Check system path
    print("\nSystem Path:")
    for path in sys.path:
        print(f"  - {path}")

def check_required_files():
    print_header("REQUIRED FILES")
    
    required_files = [
        "heticontrol.py",
        "tools/openmemory_client.py",
        "agent/memory_monitor.py",
        "config/memory_monitor.yaml",
        "logs/memory_events/memory_events.jsonl"
    ]
    
    for file_path in required_files:
        status = "✅ EXISTS" if os.path.exists(file_path) else "❌ MISSING"
        print(f"{status}: {file_path}")
    
    # Check directory structure
    print("\nKey Directories:")
    for directory in ["logs", "logs/memory_events", "tools", "agent", "config"]:
        status = "✅ EXISTS" if os.path.isdir(directory) else "❌ MISSING"
        print(f"{status}: {directory}")

def check_docker_status():
    print_header("DOCKER STATUS")
    
    try:
        # Check if Docker is running
        result = subprocess.run(
            ["docker", "info"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print("✅ Docker is running")
            
            # Check Docker Compose
            compose_result = subprocess.run(
                ["docker-compose", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if compose_result.returncode == 0:
                print(f"✅ Docker Compose is installed: {compose_result.stdout.strip()}")
            else:
                print("❌ Docker Compose is not installed or not in PATH")
                print(f"Error: {compose_result.stderr.strip()}")
        else:
            print("❌ Docker is not running or not installed")
            print(f"Error: {result.stderr.strip()}")
    except FileNotFoundError:
        print("❌ Docker command not found in PATH")

def check_memory_events():
    print_header("MEMORY EVENTS")
    
    jsonl_path = "logs/memory_events/memory_events.jsonl"
    if os.path.exists(jsonl_path):
        print(f"✅ Memory events log file exists: {jsonl_path}")
        
        # Try to parse the events
        try:
            with open(jsonl_path, 'r') as f:
                lines = f.readlines()
                print(f"Found {len(lines)} event records")
                
                # Parse a sample of events
                events_by_type = {}
                for line in lines:
                    try:
                        event = json.loads(line.strip())
                        event_type = event.get("event_type", "unknown")
                        if event_type not in events_by_type:
                            events_by_type[event_type] = 0
                        events_by_type[event_type] += 1
                    except json.JSONDecodeError:
                        print(f"⚠️ Warning: Invalid JSON in log file: {line[:50]}...")
                
                # Print event counts by type
                print("\nEvent counts by type:")
                for event_type, count in events_by_type.items():
                    print(f"  - {event_type}: {count}")
        except Exception as e:
            print(f"❌ Error reading events log: {str(e)}")
    else:
        print(f"❌ Memory events log file is missing: {jsonl_path}")
        print("Creating empty events file...")
        os.makedirs(os.path.dirname(jsonl_path), exist_ok=True)
        with open(jsonl_path, 'w') as f:
            # Add a sample event to initialize the file
            sample_event = {
                "event_type": "creation",
                "timestamp": "2023-01-01T00:00:00Z",
                "memory_id": "test-memory-id",
                "details": {
                    "user_id": "test-user",
                    "content_summary": "This is a test memory"
                }
            }
            f.write(json.dumps(sample_event) + '\n')
        print(f"✅ Created sample events file: {jsonl_path}")

def check_module_imports():
    print_header("MODULE IMPORTS")
    
    modules_to_check = [
        ("agent.memory_monitor", "MemoryMonitor"),
        ("tools.openmemory_client", "OpenMemoryClient")
    ]
    
    for module_name, class_name in modules_to_check:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, class_name):
                print(f"✅ Successfully imported {class_name} from {module_name}")
            else:
                print(f"❌ Module {module_name} imported but {class_name} class not found")
        except ImportError as e:
            print(f"❌ Failed to import {module_name}: {str(e)}")
            
            # Try to fix the path and retry
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            try:
                module = importlib.import_module(module_name)
                print(f"✅ After path fix: Successfully imported {module_name}")
            except ImportError as e2:
                print(f"❌ After path fix: Still failed to import {module_name}: {str(e2)}")

def check_config():
    print_header("CONFIGURATION")
    
    config_path = "config/memory_monitor.yaml"
    if os.path.exists(config_path):
        print(f"✅ Configuration file exists: {config_path}")
        try:
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            print("Configuration sections:")
            for section in config:
                print(f"  - {section}")
                
            # Check specific important settings
            if "logging" in config:
                log_path = config["logging"].get("event_log_path")
                print(f"\nEvent log path from config: {log_path}")
                if log_path:
                    log_path_exists = os.path.exists(log_path)
                    print(f"{'✅' if log_path_exists else '❌'} Log path exists: {log_path}")
                else:
                    print("❌ No event_log_path specified in config")
        except Exception as e:
            print(f"❌ Error reading config: {str(e)}")
    else:
        print(f"❌ Configuration file is missing: {config_path}")
        # Create a basic config
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        try:
            import yaml
            basic_config = {
                "polling": {
                    "enabled": True,
                    "interval_seconds": 5
                },
                "logging": {
                    "file_enabled": True,
                    "event_log_path": "logs/memory_events/memory_events.jsonl"
                }
            }
            with open(config_path, 'w') as f:
                yaml.dump(basic_config, f)
            print(f"✅ Created basic config file: {config_path}")
        except Exception as e:
            print(f"❌ Error creating config: {str(e)}")

def run_heticontrol_check():
    print_header("RUNNING HETICONTROL CHECK")
    try:
        # Try to import heticontrol to check for syntax errors
        spec = importlib.util.spec_from_file_location("heticontrol", "heticontrol.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print("✅ heticontrol.py loaded successfully (no syntax errors)")
            
            # Check for key classes and functions
            if hasattr(module, "HetiController"):
                controller_class = getattr(module, "HetiController")
                print("✅ HetiController class found")
                
                # Check for key methods
                key_methods = [
                    "start_all", "stop_all", 
                    "create_memory", "update_memory", "delete_memory", "list_memories",
                    "start_memory_monitor", "stop_memory_monitor",
                    "show_create_memory_dialog", "show_update_memory_dialog", 
                    "show_delete_memory_dialog", "show_list_memories_dialog"
                ]
                
                for method in key_methods:
                    if hasattr(controller_class, method):
                        print(f"✅ Method found: {method}")
                    else:
                        print(f"❌ Missing method: {method}")
            else:
                print("❌ HetiController class not found in heticontrol.py")
        else:
            print("❌ Failed to load heticontrol.py")
    except Exception as e:
        print(f"❌ Error checking heticontrol.py: {str(e)}")

def main():
    print_header("HETICONTROL DIAGNOSTICS")
    
    # Run all checks
    check_python_environment()
    check_required_files()
    check_docker_status()
    check_memory_events()
    check_module_imports()
    check_config()
    run_heticontrol_check()
    
    print_header("DIAGNOSTICS COMPLETE")
    print("If you found issues, here are potential fixes:")
    print("")
    print("1. Missing directories: mkdir -p logs/memory_events config")
    print("2. Import errors: Ensure agent and tools directories are in your Python path")
    print("3. Docker issues: Ensure Docker is running and Docker Compose is installed")
    print("4. Missing log file: The script created a sample log file if it was missing")
    print("5. Missing config: The script created a basic config file if it was missing")
    print("")
    print("Now try running: python heticontrol.py")

if __name__ == "__main__":
    main() 