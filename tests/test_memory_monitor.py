"""
Unit tests for the Memory Monitor

These tests verify the core functionality of the Memory Monitor including:
- Configuration loading
- Event detection
- Log handling
- Error recovery
- Deduplication
"""

import os
import json
import uuid
import tempfile
import unittest
import logging
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC, timedelta

# Import the module we're testing
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.memory_monitor import MemoryMonitor


class TestMemoryMonitor(unittest.TestCase):
    """Test suite for Memory Monitor."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary config file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "test_config.yaml")
        
        # Create log directory
        self.log_dir = os.path.join(self.temp_dir.name, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create unique file paths for each test
        self.test_id = str(uuid.uuid4())[:8]
        self.log_file = os.path.join(self.log_dir, f"test_monitor_{self.test_id}.log")
        self.event_log_file = os.path.join(self.log_dir, f"test_events_{self.test_id}.jsonl")
        
        # Basic config with test settings
        self.test_config = {
            "polling": {
                "enabled": True,
                "interval_seconds": 1,  # Fast polling for tests
                "max_batch_size": 10
            },
            "logging": {
                "file_enabled": True,
                "file_path": self.log_file,
                "event_log_path": self.event_log_file,
                "console_level": "ERROR"  # Quiet during tests
            }
        }
        
        # Write config to file
        with open(self.config_path, 'w') as f:
            import yaml
            yaml.dump(self.test_config, f)
        
        # Patch the file handlers to ensure we can close them later
        self.file_handlers = []
        self.original_rotating_handler = logging.handlers.RotatingFileHandler
        
        def patched_rotating_handler(*args, **kwargs):
            handler = self.original_rotating_handler(*args, **kwargs)
            self.file_handlers.append(handler)
            return handler
        
        self.handler_patcher = patch('logging.handlers.RotatingFileHandler', side_effect=patched_rotating_handler)
        self.handler_patcher.start()
        
        # Create monitor with test config
        self.monitor = MemoryMonitor(config_path=self.config_path)
        
        # Mock the OpenMemory client
        self.mock_client = Mock()
        self.monitor.client = self.mock_client
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop monitor if running
        if self.monitor.running:
            self.monitor.stop(wait_for_completion=True)
        
        # Stop the handler patcher
        self.handler_patcher.stop()
        
        # Close all file handlers
        for handler in self.file_handlers:
            try:
                handler.close()
            except Exception as e:
                print(f"Warning: Failed to close handler: {e}")
        
        # Reset the logger to release file handles
        logger = logging.getLogger("memory_monitor")
        for handler in logger.handlers[:]:
            try:
                handler.close()
                logger.removeHandler(handler)
            except Exception as e:
                print(f"Warning: Failed to close logger handler: {e}")
        
        # Give the OS a moment to release file handles
        time.sleep(0.1)
        
        # Try to explicitly remove log files before cleaning up the directory
        for log_path in [self.log_file, self.event_log_file]:
            try:
                if os.path.exists(log_path):
                    os.remove(log_path)
            except OSError as e:
                print(f"Warning: Could not delete log file {log_path}: {e}")
        
        # Clean up temp directory with ignore_errors to prevent test failures
        # but log a warning if there's an issue
        try:
            self.temp_dir.cleanup()
        except Exception as e:
            print(f"Warning: Failed to clean up temporary directory: {e}")
            # Try to clean it up with shutil which can force delete
            import shutil
            try:
                shutil.rmtree(self.temp_dir.name, ignore_errors=True)
            except Exception:
                print(f"Warning: Even forced cleanup failed for {self.temp_dir.name}")
    
    def test_initialization(self):
        """Test monitor initialization with config file."""
        # Verify config loaded correctly
        self.assertEqual(self.monitor.config["polling"]["interval_seconds"], 1)
        self.assertEqual(self.monitor.config["polling"]["max_batch_size"], 10)
        
        # Verify initial state
        self.assertFalse(self.monitor.running)
        self.assertIsNone(self.monitor.start_time)
        self.assertEqual(self.monitor.consecutive_errors, 0)
        self.assertIsInstance(self.monitor.monitor_id, str)
        
        # Verify event counters initialized
        for event_type in self.monitor.event_counters:
            self.assertEqual(self.monitor.event_counters[event_type], 0)
    
    def test_start_stop(self):
        """Test starting and stopping the monitor."""
        # Start the monitor
        result = self.monitor.start()
        self.assertTrue(result)
        self.assertTrue(self.monitor.running)
        self.assertIsNotNone(self.monitor.start_time)
        self.assertIsNotNone(self.monitor.poll_thread)
        
        # Try starting again (should fail)
        result = self.monitor.start()
        self.assertFalse(result)
        
        # Stop the monitor
        result = self.monitor.stop()
        self.assertTrue(result)
        self.assertFalse(self.monitor.running)
        
        # Try stopping again (should fail)
        result = self.monitor.stop()
        self.assertFalse(result)
    
    def test_get_status(self):
        """Test getting monitor status."""
        # Get initial status
        status = self.monitor.get_status()
        
        # Verify status fields
        self.assertEqual(status["running"], False)
        self.assertEqual(status["events_processed"], 0)
        self.assertEqual(status["health"], "STOPPED")
        self.assertEqual(status["monitor_id"], self.monitor.monitor_id)
        
        # Start monitor and check status again
        self.monitor.start()
        status = self.monitor.get_status()
        
        self.assertEqual(status["running"], True)
        self.assertEqual(status["health"], "OK")
        
        # Stop monitor
        self.monitor.stop()
    
    @patch('agent.memory_monitor.MemoryMonitor._bootstrap_poll')
    def test_bootstrap_poll_called_on_start(self, mock_bootstrap):
        """Test that bootstrap poll is called when monitor starts."""
        self.monitor.start()
        mock_bootstrap.assert_called_once()
        self.monitor.stop()
    
    def test_process_memory_created_event(self):
        """Test processing of memory creation events."""
        # Create test memory
        memory = {
            "id": str(uuid.uuid4()),
            "user_id": "test-user",
            "app_id": "test-app",
            "content": "Test memory content",
            "metadata_": {"test": True},
            "state": "active",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "categories": ["test"],
            "app_name": "test-app"
        }
        
        # Process event
        self.monitor._process_memory_created_event(memory)
        
        # Verify event counter incremented
        self.assertEqual(self.monitor.event_counters["memory.created"], 1)
        
        # Verify event timestamp and type updated
        self.assertIsNotNone(self.monitor.last_event_time)
        self.assertEqual(self.monitor.last_event_type, "memory.created")
        
        # Process same event again (should be deduplicated)
        self.monitor._process_memory_created_event(memory)
        
        # Counter should still be 1 (deduplication working)
        self.assertEqual(self.monitor.event_counters["memory.created"], 1)
    
    def test_process_memory_updated_event(self):
        """Test processing of memory update events."""
        # Create test memory
        memory = {
            "id": str(uuid.uuid4()),
            "user_id": "test-user",
            "app_id": "test-app",
            "content": "Updated memory content",
            "metadata_": {"test": True, "updated": True},
            "state": "active",
            "created_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "categories": ["test", "updated"],
            "app_name": "test-app"
        }
        
        # Process event
        self.monitor._process_memory_updated_event(memory)
        
        # Verify event counter incremented
        self.assertEqual(self.monitor.event_counters["memory.updated"], 1)
        
        # Verify event timestamp and type updated
        self.assertIsNotNone(self.monitor.last_event_time)
        self.assertEqual(self.monitor.last_event_type, "memory.updated")
    
    def test_process_memory_deleted_event(self):
        """Test processing of memory deletion events."""
        # Create test memory ID
        memory_id = str(uuid.uuid4())
        
        # Process event
        self.monitor._process_memory_deleted_event(memory_id)
        
        # Verify event counter incremented
        self.assertEqual(self.monitor.event_counters["memory.deleted"], 1)
        
        # Verify event timestamp and type updated
        self.assertIsNotNone(self.monitor.last_event_time)
        self.assertEqual(self.monitor.last_event_type, "memory.deleted")
    
    def test_generate_event_fingerprint(self):
        """Test event fingerprint generation for deduplication."""
        # Generate fingerprints for different event combinations
        fp1 = self.monitor._generate_event_fingerprint("memory.created", "id1", "timestamp1")
        fp2 = self.monitor._generate_event_fingerprint("memory.created", "id1", "timestamp1")
        fp3 = self.monitor._generate_event_fingerprint("memory.created", "id2", "timestamp1")
        fp4 = self.monitor._generate_event_fingerprint("memory.updated", "id1", "timestamp1")
        
        # Same inputs should produce same fingerprint
        self.assertEqual(fp1, fp2)
        
        # Different inputs should produce different fingerprints
        self.assertNotEqual(fp1, fp3)
        self.assertNotEqual(fp1, fp4)
    
    def test_generate_content_summary(self):
        """Test content summary generation."""
        # Test with short content
        short_content = "This is short content"
        summary = self.monitor._generate_content_summary(short_content)
        self.assertEqual(summary, short_content)
        
        # Test with long content
        long_content = "A" * 200
        summary = self.monitor._generate_content_summary(long_content)
        self.assertEqual(len(summary), 100)  # Default max length
        self.assertTrue(summary.endswith("..."))
        
        # Test with custom max length
        summary = self.monitor._generate_content_summary(long_content, max_length=50)
        self.assertEqual(len(summary), 50)
        self.assertTrue(summary.endswith("..."))
        
        # Test with empty content
        self.assertEqual(self.monitor._generate_content_summary(""), "")
        self.assertEqual(self.monitor._generate_content_summary(None), "")
    
    def test_parse_timestamp(self):
        """Test timestamp parsing function."""
        # Test with various formats
        ts1 = "2023-08-10T14:35:22.123Z"
        ts2 = "2023-08-10T14:35:22Z"
        ts3 = "2023-08-10T14:35:22"
        
        # All should parse successfully
        dt1 = self.monitor._parse_timestamp(ts1)
        dt2 = self.monitor._parse_timestamp(ts2)
        dt3 = self.monitor._parse_timestamp(ts3)
        
        self.assertIsNotNone(dt1)
        self.assertIsNotNone(dt2)
        self.assertIsNotNone(dt3)
        
        # All should have UTC timezone
        self.assertEqual(dt1.tzinfo, UTC)
        self.assertEqual(dt2.tzinfo, UTC)
        self.assertEqual(dt3.tzinfo, UTC)
        
        # Invalid format should return None
        self.assertIsNone(self.monitor._parse_timestamp("invalid"))
        self.assertIsNone(self.monitor._parse_timestamp(None))
    
    def test_get_current_poll_interval(self):
        """Test polling interval calculation with error backoff."""
        # Default interval
        self.assertEqual(self.monitor._get_current_poll_interval(), 1)  # From test config
        
        # With errors
        self.monitor.consecutive_errors = 1
        self.assertEqual(self.monitor._get_current_poll_interval(), 2)  # 2^1 = 2
        
        self.monitor.consecutive_errors = 2
        self.assertEqual(self.monitor._get_current_poll_interval(), 4)  # 2^2 = 4
        
        self.monitor.consecutive_errors = 3
        self.assertEqual(self.monitor._get_current_poll_interval(), 8)  # 2^3 = 8
        
        # Test max backoff (capped at 10x)
        self.monitor.consecutive_errors = 20
        self.assertEqual(self.monitor._get_current_poll_interval(), 10)  # Capped at 10x
    
    def test_log_event(self):
        """Test event logging to file."""
        # Create test event
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "memory.created",
            "timestamp": datetime.now(UTC).isoformat(),
            "memory_id": str(uuid.uuid4())
        }
        
        # Use a unique log file for this test
        test_log_file = os.path.join(self.log_dir, f"test_log_event_{self.test_id}.jsonl")
        
        # Mock the open function to verify it's called with the correct parameters
        with patch('builtins.open', unittest.mock.mock_open()) as mock_open:
            # Temporarily override the config
            original_event_log_path = self.monitor.config.get("logging", {}).get("event_log_path")
            self.monitor.config["logging"]["event_log_path"] = test_log_file
            
            try:
                # Call log_event
                self.monitor._log_event(event)
                
                # Verify file was opened for writing
                mock_open.assert_called_once()
                
                # Get the call arguments
                args, kwargs = mock_open.call_args
                
                # Verify the path and mode are correct
                self.assertEqual(args[0], test_log_file)
                self.assertEqual(args[1], 'a')
                self.assertEqual(kwargs['encoding'], 'utf-8')
            finally:
                # Restore original config
                self.monitor.config["logging"]["event_log_path"] = original_event_log_path
    
    def test_poll_new_creations(self):
        """Test detecting and logging of new memory creation events."""
        # Mock the client.list_memories method to return test data
        test_memory_id = str(uuid.uuid4())
        test_memory = {
            "id": test_memory_id,
            "user_id": "test-user",
            "app_id": "test-app",
            "content": "Test memory content for creation event",
            "metadata_": {"test": True},
            "state": "active",
            "created_at": datetime.now(UTC).isoformat(),
            "categories": ["test-category"],
            "app_name": "test-app"
        }
        
        # Create mock response
        mock_response = {
            "items": [test_memory],
            "total": 1,
            "page": 1,
            "size": 10,
            "pages": 1
        }
        
        # Configure the mock to return our test data
        self.mock_client.list_memories.return_value = mock_response
        
        # Use a temp file for log output
        test_log_file = os.path.join(self.log_dir, f"test_poll_new_creations_{self.test_id}.jsonl")
        original_event_log_path = self.monitor.config.get("logging", {}).get("event_log_path")
        self.monitor.config["logging"]["event_log_path"] = test_log_file
        
        try:
            # Run the method we're testing
            events = self.monitor.poll_new_creations()
            
            # Verify client method was called with correct parameters
            self.mock_client.list_memories.assert_called_once()
            call_args = self.mock_client.list_memories.call_args[1]
            self.assertEqual(call_args["user_id"], "*")
            self.assertEqual(call_args["sort_column"], "created_at")
            self.assertEqual(call_args["sort_direction"], "asc")
            
            # Verify event detection
            self.assertEqual(len(events), 1, "Should detect exactly one new memory")
            
            # Verify the event has the correct structure
            event = events[0]
            self.assertEqual(event["event_type"], "creation")
            self.assertEqual(event["memory_id"], test_memory_id)
            self.assertEqual(event["source"], "MemoryMonitor")
            self.assertEqual(event["run_id"], self.monitor.monitor_id)
            
            # Verify details
            details = event["details"]
            self.assertEqual(details["user_id"], "test-user")
            self.assertEqual(details["app_id"], "test-app")
            self.assertTrue("content_summary" in details)
            self.assertEqual(details["categories"], ["test-category"])
            
            # Verify counter was incremented
            self.assertEqual(self.monitor.event_counters["memory.created"], 1)
            
            # Verify memory ID was added to deduplication cache
            self.assertIn(test_memory_id, self.monitor.known_memory_ids)
            
            # Call again to test deduplication
            events = self.monitor.poll_new_creations()
            
            # Should not detect any new memories (because ID is now in the cache)
            self.assertEqual(len(events), 0, "Should not detect any new memories on second call")
            
            # Counter should still be 1 (no new increment)
            self.assertEqual(self.monitor.event_counters["memory.created"], 1)
        finally:
            # Restore original config
            self.monitor.config["logging"]["event_log_path"] = original_event_log_path
            
            # Explicitly remove the test log file
            if os.path.exists(test_log_file):
                try:
                    os.remove(test_log_file)
                except OSError as e:
                    print(f"Warning: Could not delete test log file {test_log_file}: {e}")
    
    def test_poll_new_creations_error_handling(self):
        """Test error handling during memory creation polling."""
        # Configure mock to raise an exception
        self.mock_client.list_memories.side_effect = Exception("Test API error")
        
        # Capture initial error count
        initial_errors = self.monitor.consecutive_errors
        
        # Use a temp file for log output
        test_log_file = os.path.join(self.log_dir, f"test_poll_error_{self.test_id}.jsonl")
        original_event_log_path = self.monitor.config.get("logging", {}).get("event_log_path")
        self.monitor.config["logging"]["event_log_path"] = test_log_file
        
        try:
            # Run the method we're testing
            events = self.monitor.poll_new_creations()
            
            # Verify error handling
            self.assertEqual(len(events), 0, "Should not return any events on error")
            self.assertEqual(self.monitor.consecutive_errors, initial_errors + 1, "Error counter should increment")
            self.assertEqual(self.monitor.last_error, "Test API error")
            self.assertIsNotNone(self.monitor.last_error_time)
        finally:
            # Restore original config
            self.monitor.config["logging"]["event_log_path"] = original_event_log_path
            
            # Explicitly remove the test log file
            if os.path.exists(test_log_file):
                try:
                    os.remove(test_log_file)
                except OSError as e:
                    print(f"Warning: Could not delete test log file {test_log_file}: {e}")
    
    def test_log_memory_event(self):
        """Test memory event logging to file."""
        # Create a test event
        test_event = {
            "event_type": "creation",
            "timestamp": datetime.now(UTC).isoformat(),
            "memory_id": str(uuid.uuid4()),
            "details": {
                "user_id": "test-user",
                "content_summary": "Test content"
            },
            "source": "MemoryMonitor",
            "run_id": self.monitor.monitor_id
        }
        
        # Create a temporary log file with unique name
        test_log_file = os.path.join(self.log_dir, f"test_mem_event_{self.test_id}.jsonl")
        
        # Save original config and set to use our test file
        original_event_log_path = self.monitor.config.get("logging", {}).get("event_log_path")
        self.monitor.config["logging"]["event_log_path"] = test_log_file
        
        try:
            # Log the event
            self.monitor._log_memory_event(test_event)
            
            # Verify log file was created
            self.assertTrue(os.path.exists(test_log_file), "Log file should be created")
            
            # Read the log file and verify content
            with open(test_log_file, 'r') as f:
                log_content = f.read().strip()
                parsed_event = json.loads(log_content)
                
                # Verify key fields were logged correctly
                self.assertEqual(parsed_event["event_type"], "creation")
                self.assertEqual(parsed_event["memory_id"], test_event["memory_id"])
                self.assertEqual(parsed_event["source"], "MemoryMonitor")
                self.assertEqual(parsed_event["details"]["user_id"], "test-user")
        finally:
            # Restore original config
            self.monitor.config["logging"]["event_log_path"] = original_event_log_path
            
            # Ensure file is closed before attempting to delete
            # Python garbage collection should have closed the file,
            # but we'll force it with a sleep to be safe
            time.sleep(0.1)
            
            # Explicitly remove the test log file
            if os.path.exists(test_log_file):
                try:
                    os.remove(test_log_file)
                except OSError as e:
                    print(f"Warning: Could not delete test log file {test_log_file}: {e}")
    
    def test_poll_memory_updates(self):
        """Test detecting and logging of memory update events."""
        # Create a unique test ID
        test_id = str(uuid.uuid4())[:8]
        
        # Set up a test log file
        test_log_file = os.path.join(self.log_dir, f"test_updates_{test_id}.jsonl")
        
        # Save original config and set to use our test file
        original_event_log_path = self.monitor.config.get("logging", {}).get("event_log_path")
        self.monitor.config["logging"]["event_log_path"] = test_log_file
        
        # Mock data: First create a memory to add to known_memory_ids
        test_memory_id = str(uuid.uuid4())
        
        # Use specific timestamp formats that will parse correctly
        created_time = "2023-01-01T10:00:00Z"  # ISO format with Z for UTC
        updated_time = "2023-01-02T15:30:00Z"  # Later timestamp in the same format
        
        # Original memory that should be in known_memory_ids
        test_memory_original = {
            "id": test_memory_id,
            "user_id": "test-user",
            "app_id": "test-app",
            "content": "Original content",
            "metadata_": {"test": True},
            "state": "active",
            "created_at": created_time,
            "updated_at": created_time,  # Same as created initially
            "categories": ["test-category"],
            "app_name": "test-app"
        }
        
        # Updated version of the memory
        test_memory_updated = {
            "id": test_memory_id,
            "user_id": "test-user",
            "app_id": "test-app",
            "content": "Updated content",
            "metadata_": {"test": True, "updated": True},
            "state": "active",
            "created_at": created_time,
            "updated_at": updated_time,  # Updated timestamp
            "categories": ["test-category", "updated"],
            "app_name": "test-app"
        }
        
        try:
            # Add the memory ID to known_memory_ids to simulate a previously seen memory
            self.monitor.known_memory_ids.add(test_memory_id)
            
            # Mock response for update query
            mock_response = {
                "items": [test_memory_updated],
                "total": 1,
                "page": 1,
                "size": 10,
                "pages": 1
            }
            
            # Configure the mock to return our test data
            self.mock_client.list_memories.return_value = mock_response
            
            # Run the method we're testing
            events = self.monitor.poll_memory_updates()
            
            # Verify client method was called with correct parameters
            self.mock_client.list_memories.assert_called_once()
            call_args = self.mock_client.list_memories.call_args[1]
            self.assertEqual(call_args["user_id"], "*")
            self.assertEqual(call_args["sort_column"], "updated_at")
            self.assertEqual(call_args["sort_direction"], "asc")
            
            # Verify event detection
            self.assertEqual(len(events), 1, "Should detect exactly one updated memory")
            
            # Verify the event has the correct structure
            event = events[0]
            self.assertEqual(event["event_type"], "update")
            self.assertEqual(event["memory_id"], test_memory_id)
            self.assertEqual(event["source"], "MemoryMonitor")
            self.assertEqual(event["run_id"], self.monitor.monitor_id)
            
            # Verify details
            details = event["details"]
            self.assertEqual(details["user_id"], "test-user")
            self.assertEqual(details["app_id"], "test-app")
            self.assertTrue("content_summary" in details)
            self.assertEqual(details["categories"], ["test-category", "updated"])
            self.assertEqual(details["updated_at"], updated_time)
            
            # Verify counter was incremented
            self.assertEqual(self.monitor.event_counters["memory.updated"], 1)
            
            # Verify log file was created and contains valid JSON
            self.assertTrue(os.path.exists(test_log_file), "Log file should be created")
            with open(test_log_file, 'r') as f:
                log_content = f.read().strip()
                parsed_event = json.loads(log_content)
                self.assertEqual(parsed_event["event_type"], "update")
                self.assertEqual(parsed_event["memory_id"], test_memory_id)
            
            # Call again to test deduplication
            self.mock_client.list_memories.reset_mock()
            events = self.monitor.poll_memory_updates()
            
            # Should not detect any updates (because fingerprint is now in the cache)
            self.assertEqual(len(events), 0, "Should not detect any updates on second call")
            
            # Counter should still be 1 (no new increment)
            self.assertEqual(self.monitor.event_counters["memory.updated"], 1)
            
        finally:
            # Restore original config
            self.monitor.config["logging"]["event_log_path"] = original_event_log_path
            
            # Explicitly remove the test log file
            if os.path.exists(test_log_file):
                try:
                    os.remove(test_log_file)
                except OSError as e:
                    print(f"Warning: Could not delete test log file {test_log_file}: {e}")
    
    def test_poll_memory_updates_no_updates(self):
        """Test handling when no updates are available."""
        # Mock response with no items
        mock_response = {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 10,
            "pages": 0
        }
        
        # Configure the mock
        self.mock_client.list_memories.return_value = mock_response
        
        # Run the method
        events = self.monitor.poll_memory_updates()
        
        # Verify client method was called
        self.mock_client.list_memories.assert_called_once()
        
        # Verify no events detected
        self.assertEqual(len(events), 0, "Should not detect any updates")
        
        # Verify counter was not incremented
        self.assertEqual(self.monitor.event_counters["memory.updated"], 0)
    
    def test_poll_memory_deletions(self):
        """Test detecting and logging of memory deletion events."""
        # Create a unique test ID
        test_id = str(uuid.uuid4())[:8]
        
        # Set up a test log file
        test_log_file = os.path.join(self.log_dir, f"test_deletions_{test_id}.jsonl")
        
        # Save original config and set to use our test file
        original_event_log_path = self.monitor.config.get("logging", {}).get("event_log_path")
        self.monitor.config["logging"]["event_log_path"] = test_log_file
        
        # First, set up some known memory IDs
        test_memory_id_1 = str(uuid.uuid4())  # This one will be "deleted"
        test_memory_id_2 = str(uuid.uuid4())  # This one will still exist
        
        # Add both memory IDs to the known_memory_ids set
        self.monitor.known_memory_ids.add(test_memory_id_1)
        self.monitor.known_memory_ids.add(test_memory_id_2)
        
        # Set up mock responses
        
        # 1. Mock the list_memories to return only memory 2 (simulating memory 1 was deleted)
        list_response = {
            "items": [
                {"id": test_memory_id_2, "user_id": "test-user"}
            ],
            "total": 1,
            "page": 1,
            "size": 10,
            "pages": 1
        }
        
        # 2. Configure the get_memory mock to raise "Memory not found" for deleted memory
        def mock_get_memory(memory_id):
            if memory_id == test_memory_id_1:
                raise ValueError("Memory not found")
            elif memory_id == test_memory_id_2:
                return {"id": memory_id, "content": "Test content"}
            else:
                raise ValueError("Unexpected memory ID in test")
        
        try:
            # Configure the mocks
            self.mock_client.list_memories.return_value = list_response
            self.mock_client.get_memory.side_effect = mock_get_memory
            
            # Run the method we're testing
            events = self.monitor.poll_memory_deletions()
            
            # Verify client methods were called correctly
            self.mock_client.list_memories.assert_called_once()
            self.mock_client.get_memory.assert_called_with(test_memory_id_1)
            
            # Verify exactly one deletion was detected
            self.assertEqual(len(events), 1, "Should detect exactly one deleted memory")
            
            # Verify the event has the correct structure
            event = events[0]
            self.assertEqual(event["event_type"], "deletion")
            self.assertEqual(event["memory_id"], test_memory_id_1)
            self.assertEqual(event["source"], "MemoryMonitor")
            self.assertEqual(event["run_id"], self.monitor.monitor_id)
            
            # Verify details
            details = event["details"]
            self.assertEqual(details["detection_method"], "id_comparison")
            
            # Verify counter was incremented
            self.assertEqual(self.monitor.event_counters["memory.deleted"], 1)
            
            # Verify memory was removed from known_memory_ids
            self.assertNotIn(test_memory_id_1, self.monitor.known_memory_ids)
            self.assertIn(test_memory_id_2, self.monitor.known_memory_ids)
            
            # Verify log file was created and contains valid JSON
            self.assertTrue(os.path.exists(test_log_file), "Log file should be created")
            with open(test_log_file, 'r') as f:
                log_content = f.read().strip()
                parsed_event = json.loads(log_content)
                self.assertEqual(parsed_event["event_type"], "deletion")
                self.assertEqual(parsed_event["memory_id"], test_memory_id_1)
            
            # Call again to test deduplication
            # Reset the mock to avoid test interference
            self.mock_client.list_memories.reset_mock()
            self.mock_client.get_memory.reset_mock()
            
            # Second call should not detect any new deletions (already processed)
            events = self.monitor.poll_memory_deletions()
            self.assertEqual(len(events), 0, "Should not detect any deletions on second call")
            
            # Counter should still be 1 (no new increment)
            self.assertEqual(self.monitor.event_counters["memory.deleted"], 1)
            
        finally:
            # Restore original config
            self.monitor.config["logging"]["event_log_path"] = original_event_log_path
            
            # Explicitly remove the test log file
            if os.path.exists(test_log_file):
                try:
                    os.remove(test_log_file)
                except OSError as e:
                    print(f"Warning: Could not delete test log file {test_log_file}: {e}")
    
    def test_poll_memory_deletions_empty_known_ids(self):
        """Test deletion polling when no known memory IDs exist yet."""
        # Ensure known_memory_ids is empty
        self.monitor.known_memory_ids.clear()
        
        # Run the method
        events = self.monitor.poll_memory_deletions()
        
        # Should return an empty list without making any API calls
        self.assertEqual(len(events), 0, "Should not detect any deletions without known IDs")
        self.mock_client.list_memories.assert_not_called()
        self.mock_client.get_memory.assert_not_called()
    
    def test_poll_memory_deletions_error_handling(self):
        """Test error handling during deletion detection."""
        # Add a known memory ID so the method doesn't early exit
        test_memory_id = str(uuid.uuid4())
        self.monitor.known_memory_ids.add(test_memory_id)
        
        # Configure mock to raise an exception
        self.mock_client.list_memories.side_effect = Exception("Test API error")
        
        # Capture initial error count
        initial_errors = self.monitor.consecutive_errors
        
        # Run the method
        events = self.monitor.poll_memory_deletions()
        
        # Verify error handling
        self.assertEqual(len(events), 0, "Should not return any events on error")
        self.assertEqual(self.monitor.consecutive_errors, initial_errors + 1, "Error counter should increment")
        self.assertEqual(self.monitor.last_error, "Test API error")
        self.assertIsNotNone(self.monitor.last_error_time)
    
    def test_log_monitor_error(self):
        """Test logging of monitor error events."""
        # Create a unique test ID
        test_id = str(uuid.uuid4())[:8]
        
        # Set up a test log file
        test_log_file = os.path.join(self.log_dir, f"test_errors_{test_id}.jsonl")
        
        # Save original config and set to use our test file
        original_event_log_path = self.monitor.config.get("logging", {}).get("event_log_path")
        self.monitor.config["logging"]["event_log_path"] = test_log_file
        
        # Set up a shorter deduplication window for testing
        if "error" not in self.monitor.config:
            self.monitor.config["error"] = {}
        self.monitor.config["error"]["deduplication_window_seconds"] = 1
        
        try:
            # 1. Test basic error logging
            error_type = "APIError"
            message = "Failed to connect to API endpoint"
            context = {"endpoint": "/api/memories", "status_code": 500}
            
            # Log the error
            self.monitor.log_monitor_error(error_type, message, context)
            
            # Verify log file was created
            self.assertTrue(os.path.exists(test_log_file), "Log file should be created")
            
            # Read the log file and verify content
            with open(test_log_file, 'r') as f:
                log_content = f.read().strip()
                parsed_event = json.loads(log_content)
                
                # Verify key fields were logged correctly
                self.assertEqual(parsed_event["event_type"], "error")
                self.assertEqual(parsed_event["error_type"], error_type)
                self.assertEqual(parsed_event["message"], message)
                self.assertEqual(parsed_event["context"]["endpoint"], "/api/memories")
                self.assertEqual(parsed_event["context"]["status_code"], 500)
                self.assertEqual(parsed_event["source"], "MemoryMonitor")
                self.assertEqual(parsed_event["run_id"], self.monitor.monitor_id)
            
            # Verify counter was incremented
            self.assertEqual(self.monitor.event_counters["memory.error"], 1)
            
            # 2. Test deduplication for the same error
            self.monitor.log_monitor_error(error_type, message, context)
            
            # The file should still only have one line (deduplication worked)
            with open(test_log_file, 'r') as f:
                log_lines = f.readlines()
                self.assertEqual(len(log_lines), 1, "Same error should be deduplicated")
            
            # Counter should still be 1 (no new increment)
            self.assertEqual(self.monitor.event_counters["memory.error"], 1)
            
            # 3. Test different error (should not be deduplicated)
            new_error_type = "ConfigError"
            new_message = "Invalid configuration parameter"
            new_context = {"parameter": "polling.interval", "value": -1}
            
            self.monitor.log_monitor_error(new_error_type, new_message, new_context)
            
            # Now there should be two lines
            with open(test_log_file, 'r') as f:
                log_lines = f.readlines()
                self.assertEqual(len(log_lines), 2, "Different error should not be deduplicated")
                
                # Parse the second event
                second_event = json.loads(log_lines[1])
                self.assertEqual(second_event["error_type"], new_error_type)
                self.assertEqual(second_event["message"], new_message)
            
            # Counter should now be 2
            self.assertEqual(self.monitor.event_counters["memory.error"], 2)
            
            # 4. Test that deduplication expires after the configured window
            time.sleep(1.1)  # Slightly longer than our test deduplication window
            
            # Log the first error again
            self.monitor.log_monitor_error(error_type, message, context)
            
            # Now there should be three lines
            with open(test_log_file, 'r') as f:
                log_lines = f.readlines()
                self.assertEqual(len(log_lines), 3, "Error after deduplication window should be logged")
            
            # Counter should now be 3
            self.assertEqual(self.monitor.event_counters["memory.error"], 3)
            
        finally:
            # Restore original config
            self.monitor.config["logging"]["event_log_path"] = original_event_log_path
            
            # Explicitly remove the test log file
            if os.path.exists(test_log_file):
                try:
                    os.remove(test_log_file)
                except OSError as e:
                    print(f"Warning: Could not delete test log file {test_log_file}: {e}")


if __name__ == '__main__':
    unittest.main() 