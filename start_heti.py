#!/usr/bin/env python3
"""
Heti Startup and Validation Launcher

This script performs comprehensive validation of the Heti environment before launching the UI:
1. Checks if Docker is running
2. Validates configuration files
3. Ensures required directories exist
4. Checks for port conflicts
5. Verifies backend containers are running (or starts them)
6. Waits for API to be ready
7. Launches the Heti Control UI

Usage: python start_heti.py [--skip-checks] [--timeout SECONDS]
"""

import os
import sys
import time
import socket
import subprocess
import argparse
import json
import yaml
import requests
import shutil
import logging
import datetime
import importlib.util
import tkinter as tk
from tkinter import messagebox, scrolledtext

# Configuration
DOCKER_COMPOSE_DIR = os.path.join("mem0", "openmemory", "openmemory")
DOCKER_COMPOSE_FILE = os.path.join(DOCKER_COMPOSE_DIR, "docker-compose.yml")
CONFIG_DIR = "config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "memory_monitor.yaml")
LOGS_DIR = "logs"
MEMORY_EVENTS_DIR = os.path.join(LOGS_DIR, "memory_events")
DEFAULT_TIMEOUT = 60  # seconds
API_URL = "http://localhost:8000"
API_DOCS_URL = "http://localhost:8000/docs"
API_HEALTH_ENDPOINT = "/api/v1/memories?limit=1"
REQUIRED_PORTS = [8000, 8001]  # API and MCP server ports
LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_FILE = os.path.join(LOGS_DIR, "heti_startup.log")
UI_SCRIPT = "heticontrol.py"

# Setup logging
def setup_logging():
    os.makedirs(LOGS_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("heti_launcher")

logger = setup_logging()

class StartupValidator:
    """Handles validation of the Heti environment and startup sequence."""
    
    def __init__(self, timeout=DEFAULT_TIMEOUT, skip_checks=False):
        self.timeout = timeout
        self.skip_checks = skip_checks
        self.docker_available = False
        self.config_valid = False
        self.directories_ready = False
        self.ports_available = False
        self.containers_running = False
        self.api_ready = False
        self.startup_success = False
        self.issues = []
        self.docker_output = ""
    
    def check_docker_available(self):
        """Check if Docker is installed and running."""
        logger.info("Checking if Docker is available...")
        try:
            result = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info("Docker is running")
                self.docker_available = True
                return True
            else:
                logger.error("Docker is not running or not accessible")
                self.issues.append("Docker is not running or not accessible")
                return False
        except FileNotFoundError:
            logger.error("Docker is not installed or not in PATH")
            self.issues.append("Docker is not installed or not in PATH")
            return False
    
    def check_docker_compose_available(self):
        """Check if docker-compose is available."""
        logger.info("Checking if docker-compose is available...")
        
        # Check for docker-compose file first
        if not os.path.exists(DOCKER_COMPOSE_FILE):
            logger.error(f"Docker compose file not found at {DOCKER_COMPOSE_FILE}")
            self.issues.append(f"Docker compose file not found at {DOCKER_COMPOSE_FILE}")
            return False
        
        try:
            # Try docker compose (v2)
            result = subprocess.run(
                ["docker", "compose", "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info("Docker Compose v2 is available")
                self.docker_compose_cmd = ["docker", "compose"]
                return True
            
            # Try docker-compose (v1)
            result = subprocess.run(
                ["docker-compose", "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info("Docker Compose v1 is available")
                self.docker_compose_cmd = ["docker-compose"]
                return True
            
            logger.error("Neither Docker Compose v1 nor v2 is available")
            self.issues.append("Docker Compose is not installed or not in PATH")
            return False
        except Exception as e:
            logger.error(f"Error checking docker-compose: {str(e)}")
            self.issues.append(f"Error checking docker-compose: {str(e)}")
            return False
    
    def validate_config_files(self):
        """Check if all required configuration files exist and are valid."""
        logger.info("Validating configuration files...")
        
        # Check if config directory exists
        if not os.path.exists(CONFIG_DIR):
            logger.warning(f"Config directory not found, creating {CONFIG_DIR}")
            os.makedirs(CONFIG_DIR, exist_ok=True)
        
        # Check if config file exists
        if not os.path.exists(CONFIG_FILE):
            logger.warning(f"Config file not found: {CONFIG_FILE}")
            
            # Create default config
            self.create_default_config()
            
            if not os.path.exists(CONFIG_FILE):
                logger.error("Failed to create default config file")
                self.issues.append(f"Configuration file missing: {CONFIG_FILE}")
                return False
        
        # Validate config file format (YAML)
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f)
                
            if not isinstance(config, dict):
                logger.error(f"Invalid config format in {CONFIG_FILE}")
                self.issues.append(f"Invalid config format in {CONFIG_FILE}")
                return False
                
            logger.info("Config file is valid")
            self.config_valid = True
            return True
        except Exception as e:
            logger.error(f"Error validating config file: {str(e)}")
            self.issues.append(f"Error in config file: {str(e)}")
            return False
    
    def create_default_config(self):
        """Create a default configuration file."""
        logger.info("Creating default configuration file...")
        
        default_config = {
            "logging": {
                "level": "INFO",
                "event_log_path": os.path.join(MEMORY_EVENTS_DIR, "memory_events.jsonl")
            },
            "monitoring": {
                "poll_interval": 5,
                "deduplication_window": 60
            }
        }
        
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            logger.info(f"Created default config at {CONFIG_FILE}")
            return True
        except Exception as e:
            logger.error(f"Failed to create default config: {str(e)}")
            return False
    
    def ensure_directories_exist(self):
        """Ensure all required directories exist."""
        logger.info("Checking required directories...")
        
        required_dirs = [
            LOGS_DIR,
            MEMORY_EVENTS_DIR,
            os.path.join(".cursor")
        ]
        
        missing_dirs = []
        for directory in required_dirs:
            if not os.path.exists(directory):
                missing_dirs.append(directory)
                logger.warning(f"Directory not found: {directory}")
        
        # Create missing directories
        if missing_dirs:
            logger.info("Creating missing directories...")
            for directory in missing_dirs:
                try:
                    os.makedirs(directory, exist_ok=True)
                    logger.info(f"Created directory: {directory}")
                except Exception as e:
                    logger.error(f"Failed to create directory {directory}: {str(e)}")
                    self.issues.append(f"Failed to create directory {directory}: {str(e)}")
                    return False
        
        self.directories_ready = True
        logger.info("All required directories are present")
        return True
    
    def check_port_availability(self):
        """Check if required ports are available."""
        logger.info("Checking port availability...")
        
        unavailable_ports = []
        for port in REQUIRED_PORTS:
            if self.is_port_in_use(port):
                unavailable_ports.append(port)
                logger.warning(f"Port {port} is already in use")
        
        if unavailable_ports:
            logger.error(f"Ports already in use: {unavailable_ports}")
            self.issues.append(f"Ports already in use: {unavailable_ports}")
            return False
        
        self.ports_available = True
        logger.info("All required ports are available")
        return True
    
    def is_port_in_use(self, port):
        """Check if a port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    def check_containers_running(self):
        """Check if required containers are running."""
        logger.info("Checking if OpenMemory containers are running...")
        
        if not self.docker_available:
            logger.error("Cannot check containers: Docker is not available")
            return False
        
        try:
            # Use the previously determined docker compose command
            result = subprocess.run(
                self.docker_compose_cmd + ["ps", "--format", "json"],
                cwd=DOCKER_COMPOSE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                # Fallback to standard output if JSON format is not supported
                result = subprocess.run(
                    self.docker_compose_cmd + ["ps"],
                    cwd=DOCKER_COMPOSE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    logger.error(f"Failed to check container status: {result.stderr}")
                    self.issues.append(f"Failed to check container status: {result.stderr}")
                    return False
                
                # Check if containers are up from standard output
                self.docker_output = result.stdout
                required_containers = ["openmemory-mcp", "mem0_store"]
                all_running = all(container in result.stdout for container in required_containers)
                
                if all_running:
                    logger.info("All required containers are running")
                    self.containers_running = True
                    return True
                else:
                    logger.warning("Not all required containers are running")
                    return False
            
            # Parse JSON output
            try:
                containers = json.loads(result.stdout)
                if not containers:  # Empty list
                    logger.warning("No containers found")
                    return False
                    
                # Check if all required containers are running
                all_running = all(container.get("State") == "running" for container in containers)
                
                if all_running:
                    logger.info("All required containers are running")
                    self.containers_running = True
                    return True
                else:
                    logger.warning("Not all required containers are running")
                    return False
            except json.JSONDecodeError:
                # Handle case where output is not valid JSON
                logger.warning("Could not parse container status as JSON")
                self.docker_output = result.stdout
                return False
            
        except Exception as e:
            logger.error(f"Error checking container status: {str(e)}")
            self.issues.append(f"Error checking container status: {str(e)}")
            return False
    
    def start_containers(self):
        """Start the OpenMemory containers using docker-compose."""
        logger.info("Starting OpenMemory containers...")
        
        if not self.docker_available:
            logger.error("Cannot start containers: Docker is not available")
            return False
        
        try:
            result = subprocess.run(
                self.docker_compose_cmd + ["up", "-d"],
                cwd=DOCKER_COMPOSE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info("Containers started successfully")
                self.docker_output = result.stdout
                return True
            else:
                logger.error(f"Failed to start containers: {result.stderr}")
                self.docker_output = result.stderr
                self.issues.append(f"Failed to start containers: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error starting containers: {str(e)}")
            self.issues.append(f"Error starting containers: {str(e)}")
            return False
    
    def wait_for_api_ready(self):
        """Wait for the API to be ready and responding."""
        logger.info(f"Waiting up to {self.timeout} seconds for API to be ready...")
        
        url = f"{API_URL}{API_HEALTH_ENDPOINT}"
        start_time = time.time()
        end_time = start_time + self.timeout
        
        while time.time() < end_time:
            try:
                # First check if the port is open
                if not self.is_port_in_use(8000):
                    logger.debug("Port 8000 is not yet open")
                    time.sleep(2)
                    continue
                    
                # Try to connect to the API
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    logger.info("API is ready and responding")
                    self.api_ready = True
                    return True
                else:
                    logger.debug(f"API returned status code: {response.status_code}")
            except requests.exceptions.ConnectionError:
                logger.debug("Connection refused")
            except requests.exceptions.Timeout:
                logger.debug("Request timed out")
            except Exception as e:
                logger.debug(f"Error connecting to API: {str(e)}")
                
            # Wait before next attempt
            time.sleep(2)
            
            # Calculate and log remaining time every 10 seconds
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0:
                remaining = int(self.timeout - elapsed)
                logger.info(f"Still waiting for API... {remaining}s remaining")
        
        logger.error(f"API did not become ready within {self.timeout} seconds")
        self.issues.append(f"API did not become ready within {self.timeout} seconds")
        return False
    
    def check_ui_script_exists(self):
        """Check if the UI script exists."""
        logger.info(f"Checking if UI script exists: {UI_SCRIPT}")
        
        if not os.path.exists(UI_SCRIPT):
            logger.error(f"UI script not found: {UI_SCRIPT}")
            self.issues.append(f"UI script not found: {UI_SCRIPT}")
            return False
        
        logger.info("UI script found")
        return True
    
    def start_ui(self):
        """Start the Heti UI."""
        logger.info("Starting Heti UI...")
        
        if not self.check_ui_script_exists():
            return False
        
        try:
            # Import the UI module dynamically
            spec = importlib.util.spec_from_file_location("heticontrol", UI_SCRIPT)
            heticontrol = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(heticontrol)
            
            # Set startup information in the module
            heticontrol.LAUNCHER_VALIDATED = True
            heticontrol.STARTUP_ISSUES = self.issues
            heticontrol.API_STATUS = self.api_ready
            
            # Start the UI
            logger.info("Launching Heti UI")
            
            # Create root window
            root = tk.Tk()
            heticontrol.HetiController(root)
            root.mainloop()
            
            return True
        except Exception as e:
            logger.error(f"Error starting UI: {str(e)}")
            self.issues.append(f"Error starting UI: {str(e)}")
            return False
    
    def run_full_validation(self):
        """Run the full validation sequence."""
        logger.info("Starting Heti validation sequence")
        
        if self.skip_checks:
            logger.info("Skipping validation checks as requested")
            self.startup_success = True
            return True
        
        # Check Docker
        if not self.check_docker_available():
            logger.error("Docker validation failed")
            self.show_error_dialog("Docker Error", 
                                   "Docker is not running or not available.\n\n"
                                   "Please ensure Docker is installed and running before launching Heti.")
            return False
        
        # Check docker-compose
        if not self.check_docker_compose_available():
            logger.error("Docker Compose validation failed")
            self.show_error_dialog("Docker Compose Error",
                                  "Docker Compose is not available.\n\n"
                                  "Please ensure Docker Compose is installed and in your PATH.")
            return False
            
        # Validate directories
        self.ensure_directories_exist()
        
        # Validate config files
        self.validate_config_files()
        
        # Check port availability
        if not self.check_port_availability():
            self.show_port_conflict_dialog()
            return False
        
        # Check if containers are running
        if not self.check_containers_running():
            logger.info("Containers not running, attempting to start them")
            if not self.start_containers():
                self.show_error_dialog("Container Error",
                                      f"Failed to start OpenMemory containers.\n\n"
                                      f"Docker output:\n{self.docker_output}")
                return False
        
        # Wait for API to be ready
        if not self.wait_for_api_ready():
            self.show_api_timeout_dialog()
            return False
        
        logger.info("Validation sequence completed successfully")
        self.startup_success = True
        return True
    
    def show_error_dialog(self, title, message):
        """Show an error dialog with the given title and message."""
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        messagebox.showerror(title, message)
        root.destroy()
    
    def show_port_conflict_dialog(self):
        """Show a dialog for port conflicts."""
        root = tk.Tk()
        root.withdraw()
        
        result = messagebox.askretrycancel(
            "Port Conflict",
            f"Required ports {REQUIRED_PORTS} are already in use.\n\n"
            "Please close any applications using these ports and try again.\n\n"
            "Common issues:\n"
            "- Another instance of Heti is running\n"
            "- Development servers using the same ports\n"
            "- Other Docker containers using these ports"
        )
        
        root.destroy()
        
        if result:  # Retry
            self.check_port_availability()
    
    def show_api_timeout_dialog(self):
        """Show a dialog for API timeout."""
        root = tk.Tk()
        root.withdraw()
        
        result = messagebox.askyesno(
            "API Connection Timeout",
            f"Could not connect to the OpenMemory API after {self.timeout} seconds.\n\n"
            "Would you like to continue anyway?\n\n"
            "(The UI will launch but may not be able to communicate with the backend.)"
        )
        
        root.destroy()
        
        if result:  # Yes
            self.startup_success = True

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Heti Startup and Validation Launcher")
    parser.add_argument("--skip-checks", action="store_true", help="Skip validation checks")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, 
                        help=f"Timeout in seconds for API readiness (default: {DEFAULT_TIMEOUT})")
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_arguments()
    
    validator = StartupValidator(timeout=args.timeout, skip_checks=args.skip_checks)
    if validator.run_full_validation() or args.skip_checks:
        validator.start_ui()
        return 0
    else:
        logger.error("Validation failed, not starting UI")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 