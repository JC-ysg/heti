"""
Real-Time Memory Monitor for Heti

This module implements a Memory Monitor service that tracks memory-related operations 
in the OpenMemory system in real-time. It detects, logs, and manages events including 
creation, updates, deletion, access, embeddings, and errors.

Configuration is read from config/memory_monitor.yaml and includes:
- Polling interval
- Event types to monitor
- Logging settings
- Error handling and retry policies

Usage:
    from agent.memory_monitor import MemoryMonitor
    
    # Start the monitor
    monitor = MemoryMonitor()
    monitor.start()
    
    # Check status
    status = monitor.get_status()
    print(status)
    
    # Stop the monitor
    monitor.stop(wait_for_completion=True)

Integration with Heticontrol.py:
    The monitor can be started, stopped, and queried for status directly from Heticontrol.py
    using the provided methods.

Log Format:
    {
        "event_id": "unique-event-id",
        "event_type": "memory.created",
        "timestamp": "2023-08-10T14:35:22.123Z",
        "memory_id": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": "user-123",
        "app_id": "app-456",
        "details": {},
        "source": "polling",
        "version": "1.0"
    }

For more detailed information, see @file(.cursor/memory_monitor_spec.mdc)
"""

import os
import sys
import time
import json
import uuid
import yaml
import logging
import hashlib
import threading
import datetime
from typing import Dict, List, Any, Optional, Set, Union
from datetime import datetime, UTC, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Import OpenMemory client
try:
    from tools.openmemory_client import OpenMemoryClient
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tools.openmemory_client import OpenMemoryClient

# Configure logging
logger = logging.getLogger("memory_monitor")

class MemoryMonitor:
    """
    Real-time monitor for OpenMemory operations.
    
    Detects and logs memory events including creation, updates, access, and errors.
    Uses configurable polling and event detection mechanisms.
    """
    
    DEFAULT_CONFIG = {
        "polling": {
            "enabled": True,
            "interval_seconds": 5,
            "max_batch_size": 100,
            "lookback_window_minutes": 5
        },
        "webhooks": {
            "enabled": False,
            "endpoint": "http://localhost:8000/webhook",
            "secret_token": "${WEBHOOK_SECRET}"
        },
        "logging": {
            "file_enabled": True,
            "file_path": "logs/memory_events/events.log",
            "console_level": "INFO",
            "file_level": "DEBUG",
            "rotation": {
                "max_size_mb": 10,
                "backup_count": 5
            }
        },
        "event_types": {
            "memory.created": True,
            "memory.updated": True,
            "memory.deleted": True,
            "memory.accessed": False,
            "embedding.started": True,
            "embedding.completed": True,
            "memory.error": True,
            "memory.batch_operation": True
        },
        "notifications": {
            "error_alert": True,
            "error_threshold": 3,
            "batch_summary_interval_minutes": 15
        },
        "performance": {
            "max_memory_mb": 100,
            "cpu_throttle_percent": 80
        }
    }
    
    def __init__(self, config_path: str = "config/memory_monitor.yaml", api_base_url: str = None):
        """
        Initialize the Memory Monitor.
        
        Args:
            config_path: Path to the YAML configuration file
            api_base_url: Override for the OpenMemory API base URL
        """
        self.config_path = config_path
        self.api_base_url = api_base_url
        
        # Load configuration
        self.config = self._load_config()
        
        # Set up client
        self.client = self._setup_client()
        
        # Set up logging
        self._setup_logging()
        
        # Initialize state
        self.running = False
        self.poll_thread = None
        self.stop_event = threading.Event()
        self.monitor_id = str(uuid.uuid4())
        
        # Event tracking
        self.last_poll_time = datetime.now(UTC)
        self.known_memory_ids = set()
        self.processed_events = set()  # For deduplication
        self.event_counters = {
            "memory.created": 0,
            "memory.updated": 0,
            "memory.deleted": 0,
            "memory.accessed": 0,
            "embedding.started": 0,
            "embedding.completed": 0,
            "memory.error": 0,
            "memory.batch_operation": 0
        }
        
        # Error tracking
        self.consecutive_errors = 0
        self.last_error = None
        self.last_error_time = None
        
        # Status tracking
        self.start_time = None
        self.last_event_time = None
        self.last_event_type = None
        
        logger.info(f"Memory Monitor initialized with ID: {self.monitor_id}")
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file with fallback to defaults.
        
        Returns:
            Dict containing the configuration
        """
        config = self.DEFAULT_CONFIG.copy()
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                
                # Merge configurations (file config takes precedence)
                if file_config:
                    self._merge_dict(config, file_config)
                    logger.info(f"Configuration loaded from {self.config_path}")
            else:
                logger.warning(f"Configuration file {self.config_path} not found, using defaults")
                
                # Create default config file
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False)
                logger.info(f"Default configuration written to {self.config_path}")
                
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            logger.info("Using default configuration")
        
        # Apply environment variable overrides
        self._apply_env_overrides(config)
        
        return config
    
    def _merge_dict(self, base: Dict, update: Dict) -> None:
        """
        Recursively merge two dictionaries.
        
        Args:
            base: Base dictionary to update
            update: Dictionary with updates to apply
        """
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_dict(base[key], value)
            else:
                base[key] = value
    
    def _apply_env_overrides(self, config: Dict) -> None:
        """
        Apply environment variable overrides to configuration.
        
        Uses HETI_MEMORY_MONITOR_* prefix for environment variables.
        
        Args:
            config: Configuration dictionary to update
        """
        prefix = "HETI_MEMORY_MONITOR_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert environment variable to config path
                path = key[len(prefix):].lower().split('_')
                
                # Navigate to the right spot in the config
                current = config
                for part in path[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                # Convert value to appropriate type
                env_value = value
                if env_value.lower() in ('true', 'yes', '1'):
                    env_value = True
                elif env_value.lower() in ('false', 'no', '0'):
                    env_value = False
                elif env_value.isdigit():
                    env_value = int(env_value)
                elif env_value.replace('.', '').isdigit() and env_value.count('.') == 1:
                    env_value = float(env_value)
                
                # Set the value
                current[path[-1]] = env_value
                logger.debug(f"Applied environment override for {key}")
    
    def _setup_client(self) -> OpenMemoryClient:
        """
        Set up the OpenMemory API client.
        
        Returns:
            Configured OpenMemoryClient instance
        """
        base_url = self.api_base_url or "http://localhost:8000"
        timeout = self.config.get("polling", {}).get("timeout_seconds", 30)
        
        return OpenMemoryClient(base_url=base_url, timeout=timeout)
    
    def _setup_logging(self) -> None:
        """Set up logging for the memory monitor."""
        log_config = self.config.get("logging", {})
        
        # Set up logger
        logger.setLevel(logging.DEBUG)  # Capture all logs at logger level
        
        # Clear existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Console handler
        console_level = getattr(logging, log_config.get("console_level", "INFO"))
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler
        if log_config.get("file_enabled", True):
            file_path = log_config.get("file_path", "logs/memory_events/events.log")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            rotation_config = log_config.get("rotation", {})
            max_bytes = rotation_config.get("max_size_mb", 10) * 1024 * 1024
            backup_count = rotation_config.get("backup_count", 5)
            
            file_level = getattr(logging, log_config.get("file_level", "DEBUG"))
            file_handler = RotatingFileHandler(
                file_path, 
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setLevel(file_level)
            
            # Use JSON formatter for file logs
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
            logger.info(f"Log file configured at {file_path}")
        
        logger.debug("Logging configured")
    
    def start(self, config_override: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start the memory monitor.
        
        Args:
            config_override: Optional configuration overrides
            
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            logger.warning("Memory Monitor is already running")
            return False
        
        # Apply config overrides if provided
        if config_override:
            self._merge_dict(self.config, config_override)
            logger.info("Applied configuration overrides")
        
        # Record start time
        self.start_time = datetime.now(UTC)
        
        # Set initial last poll time with lookback window
        lookback_minutes = self.config.get("polling", {}).get("lookback_window_minutes", 5)
        self.last_poll_time = datetime.now(UTC) - timedelta(minutes=lookback_minutes)
        
        # Reset state
        self.stop_event.clear()
        self.running = True
        self.consecutive_errors = 0
        
        # Start polling thread
        self.poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.poll_thread.start()
        
        logger.info(f"Memory Monitor started with ID: {self.monitor_id}")
        
        # Write status file
        self._write_status()
        
        return True
    
    def stop(self, wait_for_completion: bool = True) -> bool:
        """
        Stop the memory monitor.
        
        Args:
            wait_for_completion: Whether to wait for the polling thread to complete
            
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.running:
            logger.warning("Memory Monitor is not running")
            return False
        
        logger.info("Stopping Memory Monitor...")
        
        # Signal the polling thread to stop
        self.stop_event.set()
        self.running = False
        
        # Wait for the thread to complete if requested
        if wait_for_completion and self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=10)
            if self.poll_thread.is_alive():
                logger.warning("Polling thread did not terminate within timeout")
        
        logger.info(f"Memory Monitor stopped. Total events processed: {sum(self.event_counters.values())}")
        
        # Write final status
        self._write_status()
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the memory monitor.
        
        Returns:
            Dict containing status information
        """
        uptime = None
        if self.start_time:
            uptime = (datetime.now(UTC) - self.start_time).total_seconds()
        
        status = {
            "monitor_id": self.monitor_id,
            "running": self.running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": uptime,
            "events_processed": sum(self.event_counters.values()),
            "events_by_type": self.event_counters.copy(),
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
            "last_event_type": self.last_event_type,
            "last_poll_time": self.last_poll_time.isoformat() if self.last_poll_time else None,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "consecutive_errors": self.consecutive_errors,
            "health": self._calculate_health_status()
        }
        
        return status
    
    def _calculate_health_status(self) -> str:
        """
        Calculate the current health status of the monitor.
        
        Returns:
            str: "OK", "WARNING", or "ERROR"
        """
        if not self.running:
            return "STOPPED"
            
        error_threshold = self.config.get("notifications", {}).get("error_threshold", 3)
        
        if self.consecutive_errors >= error_threshold:
            return "ERROR"
        elif self.consecutive_errors > 0:
            return "WARNING"
        else:
            return "OK"
    
    def _write_status(self) -> None:
        """Write the current status to a JSON file for external monitoring."""
        try:
            status_path = "logs/memory_monitor_status.json"
            os.makedirs(os.path.dirname(status_path), exist_ok=True)
            
            with open(status_path, 'w') as f:
                json.dump(self.get_status(), f, indent=2)
                
            logger.debug(f"Status written to {status_path}")
        except Exception as e:
            logger.error(f"Error writing status file: {str(e)}")
    
    def _polling_loop(self) -> None:
        """Main polling loop for detecting memory events."""
        logger.info("Polling loop started")
        
        # Initialize with bootstrap poll to get current memories
        try:
            self._bootstrap_poll()
        except Exception as e:
            logger.error(f"Error during bootstrap poll: {str(e)}")
        
        # Main polling loop
        while not self.stop_event.is_set():
            try:
                # Poll for new events
                self._poll_for_events()
                
                # Reset consecutive errors on success
                if self.consecutive_errors > 0:
                    logger.info(f"Recovered after {self.consecutive_errors} consecutive errors")
                    self.consecutive_errors = 0
                
                # Write status periodically
                self._write_status()
                
            except Exception as e:
                # Log error and increment counter
                self.consecutive_errors += 1
                self.last_error = str(e)
                self.last_error_time = datetime.now(UTC)
                
                logger.error(f"Error during polling (attempt {self.consecutive_errors}): {str(e)}")
                
                # Handle consecutive failures
                if self.consecutive_errors >= self.config.get("notifications", {}).get("error_threshold", 3):
                    self._handle_persistent_error()
            
            # Wait for next poll interval
            interval = self._get_current_poll_interval()
            logger.debug(f"Waiting {interval} seconds until next poll")
            
            # Use stop_event to allow clean shutdown
            if self.stop_event.wait(interval):
                break
    
    def _bootstrap_poll(self) -> None:
        """
        Perform initial poll to establish baseline of existing memories.
        This prevents false "new memory" detections on startup.
        """
        logger.info("Performing bootstrap poll...")
        
        # Use a larger batch size for initial poll
        batch_size = self.config.get("polling", {}).get("max_batch_size", 100) * 2
        
        # Get recent memories
        try:
            result = self.client.list_memories(
                user_id="*",  # All users
                page=1,
                size=batch_size
            )
            
            # Store memory IDs for baseline
            if "items" in result and isinstance(result["items"], list):
                for memory in result["items"]:
                    if "id" in memory:
                        self.known_memory_ids.add(memory["id"])
                
                logger.info(f"Bootstrap poll complete. Tracking {len(self.known_memory_ids)} existing memories")
            else:
                logger.warning("Bootstrap poll returned unexpected data structure")
                
        except Exception as e:
            logger.error(f"Bootstrap poll failed: {str(e)}")
            # Continue anyway - we'll recover in subsequent polls
    
    def _poll_for_events(self) -> None:
        """
        Poll for memory events from the OpenMemory API.
        Detects created, updated, and other event types.
        """
        # Get poll configuration
        polling_config = self.config.get("polling", {})
        batch_size = polling_config.get("max_batch_size", 100)
        
        # Timestamp for this poll
        current_poll_time = datetime.now(UTC)
        
        # Add a small buffer to avoid missing events due to clock skew
        buffer_seconds = polling_config.get("timestamp_buffer_seconds", 1)
        from_time = self.last_poll_time - timedelta(seconds=buffer_seconds)
        
        logger.debug(f"Polling for events since {from_time.isoformat()}")
        
        # Check for different event types based on configuration
        event_types_config = self.config.get("event_types", {})
        
        # Track new memory IDs seen in this poll
        memories_this_poll = set()
        
        # 1. Check for created/updated memories
        if event_types_config.get("memory.created", True) or event_types_config.get("memory.updated", True):
            self._poll_for_created_and_updated_memories(from_time, batch_size, memories_this_poll)
        
        # 2. Check for deleted memories (if enabled)
        if event_types_config.get("memory.deleted", True):
            self._detect_deleted_memories(memories_this_poll)
        
        # 3. Check for memory access (if enabled and endpoint available)
        if event_types_config.get("memory.accessed", False):
            self._poll_for_memory_access(from_time, batch_size)
        
        # 4. Check for embedding operations (if enabled)
        if event_types_config.get("embedding.started", True) or event_types_config.get("embedding.completed", True):
            self._poll_for_embedding_operations(from_time, batch_size)
        
        # Update last poll time
        self.last_poll_time = current_poll_time
    
    def _poll_for_created_and_updated_memories(
        self, 
        from_time: datetime, 
        batch_size: int,
        memories_this_poll: Set[str]
    ) -> None:
        """
        Poll for created and updated memories.
        
        Args:
            from_time: Time to poll from
            batch_size: Maximum batch size
            memories_this_poll: Set to track memories seen in this poll
        """
        try:
            # Poll for created memories
            if self.config.get("event_types", {}).get("memory.created", True):
                created_result = self.client.list_memories(
                    user_id="*",  # All users
                    from_date=int(from_time.timestamp()),
                    page=1,
                    size=batch_size,
                    sort_column="created_at",
                    sort_direction="asc"
                )
                
                if "items" in created_result and isinstance(created_result["items"], list):
                    for memory in created_result["items"]:
                        memory_id = memory.get("id")
                        if memory_id:
                            memories_this_poll.add(memory_id)
                            
                            # If this is a new memory (not seen before)
                            if memory_id not in self.known_memory_ids:
                                self._process_memory_created_event(memory)
                                self.known_memory_ids.add(memory_id)
            
            # Poll for updated memories
            if self.config.get("event_types", {}).get("memory.updated", True):
                updated_result = self.client.list_memories(
                    user_id="*",  # All users
                    from_date=int(from_time.timestamp()),
                    page=1,
                    size=batch_size,
                    sort_column="updated_at",
                    sort_direction="asc"
                )
                
                if "items" in updated_result and isinstance(updated_result["items"], list):
                    for memory in updated_result["items"]:
                        memory_id = memory.get("id")
                        if memory_id:
                            memories_this_poll.add(memory_id)
                            
                            # Check if this is an update (not a new memory)
                            if memory_id in self.known_memory_ids:
                                # Further check if updated_at is newer than created_at
                                created_at = self._parse_timestamp(memory.get("created_at"))
                                updated_at = self._parse_timestamp(memory.get("updated_at"))
                                
                                if updated_at and created_at and updated_at > created_at:
                                    self._process_memory_updated_event(memory)
        
        except Exception as e:
            logger.error(f"Error polling for created/updated memories: {str(e)}")
            raise
    
    def _detect_deleted_memories(self, current_memories: Set[str]) -> None:
        """
        Detect deleted memories by comparing previous known IDs with current ones.
        
        Args:
            current_memories: Set of memory IDs seen in the current poll
        """
        if not self.config.get("event_types", {}).get("memory.deleted", True):
            return
            
        # Skip detection on first poll (known_memory_ids might be incomplete)
        if not self.known_memory_ids or len(current_memories) == 0:
            return
            
        # Find memories that were known but not seen in this poll
        potentially_deleted = self.known_memory_ids - current_memories
        
        if potentially_deleted:
            logger.debug(f"Detected {len(potentially_deleted)} potentially deleted memories")
            
            # For each potentially deleted memory, check if it still exists
            for memory_id in list(potentially_deleted):
                try:
                    # Try to get the memory
                    self.client.get_memory(memory_id)
                    # If we get here, memory still exists
                    logger.debug(f"Memory {memory_id} still exists despite not being in poll results")
                except ValueError as e:
                    # If we get "Memory not found" error, it's confirmed deleted
                    if "Memory not found" in str(e):
                        self._process_memory_deleted_event(memory_id)
                        self.known_memory_ids.remove(memory_id)
                except Exception as e:
                    logger.error(f"Error checking memory {memory_id} deletion status: {str(e)}")
    
    def _poll_for_memory_access(self, from_time: datetime, batch_size: int) -> None:
        """
        Poll for memory access events.
        
        Args:
            from_time: Time to poll from
            batch_size: Maximum batch size
        """
        # NOTE: This is a placeholder implementation as the exact API for access logs is not specified
        # In a real implementation, this would call a specific endpoint like /api/v1/memories/access-log
        logger.debug("Memory access polling not implemented - requires specific API endpoint")
    
    def _poll_for_embedding_operations(self, from_time: datetime, batch_size: int) -> None:
        """
        Poll for embedding operations.
        
        Args:
            from_time: Time to poll from
            batch_size: Maximum batch size
        """
        # NOTE: This is a placeholder implementation as the exact API for embedding ops is not specified
        # In a real implementation, this would call a specific endpoint
        logger.debug("Embedding operations polling not implemented - requires specific API endpoint")
    
    def _process_memory_created_event(self, memory: Dict[str, Any]) -> None:
        """
        Process a memory creation event.
        
        Args:
            memory: Memory object data
        """
        event_id = str(uuid.uuid4())
        memory_id = memory.get("id")
        
        # Generate fingerprint for deduplication
        fingerprint = self._generate_event_fingerprint("memory.created", memory_id, memory.get("created_at"))
        
        # Skip if already processed
        if fingerprint in self.processed_events:
            logger.debug(f"Skipping duplicate memory.created event for {memory_id}")
            return
        
        # Add to processed set
        self.processed_events.add(fingerprint)
        
        # Trim processed events set if it gets too large
        if len(self.processed_events) > 1000:
            self.processed_events = set(list(self.processed_events)[-500:])
        
        # Create event object
        event = {
            "event_id": event_id,
            "event_type": "memory.created",
            "timestamp": datetime.now(UTC).isoformat(),
            "memory_id": memory_id,
            "user_id": memory.get("user_id"),
            "app_id": memory.get("app_id"),
            "content_summary": self._generate_content_summary(memory.get("content", "")),
            "categories": memory.get("categories", []),
            "created_at": memory.get("created_at"),
            "details": {
                "metadata": memory.get("metadata_", {}),
                "state": memory.get("state"),
                "app_name": memory.get("app_name")
            },
            "source": "polling",
            "version": "1.0",
            "monitor_id": self.monitor_id
        }
        
        # Log the event
        self._log_event(event)
        
        # Update counters
        self.event_counters["memory.created"] += 1
        self.last_event_time = datetime.now(UTC)
        self.last_event_type = "memory.created"
        
        logger.info(f"Detected memory creation: {memory_id}")
    
    def _process_memory_updated_event(self, memory: Dict[str, Any]) -> None:
        """
        Process a memory update event.
        
        Args:
            memory: Memory object data
        """
        event_id = str(uuid.uuid4())
        memory_id = memory.get("id")
        
        # Generate fingerprint for deduplication
        fingerprint = self._generate_event_fingerprint("memory.updated", memory_id, memory.get("updated_at"))
        
        # Skip if already processed
        if fingerprint in self.processed_events:
            logger.debug(f"Skipping duplicate memory.updated event for {memory_id}")
            return
        
        # Add to processed set
        self.processed_events.add(fingerprint)
        
        # Create event object
        event = {
            "event_id": event_id,
            "event_type": "memory.updated",
            "timestamp": datetime.now(UTC).isoformat(),
            "memory_id": memory_id,
            "user_id": memory.get("user_id"),
            "app_id": memory.get("app_id"),
            "content_summary": self._generate_content_summary(memory.get("content", "")),
            "categories": memory.get("categories", []),
            "created_at": memory.get("created_at"),
            "updated_at": memory.get("updated_at"),
            "details": {
                "metadata": memory.get("metadata_", {}),
                "state": memory.get("state"),
                "app_name": memory.get("app_name")
            },
            "source": "polling",
            "version": "1.0",
            "monitor_id": self.monitor_id
        }
        
        # Log the event
        self._log_event(event)
        
        # Update counters
        self.event_counters["memory.updated"] += 1
        self.last_event_time = datetime.now(UTC)
        self.last_event_type = "memory.updated"
        
        logger.info(f"Detected memory update: {memory_id}")
    
    def _process_memory_deleted_event(self, memory_id: str) -> None:
        """
        Process a memory deletion event.
        
        Args:
            memory_id: ID of the deleted memory
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()
        
        # Generate fingerprint for deduplication
        fingerprint = self._generate_event_fingerprint("memory.deleted", memory_id, timestamp)
        
        # Skip if already processed
        if fingerprint in self.processed_events:
            logger.debug(f"Skipping duplicate memory.deleted event for {memory_id}")
            return
        
        # Add to processed set
        self.processed_events.add(fingerprint)
        
        # Create event object
        event = {
            "event_id": event_id,
            "event_type": "memory.deleted",
            "timestamp": timestamp,
            "memory_id": memory_id,
            "details": {
                "detection_method": "polling_comparison"
            },
            "source": "polling",
            "version": "1.0",
            "monitor_id": self.monitor_id
        }
        
        # Log the event
        self._log_event(event)
        
        # Update counters
        self.event_counters["memory.deleted"] += 1
        self.last_event_time = datetime.now(UTC)
        self.last_event_type = "memory.deleted"
        
        logger.info(f"Detected memory deletion: {memory_id}")
    
    def _log_event(self, event: Dict[str, Any]) -> None:
        """
        Log a memory event to the event log file.
        
        Args:
            event: Event data to log
        """
        # Log to dedicated event log file
        event_log_path = self.config.get("logging", {}).get("event_log_path", "logs/memory_events/memory_events.jsonl")
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(event_log_path), exist_ok=True)
            
            # Append to log file
            with open(event_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
            
            # Log event detection with normal logger
            event_type = event.get("event_type", "unknown")
            memory_id = event.get("memory_id", "unknown")
            
            log_message = f"Memory event: {event_type} - Memory ID: {memory_id}"
            logger.info(log_message)
            
        except Exception as e:
            logger.error(f"Error logging event: {str(e)}")
    
    def _generate_content_summary(self, content: str, max_length: int = 100) -> str:
        """
        Generate a summary of memory content suitable for logging.
        
        Args:
            content: The full memory content
            max_length: Maximum length of the summary
            
        Returns:
            Shortened content summary
        """
        if not content:
            return ""
            
        # Truncate if needed
        if len(content) <= max_length:
            return content
            
        # Truncate and add ellipsis
        return content[:max_length - 3] + "..."
    
    def _generate_event_fingerprint(self, event_type: str, memory_id: str, timestamp: str) -> str:
        """
        Generate a unique fingerprint for event deduplication.
        
        Args:
            event_type: Type of the event
            memory_id: Memory ID
            timestamp: Event timestamp
            
        Returns:
            Fingerprint string
        """
        # Combine data into a string
        data = f"{event_type}:{memory_id}:{timestamp}"
        
        # Generate a hash
        return hashlib.md5(data.encode()).hexdigest()
    
    def _handle_persistent_error(self) -> None:
        """Handle persistent errors in the polling process."""
        error_threshold = self.config.get("notifications", {}).get("error_threshold", 3)
        
        if self.consecutive_errors >= error_threshold:
            logger.error(f"Persistent error condition detected: {self.consecutive_errors} consecutive errors")
            
            # Increase polling interval temporarily
            logger.info("Increasing polling interval temporarily to allow system recovery")
            
            # Alert if configured
            if self.config.get("notifications", {}).get("error_alert", True):
                # In a real implementation, this would send alerts via configured channels
                logger.critical(f"ALERT: Memory Monitor experiencing persistent errors: {self.last_error}")
    
    def _get_current_poll_interval(self) -> float:
        """
        Get the current polling interval, adjusted for error conditions.
        
        Returns:
            float: Polling interval in seconds
        """
        base_interval = self.config.get("polling", {}).get("interval_seconds", 5)
        
        # Increase interval during error conditions
        if self.consecutive_errors > 0:
            # Apply exponential backoff
            backoff_factor = min(2 ** self.consecutive_errors, 10)  # Cap at 10x
            return base_interval * backoff_factor
        
        return base_interval
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """
        Parse an ISO timestamp string to datetime.
        
        Args:
            timestamp_str: ISO timestamp string
            
        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp_str:
            return None
            
        try:
            # Try to parse ISO format with timezone info
            if isinstance(timestamp_str, str):
                # Handle +00:00 format (Python 3.6+ compatible)
                if '+00:00' in timestamp_str:
                    timestamp_str = timestamp_str.replace('+00:00', 'Z')
                
                # Try datetime.fromisoformat for modern Python versions
                try:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    # Ensure UTC timezone
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    return dt
                except ValueError:
                    pass
                
                # Fall back to manual parsing
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        dt = datetime.strptime(timestamp_str, fmt)
                        # Always ensure UTC timezone
                        return dt.replace(tzinfo=UTC)
                    except ValueError:
                        continue
                    
                # If we get here, none of the formats matched
                logger.warning(f"Could not parse timestamp: {timestamp_str}")
                return None
            else:
                logger.warning(f"Invalid timestamp type: {type(timestamp_str)}")
                return None
            
        except Exception as e:
            logger.error(f"Error parsing timestamp {timestamp_str}: {str(e)}")
            return None

    def poll_new_creations(self) -> List[Dict[str, Any]]:
        """
        Poll the OpenMemory API for newly created memories since the last checked timestamp.
        
        This method queries the OpenMemory API for memories created after the last_checked 
        timestamp, logs them as "creation" events, and updates the deduplication cache to 
        prevent duplicate event logging.
        
        Returns:
            List of new memory creation events detected and logged
            
        Configuration used:
            - polling.interval_seconds: Time between polls
            - polling.max_batch_size: Maximum memories to fetch per request
            - logging.event_log_path: Path to log events
            
        Deduplication:
            Uses memory_id to prevent duplicate "creation" events for the same memory
        """
        # Get config values
        polling_config = self.config.get("polling", {})
        batch_size = polling_config.get("max_batch_size", 100)
        
        # Calculate from_time with a small buffer to avoid missing events due to clock skew
        buffer_seconds = polling_config.get("timestamp_buffer_seconds", 1)
        from_time = self.last_poll_time - timedelta(seconds=buffer_seconds)
        
        logger.debug(f"Polling for newly created memories since {from_time.isoformat()}")
        
        # List to store detected events
        detected_events = []
        
        try:
            # Query the OpenMemory API for new memories
            created_result = self.client.list_memories(
                user_id="*",  # All users
                from_date=int(from_time.timestamp()),
                page=1,
                size=batch_size,
                sort_column="created_at",
                sort_direction="asc"
            )
            
            if "items" in created_result and isinstance(created_result["items"], list):
                # Process each memory item
                for memory in created_result["items"]:
                    memory_id = memory.get("id")
                    if memory_id:
                        # If this is a new memory (not seen before)
                        if memory_id not in self.known_memory_ids:
                            # Process and log the memory creation event
                            event = self._create_memory_creation_event(memory)
                            if event:
                                detected_events.append(event)
                            
                            # Add memory_id to deduplication cache
                            self.known_memory_ids.add(memory_id)
                
                logger.info(f"Detected {len(detected_events)} new memory creation events")
            else:
                logger.warning("Memory query returned unexpected data structure")
                
            # Update the last poll time (only if the API call was successful)
            self.last_poll_time = datetime.now(UTC)
            
        except Exception as e:
            # Log error but don't update last_poll_time to retry on next poll
            logger.error(f"Error polling for new memories: {str(e)}")
            self.consecutive_errors += 1
            self.last_error = str(e)
            self.last_error_time = datetime.now(UTC)
        
        return detected_events
    
    def _create_memory_creation_event(self, memory: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create and log a memory creation event.
        
        Args:
            memory: Memory object data from API
            
        Returns:
            Event object that was logged or None if skipped
        """
        event_id = str(uuid.uuid4())
        memory_id = memory.get("id")
        
        # Generate fingerprint for deduplication
        fingerprint = self._generate_event_fingerprint("creation", memory_id, memory.get("created_at"))
        
        # Skip if already processed
        if fingerprint in self.processed_events:
            logger.debug(f"Skipping duplicate creation event for {memory_id}")
            return None
        
        # Add to processed set
        self.processed_events.add(fingerprint)
        
        # Trim processed events set if it gets too large
        if len(self.processed_events) > 1000:
            self.processed_events = set(list(self.processed_events)[-500:])
        
        # Create event object
        event = {
            "event_type": "creation",
            "timestamp": datetime.now(UTC).isoformat(),
            "memory_id": memory_id,
            "details": {
                "user_id": memory.get("user_id"),
                "app_id": memory.get("app_id"),
                "content_summary": self._generate_content_summary(memory.get("content", "")),
                "categories": memory.get("categories", []),
                "created_at": memory.get("created_at"),
                "metadata": memory.get("metadata_", {})
            },
            "source": "MemoryMonitor",
            "run_id": self.monitor_id
        }
        
        # Log the event
        self._log_memory_event(event)
        
        # Update counters
        self.event_counters["memory.created"] += 1
        self.last_event_time = datetime.now(UTC)
        self.last_event_type = "memory.created"
        
        logger.info(f"Detected memory creation: {memory_id}")
        
        return event
    
    def _log_memory_event(self, event: Dict[str, Any]) -> None:
        """
        Log a memory event to the configured log file in JSON format.
        
        Args:
            event: Event data to log
        """
        # Get log file path from config
        log_file_path = self.config.get("logging", {}).get("event_log_path", "logs/memory_monitor.log")
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            
            # Append to log file as a single JSON line
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
            
            # Also log a summary with normal logger
            event_type = event.get("event_type", "unknown")
            memory_id = event.get("memory_id", "unknown")
            
            log_message = f"Memory event: {event_type} - Memory ID: {memory_id}"
            logger.info(log_message)
            
        except Exception as e:
            logger.error(f"Error logging memory event: {str(e)}")

    def poll_memory_updates(self) -> List[Dict[str, Any]]:
        """
        Poll the OpenMemory API for memories updated since the last checked timestamp.
        
        This method queries the OpenMemory API for memories with updated_at times after
        the last_checked timestamp, logs them as "update" events, and updates the
        deduplication cache to prevent duplicate event logging.
        
        Returns:
            List of memory update events detected and logged
            
        Configuration used:
            - polling.interval_seconds: Time between polls
            - polling.max_batch_size: Maximum memories to fetch per request
            - logging.event_log_path: Path to log events
            
        Deduplication:
            Uses memory_id and updated_at timestamp to prevent duplicate "update" events
        """
        # Get config values
        polling_config = self.config.get("polling", {})
        batch_size = polling_config.get("max_batch_size", 100)
        
        # Calculate from_time with a small buffer to avoid missing events due to clock skew
        buffer_seconds = polling_config.get("timestamp_buffer_seconds", 1)
        from_time = self.last_poll_time - timedelta(seconds=buffer_seconds)
        
        logger.debug(f"Polling for updated memories since {from_time.isoformat()}")
        
        # Initialize update deduplication cache if not present
        if not hasattr(self, "update_deduplication_cache"):
            self.update_deduplication_cache = set()
            
        # List to store detected update events
        detected_updates = []
        
        try:
            # Query the OpenMemory API for updated memories
            updated_result = self.client.list_memories(
                user_id="*",  # All users
                from_date=int(from_time.timestamp()),
                page=1,
                size=batch_size,
                sort_column="updated_at",
                sort_direction="asc"
            )
            
            if "items" in updated_result and isinstance(updated_result["items"], list):
                # Process each memory item
                for memory in updated_result["items"]:
                    memory_id = memory.get("id")
                    updated_at = memory.get("updated_at")
                    created_at = memory.get("created_at")
                    
                    if memory_id and updated_at and created_at:
                        # Parse timestamps for comparison
                        updated_time = self._parse_timestamp(updated_at)
                        created_time = self._parse_timestamp(created_at)
                        
                        # Only consider this an update if:
                        # 1. The memory is already known (not a new memory)
                        # 2. updated_at is newer than created_at (actual update occurred)
                        if (memory_id in self.known_memory_ids and 
                            updated_time and created_time and 
                            updated_time > created_time):
                            
                            # Generate fingerprint for deduplication
                            fingerprint = self._generate_event_fingerprint("update", memory_id, updated_at)
                            
                            # Process if not already seen
                            if fingerprint not in self.update_deduplication_cache:
                                # Process and log the memory update event
                                event = self._create_memory_update_event(memory)
                                if event:
                                    detected_updates.append(event)
                                
                                # Add to deduplication cache
                                self.update_deduplication_cache.add(fingerprint)
                        
                        # Always ensure the memory is in known_memory_ids
                        # This helps identify future updates properly
                        if memory_id not in self.known_memory_ids:
                            self.known_memory_ids.add(memory_id)
                
                logger.info(f"Detected {len(detected_updates)} memory update events")
                
                # Trim deduplication cache if it gets too large
                if len(self.update_deduplication_cache) > 1000:
                    self.update_deduplication_cache = set(list(self.update_deduplication_cache)[-500:])
            else:
                logger.warning("Memory query returned unexpected data structure")
                
            # Update the last poll time (only if the API call was successful)
            self.last_poll_time = datetime.now(UTC)
            
        except Exception as e:
            # Log error but don't update last_poll_time to retry on next poll
            logger.error(f"Error polling for updated memories: {str(e)}")
            self.consecutive_errors += 1
            self.last_error = str(e)
            self.last_error_time = datetime.now(UTC)
        
        return detected_updates
    
    def _create_memory_update_event(self, memory: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create and log a memory update event.
        
        Args:
            memory: Memory object data from API
            
        Returns:
            Event object that was logged or None if skipped
        """
        event_id = str(uuid.uuid4())
        memory_id = memory.get("id")
        
        # Create event object
        event = {
            "event_type": "update",
            "timestamp": datetime.now(UTC).isoformat(),
            "memory_id": memory_id,
            "details": {
                "user_id": memory.get("user_id"),
                "app_id": memory.get("app_id"),
                "content_summary": self._generate_content_summary(memory.get("content", "")),
                "categories": memory.get("categories", []),
                "created_at": memory.get("created_at"),
                "updated_at": memory.get("updated_at"),
                "metadata": memory.get("metadata_", {})
            },
            "source": "MemoryMonitor",
            "run_id": self.monitor_id
        }
        
        # Log the event
        self._log_memory_event(event)
        
        # Update counters
        self.event_counters["memory.updated"] += 1
        self.last_event_time = datetime.now(UTC)
        self.last_event_type = "memory.updated"
        
        logger.info(f"Detected memory update: {memory_id}")
        
        return event

    def poll_memory_deletions(self) -> List[Dict[str, Any]]:
        """
        Poll for memory deletion events since the last checked timestamp.
        
        This method detects deleted memories by comparing the current set of memory IDs
        from the OpenMemory API with the previously known set of IDs. When a memory ID
        is present in the known set but missing from the current set, it is considered
        a potential deletion. Each potential deletion is verified by attempting to retrieve
        the memory directly, and if a "Memory not found" error is received, the deletion
        is confirmed and logged.
        
        Returns:
            List of memory deletion events detected and logged
            
        Configuration used:
            - polling.interval_seconds: Time between polls
            - polling.max_batch_size: Maximum memories to fetch per request
            - logging.event_log_path: Path to log events
            
        Deduplication:
            Uses memory_id and detection timestamp to prevent duplicate "deletion" events
        """
        # Get config values
        polling_config = self.config.get("polling", {})
        batch_size = polling_config.get("max_batch_size", 100)
        
        logger.debug("Polling for memory deletion events")
        
        # Initialize deletion deduplication cache if not present
        if not hasattr(self, "deletion_deduplication_cache"):
            self.deletion_deduplication_cache = set()
        
        # List to store detected deletion events
        detected_deletions = []
        
        # Skip detection if we don't have any known memory IDs yet
        if not self.known_memory_ids:
            logger.debug("No known memory IDs yet, skipping deletion detection")
            return detected_deletions
        
        try:
            # Get current list of all memory IDs
            current_memories_result = self.client.list_memories(
                user_id="*",  # All users
                page=1,
                size=batch_size
            )
            
            # Set to hold current memory IDs
            current_memory_ids = set()
            
            # Extract memory IDs from response
            if "items" in current_memories_result and isinstance(current_memories_result["items"], list):
                for memory in current_memories_result["items"]:
                    if "id" in memory:
                        current_memory_ids.add(memory["id"])
                
                logger.debug(f"Found {len(current_memory_ids)} memories in current API response")
            else:
                logger.warning("Memory query returned unexpected data structure")
                return detected_deletions
            
            # Find potentially deleted memories (present in known set but missing from current set)
            potentially_deleted = self.known_memory_ids - current_memory_ids
            
            if potentially_deleted:
                logger.debug(f"Detected {len(potentially_deleted)} potentially deleted memories")
                
                # For each potentially deleted memory, verify deletion by direct query
                for memory_id in list(potentially_deleted):
                    # Skip if this deletion was already processed
                    deletion_fingerprint = self._generate_event_fingerprint(
                        "deletion", memory_id, datetime.now(UTC).isoformat()
                    )
                    
                    if deletion_fingerprint in self.deletion_deduplication_cache:
                        logger.debug(f"Skipping already processed deletion of memory {memory_id}")
                        continue
                    
                    try:
                        # Try to get the memory directly to confirm deletion
                        self.client.get_memory(memory_id)
                        # If we get here, memory still exists
                        logger.debug(f"Memory {memory_id} still exists despite not being in poll results")
                    except ValueError as e:
                        # If we get "Memory not found" error, it's confirmed deleted
                        if "Memory not found" in str(e):
                            # Process and log the deletion event
                            event = self._create_memory_deletion_event(memory_id)
                            if event:
                                detected_deletions.append(event)
                            
                            # Add to deduplication cache
                            self.deletion_deduplication_cache.add(deletion_fingerprint)
                            
                            # Remove from known_memory_ids
                            self.known_memory_ids.remove(memory_id)
                    except Exception as e:
                        logger.error(f"Error checking memory {memory_id} deletion status: {str(e)}")
                
                # Trim deduplication cache if it gets too large
                if len(self.deletion_deduplication_cache) > 1000:
                    self.deletion_deduplication_cache = set(list(self.deletion_deduplication_cache)[-500:])
            
            # Update the last poll time
            self.last_poll_time = datetime.now(UTC)
            
        except Exception as e:
            # Log error but don't update last_poll_time to retry on next poll
            logger.error(f"Error polling for deleted memories: {str(e)}")
            self.consecutive_errors += 1
            self.last_error = str(e)
            self.last_error_time = datetime.now(UTC)
        
        return detected_deletions
    
    def _create_memory_deletion_event(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Create and log a memory deletion event.
        
        Args:
            memory_id: ID of the deleted memory
            
        Returns:
            Event object that was logged or None if skipped
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()
        
        # Create event object
        event = {
            "event_type": "deletion",
            "timestamp": timestamp,
            "memory_id": memory_id,
            "details": {
                "detection_method": "id_comparison"
            },
            "source": "MemoryMonitor",
            "run_id": self.monitor_id
        }
        
        # Log the event
        self._log_memory_event(event)
        
        # Update counters
        self.event_counters["memory.deleted"] += 1
        self.last_event_time = datetime.now(UTC)
        self.last_event_type = "memory.deleted"
        
        logger.info(f"Detected memory deletion: {memory_id}")
        
        return event

    def log_monitor_error(self, error_type: str, message: str, context: dict = None) -> None:
        """
        Log a monitor error event.
        
        This method is called internally whenever the monitor encounters a recoverable error
        such as API/network failures, malformed data, polling failures, or unhandled exceptions.
        It logs the error as an "error" event and implements deduplication to avoid logging
        the same error repeatedly in rapid succession.
        
        Args:
            error_type: Type of error (e.g., "APIError", "NetworkError", "ConfigError")
            message: Short error message
            context: Additional context or metadata for the error (optional)
                
        Configuration used:
            - logging.event_log_path: Path to log events
            - error.deduplication_window_seconds: Time window for error deduplication (default: 60s)
            
        Deduplication:
            Uses error_type, message, and a hash of the context to prevent duplicate error logging
            within a configured time window.
        """
        # Normalize context to empty dict if None
        if context is None:
            context = {}
        
        # Generate fingerprint for deduplication
        fingerprint = self._generate_error_fingerprint(error_type, message, context)
        
        # Initialize error deduplication cache if not present
        if not hasattr(self, "error_deduplication_cache"):
            self.error_deduplication_cache = {}
        
        # Get current time
        current_time = datetime.now(UTC)
        
        # Check for deduplication
        if fingerprint in self.error_deduplication_cache:
            last_logged_time = self.error_deduplication_cache[fingerprint]
            
            # Get deduplication window from config (default: 60 seconds)
            dedup_window = self.config.get("error", {}).get("deduplication_window_seconds", 60)
            
            # If the same error was logged recently, skip logging
            if (current_time - last_logged_time).total_seconds() < dedup_window:
                logger.debug(f"Skipping duplicate error log for {error_type}: {message}")
                return
        
        # Update deduplication cache
        self.error_deduplication_cache[fingerprint] = current_time
        
        # Trim error deduplication cache if it gets too large
        if len(self.error_deduplication_cache) > 1000:
            # Remove oldest entries
            sorted_items = sorted(self.error_deduplication_cache.items(), key=lambda x: x[1])
            self.error_deduplication_cache = dict(sorted_items[-500:])
        
        # Create event object
        event = {
            "event_type": "error",
            "timestamp": current_time.isoformat(),
            "error_type": error_type,
            "message": message,
            "context": context,
            "source": "MemoryMonitor",
            "run_id": self.monitor_id
        }
        
        # Log the event
        self._log_memory_event(event)
        
        # Update counters
        self.event_counters["memory.error"] += 1
        self.last_event_time = current_time
        self.last_event_type = "memory.error"
        
        # Update error tracking properties
        self.last_error = message
        self.last_error_time = current_time
        
        logger.error(f"Monitor error: {error_type} - {message}")
    
    def _generate_error_fingerprint(self, error_type: str, message: str, context: dict) -> str:
        """
        Generate a unique fingerprint for error deduplication.
        
        Args:
            error_type: Type of the error
            message: Error message
            context: Error context dictionary
                
        Returns:
            Fingerprint string
        """
        # Combine data into a string, only including stable parts of the context
        # Sort the context keys to ensure consistent fingerprinting
        context_str = json.dumps(context, sort_keys=True) if context else ""
        data = f"{error_type}:{message}:{context_str}"
        
        # Generate a hash
        return hashlib.md5(data.encode()).hexdigest()


# For direct execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Heti Memory Monitor")
    parser.add_argument("--config", default="config/memory_monitor.yaml", help="Path to configuration file")
    parser.add_argument("--api-url", help="Override for OpenMemory API base URL")
    parser.add_argument("--run", action="store_true", help="Start the monitor immediately")
    parser.add_argument("--status", action="store_true", help="Print current status and exit")
    
    args = parser.parse_args()
    
    # Create monitor
    monitor = MemoryMonitor(config_path=args.config, api_base_url=args.api_url)
    
    if args.status:
        # Print status and exit
        status = monitor.get_status()
        print(json.dumps(status, indent=2))
        sys.exit(0)
        
    if args.run:
        # Run the monitor
        try:
            monitor.start()
            print(f"Memory Monitor started. Press Ctrl+C to stop.")
            
            # Keep main thread alive
            while monitor.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("Shutting down Memory Monitor...")
            monitor.stop(wait_for_completion=True)
            print("Memory Monitor stopped.") 