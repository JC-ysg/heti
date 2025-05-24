import os
import threading
import subprocess
import signal
import time
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, simpledialog, filedialog
import datetime
import re
import json
import yaml
import uuid
import socket
import requests
import importlib
import importlib.util
from typing import Dict, Any, List, Optional

# Import Memory Monitor
try:
    from agent.memory_monitor import MemoryMonitor
except ImportError:
    # Add parent directory to path if needed
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from agent.memory_monitor import MemoryMonitor
    except ImportError:
        # Will be initialized to None if import fails
        MemoryMonitor = None

# Import OpenMemory Client
try:
    from tools.openmemory_client import OpenMemoryClient
except ImportError:
    # Will be initialized to None if import fails
    OpenMemoryClient = None

# Global variables for launcher integration
LAUNCHER_VALIDATED = False  # Whether the launcher has validated the environment
STARTUP_ISSUES = []  # List of issues found during startup
API_STATUS = False  # Whether the API is available

# Configuration
DOCKER_COMPOSE_DIR = os.path.join("mem0", "openmemory", "openmemory")
MCP_SERVER_CMD = ["uvicorn", "Heti.mcp_server:app", "--port", "8001", "--reload"]
MONITOR_CMD = [
    sys.executable,
    "-u",
    os.path.join("Heti", "loop_scripts", "monitor_embedder.py"),
    "--interval",
    "5",
    "--duration",
    "0",
]
API_TEST_CMD = ["python", "-m", "pytest", "tests/test_openmemory_client.py", "-v"]
LOG_DIR = os.path.join(".cursor")
OPENMEMORY_DASHBOARD_URL = "http://localhost:8765/docs"
OPENMEMORY_API_URL = "http://localhost:8765"
API_CONNECTION_CHECK_ENDPOINT = "/api/v1/memories?limit=1&user_id=default_user"  # Updated to use correct default user
API_CONNECTION_TIMEOUT = 10  # Increased timeout for connection check
API_STARTUP_GRACE_PERIOD = 30  # Grace period in seconds to wait for API to start
API_AUTO_RETRY_INTERVAL = 5000  # Auto-retry interval in milliseconds

# Memory Monitor Events UI Configuration
CREATION_EVENTS_MAX_DISPLAY = 20  # Number of creation events to display
CREATION_EVENTS_REFRESH_INTERVAL = 5000  # Refresh interval in milliseconds
UPDATE_EVENTS_MAX_DISPLAY = 20  # Number of update events to display
UPDATE_EVENTS_REFRESH_INTERVAL = 5000  # Refresh interval in milliseconds
DELETION_EVENTS_MAX_DISPLAY = 20  # Number of deletion events to display
DELETION_EVENTS_REFRESH_INTERVAL = 5000  # Refresh interval in milliseconds
ERROR_EVENTS_MAX_DISPLAY = 20  # Number of error events to display
ERROR_EVENTS_REFRESH_INTERVAL = 5000  # Refresh interval in milliseconds

# Memory Manager settings
API_BASE_URL = "http://localhost:8765"  # Updated to match OPENMEMORY_API_URL
DEFAULT_USER_ID = "default_user"  # Updated to match OpenMemory configuration
DEFAULT_APP_ID = "heti-app"

class HetiController:
    """
    Main controller for the Heti system.
    
    Provides a unified interface for:
    - Starting/stopping backend components
    - Managing memory operations (create, update, delete)
    - Viewing memory events
    - Monitoring system status
    """
    
    def create_memory(self, user_id: str, content: str, metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Create a new memory using the OpenMemory API.
        
        Args:
            user_id: User identifier for the memory
            content: Text content of the memory
            metadata: Optional metadata for the memory
            
        Returns:
            The created memory object or None if there was an error
        """
        if OpenMemoryClient is None:
            self.log_error("OpenMemoryClient is not available")
            return None
            
        try:
            # Initialize client
            client = OpenMemoryClient(base_url=API_BASE_URL)
            
            # Create memory with correct parameter names
            memory = client.create_memory(
                user_id=user_id,
                text=content,  # Changed from content to text
                infer=True,
                app="heti"
            )
            
            # Log success
            self.log_operation(f"Created memory with ID: {memory.get('id')}")
            
            return memory
        except Exception as e:
            self.log_error(f"Error creating memory: {str(e)}")
            return None
    
    def update_memory(self, memory_id: str, content: str, metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Update an existing memory using the OpenMemory API.
        
        Args:
            memory_id: ID of the memory to update
            content: New text content
            metadata: New metadata (optional)
            
        Returns:
            The updated memory object or None if there was an error
        """
        if OpenMemoryClient is None:
            self.log_error("OpenMemoryClient is not available")
            return None
            
        try:
            # Initialize client
            client = OpenMemoryClient(base_url=API_BASE_URL)
            
            # Update memory with correct parameter names
            memory = client.update_memory(
                memory_id=memory_id,
                content=content,  # This is correct as per the client implementation
                metadata=metadata
            )
            
            # Log success
            self.log_operation(f"Updated memory with ID: {memory_id}")
            
            return memory
        except Exception as e:
            self.log_error(f"Error updating memory: {str(e)}")
            return None
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory using the OpenMemory API.
        
        Args:
            memory_id: ID of the memory to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if OpenMemoryClient is None:
            self.log_error("OpenMemoryClient is not available")
            return False
            
        try:
            # Initialize client
            client = OpenMemoryClient(base_url=API_BASE_URL)
            
            # The OpenMemory client doesn't have a direct delete_memory method in its public API
            # So we'll use a custom request to do this
            response = client._make_request(
                method="DELETE",
                endpoint=f"/api/v1/memories/{memory_id}"
            )
            
            # Log success
            self.log_operation(f"Deleted memory with ID: {memory_id}")
            
            return True
        except Exception as e:
            self.log_error(f"Error deleting memory: {str(e)}")
            return False
    
    def list_memories(self, user_id: str, page: int = 1, size: int = 10) -> Optional[Dict[str, Any]]:
        """
        List memories for a specific user.
        
        Args:
            user_id: User identifier to filter memories
            page: Page number for pagination
            size: Number of memories per page
            
        Returns:
            Dict with memories and pagination info, or None if there was an error
        """
        if OpenMemoryClient is None:
            self.log_error("OpenMemoryClient is not available")
            return None
            
        try:
            # Initialize client
            client = OpenMemoryClient(base_url=API_BASE_URL)
            
            # List memories
            result = client.list_memories(
                user_id=user_id,
                page=page,
                size=size
            )
            
            # Log success
            self.log_operation(f"Listed memories for user: {user_id}, found {len(result.get('memories', []))} memories")
            
            return result
        except Exception as e:
            self.log_error(f"Error listing memories: {str(e)}")
            return None
    
    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific memory by ID.
        
        Args:
            memory_id: ID of the memory to retrieve
            
        Returns:
            The memory object or None if not found or error
        """
        if OpenMemoryClient is None:
            self.log_error("OpenMemoryClient is not available")
            return None
            
        try:
            # Initialize client
            client = OpenMemoryClient(base_url=API_BASE_URL)
            
            # Get memory
            memory = client.get_memory(memory_id)
            
            # Log success
            self.log_operation(f"Retrieved memory with ID: {memory_id}")
            
            return memory
        except Exception as e:
            self.log_error(f"Error retrieving memory: {str(e)}")
            return None
    
    def log_operation(self, message: str):
        """Log a user or system operation with timestamp."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        # Add to UI log if available
        if hasattr(self, 'operation_log_text'):
            self.operation_log_text.insert(tk.END, log_message + "\n")
            self.operation_log_text.see(tk.END)
        
        # Print to console as well
        print(log_message)
    
    def log_error(self, message: str):
        """Log an error with timestamp."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_message = f"[{timestamp}] ERROR: {message}"
        
        # Add to UI log if available
        if hasattr(self, 'operation_log_text'):
            self.operation_log_text.insert(tk.END, error_message + "\n")
            self.operation_log_text.see(tk.END)
            
        # Print to console as well
        print(error_message)
        
        # Show error popup if messagebox is available
        if messagebox:
            messagebox.showerror("Error", message)
    
    def check_api_connection(self) -> tuple[bool, str]:
        """
        Check if the OpenMemory API is available.
        
        Returns:
            tuple: (is_connected, error_message)
        """
        # First check if the port is open to provide better diagnostics
        def check_port_open(host, port):
            """Check if the specified port is open on the host."""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, port))
                sock.close()
                return result == 0
            except Exception:
                return False
        
        # Check if port 8000 is open
        port_open = check_port_open("localhost", 8765)  # Updated to check port 8765
        if not port_open:
            return False, "Port 8765 is not open. OpenMemory API server is not running."
        
        # If port is open, try to make the API request
        try:
            url = f"{OPENMEMORY_API_URL}{API_CONNECTION_CHECK_ENDPOINT}"
            self.log_operation(f"Checking API connection: {url}")
            response = requests.get(url, timeout=API_CONNECTION_TIMEOUT)
            
            if response.status_code == 200:
                # Try parsing the response to confirm it's valid JSON
                try:
                    data = response.json()
                    memory_count = len(data.get('memories', []))
                    return True, f"Connected successfully. Found {memory_count} memories."
                except Exception as e:
                    return False, f"API returned 200 but invalid JSON: {str(e)}"
            else:
                return False, f"API returned status code: {response.status_code}"
        except requests.exceptions.ConnectionError as e:
            return False, "Connection refused. OpenMemory API is not running."
        except requests.exceptions.Timeout as e:
            return False, "Connection timed out. OpenMemory API is not responding."
        except Exception as e:
            return False, f"Error connecting to OpenMemory API: {str(e)}"
    
    def update_connection_status(self):
        """Update the connection status indicator in the UI."""
        is_connected, error_message = self.check_api_connection()
        
        if is_connected:
            self.connection_status_indicator.config(
                text="✅ Connected to OpenMemory",
                fg="green"
            )
            self.retry_connection_button.config(state=tk.DISABLED)
            self.log_operation("Successfully connected to OpenMemory API")
            
            # Enable dependent buttons
            if self.running:
                self.test_button.config(state=tk.NORMAL)
                self.dashboard_button.config(state=tk.NORMAL)
        else:
            self.connection_status_indicator.config(
                text="❌ OpenMemory backend not running",
                fg="red"
            )
            self.retry_connection_button.config(state=tk.NORMAL)
            self.log_error(f"Failed to connect to OpenMemory API: {error_message}")
            
            # Disable dependent buttons
            self.test_button.config(state=tk.DISABLED)
            self.dashboard_button.config(state=tk.DISABLED)
        
        # Update tooltip
        self.connection_status_tooltip.config(text=error_message if not is_connected else "")
        
        return is_connected
    
    def retry_connection(self):
        """Retry the connection to the OpenMemory API."""
        self.connection_status_indicator.config(
            text="🔄 Checking connection...",
            fg="blue"
        )
        self.retry_connection_button.config(state=tk.DISABLED)
        self.root.update()  # Force UI update
        
        # Schedule the actual check to allow UI to update
        self.root.after(100, self.update_connection_status)
        
    def schedule_auto_retry_connection(self):
        """Schedule automatic retry for connection status check."""
        # Only schedule auto-retry if currently disconnected
        is_connected, _ = self.check_api_connection()
        if not is_connected:
            self.root.after(API_AUTO_RETRY_INTERVAL, self.auto_retry_connection)
    
    def auto_retry_connection(self):
        """Automatically retry the connection without user intervention."""
        # Only perform auto-retry if button is currently enabled (disconnected state)
        if self.retry_connection_button.cget('state') == tk.NORMAL:
            self.connection_status_indicator.config(
                text="🔄 Auto-retrying connection...",
                fg="blue"
            )
            self.root.update()  # Force UI update
            
            # Check connection
            is_connected = self.update_connection_status()
            
            # If still not connected, schedule another retry
            if not is_connected:
                self.root.after(API_AUTO_RETRY_INTERVAL, self.auto_retry_connection)

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Heti Control Panel")
        self.root.geometry("1000x700")  # Increased window size

        # Initialize Memory Monitor
        self.memory_monitor = None
        if MemoryMonitor is not None:
            try:
                self.memory_monitor = MemoryMonitor()
            except Exception as e:
                print(f"Error initializing Memory Monitor: {str(e)}")

        # Status bar at the bottom
        self.status_bar = tk.Label(
            root, 
            text="Ready", 
            bd=1, 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Main control frame
        control_frame = tk.Frame(root)
        control_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Connection status frame - NEW
        connection_frame = tk.LabelFrame(control_frame, text="API Connection Status")
        connection_frame.pack(side=tk.TOP, padx=10, pady=5, fill=tk.X)
        
        # Connection status indicator
        self.connection_status_indicator = tk.Label(
            connection_frame,
            text="🔄 Checking connection...",
            fg="blue",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=5
        )
        self.connection_status_indicator.pack(side=tk.LEFT)
        
        # Connection retry button
        self.retry_connection_button = tk.Button(
            connection_frame,
            text="Retry Connection",
            command=self.retry_connection,
            state=tk.DISABLED
        )
        self.retry_connection_button.pack(side=tk.RIGHT, padx=10)
        
        # Troubleshoot button
        self.troubleshoot_button = tk.Button(
            connection_frame,
            text="Troubleshoot",
            command=self.show_troubleshooting_dialog,
            padx=10
        )
        self.troubleshoot_button.pack(side=tk.RIGHT, padx=10)
        
        # Error message tooltip/label
        self.connection_status_tooltip = tk.Label(
            connection_frame,
            text="",
            fg="red",
            font=("Arial", 9),
            wraplength=500
        )
        self.connection_status_tooltip.pack(side=tk.BOTTOM, fill=tk.X, padx=10)
        
        # Create a frame for backend controls
        backend_frame = tk.LabelFrame(control_frame, text="Backend Controls")
        backend_frame.pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # Services control button
        self.button = tk.Button(backend_frame, text="Start Backend", width=15, command=self.toggle)
        self.button.pack(side=tk.TOP, padx=5, pady=5)

        # Memory Monitor controls
        self.mm_start_button = tk.Button(
            backend_frame,
            text="Start Monitor",
            width=15,
            command=self.start_memory_monitor,
            state=tk.NORMAL if self.memory_monitor is not None else tk.DISABLED
        )
        self.mm_start_button.pack(side=tk.TOP, padx=5, pady=5)
        
        self.mm_stop_button = tk.Button(
            backend_frame,
            text="Stop Monitor",
            width=15,
            command=self.stop_memory_monitor,
            state=tk.DISABLED
        )
        self.mm_stop_button.pack(side=tk.TOP, padx=5, pady=5)

        # API Test Suite button
        self.test_button = tk.Button(
            backend_frame, 
            text="Run API Tests", 
            width=15, 
            command=self.run_api_tests,
            state=tk.DISABLED  # Initially disabled until services are running
        )
        self.test_button.pack(side=tk.TOP, padx=5, pady=5)
        
        # Dashboard button
        self.dashboard_button = tk.Button(
            backend_frame,
            text="Open Dashboard",
            width=15,
            command=self.open_dashboard,
            state=tk.DISABLED  # Initially disabled until services are running
        )
        self.dashboard_button.pack(side=tk.TOP, padx=5, pady=5)
        
        # Create a frame for memory operations
        memory_frame = tk.LabelFrame(control_frame, text="Memory Operations")
        memory_frame.pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # Memory Create button
        self.create_memory_button = tk.Button(
            memory_frame,
            text="Create Memory",
            width=15,
            command=self.show_create_memory_dialog
        )
        self.create_memory_button.pack(side=tk.TOP, padx=5, pady=5)
        
        # Memory Update button
        self.update_memory_button = tk.Button(
            memory_frame,
            text="Update Memory",
            width=15,
            command=self.show_update_memory_dialog
        )
        self.update_memory_button.pack(side=tk.TOP, padx=5, pady=5)
        
        # Memory Delete button
        self.delete_memory_button = tk.Button(
            memory_frame,
            text="Delete Memory",
            width=15,
            command=self.show_delete_memory_dialog
        )
        self.delete_memory_button.pack(side=tk.TOP, padx=5, pady=5)
        
        # Memory List button
        self.list_memories_button = tk.Button(
            memory_frame,
            text="List Memories",
            width=15,
            command=self.show_list_memories_dialog
        )
        self.list_memories_button.pack(side=tk.TOP, padx=5, pady=5)
        
        # Status indicator
        self.status_frame = tk.Frame(root)
        self.status_frame.pack(pady=5, padx=20, fill=tk.X)
        
        self.status_label = tk.Label(
            self.status_frame, 
            text="Status: Services Stopped", 
            fg="gray",
            font=("Arial", 10, "bold")
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Operations Log tab
        self.operations_log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.operations_log_frame, text="Operations Log")
        
        # Operations log display
        self.operation_log_text = scrolledtext.ScrolledText(self.operations_log_frame, height=10)
        self.operation_log_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        # Operations log controls
        self.operations_log_buttons = tk.Frame(self.operations_log_frame)
        self.operations_log_buttons.pack(pady=5, padx=10, fill=tk.X)
        
        self.clear_operations_log_button = tk.Button(
            self.operations_log_buttons,
            text="Clear Log",
            command=lambda: self.operation_log_text.delete(1.0, tk.END)
        )
        self.clear_operations_log_button.pack(side=tk.LEFT, padx=5)
        
        # Test results tab
        self.results_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.results_frame, text="API Test Results")
        
        # Test summary frame
        self.summary_frame = tk.Frame(self.results_frame)
        self.summary_frame.pack(pady=5, padx=10, fill=tk.X)
        
        self.summary_label = tk.Label(
            self.summary_frame,
            text="API Integration Status: Not Tested",
            fg="gray",
            font=("Arial", 12, "bold")
        )
        self.summary_label.pack(anchor=tk.W)
        
        # Endpoint status table
        self.endpoints_frame = tk.Frame(self.results_frame)
        self.endpoints_frame.pack(pady=5, padx=10, fill=tk.X)
        
        # Column headers
        tk.Label(self.endpoints_frame, text="Endpoint", width=20, font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W)
        tk.Label(self.endpoints_frame, text="Method", width=10, font=("Arial", 10, "bold")).grid(row=0, column=1)
        tk.Label(self.endpoints_frame, text="Status", width=15, font=("Arial", 10, "bold")).grid(row=0, column=2)
        tk.Label(self.endpoints_frame, text="Tests", width=10, font=("Arial", 10, "bold")).grid(row=0, column=3)
        
        # Endpoint rows
        self.endpoint_statuses = {}
        endpoints = [
            ("/api/v1/memories", "POST", "Create"),
            ("/api/v1/memories", "GET", "List"),
            ("/api/v1/memories/{id}", "GET", "Get"),
            ("/api/v1/memories/{id}", "PUT", "Update"),
            ("/api/v1/memories/filter", "POST", "Filter")
        ]
        
        for i, (endpoint, method, name) in enumerate(endpoints, 1):
            tk.Label(self.endpoints_frame, text=endpoint, anchor=tk.W).grid(row=i, column=0, sticky=tk.W)
            tk.Label(self.endpoints_frame, text=method).grid(row=i, column=1)
            status_label = tk.Label(self.endpoints_frame, text="Not Tested", fg="gray")
            status_label.grid(row=i, column=2)
            tests_label = tk.Label(self.endpoints_frame, text="0/0")
            tests_label.grid(row=i, column=3)
            
            self.endpoint_statuses[name.lower()] = {
                "status_label": status_label,
                "tests_label": tests_label
            }
        
        # Test output
        self.output_label = tk.Label(self.results_frame, text="Test Output:", anchor=tk.W)
        self.output_label.pack(pady=(10, 5), padx=10, anchor=tk.W)
        
        self.output_text = scrolledtext.ScrolledText(self.results_frame, height=15)
        self.output_text.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        # Logs tab
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="API Logs")
        
        self.log_text = scrolledtext.ScrolledText(self.logs_frame, height=20)
        self.log_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        self.log_buttons_frame = tk.Frame(self.logs_frame)
        self.log_buttons_frame.pack(pady=5, padx=10, fill=tk.X)
        
        self.clear_logs_button = tk.Button(
            self.log_buttons_frame,
            text="Clear Logs",
            command=self.clear_logs
        )
        self.clear_logs_button.pack(side=tk.LEFT, padx=5)
        
        self.refresh_logs_button = tk.Button(
            self.log_buttons_frame,
            text="Refresh Logs",
            command=self.refresh_logs
        )
        self.refresh_logs_button.pack(side=tk.LEFT, padx=5)
        
        # Memory Monitor tab
        self.memory_monitor_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.memory_monitor_frame, text="Memory Monitor")
        
        # Memory Monitor status display
        self.mm_status_frame = tk.Frame(self.memory_monitor_frame)
        self.mm_status_frame.pack(pady=10, padx=20, fill=tk.X)
        
        self.mm_status_label = tk.Label(
            self.mm_status_frame,
            text="Memory Monitor Status: Not Initialized",
            fg="gray",
            font=("Arial", 12, "bold")
        )
        self.mm_status_label.pack(anchor=tk.W)
        
        # Memory Monitor statistics
        self.mm_stats_frame = tk.Frame(self.memory_monitor_frame)
        self.mm_stats_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Create a grid for stats
        stats_headers = ["Event Type", "Count", "Last Detected"]
        for i, header in enumerate(stats_headers):
            tk.Label(
                self.mm_stats_frame, 
                text=header, 
                font=("Arial", 10, "bold")
            ).grid(row=0, column=i, padx=5, pady=5, sticky=tk.W)
        
        # Event type rows
        self.mm_event_rows = {}
        event_types = [
            "memory.created", 
            "memory.updated", 
            "memory.deleted", 
            "memory.accessed", 
            "embedding.started", 
            "embedding.completed", 
            "memory.error", 
            "memory.batch_operation"
        ]
        
        for i, event_type in enumerate(event_types, 1):
            # Event type label
            tk.Label(
                self.mm_stats_frame, 
                text=event_type
            ).grid(row=i, column=0, padx=5, pady=2, sticky=tk.W)
            
            # Count label
            count_label = tk.Label(self.mm_stats_frame, text="0")
            count_label.grid(row=i, column=1, padx=5, pady=2)
            
            # Last detected label
            last_label = tk.Label(self.mm_stats_frame, text="Never")
            last_label.grid(row=i, column=2, padx=5, pady=2)
            
            # Store references to labels
            self.mm_event_rows[event_type] = {
                "count_label": count_label,
                "last_label": last_label
            }
        
        # Memory Monitor log display
        self.mm_log_frame = tk.Frame(self.memory_monitor_frame)
        self.mm_log_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(
            self.mm_log_frame, 
            text="Recent Events:", 
            font=("Arial", 10, "bold"),
            anchor=tk.W
        ).pack(fill=tk.X)
        
        self.mm_log_text = scrolledtext.ScrolledText(self.mm_log_frame, height=10)
        self.mm_log_text.pack(fill=tk.BOTH, expand=True)
        
        # Creation Events tab
        self.creation_events_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.creation_events_frame, text="Creation Events")
        
        # Creation Events control frame
        self.creation_controls_frame = tk.Frame(self.creation_events_frame)
        self.creation_controls_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Refresh button
        self.creation_refresh_button = tk.Button(
            self.creation_controls_frame,
            text="Refresh Events",
            width=15,
            command=self.refresh_creation_events
        )
        self.creation_refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Settings and status
        self.creation_settings_frame = tk.Frame(self.creation_controls_frame)
        self.creation_settings_frame.pack(side=tk.LEFT, padx=20)
        
        # Display count setting
        tk.Label(self.creation_settings_frame, text="Display count:").grid(row=0, column=0, padx=5)
        
        self.creation_count_var = tk.StringVar(value=str(CREATION_EVENTS_MAX_DISPLAY))
        self.creation_count_entry = tk.Entry(
            self.creation_settings_frame, 
            textvariable=self.creation_count_var,
            width=5
        )
        self.creation_count_entry.grid(row=0, column=1, padx=5)
        
        # Auto-refresh option
        self.creation_auto_refresh_var = tk.BooleanVar(value=True)
        self.creation_auto_refresh_check = tk.Checkbutton(
            self.creation_settings_frame,
            text="Auto-refresh",
            variable=self.creation_auto_refresh_var,
            command=self.toggle_creation_auto_refresh
        )
        self.creation_auto_refresh_check.grid(row=0, column=2, padx=10)
        
        # Status label
        self.creation_status_label = tk.Label(
            self.creation_events_frame,
            text="Status: Waiting for events...",
            fg="blue",
            anchor=tk.W
        )
        self.creation_status_label.pack(pady=5, padx=20, fill=tk.X)
        
        # Creation Events display
        self.creation_events_display = ttk.Treeview(
            self.creation_events_frame,
            columns=("timestamp", "memory_id", "user_id", "content"),
            show="headings",
            height=15
        )
        
        # Configure columns
        self.creation_events_display.heading("timestamp", text="Timestamp")
        self.creation_events_display.heading("memory_id", text="Memory ID")
        self.creation_events_display.heading("user_id", text="User ID")
        self.creation_events_display.heading("content", text="Content Summary")
        
        self.creation_events_display.column("timestamp", width=180, anchor=tk.W)
        self.creation_events_display.column("memory_id", width=180, anchor=tk.W)
        self.creation_events_display.column("user_id", width=100, anchor=tk.W)
        self.creation_events_display.column("content", width=300, anchor=tk.W)
        
        # Add scrollbar
        creation_scrollbar = ttk.Scrollbar(
            self.creation_events_frame, 
            orient=tk.VERTICAL, 
            command=self.creation_events_display.yview
        )
        self.creation_events_display.configure(yscrollcommand=creation_scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.creation_events_display.pack(pady=5, padx=20, fill=tk.BOTH, expand=True, side=tk.LEFT)
        creation_scrollbar.pack(pady=5, fill=tk.Y, side=tk.RIGHT)
        
        # Event details frame
        self.creation_details_frame = tk.Frame(self.creation_events_frame)
        self.creation_details_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(
            self.creation_details_frame,
            text="Event Details:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)
        
        self.creation_details_text = scrolledtext.ScrolledText(
            self.creation_details_frame,
            height=5,
            wrap=tk.WORD
        )
        self.creation_details_text.pack(fill=tk.X)
        
        # Bind selection event
        self.creation_events_display.bind("<<TreeviewSelect>>", self.show_creation_event_details)
        
        # Update Events tab
        self.update_events_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.update_events_frame, text="Update Events")
        
        # Update Events control frame
        self.update_controls_frame = tk.Frame(self.update_events_frame)
        self.update_controls_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Refresh button
        self.update_refresh_button = tk.Button(
            self.update_controls_frame,
            text="Refresh Events",
            width=15,
            command=self.refresh_update_events
        )
        self.update_refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Settings and status
        self.update_settings_frame = tk.Frame(self.update_controls_frame)
        self.update_settings_frame.pack(side=tk.LEFT, padx=20)
        
        # Display count setting
        tk.Label(self.update_settings_frame, text="Display count:").grid(row=0, column=0, padx=5)
        
        self.update_count_var = tk.StringVar(value=str(UPDATE_EVENTS_MAX_DISPLAY))
        self.update_count_entry = tk.Entry(
            self.update_settings_frame, 
            textvariable=self.update_count_var,
            width=5
        )
        self.update_count_entry.grid(row=0, column=1, padx=5)
        
        # Auto-refresh option
        self.update_auto_refresh_var = tk.BooleanVar(value=True)
        self.update_auto_refresh_check = tk.Checkbutton(
            self.update_settings_frame,
            text="Auto-refresh",
            variable=self.update_auto_refresh_var,
            command=self.toggle_update_auto_refresh
        )
        self.update_auto_refresh_check.grid(row=0, column=2, padx=10)
        
        # Status label
        self.update_status_label = tk.Label(
            self.update_events_frame,
            text="Status: Waiting for events...",
            fg="blue",
            anchor=tk.W
        )
        self.update_status_label.pack(pady=5, padx=20, fill=tk.X)
        
        # Update Events display
        self.update_events_display = ttk.Treeview(
            self.update_events_frame,
            columns=("timestamp", "memory_id", "user_id", "content"),
            show="headings",
            height=15
        )
        
        # Configure columns
        self.update_events_display.heading("timestamp", text="Timestamp")
        self.update_events_display.heading("memory_id", text="Memory ID")
        self.update_events_display.heading("user_id", text="User ID")
        self.update_events_display.heading("content", text="Content Summary")
        
        self.update_events_display.column("timestamp", width=180, anchor=tk.W)
        self.update_events_display.column("memory_id", width=180, anchor=tk.W)
        self.update_events_display.column("user_id", width=100, anchor=tk.W)
        self.update_events_display.column("content", width=300, anchor=tk.W)
        
        # Add scrollbar
        update_scrollbar = ttk.Scrollbar(
            self.update_events_frame, 
            orient=tk.VERTICAL, 
            command=self.update_events_display.yview
        )
        self.update_events_display.configure(yscrollcommand=update_scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.update_events_display.pack(pady=5, padx=20, fill=tk.BOTH, expand=True, side=tk.LEFT)
        update_scrollbar.pack(pady=5, fill=tk.Y, side=tk.RIGHT)
        
        # Event details frame
        self.update_details_frame = tk.Frame(self.update_events_frame)
        self.update_details_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(
            self.update_details_frame,
            text="Event Details:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)
        
        self.update_details_text = scrolledtext.ScrolledText(
            self.update_details_frame,
            height=5,
            wrap=tk.WORD
        )
        self.update_details_text.pack(fill=tk.X)
        
        # Bind selection event
        self.update_events_display.bind("<<TreeviewSelect>>", self.show_update_event_details)
        
        # Deletion Events tab
        self.deletion_events_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.deletion_events_frame, text="Deletion Events")
        
        # Deletion Events control frame
        self.deletion_controls_frame = tk.Frame(self.deletion_events_frame)
        self.deletion_controls_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Refresh button
        self.deletion_refresh_button = tk.Button(
            self.deletion_controls_frame,
            text="Refresh Events",
            width=15,
            command=self.refresh_deletion_events
        )
        self.deletion_refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Settings and status
        self.deletion_settings_frame = tk.Frame(self.deletion_controls_frame)
        self.deletion_settings_frame.pack(side=tk.LEFT, padx=20)
        
        # Display count setting
        tk.Label(self.deletion_settings_frame, text="Display count:").grid(row=0, column=0, padx=5)
        
        self.deletion_count_var = tk.StringVar(value=str(DELETION_EVENTS_MAX_DISPLAY))
        self.deletion_count_entry = tk.Entry(
            self.deletion_settings_frame, 
            textvariable=self.deletion_count_var,
            width=5
        )
        self.deletion_count_entry.grid(row=0, column=1, padx=5)
        
        # Auto-refresh option
        self.deletion_auto_refresh_var = tk.BooleanVar(value=True)
        self.deletion_auto_refresh_check = tk.Checkbutton(
            self.deletion_settings_frame,
            text="Auto-refresh",
            variable=self.deletion_auto_refresh_var,
            command=self.toggle_deletion_auto_refresh
        )
        self.deletion_auto_refresh_check.grid(row=0, column=2, padx=10)
        
        # Status label
        self.deletion_status_label = tk.Label(
            self.deletion_events_frame,
            text="Status: Waiting for events...",
            fg="blue",
            anchor=tk.W
        )
        self.deletion_status_label.pack(pady=5, padx=20, fill=tk.X)
        
        # Deletion Events display
        self.deletion_events_display = ttk.Treeview(
            self.deletion_events_frame,
            columns=("timestamp", "memory_id", "user_id", "content"),
            show="headings",
            height=15
        )
        
        # Configure columns
        self.deletion_events_display.heading("timestamp", text="Timestamp")
        self.deletion_events_display.heading("memory_id", text="Memory ID")
        self.deletion_events_display.heading("user_id", text="User ID")
        self.deletion_events_display.heading("content", text="Content Summary")
        
        self.deletion_events_display.column("timestamp", width=180, anchor=tk.W)
        self.deletion_events_display.column("memory_id", width=180, anchor=tk.W)
        self.deletion_events_display.column("user_id", width=100, anchor=tk.W)
        self.deletion_events_display.column("content", width=300, anchor=tk.W)
        
        # Add scrollbar
        deletion_scrollbar = ttk.Scrollbar(
            self.deletion_events_frame, 
            orient=tk.VERTICAL, 
            command=self.deletion_events_display.yview
        )
        self.deletion_events_display.configure(yscrollcommand=deletion_scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.deletion_events_display.pack(pady=5, padx=20, fill=tk.BOTH, expand=True, side=tk.LEFT)
        deletion_scrollbar.pack(pady=5, fill=tk.Y, side=tk.RIGHT)
        
        # Event details frame
        self.deletion_details_frame = tk.Frame(self.deletion_events_frame)
        self.deletion_details_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(
            self.deletion_details_frame,
            text="Event Details:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)
        
        self.deletion_details_text = scrolledtext.ScrolledText(
            self.deletion_details_frame,
            height=5,
            wrap=tk.WORD
        )
        self.deletion_details_text.pack(fill=tk.X)
        
        # Bind selection event
        self.deletion_events_display.bind("<<TreeviewSelect>>", self.show_deletion_event_details)
        
        # Error Events tab
        self.error_events_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.error_events_frame, text="Error Events")
        
        # Error Events control frame
        self.error_controls_frame = tk.Frame(self.error_events_frame)
        self.error_controls_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Refresh button
        self.error_refresh_button = tk.Button(
            self.error_controls_frame,
            text="Refresh Events",
            width=15,
            command=self.refresh_error_events
        )
        self.error_refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Settings and status
        self.error_settings_frame = tk.Frame(self.error_controls_frame)
        self.error_settings_frame.pack(side=tk.LEFT, padx=20)
        
        # Display count setting
        tk.Label(self.error_settings_frame, text="Display count:").grid(row=0, column=0, padx=5)
        
        self.error_count_var = tk.StringVar(value=str(ERROR_EVENTS_MAX_DISPLAY))
        self.error_count_entry = tk.Entry(
            self.error_settings_frame, 
            textvariable=self.error_count_var,
            width=5
        )
        self.error_count_entry.grid(row=0, column=1, padx=5)
        
        # Auto-refresh option
        self.error_auto_refresh_var = tk.BooleanVar(value=True)
        self.error_auto_refresh_check = tk.Checkbutton(
            self.error_settings_frame,
            text="Auto-refresh",
            variable=self.error_auto_refresh_var,
            command=self.toggle_error_auto_refresh
        )
        self.error_auto_refresh_check.grid(row=0, column=2, padx=10)
        
        # Status label
        self.error_status_label = tk.Label(
            self.error_events_frame,
            text="Status: Waiting for error events...",
            fg="blue",
            anchor=tk.W
        )
        self.error_status_label.pack(pady=5, padx=20, fill=tk.X)
        
        # Error Events display
        self.error_events_display = ttk.Treeview(
            self.error_events_frame,
            columns=("timestamp", "memory_id", "error_type", "message"),
            show="headings",
            height=15
        )
        
        # Configure columns
        self.error_events_display.heading("timestamp", text="Timestamp")
        self.error_events_display.heading("memory_id", text="Memory ID")
        self.error_events_display.heading("error_type", text="Error Type")
        self.error_events_display.heading("message", text="Error Message")
        
        self.error_events_display.column("timestamp", width=180, anchor=tk.W)
        self.error_events_display.column("memory_id", width=180, anchor=tk.W)
        self.error_events_display.column("error_type", width=120, anchor=tk.W)
        self.error_events_display.column("message", width=280, anchor=tk.W)
        
        # Add scrollbar
        error_scrollbar = ttk.Scrollbar(
            self.error_events_frame, 
            orient=tk.VERTICAL, 
            command=self.error_events_display.yview
        )
        self.error_events_display.configure(yscrollcommand=error_scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.error_events_display.pack(pady=5, padx=20, fill=tk.BOTH, expand=True, side=tk.LEFT)
        error_scrollbar.pack(pady=5, fill=tk.Y, side=tk.RIGHT)
        
        # Error Event details frame
        self.error_details_frame = tk.Frame(self.error_events_frame)
        self.error_details_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(
            self.error_details_frame,
            text="Error Details:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)
        
        self.error_details_text = scrolledtext.ScrolledText(
            self.error_details_frame,
            height=5,
            wrap=tk.WORD
        )
        self.error_details_text.pack(fill=tk.X)
        
        # Bind selection event
        self.error_events_display.bind("<<TreeviewSelect>>", self.show_error_event_details)
        
        # Store auto-refresh state
        self.creation_auto_refresh_id = None
        self.update_auto_refresh_id = None
        self.deletion_auto_refresh_id = None
        self.error_auto_refresh_id = None
        
        # Memory monitor config
        self.memory_monitor_config = self._load_memory_monitor_config()
        
        # State variables
        self.processes: list[subprocess.Popen] = []
        self.running = False
        self.test_running = False
        self.mm_status_refresh_id = None
        
        # Start auto-refresh for events if enabled
        if self.creation_auto_refresh_var.get():
            self.schedule_creation_events_refresh()
            
        if self.update_auto_refresh_var.get():
            self.schedule_update_events_refresh()
            
        if self.deletion_auto_refresh_var.get():
            self.schedule_deletion_events_refresh()
            
        if self.error_auto_refresh_var.get():
            self.schedule_error_events_refresh()
            
        # Log startup
        self.log_operation("Heti Control Panel started")
        self.update_status_bar("Ready")
        
        # Check OpenMemory API connection on startup
        # Schedule it after a short delay to allow UI to fully initialize
        self.root.after(500, self.initial_connection_check)
    
    def initial_connection_check(self):
        """Initial connection check with auto-retry capability."""
        self.log_operation("Performing initial API connection check...")
        
        # If launched by start_heti.py, use the validated API status
        if LAUNCHER_VALIDATED and API_STATUS:
            self.log_operation("Using launcher-validated API status: Connected")
            self.connection_status_indicator.config(
                text="✅ Connected to OpenMemory",
                fg="green"
            )
            self.retry_connection_button.config(state=tk.DISABLED)
            
            # Enable backend-dependent buttons
            if self.running:
                self.test_button.config(state=tk.NORMAL)
                self.dashboard_button.config(state=tk.NORMAL)
            return True
        
        # Perform normal connection check if not launcher-validated
        is_connected = self.update_connection_status()
        
        if not is_connected:
            self.log_operation(f"API not available. Will retry automatically every {API_AUTO_RETRY_INTERVAL/1000} seconds.")
            # Start auto-retry process
            self.schedule_auto_retry_connection()
            
        return is_connected
        
    def show_troubleshooting_dialog(self):
        """Show a comprehensive troubleshooting dialog with diagnostics."""
        # Create a dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Heti Troubleshooting")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Add a notebook for tabs
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # System status tab
        system_frame = ttk.Frame(notebook)
        notebook.add(system_frame, text="System Status")
        
        # Status display
        status_text = scrolledtext.ScrolledText(system_frame, height=25)
        status_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Docker status tab
        docker_frame = ttk.Frame(notebook)
        notebook.add(docker_frame, text="Docker Status")
        
        # Docker status display
        docker_text = scrolledtext.ScrolledText(docker_frame, height=25)
        docker_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # API status tab
        api_frame = ttk.Frame(notebook)
        notebook.add(api_frame, text="API Status")
        
        # API status display
        api_text = scrolledtext.ScrolledText(api_frame, height=25)
        api_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Config status tab
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="Configuration")
        
        # Config status display
        config_text = scrolledtext.ScrolledText(config_frame, height=25)
        config_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Button frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Run diagnostics button
        run_button = tk.Button(
            button_frame,
            text="Run Diagnostics",
            command=lambda: self.run_diagnostics(status_text, docker_text, api_text, config_text)
        )
        run_button.pack(side=tk.LEFT, padx=5)
        
        # Close button
        close_button = tk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy
        )
        close_button.pack(side=tk.RIGHT, padx=5)
        
        # Run diagnostics automatically
        self.run_diagnostics(status_text, docker_text, api_text, config_text)
    
    def run_diagnostics(self, status_text, docker_text, api_text, config_text):
        """Run comprehensive system diagnostics."""
        status_text.delete(1.0, tk.END)
        docker_text.delete(1.0, tk.END)
        api_text.delete(1.0, tk.END)
        config_text.delete(1.0, tk.END)
        
        # Helper to add text with timestamp
        def add_text(widget, text, color=None):
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"[{timestamp}] {text}\n"
            widget.insert(tk.END, message)
            if color:
                # Get the last line's position
                end_of_text = widget.index(tk.END)
                # Get start of the last line
                last_line_start = f"{float(end_of_text) - 1.0 - len(message) / 1000}"
                widget.tag_add(color, last_line_start, end_of_text)
                widget.tag_config("green", foreground="green")
                widget.tag_config("red", foreground="red")
                widget.tag_config("orange", foreground="orange")
            widget.see(tk.END)
        
        # Check system status
        add_text(status_text, "Starting system diagnostics...")
        
        # Python version
        add_text(status_text, f"Python version: {sys.version}")
        
        # Check if required modules are available
        required_modules = ["tkinter", "yaml", "json", "requests", "subprocess", "threading"]
        for module in required_modules:
            try:
                importlib.import_module(module)
                add_text(status_text, f"Module {module} is available", "green")
            except ImportError:
                add_text(status_text, f"Module {module} is NOT available", "red")
        
        # Check port availability
        add_text(status_text, "Checking port availability...")
        for port in [8765, 8001]:  # Updated to check port 8765
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                result = s.connect_ex(('localhost', port))
                if result == 0:
                    add_text(status_text, f"Port {port} is in use", "green" if port == 8765 else "red")
                else:
                    add_text(status_text, f"Port {port} is not in use", "red" if port == 8765 else "green")
        
        # Check Docker status
        add_text(docker_text, "Checking Docker status...")
        
        try:
            result = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                add_text(docker_text, "Docker is running", "green")
                # Add some useful info from docker info
                for line in result.stdout.split('\n'):
                    if any(key in line for key in ['Server Version', 'OS/Arch', 'Containers', 'Images']):
                        add_text(docker_text, line.strip())
            else:
                add_text(docker_text, "Docker is not running or not accessible", "red")
                add_text(docker_text, result.stderr)
        except FileNotFoundError:
            add_text(docker_text, "Docker is not installed or not in PATH", "red")
        
        # Check Docker Compose
        add_text(docker_text, "Checking Docker Compose...")
        
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
                add_text(docker_text, "Docker Compose v2 is available", "green")
                add_text(docker_text, result.stdout)
                docker_compose_cmd = ["docker", "compose"]
            else:
                # Try docker-compose (v1)
                result = subprocess.run(
                    ["docker-compose", "version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    add_text(docker_text, "Docker Compose v1 is available", "green")
                    add_text(docker_text, result.stdout)
                    docker_compose_cmd = ["docker-compose"]
                else:
                    add_text(docker_text, "Docker Compose is not available", "red")
                    add_text(docker_text, result.stderr)
                    docker_compose_cmd = None
        except Exception as e:
            add_text(docker_text, f"Error checking Docker Compose: {str(e)}", "red")
            docker_compose_cmd = None
        
        # Check container status if Docker Compose is available
        if docker_compose_cmd:
            add_text(docker_text, "Checking container status...")
            
            try:
                result = subprocess.run(
                    docker_compose_cmd + ["ps"],
                    cwd=DOCKER_COMPOSE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    add_text(docker_text, "Container status:", "green")
                    add_text(docker_text, result.stdout)
                else:
                    add_text(docker_text, "Failed to get container status", "red")
                    add_text(docker_text, result.stderr)
            except Exception as e:
                add_text(docker_text, f"Error checking container status: {str(e)}", "red")
        
        # Check API status
        add_text(api_text, "Checking API status...")
        
        # Test API connection
        try:
            url = f"{OPENMEMORY_API_URL}{API_CONNECTION_CHECK_ENDPOINT}"
            add_text(api_text, f"Testing connection to: {url}")
            
            response = requests.get(url, timeout=5)
            add_text(api_text, f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                add_text(api_text, "API is responding correctly", "green")
                try:
                    data = response.json()
                    add_text(api_text, f"Response data: {data}")
                except:
                    add_text(api_text, "Could not parse response as JSON", "orange")
            else:
                add_text(api_text, f"API returned non-200 status: {response.status_code}", "red")
                add_text(api_text, f"Response content: {response.text[:500]}")
        except requests.exceptions.ConnectionError as e:
            add_text(api_text, f"Connection error: {str(e)}", "red")
            add_text(api_text, "The API server is not running or not accessible.")
        except requests.exceptions.Timeout as e:
            add_text(api_text, f"Connection timeout: {str(e)}", "red")
            add_text(api_text, "The API server is not responding in time.")
        except Exception as e:
            add_text(api_text, f"Unexpected error: {str(e)}", "red")
        
        # Check the OpenMemory docs endpoint
        try:
            url = OPENMEMORY_DASHBOARD_URL
            add_text(api_text, f"Testing connection to dashboard: {url}")
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                add_text(api_text, "Dashboard is accessible", "green")
            else:
                add_text(api_text, f"Dashboard returned status code: {response.status_code}", "red")
        except Exception as e:
            add_text(api_text, f"Error accessing dashboard: {str(e)}", "red")
        
        # Check configuration files
        add_text(config_text, "Checking configuration files...")
        
        # Check config directory
        config_dir = "config"
        if os.path.exists(config_dir):
            add_text(config_text, f"Config directory exists: {config_dir}", "green")
            
            # List files in config directory
            files = os.listdir(config_dir)
            add_text(config_text, f"Files in config directory: {', '.join(files)}")
            
            # Check for memory_monitor.yaml
            config_file = os.path.join(config_dir, "memory_monitor.yaml")
            if os.path.exists(config_file):
                add_text(config_text, f"Config file exists: {config_file}", "green")
                
                # Try to read config file
                try:
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    add_text(config_text, "Config file is valid YAML", "green")
                    add_text(config_text, f"Config contents: {config}")
                except Exception as e:
                    add_text(config_text, f"Error reading config file: {str(e)}", "red")
            else:
                add_text(config_text, f"Config file does not exist: {config_file}", "red")
        else:
            add_text(config_text, f"Config directory does not exist: {config_dir}", "red")
        
        # Check log directories
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            add_text(config_text, f"Logs directory exists: {logs_dir}", "green")
            
            # Check memory events directory
            memory_events_dir = os.path.join(logs_dir, "memory_events")
            if os.path.exists(memory_events_dir):
                add_text(config_text, f"Memory events directory exists: {memory_events_dir}", "green")
                
                # List files in memory events directory
                try:
                    files = os.listdir(memory_events_dir)
                    add_text(config_text, f"Files in memory events directory: {', '.join(files)}")
                except Exception as e:
                    add_text(config_text, f"Error listing memory events directory: {str(e)}", "red")
            else:
                add_text(config_text, f"Memory events directory does not exist: {memory_events_dir}", "red")
        else:
            add_text(config_text, f"Logs directory does not exist: {logs_dir}", "red")
            
        # Finish diagnostics
        add_text(status_text, "Diagnostics complete.")
        add_text(docker_text, "Docker diagnostics complete.")
        add_text(api_text, "API diagnostics complete.")
        add_text(config_text, "Configuration diagnostics complete.")
    
    def _load_memory_monitor_config(self) -> dict:
        """Load memory monitor configuration from the config file."""
        config_path = "config/memory_monitor.yaml"
        default_config = {
            "logging": {
                "event_log_path": "logs/memory_events/memory_events.jsonl"
            }
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    return config
            else:
                self.creation_status_label.config(
                    text="Warning: Config file not found. Using default log path.",
                    fg="orange"
                )
        except Exception as e:
            self.creation_status_label.config(
                text=f"Error loading config: {str(e)}",
                fg="red"
            )
        
        return default_config

    def toggle(self):
        if not self.running:
            threading.Thread(target=self.start_all, daemon=True).start()
            self.button.config(text="Stop All")
            self.status_label.config(text="Status: Starting Services...", fg="blue")
        else:
            threading.Thread(target=self.stop_all, daemon=True).start()
            self.button.config(text="Start All")
            self.test_button.config(state=tk.DISABLED)
            self.dashboard_button.config(state=tk.DISABLED)
            self.status_label.config(text="Status: Stopping Services...", fg="orange")
        self.running = not self.running

    def start_all(self):
        try:
            # Start services via docker-compose
            self.log_operation("Starting Docker containers...")
            subprocess.run(
                ["docker-compose", "up", "-d"],
                cwd=DOCKER_COMPOSE_DIR,
                check=True,
            )
            
            # Start Heti MCP server
            self.log_operation("Starting MCP server...")
            proc_mcp = subprocess.Popen(MCP_SERVER_CMD)
            self.processes.append(proc_mcp)
            
            # Start live monitor embedder indefinitely
            self.log_operation("Starting monitor embedder...")
            proc_mon = subprocess.Popen(MONITOR_CMD)
            self.processes.append(proc_mon)
            
            # Wait for services to fully start
            self.status_label.config(text="Status: Waiting for services to initialize...", fg="blue")
            self.root.update()
            
            # Implement a grace period with visual feedback
            self.log_operation(f"Allowing {API_STARTUP_GRACE_PERIOD} seconds for API initialization...")
            
            # Show a countdown timer in the status bar
            start_time = time.time()
            grace_period_end = start_time + API_STARTUP_GRACE_PERIOD
            
            # Try connecting periodically during the grace period
            while time.time() < grace_period_end:
                # Calculate remaining time
                remaining = int(grace_period_end - time.time())
                self.status_label.config(
                    text=f"Status: Waiting for API to initialize ({remaining}s remaining)...",
                    fg="blue"
                )
                self.root.update()
                
                # Try to connect to the API
                is_connected, _ = self.check_api_connection()
                if is_connected:
                    self.log_operation("API connected successfully during grace period!")
                    break
                    
                # Wait a bit before next attempt
                time.sleep(2)
            
            # Final check of the connection status
            self.log_operation("Grace period complete. Checking API status...")
            if self.update_connection_status():
                self.status_label.config(text="Status: Services Running", fg="green")
                self.test_button.config(state=tk.NORMAL)
                self.dashboard_button.config(state=tk.NORMAL)
                messagebox.showinfo("Heti Control", "All services started.")
            else:
                self.status_label.config(text="Status: Services Started but API not responding", fg="orange")
                self.log_operation("Starting automatic connection retry...")
                self.schedule_auto_retry_connection()
                messagebox.showwarning(
                    "Heti Control", 
                    "Services started but OpenMemory API not responding yet.\n\n"
                    "This is normal during first startup. The system will automatically "
                    "retry connecting periodically."
                )
        except Exception as e:
            self.status_label.config(text=f"Status: Error - {str(e)[:30]}...", fg="red")
            messagebox.showerror("Error Starting", str(e))
            self.running = False
            self.button.config(text="Start All")

    def stop_all(self):
        # Terminate subprocesses
        for p in self.processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                pass
        self.processes.clear()
        # Stop docker-compose services
        try:
            subprocess.run(
                ["docker-compose", "down"],
                cwd=DOCKER_COMPOSE_DIR,
                check=True,
            )
            self.status_label.config(text="Status: Services Stopped", fg="gray")
            
            # Update connection status after stopping services
            self.root.after(1000, self.update_connection_status)
            
            messagebox.showinfo("Heti Control", "All services stopped.")
        except Exception as e:
            self.status_label.config(text=f"Status: Error - {str(e)[:30]}...", fg="red")
            messagebox.showerror("Error Stopping", str(e))

    def run_api_tests(self):
        if self.test_running:
            return
            
        self.test_running = True
        threading.Thread(target=self._run_api_tests_thread, daemon=True).start()
        
    def _run_api_tests_thread(self):
        try:
            # Update UI to indicate test is running
            self.test_button.config(state=tk.DISABLED)
            self.summary_label.config(text="API Integration Test: Running...", fg="blue")
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, "Running API Test Suite...\n\n")
            self.root.update()
            
            # Reset endpoint statuses
            for endpoint_data in self.endpoint_statuses.values():
                endpoint_data["status_label"].config(text="Running...", fg="blue")
                endpoint_data["tests_label"].config(text="0/0")
            
            # Run the test suite
            process = subprocess.Popen(
                API_TEST_CMD,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Collect output
            output = ""
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    output += line
                    self.output_text.insert(tk.END, line)
                    self.output_text.see(tk.END)
                    self.root.update()
            
            # Get return code
            return_code = process.wait()
            
            # Process test results
            self._process_test_results(output, return_code)
            
            # Save test results to log
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_file = os.path.join(LOG_DIR, f"openmemory_client_test_results_{timestamp}.log")
            with open(log_file, "w") as f:
                f.write(output)
                
            # Update test status
            if return_code == 0:
                self.summary_label.config(
                    text="API Integration Status: ✅ All Systems Go!",
                    fg="green"
                )
            else:
                self.summary_label.config(
                    text="API Integration Status: ❌ Test Failures Detected",
                    fg="red"
                )
            
            # Re-enable test button
            self.test_button.config(state=tk.NORMAL)
            self.refresh_logs()
            
        except Exception as e:
            self.output_text.insert(tk.END, f"\nError running tests: {str(e)}\n")
            self.summary_label.config(text=f"API Integration Status: Error - {str(e)[:30]}...", fg="red")
            self.test_button.config(state=tk.NORMAL)
        finally:
            self.test_running = False
    
    def _process_test_results(self, output, return_code):
        # Initialize counters for each endpoint
        endpoint_tests = {
            'create': {'passed': 0, 'total': 0},
            'list': {'passed': 0, 'total': 0},
            'get': {'passed': 0, 'total': 0},
            'update': {'passed': 0, 'total': 0},
            'filter': {'passed': 0, 'total': 0}
        }
        
        # Extract test results from output
        create_tests = re.findall(r'test_create_memory_[a-z_]+\s+PASSED', output)
        list_tests = re.findall(r'test_list_memories_[a-z_]+\s+PASSED', output)
        get_tests = re.findall(r'test_get_memory_[a-z_]+\s+PASSED', output)
        update_tests = re.findall(r'test_update_memory_[a-z_]+\s+PASSED', output)
        filter_tests = re.findall(r'test_filter_memories_[a-z_]+\s+PASSED', output)
        
        # Count total tests
        create_total = len(re.findall(r'test_create_memory_[a-z_]+', output))
        list_total = len(re.findall(r'test_list_memories_[a-z_]+', output))
        get_total = len(re.findall(r'test_get_memory_[a-z_]+', output))
        update_total = len(re.findall(r'test_update_memory_[a-z_]+', output))
        filter_total = len(re.findall(r'test_filter_memories_[a-z_]+', output))
        
        # Update counts
        endpoint_tests['create'] = {'passed': len(create_tests), 'total': create_total}
        endpoint_tests['list'] = {'passed': len(list_tests), 'total': list_total}
        endpoint_tests['get'] = {'passed': len(get_tests), 'total': get_total}
        endpoint_tests['update'] = {'passed': len(update_tests), 'total': update_total}
        endpoint_tests['filter'] = {'passed': len(filter_tests), 'total': filter_total}
        
        # Update UI with test results
        for endpoint, results in endpoint_tests.items():
            status_label = self.endpoint_statuses[endpoint]["status_label"]
            tests_label = self.endpoint_statuses[endpoint]["tests_label"]
            
            # Update test count
            tests_label.config(text=f"{results['passed']}/{results['total']}")
            
            # Update status
            if results['total'] == 0:
                status_label.config(text="Not Tested", fg="gray")
            elif results['passed'] == results['total']:
                status_label.config(text="✅ PASSED", fg="green")
            else:
                status_label.config(text="❌ FAILED", fg="red")
    
    def open_dashboard(self):
        """Open the OpenMemory dashboard in the default web browser"""
        try:
            import webbrowser
            webbrowser.open(OPENMEMORY_DASHBOARD_URL)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open dashboard: {str(e)}")
    
    def clear_logs(self):
        """Clear the log display"""
        self.log_text.delete(1.0, tk.END)
    
    def refresh_logs(self):
        """Refresh the log display with latest API logs"""
        try:
            self.log_text.delete(1.0, tk.END)
            
            # Find the newest openmemory_client_test_results log file
            log_files = [f for f in os.listdir(LOG_DIR) if f.startswith("openmemory_client_test_results")]
            if log_files:
                newest_log = max(log_files, key=lambda f: os.path.getmtime(os.path.join(LOG_DIR, f)))
                log_path = os.path.join(LOG_DIR, newest_log)
                
                with open(log_path, "r") as f:
                    log_content = f.read()
                    self.log_text.insert(tk.END, log_content)
                    
                self.log_text.insert(tk.END, f"\n\n--- Log file: {log_path} ---\n")
            else:
                self.log_text.insert(tk.END, "No test logs found.")
        except Exception as e:
            self.log_text.insert(tk.END, f"Error refreshing logs: {str(e)}")

    def start_memory_monitor(self):
        """Start the Memory Monitor."""
        if self.memory_monitor is None:
            messagebox.showerror("Error", "Memory Monitor is not available.")
            return
            
        if self.memory_monitor.running:
            messagebox.showinfo("Info", "Memory Monitor is already running.")
            return
            
        try:
            # Start the monitor
            result = self.memory_monitor.start()
            
            if result:
                self.mm_start_button.config(state=tk.DISABLED)
                self.mm_stop_button.config(state=tk.NORMAL)
                self.mm_status_label.config(text="Memory Monitor Status: Running", fg="green")
                messagebox.showinfo("Success", "Memory Monitor started successfully.")
                
                # Start automatic status refresh
                self.schedule_status_refresh()
                
                # Also refresh creation events
                self.refresh_creation_events()
            else:
                messagebox.showerror("Error", "Failed to start Memory Monitor.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error starting Memory Monitor: {str(e)}")
    
    def stop_memory_monitor(self):
        """Stop the Memory Monitor."""
        if self.memory_monitor is None or not self.memory_monitor.running:
            return
            
        try:
            # Stop the monitor
            result = self.memory_monitor.stop()
            
            if result:
                self.mm_start_button.config(state=tk.NORMAL)
                self.mm_stop_button.config(state=tk.DISABLED)
                self.mm_status_label.config(text="Memory Monitor Status: Stopped", fg="gray")
                messagebox.showinfo("Success", "Memory Monitor stopped successfully.")
                
                # Cancel automatic refresh
                if self.mm_status_refresh_id:
                    self.root.after_cancel(self.mm_status_refresh_id)
                    self.mm_status_refresh_id = None
            else:
                messagebox.showerror("Error", "Failed to stop Memory Monitor.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error stopping Memory Monitor: {str(e)}")
    
    def refresh_memory_monitor_status(self):
        """Refresh the Memory Monitor status display."""
        if self.memory_monitor is None:
            self.mm_status_label.config(text="Memory Monitor Status: Not Available", fg="red")
            return
            
        try:
            # Get current status
            status = self.memory_monitor.get_status()
            
            # Update status label
            if status["running"]:
                health = status["health"]
                if health == "OK":
                    self.mm_status_label.config(text="Memory Monitor Status: Running", fg="green")
                elif health == "WARNING":
                    self.mm_status_label.config(text="Memory Monitor Status: Warning", fg="orange")
                else:
                    self.mm_status_label.config(text="Memory Monitor Status: Error", fg="red")
                
                # Update event counts
                for event_type, count in status["events_by_type"].items():
                    if event_type in self.mm_event_rows:
                        self.mm_event_rows[event_type]["count_label"].config(text=str(count))
                
                # Update last event type
                if status["last_event_type"] and status["last_event_time"]:
                    event_type = status["last_event_type"]
                    if event_type in self.mm_event_rows:
                        # Format the timestamp for display
                        try:
                            timestamp = datetime.datetime.fromisoformat(status["last_event_time"].replace('Z', '+00:00'))
                            formatted_time = timestamp.strftime("%H:%M:%S")
                            self.mm_event_rows[event_type]["last_label"].config(text=formatted_time)
                        except:
                            self.mm_event_rows[event_type]["last_label"].config(text="Recent")
                
                # Display uptime if available
                if status["uptime_seconds"]:
                    uptime = status["uptime_seconds"]
                    hours, remainder = divmod(int(uptime), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime_str = f"{hours:02}:{minutes:02}:{seconds:02}"
                    self.mm_status_label.config(text=f"Memory Monitor Status: Running (Uptime: {uptime_str})")
            else:
                self.mm_status_label.config(text="Memory Monitor Status: Stopped", fg="gray")
            
            # Show recent events
            self.refresh_memory_monitor_events()
            
        except Exception as e:
            self.mm_status_label.config(text=f"Memory Monitor Status: Error - {str(e)[:30]}...", fg="red")
    
    def refresh_memory_monitor_events(self):
        """Refresh the Memory Monitor events display."""
        try:
            # Check for event log file
            event_log_path = "logs/memory_events/memory_events.jsonl"
            if not os.path.exists(event_log_path):
                self.mm_log_text.delete(1.0, tk.END)
                self.mm_log_text.insert(tk.END, "No events logged yet.")
                return
                
            # Read recent events (last 10)
            events = []
            with open(event_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        events.append(event)
                    except:
                        pass
            
            # Display most recent events first
            events.reverse()
            events = events[:10]  # Keep only the 10 most recent
            
            # Update display
            self.mm_log_text.delete(1.0, tk.END)
            
            if not events:
                self.mm_log_text.insert(tk.END, "No events logged yet.")
                return
                
            for event in events:
                try:
                    # Format the event for display
                    event_type = event.get("event_type", "unknown")
                    memory_id = event.get("memory_id", "unknown")
                    timestamp = event.get("timestamp", "")
                    
                    # Format timestamp
                    try:
                        dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                    
                    # Add to display
                    self.mm_log_text.insert(tk.END, f"{formatted_time} - {event_type} - Memory: {memory_id}\n")
                    
                    # Add some details if available
                    if event_type == "memory.created" or event_type == "memory.updated":
                        content = event.get("content_summary", "")
                        if content:
                            self.mm_log_text.insert(tk.END, f"  Content: {content}\n")
                    
                    self.mm_log_text.insert(tk.END, "\n")
                    
                except Exception as e:
                    self.mm_log_text.insert(tk.END, f"Error formatting event: {str(e)}\n\n")
            
        except Exception as e:
            self.mm_log_text.delete(1.0, tk.END)
            self.mm_log_text.insert(tk.END, f"Error refreshing events: {str(e)}")
    
    def schedule_status_refresh(self):
        """Schedule periodic refresh of Memory Monitor status."""
        # Cancel any existing scheduled refresh
        if self.mm_status_refresh_id:
            self.root.after_cancel(self.mm_status_refresh_id)
            
        # Refresh now
        self.refresh_memory_monitor_status()
        
        # Schedule next refresh (every 5 seconds)
        if self.memory_monitor and self.memory_monitor.running:
            self.mm_status_refresh_id = self.root.after(5000, self.schedule_status_refresh)

    def refresh_creation_events(self):
        """
        Refresh the Creation Events display by reading the memory monitor log file.
        
        This function:
        1. Reads the log file path from the memory monitor config
        2. Loads the most recent creation events
        3. Displays them in the treeview with timestamp, memory_id and content summary
        """
        try:
            # Get the log file path from config
            event_log_path = self.memory_monitor_config.get("logging", {}).get(
                "event_log_path", "logs/memory_events/memory_events.jsonl")
            
            # Check if log file exists
            if not os.path.exists(event_log_path):
                self.creation_status_label.config(
                    text=f"Error: Log file not found at {event_log_path}",
                    fg="red"
                )
                return
            
            # Get max events to display
            try:
                max_events = int(self.creation_count_var.get())
                if max_events <= 0:
                    max_events = CREATION_EVENTS_MAX_DISPLAY
            except ValueError:
                max_events = CREATION_EVENTS_MAX_DISPLAY
                self.creation_count_var.set(str(max_events))
            
            # Clear current display
            for item in self.creation_events_display.get_children():
                self.creation_events_display.delete(item)
            
            # Read and parse log entries
            creation_events = []
            with open(event_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        # Only include creation events
                        if event.get("event_type") == "creation":
                            creation_events.append(event)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
            
            # Sort by timestamp (newest first) and limit to max_events
            creation_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            creation_events = creation_events[:max_events]
            
            # Update status label
            if not creation_events:
                self.creation_status_label.config(
                    text="No creation events found in log file.",
                    fg="blue"
                )
                return
            
            # Display events
            for event in creation_events:
                try:
                    # Extract fields
                    timestamp = event.get("timestamp", "")
                    memory_id = event.get("memory_id", "")
                    
                    # Extract user_id and content from details
                    details = event.get("details", {})
                    user_id = details.get("user_id", "")
                    content_summary = details.get("content_summary", "")
                    
                    # Format timestamp for display
                    try:
                        dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                    
                    # Add to treeview
                    self.creation_events_display.insert(
                        "", 
                        "end", 
                        values=(formatted_time, memory_id, user_id, content_summary),
                        tags=(memory_id,)
                    )
                except Exception as e:
                    print(f"Error processing event: {str(e)}")
            
            # Update status label
            self.creation_status_label.config(
                text=f"Displaying {len(creation_events)} creation events.",
                fg="green"
            )
            
        except Exception as e:
            self.creation_status_label.config(
                text=f"Error refreshing creation events: {str(e)}",
                fg="red"
            )
    
    def show_creation_event_details(self, event):
        """Display details for the selected creation event."""
        # Clear current details
        self.creation_details_text.delete(1.0, tk.END)
        
        # Get selected item
        selected_items = self.creation_events_display.selection()
        if not selected_items:
            return
        
        # Get values for the selected item
        item_values = self.creation_events_display.item(selected_items[0], "values")
        if not item_values or len(item_values) < 2:
            return
        
        # Get the memory_id
        memory_id = item_values[1]
        
        # Find the event in the log file
        try:
            event_log_path = self.memory_monitor_config.get("logging", {}).get(
                "event_log_path", "logs/memory_events/memory_events.jsonl")
            
            if not os.path.exists(event_log_path):
                self.creation_details_text.insert(tk.END, "Error: Log file not found.")
                return
            
            with open(event_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())
                        if (event_data.get("event_type") == "creation" and 
                            event_data.get("memory_id") == memory_id):
                            # Found the event, display its details
                            self.creation_details_text.insert(tk.END, json.dumps(event_data, indent=2))
                            return
                    except json.JSONDecodeError:
                        continue
            
            # If we get here, we didn't find the event
            self.creation_details_text.insert(tk.END, f"Event details not found for memory_id: {memory_id}")
            
        except Exception as e:
            self.creation_details_text.insert(tk.END, f"Error retrieving event details: {str(e)}")
    
    def toggle_creation_auto_refresh(self):
        """Toggle auto-refresh for creation events."""
        if self.creation_auto_refresh_var.get():
            # Enable auto-refresh
            self.schedule_creation_events_refresh()
        else:
            # Disable auto-refresh
            if self.creation_auto_refresh_id:
                self.root.after_cancel(self.creation_auto_refresh_id)
                self.creation_auto_refresh_id = None
    
    def schedule_creation_events_refresh(self):
        """Schedule periodic refresh of creation events."""
        # Cancel any existing scheduled refresh
        if self.creation_auto_refresh_id:
            self.root.after_cancel(self.creation_auto_refresh_id)
        
        # Refresh now
        self.refresh_creation_events()
        
        # Schedule next refresh if auto-refresh is enabled
        if self.creation_auto_refresh_var.get():
            self.creation_auto_refresh_id = self.root.after(
                CREATION_EVENTS_REFRESH_INTERVAL,
                self.schedule_creation_events_refresh
            )

    def refresh_update_events(self):
        """
        Refresh the Update Events display by reading the memory monitor log file.
        
        This function:
        1. Reads the log file path from the memory monitor config
        2. Loads the most recent update events
        3. Displays them in the treeview with timestamp, memory_id and content summary
        """
        try:
            # Get the log file path from config
            event_log_path = self.memory_monitor_config.get("logging", {}).get(
                "event_log_path", "logs/memory_events/memory_events.jsonl")
            
            # Check if log file exists
            if not os.path.exists(event_log_path):
                self.update_status_label.config(
                    text=f"Error: Log file not found at {event_log_path}",
                    fg="red"
                )
                return
            
            # Get max events to display
            try:
                max_events = int(self.update_count_var.get())
                if max_events <= 0:
                    max_events = UPDATE_EVENTS_MAX_DISPLAY
            except ValueError:
                max_events = UPDATE_EVENTS_MAX_DISPLAY
                self.update_count_var.set(str(max_events))
            
            # Clear current display
            for item in self.update_events_display.get_children():
                self.update_events_display.delete(item)
            
            # Read and parse log entries
            update_events = []
            with open(event_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        # Only include update events
                        if event.get("event_type") == "update":
                            update_events.append(event)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
            
            # Sort by timestamp (newest first) and limit to max_events
            update_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            update_events = update_events[:max_events]
            
            # Update status label
            if not update_events:
                self.update_status_label.config(
                    text="No update events found in log file.",
                    fg="blue"
                )
                return
            
            # Display events
            for event in update_events:
                try:
                    # Extract fields
                    timestamp = event.get("timestamp", "")
                    memory_id = event.get("memory_id", "")
                    
                    # Extract user_id and content from details
                    details = event.get("details", {})
                    user_id = details.get("user_id", "")
                    content_summary = details.get("content_summary", "")
                    
                    # Format timestamp for display
                    try:
                        dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                    
                    # Add to treeview
                    self.update_events_display.insert(
                        "", 
                        "end", 
                        values=(formatted_time, memory_id, user_id, content_summary),
                        tags=(memory_id,)
                    )
                except Exception as e:
                    print(f"Error processing event: {str(e)}")
            
            # Update status label
            self.update_status_label.config(
                text=f"Displaying {len(update_events)} update events.",
                fg="green"
            )
            
        except Exception as e:
            self.update_status_label.config(
                text=f"Error refreshing update events: {str(e)}",
                fg="red"
            )
    
    def show_update_event_details(self, event):
        """Display details for the selected update event."""
        # Clear current details
        self.update_details_text.delete(1.0, tk.END)
        
        # Get selected item
        selected_items = self.update_events_display.selection()
        if not selected_items:
            return
        
        # Get values for the selected item
        item_values = self.update_events_display.item(selected_items[0], "values")
        if not item_values or len(item_values) < 2:
            return
        
        # Get the memory_id
        memory_id = item_values[1]
        
        # Find the event in the log file
        try:
            event_log_path = self.memory_monitor_config.get("logging", {}).get(
                "event_log_path", "logs/memory_events/memory_events.jsonl")
            
            if not os.path.exists(event_log_path):
                self.update_details_text.insert(tk.END, "Error: Log file not found.")
                return
            
            with open(event_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())
                        if (event_data.get("event_type") == "update" and 
                            event_data.get("memory_id") == memory_id):
                            # Found the event, display its details
                            self.update_details_text.insert(tk.END, json.dumps(event_data, indent=2))
                            return
                    except json.JSONDecodeError:
                        continue
            
            # If we get here, we didn't find the event
            self.update_details_text.insert(tk.END, f"Event details not found for memory_id: {memory_id}")
            
        except Exception as e:
            self.update_details_text.insert(tk.END, f"Error retrieving event details: {str(e)}")
    
    def toggle_update_auto_refresh(self):
        """Toggle auto-refresh for update events."""
        if self.update_auto_refresh_var.get():
            # Enable auto-refresh
            self.schedule_update_events_refresh()
        else:
            # Disable auto-refresh
            if self.update_auto_refresh_id:
                self.root.after_cancel(self.update_auto_refresh_id)
                self.update_auto_refresh_id = None
    
    def schedule_update_events_refresh(self):
        """Schedule periodic refresh of update events."""
        # Cancel any existing scheduled refresh
        if self.update_auto_refresh_id:
            self.root.after_cancel(self.update_auto_refresh_id)
        
        # Refresh now
        self.refresh_update_events()
        
        # Schedule next refresh if auto-refresh is enabled
        if self.update_auto_refresh_var.get():
            self.update_auto_refresh_id = self.root.after(
                UPDATE_EVENTS_REFRESH_INTERVAL,
                self.schedule_update_events_refresh
            )

    def refresh_deletion_events(self):
        """
        Refresh the Deletion Events display by reading the memory monitor log file.
        
        This function:
        1. Reads the log file path from the memory monitor config
        2. Loads the most recent deletion events
        3. Displays them in the treeview with timestamp, memory_id and content summary
        """
        try:
            # Get the log file path from config
            event_log_path = self.memory_monitor_config.get("logging", {}).get(
                "event_log_path", "logs/memory_events/memory_events.jsonl")
            
            # Check if log file exists
            if not os.path.exists(event_log_path):
                self.deletion_status_label.config(
                    text=f"Error: Log file not found at {event_log_path}",
                    fg="red"
                )
                return
            
            # Get max events to display
            try:
                max_events = int(self.deletion_count_var.get())
                if max_events <= 0:
                    max_events = DELETION_EVENTS_MAX_DISPLAY
            except ValueError:
                max_events = DELETION_EVENTS_MAX_DISPLAY
                self.deletion_count_var.set(str(max_events))
            
            # Clear current display
            for item in self.deletion_events_display.get_children():
                self.deletion_events_display.delete(item)
            
            # Read and parse log entries
            deletion_events = []
            with open(event_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        # Only include deletion events
                        if event.get("event_type") == "deletion":
                            deletion_events.append(event)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
            
            # Sort by timestamp (newest first) and limit to max_events
            deletion_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            deletion_events = deletion_events[:max_events]
            
            # Update status label
            if not deletion_events:
                self.deletion_status_label.config(
                    text="No deletion events found in log file.",
                    fg="blue"
                )
                return
            
            # Display events
            for event in deletion_events:
                try:
                    # Extract fields
                    timestamp = event.get("timestamp", "")
                    memory_id = event.get("memory_id", "")
                    
                    # Extract user_id and content from details
                    details = event.get("details", {})
                    user_id = details.get("user_id", "")
                    content_summary = details.get("content_summary", "")
                    
                    # Format timestamp for display
                    try:
                        dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                    
                    # Add to treeview
                    self.deletion_events_display.insert(
                        "", 
                        "end", 
                        values=(formatted_time, memory_id, user_id, content_summary),
                        tags=(memory_id,)
                    )
                except Exception as e:
                    print(f"Error processing event: {str(e)}")
            
            # Update status label
            self.deletion_status_label.config(
                text=f"Displaying {len(deletion_events)} deletion events.",
                fg="green"
            )
            
        except Exception as e:
            self.deletion_status_label.config(
                text=f"Error refreshing deletion events: {str(e)}",
                fg="red"
            )
    
    def show_deletion_event_details(self, event):
        """Display details for the selected deletion event."""
        # Clear current details
        self.deletion_details_text.delete(1.0, tk.END)
        
        # Get selected item
        selected_items = self.deletion_events_display.selection()
        if not selected_items:
            return
        
        # Get values for the selected item
        item_values = self.deletion_events_display.item(selected_items[0], "values")
        if not item_values or len(item_values) < 2:
            return
        
        # Get the memory_id
        memory_id = item_values[1]
        
        # Find the event in the log file
        try:
            event_log_path = self.memory_monitor_config.get("logging", {}).get(
                "event_log_path", "logs/memory_events/memory_events.jsonl")
            
            if not os.path.exists(event_log_path):
                self.deletion_details_text.insert(tk.END, "Error: Log file not found.")
                return
            
            with open(event_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())
                        if (event_data.get("event_type") == "deletion" and 
                            event_data.get("memory_id") == memory_id):
                            # Found the event, display its details
                            self.deletion_details_text.insert(tk.END, json.dumps(event_data, indent=2))
                            return
                    except json.JSONDecodeError:
                        continue
            
            # If we get here, we didn't find the event
            self.deletion_details_text.insert(tk.END, f"Event details not found for memory_id: {memory_id}")
            
        except Exception as e:
            self.deletion_details_text.insert(tk.END, f"Error retrieving event details: {str(e)}")
    
    def toggle_deletion_auto_refresh(self):
        """Toggle auto-refresh for deletion events."""
        if self.deletion_auto_refresh_var.get():
            # Enable auto-refresh
            self.schedule_deletion_events_refresh()
        else:
            # Disable auto-refresh
            if self.deletion_auto_refresh_id:
                self.root.after_cancel(self.deletion_auto_refresh_id)
                self.deletion_auto_refresh_id = None
    
    def schedule_deletion_events_refresh(self):
        """Schedule periodic refresh of deletion events."""
        # Cancel any existing scheduled refresh
        if self.deletion_auto_refresh_id:
            self.root.after_cancel(self.deletion_auto_refresh_id)
        
        # Refresh now
        self.refresh_deletion_events()
        
        # Schedule next refresh if auto-refresh is enabled
        if self.deletion_auto_refresh_var.get():
            self.deletion_auto_refresh_id = self.root.after(
                DELETION_EVENTS_REFRESH_INTERVAL,
                self.schedule_deletion_events_refresh
            )

    def refresh_error_events(self):
        """
        Refresh the Error Events display by reading the memory monitor log file.
        
        This function:
        1. Reads the log file path from the memory monitor config
        2. Loads the most recent error events
        3. Displays them in the treeview with timestamp, memory_id, error_type, and message
        """
        try:
            # Get the log file path from config
            event_log_path = self.memory_monitor_config.get("logging", {}).get(
                "event_log_path", "logs/memory_events/memory_events.jsonl")
            
            # Check if log file exists
            if not os.path.exists(event_log_path):
                self.error_status_label.config(
                    text=f"Error: Log file not found at {event_log_path}",
                    fg="red"
                )
                return
            
            # Get max events to display
            try:
                max_events = int(self.error_count_var.get())
                if max_events <= 0:
                    max_events = ERROR_EVENTS_MAX_DISPLAY
            except ValueError:
                max_events = ERROR_EVENTS_MAX_DISPLAY
                self.error_count_var.set(str(max_events))
            
            # Clear current display
            for item in self.error_events_display.get_children():
                self.error_events_display.delete(item)
            
            # Read and parse log entries
            error_events = []
            with open(event_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        # Only include error events
                        if event.get("event_type") == "error":
                            error_events.append(event)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
            
            # Sort by timestamp (newest first) and limit to max_events
            error_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            error_events = error_events[:max_events]
            
            # Update status label
            if not error_events:
                self.error_status_label.config(
                    text="No error events found in log file.",
                    fg="blue"
                )
                return
            
            # Display events
            for event in error_events:
                try:
                    # Extract fields
                    timestamp = event.get("timestamp", "")
                    memory_id = event.get("memory_id", "")
                    error_type = event.get("error_type", "Unknown")
                    message = event.get("message", "")
                    
                    # Format timestamp for display
                    try:
                        dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                    
                    # Add to treeview
                    self.error_events_display.insert(
                        "", 
                        "end", 
                        values=(formatted_time, memory_id, error_type, message),
                        tags=(memory_id,)
                    )
                except Exception as e:
                    print(f"Error processing event: {str(e)}")
            
            # Update status label
            self.error_status_label.config(
                text=f"Displaying {len(error_events)} error events.",
                fg="green" if error_events else "blue"
            )
            
        except Exception as e:
            self.error_status_label.config(
                text=f"Error refreshing error events: {str(e)}",
                fg="red"
            )
    
    def show_error_event_details(self, event):
        """Display details for the selected error event."""
        # Clear current details
        self.error_details_text.delete(1.0, tk.END)
        
        # Get selected item
        selected_items = self.error_events_display.selection()
        if not selected_items:
            return
        
        # Get values for the selected item
        item_values = self.error_events_display.item(selected_items[0], "values")
        if not item_values or len(item_values) < 2:
            return
        
        # Get the memory_id
        memory_id = item_values[1]
        
        # Find the event in the log file
        try:
            event_log_path = self.memory_monitor_config.get("logging", {}).get(
                "event_log_path", "logs/memory_events/memory_events.jsonl")
            
            if not os.path.exists(event_log_path):
                self.error_details_text.insert(tk.END, "Error: Log file not found.")
                return
            
            with open(event_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())
                        if (event_data.get("event_type") == "error" and 
                            event_data.get("memory_id") == memory_id):
                            # Check for the specific error event by looking at more fields
                            # This is needed since multiple error events might have the same memory_id
                            error_type = item_values[2]
                            message = item_values[3]
                            if (event_data.get("error_type") == error_type and 
                                event_data.get("message") == message):
                                # Found the event, display its details
                                self.error_details_text.insert(tk.END, json.dumps(event_data, indent=2))
                                return
                    except json.JSONDecodeError:
                        continue
            
            # If we get here, we didn't find the event
            self.error_details_text.insert(tk.END, f"Event details not found for memory_id: {memory_id}")
            
        except Exception as e:
            self.error_details_text.insert(tk.END, f"Error retrieving event details: {str(e)}")
    
    def toggle_error_auto_refresh(self):
        """Toggle auto-refresh for error events."""
        if self.error_auto_refresh_var.get():
            # Enable auto-refresh
            self.schedule_error_events_refresh()
        else:
            # Disable auto-refresh
            if self.error_auto_refresh_id:
                self.root.after_cancel(self.error_auto_refresh_id)
                self.error_auto_refresh_id = None
    
    def schedule_error_events_refresh(self):
        """Schedule periodic refresh of error events."""
        # Cancel any existing scheduled refresh
        if self.error_auto_refresh_id:
            self.root.after_cancel(self.error_auto_refresh_id)
        
        # Refresh now
        self.refresh_error_events()
        
        # Schedule next refresh if auto-refresh is enabled
        if self.error_auto_refresh_var.get():
            self.error_auto_refresh_id = self.root.after(
                ERROR_EVENTS_REFRESH_INTERVAL,
                self.schedule_error_events_refresh
            )

    def update_status_bar(self, status):
        """Update the status bar at the bottom of the window."""
        self.status_bar.config(text=f"Status: {status}")

    def show_create_memory_dialog(self):
        """Show dialog for creating a new memory."""
        # Create a dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Memory")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # User ID field
        user_frame = tk.Frame(dialog)
        user_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(user_frame, text="User ID:").pack(side=tk.LEFT)
        user_id_var = tk.StringVar(value=DEFAULT_USER_ID)
        user_id_entry = tk.Entry(user_frame, textvariable=user_id_var, width=30)
        user_id_entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        # Content field
        content_frame = tk.Frame(dialog)
        content_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(content_frame, text="Content:").pack(anchor=tk.W)
        content_text = scrolledtext.ScrolledText(content_frame)
        content_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10, padx=20, fill=tk.X)
        
        def create_memory_action():
            user_id = user_id_var.get().strip()
            content = content_text.get(1.0, tk.END).strip()
            
            if not user_id:
                messagebox.showerror("Error", "User ID is required")
                return
                
            if not content:
                messagebox.showerror("Error", "Content is required")
                return
                
            memory = self.create_memory(user_id, content)
            
            if memory:
                messagebox.showinfo("Success", f"Memory created with ID: {memory.get('id')}")
                dialog.destroy()
                
                # Refresh events
                self.refresh_creation_events()
            
        cancel_button = tk.Button(button_frame, text="Cancel", command=dialog.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=5)
        
        create_button = tk.Button(button_frame, text="Create", command=create_memory_action)
        create_button.pack(side=tk.RIGHT, padx=5)
        
        # Set focus to content field
        content_text.focus_set()
    
    def show_update_memory_dialog(self):
        """Show dialog for updating an existing memory."""
        # Ask for memory ID
        memory_id = simpledialog.askstring("Update Memory", "Enter Memory ID to update:")
        
        if not memory_id:
            return
            
        # Try to get the memory
        memory = self.get_memory(memory_id)
        
        if not memory:
            return
            
        # Create a dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Update Memory: {memory_id}")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Memory details frame
        details_frame = tk.Frame(dialog)
        details_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(details_frame, text=f"ID: {memory.get('id')}").pack(anchor=tk.W)
        tk.Label(details_frame, text=f"User: {memory.get('user_id')}").pack(anchor=tk.W)
        tk.Label(details_frame, text=f"Created: {memory.get('created_at')}").pack(anchor=tk.W)
        
        # Content field
        content_frame = tk.Frame(dialog)
        content_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(content_frame, text="Content:").pack(anchor=tk.W)
        content_text = scrolledtext.ScrolledText(content_frame)
        content_text.insert(tk.END, memory.get('content', ''))
        content_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10, padx=20, fill=tk.X)
        
        def update_memory_action():
            content = content_text.get(1.0, tk.END).strip()
            
            if not content:
                messagebox.showerror("Error", "Content is required")
                return
                
            updated_memory = self.update_memory(memory_id, content)
            
            if updated_memory:
                messagebox.showinfo("Success", f"Memory updated: {memory_id}")
                dialog.destroy()
                
                # Refresh events
                self.refresh_update_events()
            
        cancel_button = tk.Button(button_frame, text="Cancel", command=dialog.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=5)
        
        update_button = tk.Button(button_frame, text="Update", command=update_memory_action)
        update_button.pack(side=tk.RIGHT, padx=5)
        
        # Set focus to content field
        content_text.focus_set()
    
    def show_delete_memory_dialog(self):
        """Show dialog for deleting a memory."""
        # Ask for memory ID
        memory_id = simpledialog.askstring("Delete Memory", "Enter Memory ID to delete:")
        
        if not memory_id:
            return
            
        # Try to get the memory first to confirm it exists
        memory = self.get_memory(memory_id)
        
        if not memory:
            return
            
        # Ask for confirmation
        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete this memory?\n\n"
            f"ID: {memory.get('id')}\n"
            f"User: {memory.get('user_id')}\n"
            f"Content: {memory.get('content', '')[:100]}..."
        )
        
        if not confirm:
            return
            
        # Delete the memory
        success = self.delete_memory(memory_id)
        
        if success:
            messagebox.showinfo("Success", f"Memory deleted: {memory_id}")
            
            # Refresh events
            self.refresh_deletion_events()
    
    def show_list_memories_dialog(self):
        """Show dialog for listing memories."""
        # Create a dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("List Memories")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        
        # Filter frame
        filter_frame = tk.Frame(dialog)
        filter_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # User ID field
        tk.Label(filter_frame, text="User ID:").grid(row=0, column=0, sticky=tk.W, padx=5)
        user_id_var = tk.StringVar(value=DEFAULT_USER_ID)
        user_id_entry = tk.Entry(filter_frame, textvariable=user_id_var, width=30)
        user_id_entry.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Page number
        tk.Label(filter_frame, text="Page:").grid(row=0, column=2, sticky=tk.W, padx=5)
        page_var = tk.IntVar(value=1)
        page_entry = tk.Entry(filter_frame, textvariable=page_var, width=5)
        page_entry.grid(row=0, column=3, sticky=tk.W, padx=5)
        
        # Page size
        tk.Label(filter_frame, text="Size:").grid(row=0, column=4, sticky=tk.W, padx=5)
        size_var = tk.IntVar(value=10)
        size_entry = tk.Entry(filter_frame, textvariable=size_var, width=5)
        size_entry.grid(row=0, column=5, sticky=tk.W, padx=5)
        
        # Search button
        search_button = tk.Button(
            filter_frame, 
            text="Search", 
            command=lambda: refresh_memories()
        )
        search_button.grid(row=0, column=6, padx=10)
        
        # Results display
        result_frame = tk.Frame(dialog)
        result_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Create Treeview
        memory_tree = ttk.Treeview(
            result_frame,
            columns=("id", "user_id", "created_at", "content"),
            show="headings",
            height=20
        )
        
        # Configure columns
        memory_tree.heading("id", text="Memory ID")
        memory_tree.heading("user_id", text="User ID")
        memory_tree.heading("created_at", text="Created At")
        memory_tree.heading("content", text="Content")
        
        memory_tree.column("id", width=180, anchor=tk.W)

if __name__ == "__main__":
    root = tk.Tk()
    HetiController(root)
    root.mainloop()
