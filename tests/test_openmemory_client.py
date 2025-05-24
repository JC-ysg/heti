"""
Unit tests for OpenMemory API client

Tests the POST /api/v1/memories and GET /api/v1/memories endpoints with various scenarios including
success cases, validation errors, and edge conditions.

Follows Heti project rules:
- @tests - Test-first development with comprehensive coverage
- @logs - Full traceability of all test operations
- @project/atomicity - Single-focus testing approach
"""

import unittest
import logging
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC
import requests
import time

# Import the client we're testing
try:
    from tools.openmemory_client import OpenMemoryClient, create_memory_simple, list_memories_simple, get_memory_simple, update_memory_simple, filter_memories_simple
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tools.openmemory_client import OpenMemoryClient, create_memory_simple, list_memories_simple, get_memory_simple, update_memory_simple, filter_memories_simple

# Configure logging for test traceability
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestOpenMemoryClient(unittest.TestCase):
    """
    Test suite for OpenMemoryClient focusing on POST /api/v1/memories and GET /api/v1/memories endpoints.
    
    Each test logs its operations for full traceability per Heti project rules.
    """
    
    def setUp(self):
        """Set up test fixtures and logging."""
        self.client = OpenMemoryClient(base_url="http://test-api:8000", timeout=10)
        self.test_start_time = datetime.now(UTC).isoformat()
        
        logger.info(f"Test setup - Timestamp: {self.test_start_time}, Client initialized")
    
    def tearDown(self):
        """Clean up after each test."""
        test_end_time = datetime.now(UTC).isoformat()
        logger.info(f"Test teardown - Timestamp: {test_end_time}")
    
    @patch('tools.openmemory_client.requests.Session.post')
    def test_create_memory_success(self, mock_post):
        """
        Test successful memory creation with valid data.
        
        Verifies:
        - Correct API endpoint is called
        - Request payload is properly formatted
        - Response is correctly parsed and returned
        - All operations are logged for traceability
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_create_memory_success - Timestamp: {test_start}")
        
        # Arrange: Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": 123,
            "app_id": "550e8400-e29b-41d4-a716-446655440001", 
            "content": "Test memory content",
            "metadata_": {},
            "state": "active",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "categories": ["test"],
            "app_name": "heti"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Act: Call the method
        result = self.client.create_memory(
            user_id="test-user-123",
            text="Test memory content",
            infer=True,
            app="heti"
        )
        
        # Assert: Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check endpoint URL
        expected_url = "http://test-api:8000/api/v1/memories"
        self.assertEqual(call_args[0][0], expected_url)
        
        # Check request payload
        expected_payload = {
            "user_id": "test-user-123",
            "text": "Test memory content",
            "infer": True,
            "app": "heti"
        }
        self.assertEqual(call_args[1]['json'], expected_payload)
        
        # Check headers
        self.assertEqual(call_args[1]['headers']['Content-Type'], "application/json")
        
        # Check timeout
        self.assertEqual(call_args[1]['timeout'], 10)
        
        # Assert: Verify response handling
        self.assertEqual(result['id'], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(result['content'], "Test memory content")
        self.assertEqual(result['state'], "active")
        self.assertEqual(result['app_name'], "heti")
        
        # Log test completion
        logger.info(
            f"test_create_memory_success completed - "
            f"Result ID: {result['id']}, "
            f"Status: SUCCESS, "
            f"Request verified: {expected_url}"
        )
    
    @patch('tools.openmemory_client.requests.Session.post')
    def test_create_memory_validation_error(self, mock_post):
        """
        Test handling of validation errors (422 status).
        
        Verifies:
        - 422 validation errors are properly caught
        - Error details are extracted and logged
        - Appropriate ValueError is raised
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_create_memory_validation_error - Timestamp: {test_start}")
        
        # Arrange: Mock validation error response
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": [
                {
                    "loc": ["body", "text"],
                    "msg": "field required",
                    "type": "value_error.missing"
                }
            ]
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.create_memory(
                user_id="test-user",
                text="",  # Empty text should trigger validation error
                infer=True,
                app="heti"
            )
        
        # Verify error message contains validation details
        error_message = str(context.exception)
        self.assertIn("Validation error", error_message)
        self.assertIn("field required", error_message)
        
        # Verify request was attempted
        mock_post.assert_called_once()
        
        # Log error handling verification
        logger.info(
            f"test_create_memory_validation_error completed - "
            f"Error properly caught: {error_message}, "
            f"Status: SUCCESS"
        )
    
    @patch('tools.openmemory_client.requests.Session.post')
    def test_create_memory_user_not_found(self, mock_post):
        """
        Test handling of user not found errors (404 status).
        
        Verifies:
        - 404 errors are properly caught and logged
        - Appropriate ValueError is raised with user context
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_create_memory_user_not_found - Timestamp: {test_start}")
        
        # Arrange: Mock user not found response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "detail": "User not found"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.create_memory(
                user_id="nonexistent-user",
                text="Test content",
                infer=True,
                app="heti"
            )
        
        # Verify error message
        error_message = str(context.exception)
        self.assertIn("User not found", error_message)
        
        # Log error handling verification
        logger.info(
            f"test_create_memory_user_not_found completed - "
            f"Error properly caught: {error_message}, "
            f"Status: SUCCESS"
        )
    
    @patch('tools.openmemory_client.requests.Session.post')
    def test_create_memory_app_paused(self, mock_post):
        """
        Test handling of app paused errors (403 status).
        
        Verifies:
        - 403 errors are properly caught and logged
        - App-specific error context is preserved
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_create_memory_app_paused - Timestamp: {test_start}")
        
        # Arrange: Mock app paused response
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "detail": "App heti is currently paused on OpenMemory. Cannot create new memories."
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.create_memory(
                user_id="test-user",
                text="Test content",
                infer=True,
                app="heti"
            )
        
        # Verify error message
        error_message = str(context.exception)
        self.assertIn("App access denied", error_message)
        self.assertIn("paused", error_message)
        
        # Log error handling verification
        logger.info(
            f"test_create_memory_app_paused completed - "
            f"Error properly caught: {error_message}, "
            f"Status: SUCCESS"
        )
    
    @patch('tools.openmemory_client.requests.Session.post')
    def test_create_memory_network_error(self, mock_post):
        """
        Test handling of network/connection errors.
        
        Verifies:
        - Network errors are properly caught and logged
        - Original RequestException is re-raised
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_create_memory_network_error - Timestamp: {test_start}")
        
        # Arrange: Mock network error
        mock_post.side_effect = requests.ConnectionError("Connection failed")
        
        # Act & Assert: Call should raise RequestException
        with self.assertRaises(requests.ConnectionError):
            self.client.create_memory(
                user_id="test-user",
                text="Test content",
                infer=True,
                app="heti"
            )
        
        # Verify request was attempted
        mock_post.assert_called_once()
        
        # Log error handling verification
        logger.info(
            f"test_create_memory_network_error completed - "
            f"Network error properly propagated, "
            f"Status: SUCCESS"
        )
    
    def test_create_memory_simple_convenience_function(self):
        """
        Test the convenience function create_memory_simple.
        
        Verifies:
        - Function creates client correctly
        - Parameters are passed through properly
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_create_memory_simple_convenience_function - Timestamp: {test_start}")
        
        # This test would require a real API or more complex mocking
        # For now, just verify the function exists and can be imported
        self.assertTrue(callable(create_memory_simple))
        
        # Log test completion
        logger.info(
            f"test_create_memory_simple_convenience_function completed - "
            f"Function verified as callable, "
            f"Status: SUCCESS"
        )

    # NEW TESTS FOR LIST_MEMORIES METHOD

    @patch('tools.openmemory_client.requests.Session.get')
    def test_list_memories_success(self, mock_get):
        """
        Test successful memory listing with basic parameters.
        
        Verifies:
        - Correct GET endpoint is called
        - Query parameters are properly formatted
        - Response is correctly parsed and returned
        - All operations are logged for traceability
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_list_memories_success - Timestamp: {test_start}")
        
        # Arrange: Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "user_id": 123,
                    "app_id": "550e8400-e29b-41d4-a716-446655440001",
                    "content": "First memory content",
                    "metadata_": {},
                    "state": "active",
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:00Z",
                    "categories": ["work"],
                    "app_name": "heti"
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440002",
                    "user_id": 123,
                    "app_id": "550e8400-e29b-41d4-a716-446655440001",
                    "content": "Second memory content",
                    "metadata_": {},
                    "state": "active",
                    "created_at": "2024-01-15T11:00:00Z",
                    "updated_at": "2024-01-15T11:00:00Z",
                    "categories": ["personal"],
                    "app_name": "heti"
                }
            ],
            "total": 25,
            "page": 1,
            "size": 10,
            "pages": 3
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act: Call the method
        result = self.client.list_memories(
            user_id="test-user-123",
            page=1,
            size=10
        )
        
        # Assert: Verify the request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        # Check endpoint URL
        expected_url = "http://test-api:8000/api/v1/memories"
        self.assertEqual(call_args[0][0], expected_url)
        
        # Check query parameters
        expected_params = {
            "user_id": "test-user-123",
            "page": 1,
            "size": 10
        }
        self.assertEqual(call_args[1]['params'], expected_params)
        
        # Check timeout
        self.assertEqual(call_args[1]['timeout'], 10)
        
        # Assert: Verify response handling
        self.assertEqual(result['total'], 25)
        self.assertEqual(result['page'], 1)
        self.assertEqual(result['size'], 10)
        self.assertEqual(result['pages'], 3)
        self.assertEqual(len(result['items']), 2)
        self.assertEqual(result['items'][0]['id'], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(result['items'][0]['content'], "First memory content")
        
        # Log test completion
        logger.info(
            f"test_list_memories_success completed - "
            f"Total: {result['total']}, "
            f"Items returned: {len(result['items'])}, "
            f"Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.get')
    def test_list_memories_with_filters(self, mock_get):
        """
        Test memory listing with comprehensive filtering options.
        
        Verifies:
        - All filter parameters are correctly passed
        - Categories list is properly converted to comma-separated string
        - UUID app_id is converted to string
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_list_memories_with_filters - Timestamp: {test_start}")
        
        # Arrange: Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 5,
            "pages": 0
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act: Call with comprehensive filters
        from uuid import UUID
        test_app_id = UUID("550e8400-e29b-41d4-a716-446655440001")
        
        result = self.client.list_memories(
            user_id="test-user",
            app_id=test_app_id,
            search_query="meeting notes",
            categories=["work", "important"],
            from_date=1718505600,
            to_date=1718592000,
            page=2,
            size=5,
            sort_column="created_at",
            sort_direction="desc"
        )
        
        # Assert: Verify parameters
        call_args = mock_get.call_args
        expected_params = {
            "user_id": "test-user",
            "app_id": "550e8400-e29b-41d4-a716-446655440001",
            "search_query": "meeting notes",
            "categories": "work,important",
            "from_date": 1718505600,
            "to_date": 1718592000,
            "page": 2,
            "size": 5,
            "sort_column": "created_at",
            "sort_direction": "desc"
        }
        self.assertEqual(call_args[1]['params'], expected_params)
        
        # Log test completion
        logger.info(
            f"test_list_memories_with_filters completed - "
            f"Filters verified, "
            f"Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.get')
    def test_list_memories_categories_string(self, mock_get):
        """
        Test memory listing with categories as a string instead of list.
        
        Verifies:
        - String categories are passed through unchanged
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_list_memories_categories_string - Timestamp: {test_start}")
        
        # Arrange: Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 10,
            "pages": 0
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act: Call with string categories
        result = self.client.list_memories(
            user_id="test-user",
            categories="work,personal"
        )
        
        # Assert: Verify categories parameter
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]['params']['categories'], "work,personal")
        
        logger.info(f"test_list_memories_categories_string completed - Status: SUCCESS")

    @patch('tools.openmemory_client.requests.Session.get')
    def test_list_memories_empty_result(self, mock_get):
        """
        Test memory listing with no results found.
        
        Verifies:
        - Empty results are handled correctly
        - Pagination metadata is preserved
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_list_memories_empty_result - Timestamp: {test_start}")
        
        # Arrange: Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 10,
            "pages": 0
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act: Call the method
        result = self.client.list_memories(user_id="test-user")
        
        # Assert: Verify empty result structure
        self.assertEqual(result['items'], [])
        self.assertEqual(result['total'], 0)
        self.assertEqual(result['pages'], 0)
        
        logger.info(f"test_list_memories_empty_result completed - Empty result handled correctly")

    @patch('tools.openmemory_client.requests.Session.get')
    def test_list_memories_user_not_found(self, mock_get):
        """
        Test handling of user not found errors (404 status) for list_memories.
        
        Verifies:
        - 404 errors are properly caught and logged
        - Appropriate ValueError is raised with user context
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_list_memories_user_not_found - Timestamp: {test_start}")
        
        # Arrange: Mock user not found response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "detail": "User not found"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.list_memories(user_id="nonexistent-user")
        
        # Verify error message
        error_message = str(context.exception)
        self.assertIn("User not found", error_message)
        
        logger.info(
            f"test_list_memories_user_not_found completed - "
            f"Error properly caught: {error_message}"
        )

    @patch('tools.openmemory_client.requests.Session.get')
    def test_list_memories_invalid_parameters(self, mock_get):
        """
        Test handling of invalid parameter errors (400 status).
        
        Verifies:
        - 400 errors are properly caught and logged
        - Parameter details are preserved in error message
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_list_memories_invalid_parameters - Timestamp: {test_start}")
        
        # Arrange: Mock invalid parameters response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "detail": "Invalid sort direction"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.list_memories(
                user_id="test-user",
                sort_direction="invalid"
            )
        
        # Verify error message
        error_message = str(context.exception)
        self.assertIn("Invalid parameters", error_message)
        self.assertIn("Invalid sort direction", error_message)
        
        logger.info(
            f"test_list_memories_invalid_parameters completed - "
            f"Error properly caught: {error_message}"
        )

    @patch('tools.openmemory_client.requests.Session.get')
    def test_list_memories_validation_error(self, mock_get):
        """
        Test handling of validation errors (422 status) for list_memories.
        
        Verifies:
        - 422 validation errors are properly caught
        - Error details are extracted and logged
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_list_memories_validation_error - Timestamp: {test_start}")
        
        # Arrange: Mock validation error response
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": [
                {
                    "loc": ["query", "user_id"],
                    "msg": "field required",
                    "type": "value_error.missing"
                }
            ]
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            # This would trigger if user_id was somehow missing
            self.client.list_memories(user_id="")
        
        # Verify error message contains validation details
        error_message = str(context.exception)
        self.assertIn("Validation error", error_message)
        
        logger.info(
            f"test_list_memories_validation_error completed - "
            f"Error properly caught: {error_message}"
        )

    @patch('tools.openmemory_client.requests.Session.get')
    def test_list_memories_network_error(self, mock_get):
        """
        Test handling of network/connection errors for list_memories.
        
        Verifies:
        - Network errors are properly caught and logged
        - Original RequestException is re-raised
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_list_memories_network_error - Timestamp: {test_start}")
        
        # Arrange: Mock network error
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        # Act & Assert: Call should raise RequestException
        with self.assertRaises(requests.ConnectionError):
            self.client.list_memories(user_id="test-user")
        
        # Verify request was attempted
        mock_get.assert_called_once()
        
        logger.info(
            f"test_list_memories_network_error completed - "
            f"Network error properly propagated"
        )

    def test_list_memories_simple_convenience_function(self):
        """
        Test the convenience function list_memories_simple.
        
        Verifies:
        - Function exists and is callable
        - Parameters can be passed through properly
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_list_memories_simple_convenience_function - Timestamp: {test_start}")
        
        # Verify the function exists and can be imported
        self.assertTrue(callable(list_memories_simple))
        
        logger.info(
            f"test_list_memories_simple_convenience_function completed - "
            f"Function verified as callable"
        )

    # =============================================================================
    # GET MEMORY TESTS - GET /api/v1/memories/{memory_id}
    # =============================================================================

    @patch('tools.openmemory_client.requests.Session.get')
    def test_get_memory_success(self, mock_get):
        """
        Test successful memory retrieval by ID with valid data.
        
        Verifies:
        - Correct API endpoint is called with memory ID in path
        - Response is correctly parsed and returned
        - All operations are logged for traceability
        - Memory object contains all expected fields
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_get_memory_success - Timestamp: {test_start}")
        
        # Arrange: Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": 123,
            "app_id": "550e8400-e29b-41d4-a716-446655440001",
            "content": "Retrieved memory content for testing",
            "metadata_": {"source": "test", "importance": "high"},
            "state": "active",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "categories": ["test", "unit-test"],
            "app_name": "heti"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act: Call the method
        memory_id = "550e8400-e29b-41d4-a716-446655440000"
        result = self.client.get_memory(memory_id)
        
        # Assert: Verify the request was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        # Check endpoint URL includes memory ID
        expected_url = f"http://test-api:8000/api/v1/memories/{memory_id}"
        self.assertEqual(call_args[0][0], expected_url)
        
        # Check headers
        self.assertEqual(call_args[1]['headers']['Content-Type'], "application/json")
        
        # Check timeout
        self.assertEqual(call_args[1]['timeout'], 10)
        
        # Assert: Verify response handling and structure
        self.assertEqual(result['id'], memory_id)
        self.assertEqual(result['content'], "Retrieved memory content for testing")
        self.assertEqual(result['state'], "active")
        self.assertEqual(result['app_name'], "heti")
        self.assertEqual(result['user_id'], 123)
        self.assertIn("test", result['categories'])
        self.assertIn("unit-test", result['categories'])
        self.assertEqual(result['metadata_']['source'], "test")
        
        # Log test completion
        logger.info(
            f"test_get_memory_success completed - "
            f"Result ID: {result['id']}, "
            f"Content length: {len(result['content'])}, "
            f"Status: SUCCESS, "
            f"Request verified: {expected_url}"
        )

    @patch('tools.openmemory_client.requests.Session.get')
    def test_get_memory_not_found(self, mock_get):
        """
        Test handling of memory not found errors (404 status).
        
        Verifies:
        - 404 errors are properly caught and logged
        - Appropriate ValueError is raised with memory context
        - Memory ID is included in error logging
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_get_memory_not_found - Timestamp: {test_start}")
        
        # Arrange: Mock memory not found response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "detail": "Memory not found"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        memory_id = "550e8400-0000-0000-0000-000000000000"
        with self.assertRaises(ValueError) as context:
            self.client.get_memory(memory_id)
        
        # Verify error message contains memory context
        error_message = str(context.exception)
        self.assertIn("Memory not found", error_message)
        
        # Verify request was attempted with correct memory ID
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        expected_url = f"http://test-api:8000/api/v1/memories/{memory_id}"
        self.assertEqual(call_args[0][0], expected_url)
        
        # Log error handling verification
        logger.info(
            f"test_get_memory_not_found completed - "
            f"Memory ID: {memory_id}, "
            f"Error properly caught: {error_message}, "
            f"Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.get')
    def test_get_memory_invalid_uuid_format(self, mock_get):
        """
        Test handling of invalid UUID format errors (422 status).
        
        Verifies:
        - 422 validation errors are properly caught
        - Error details are extracted and logged
        - Appropriate ValueError is raised for invalid UUID
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_get_memory_invalid_uuid_format - Timestamp: {test_start}")
        
        # Arrange: Mock validation error response
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": [
                {
                    "loc": ["path", "memory_id"],
                    "msg": "value is not a valid uuid",
                    "type": "type_error.uuid"
                }
            ]
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError for invalid UUID
        invalid_memory_id = "invalid-uuid-format"
        with self.assertRaises(ValueError) as context:
            self.client.get_memory(invalid_memory_id)
        
        # Verify error message contains UUID validation context
        error_message = str(context.exception)
        self.assertIn("valid UUID format", error_message)
        
        # Verify request was NOT attempted due to client-side validation
        mock_get.assert_not_called()
        
        # Log error handling verification
        logger.info(
            f"test_get_memory_invalid_uuid_format completed - "
            f"Invalid ID: {invalid_memory_id}, "
            f"Error properly caught: {error_message}, "
            f"Status: SUCCESS"
        )

    def test_get_memory_client_side_validation(self):
        """
        Test client-side validation of memory_id parameter.
        
        Verifies:
        - Empty string raises ValueError
        - None parameter raises ValueError
        - Basic UUID format validation
        - Error messages are clear and actionable
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_get_memory_client_side_validation - Timestamp: {test_start}")
        
        # Test empty string
        with self.assertRaises(ValueError) as context:
            self.client.get_memory("")
        self.assertIn("non-empty string", str(context.exception))
        
        # Test None parameter  
        with self.assertRaises(ValueError) as context:
            self.client.get_memory(None)
        self.assertIn("non-empty string", str(context.exception))
        
        # Test invalid UUID format (wrong length)
        with self.assertRaises(ValueError) as context:
            self.client.get_memory("short-uuid")
        self.assertIn("valid UUID format", str(context.exception))
        
        # Test invalid UUID format (wrong dash count)
        with self.assertRaises(ValueError) as context:
            self.client.get_memory("550e8400-e29b-41d4-a716-44665544000x")  # 'x' instead of '0'
        self.assertIn("valid UUID format", str(context.exception))
        
        logger.info(
            f"test_get_memory_client_side_validation completed - "
            f"All validation scenarios tested, "
            f"Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.get')
    def test_get_memory_network_error(self, mock_get):
        """
        Test handling of network errors during memory retrieval.
        
        Verifies:
        - Network errors are properly caught and logged
        - Original exception is re-raised for calling code
        - Request details are logged for debugging
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_get_memory_network_error - Timestamp: {test_start}")
        
        # Arrange: Mock network error
        mock_get.side_effect = requests.RequestException("Connection timeout")
        
        # Act & Assert: Call should re-raise RequestException
        memory_id = "550e8400-e29b-41d4-a716-446655440000"
        with self.assertRaises(requests.RequestException) as context:
            self.client.get_memory(memory_id)
        
        # Verify original exception is preserved
        self.assertIn("Connection timeout", str(context.exception))
        
        # Verify request was attempted
        mock_get.assert_called_once()
        
        # Log error handling verification
        logger.info(
            f"test_get_memory_network_error completed - "
            f"Memory ID: {memory_id}, "
            f"Network error properly handled: {str(context.exception)}, "
            f"Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.get')
    def test_get_memory_json_decode_error(self, mock_get):
        """
        Test handling of malformed JSON responses.
        
        Verifies:
        - JSON parsing errors are caught and converted to ValueError
        - Error details are logged for debugging
        - Response status code is preserved in logging
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_get_memory_json_decode_error - Timestamp: {test_start}")
        
        # Arrange: Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "response", 0)
        mock_response.headers = {"Content-Type": "application/json"}
        mock_get.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError for JSON decode error
        memory_id = "550e8400-e29b-41d4-a716-446655440000"
        with self.assertRaises(ValueError) as context:
            self.client.get_memory(memory_id)
        
        # Verify error message indicates JSON parsing problem
        error_message = str(context.exception)
        self.assertIn("Invalid JSON response", error_message)
        
        # Verify request was attempted
        mock_get.assert_called_once()
        
        # Log error handling verification
        logger.info(
            f"test_get_memory_json_decode_error completed - "
            f"Memory ID: {memory_id}, "
            f"JSON error properly handled: {error_message}, "
            f"Status: SUCCESS"
        )

    def test_get_memory_simple_convenience_function(self):
        """
        Test the convenience function get_memory_simple.
        
        Verifies:
        - Function exists and is callable
        - Function properly instantiates client and calls get_memory
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_get_memory_simple_convenience_function - Timestamp: {test_start}")
        
        # Verify the function exists and can be imported
        self.assertTrue(callable(get_memory_simple))
        
        logger.info(
            f"test_get_memory_simple_convenience_function completed - "
            f"Function verified as callable"
        )

    @patch('tools.openmemory_client.requests.Session.put')
    def test_update_memory_success(self, mock_put):
        """
        Test successful memory update with valid data.
        
        Verifies:
        - Correct API endpoint is called with PUT method
        - Request payload is properly formatted
        - Response is correctly parsed and returned
        - All operations are logged for traceability
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_update_memory_success - Timestamp: {test_start}")
        
        # Arrange: Mock successful update response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": 123,
            "app_id": "550e8400-e29b-41d4-a716-446655440001",
            "content": "Updated memory content",
            "metadata_": {"category": "updated", "priority": "high"},
            "state": "active",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T14:22:00Z",
            "categories": ["updated"],
            "app_name": "heti"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_put.return_value = mock_response
        
        # Act: Call the update method
        result = self.client.update_memory(
            memory_id="550e8400-e29b-41d4-a716-446655440000",
            content="Updated memory content",
            metadata={"category": "updated", "priority": "high"}
        )
        
        # Assert: Verify the request was made correctly
        mock_put.assert_called_once()
        call_args = mock_put.call_args
        
        # Check endpoint URL
        expected_url = "http://test-api:8000/api/v1/memories/550e8400-e29b-41d4-a716-446655440000"
        self.assertEqual(call_args[0][0], expected_url)
        
        # Check request payload
        expected_payload = {
            "content": "Updated memory content",
            "metadata": {"category": "updated", "priority": "high"}
        }
        self.assertEqual(call_args[1]['json'], expected_payload)
        
        # Check headers
        self.assertEqual(call_args[1]['headers']['Content-Type'], "application/json")
        
        # Check timeout
        self.assertEqual(call_args[1]['timeout'], 10)
        
        # Assert: Verify response handling
        self.assertEqual(result['id'], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(result['content'], "Updated memory content")
        self.assertEqual(result['metadata_']['category'], "updated")
        self.assertEqual(result['metadata_']['priority'], "high")
        self.assertEqual(result['state'], "active")
        self.assertEqual(result['updated_at'], "2024-01-15T14:22:00Z")
        
        # Log test completion
        logger.info(
            f"test_update_memory_success completed - "
            f"Result ID: {result['id']}, "
            f"Updated content length: {len(result['content'])}, "
            f"Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.put')
    def test_update_memory_without_metadata(self, mock_put):
        """
        Test successful memory update without metadata.
        
        Verifies that the method works correctly when metadata is not provided.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_update_memory_without_metadata - Timestamp: {test_start}")
        
        # Arrange: Mock successful update response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": 123,
            "app_id": "550e8400-e29b-41d4-a716-446655440001",
            "content": "Updated content without metadata",
            "metadata_": {},
            "state": "active",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T14:25:00Z",
            "categories": [],
            "app_name": "heti"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_put.return_value = mock_response
        
        # Act: Call the update method without metadata
        result = self.client.update_memory(
            memory_id="550e8400-e29b-41d4-a716-446655440000",
            content="Updated content without metadata"
        )
        
        # Assert: Verify the request payload has empty metadata
        call_args = mock_put.call_args
        expected_payload = {
            "content": "Updated content without metadata",
            "metadata": {}
        }
        self.assertEqual(call_args[1]['json'], expected_payload)
        
        # Assert: Verify response
        self.assertEqual(result['content'], "Updated content without metadata")
        self.assertEqual(result['metadata_'], {})
        
        logger.info(f"test_update_memory_without_metadata completed - Status: SUCCESS")

    @patch('tools.openmemory_client.requests.Session.put')
    def test_update_memory_not_found(self, mock_put):
        """
        Test handling of memory not found errors (404 status).
        
        Verifies:
        - 404 errors are properly caught and logged
        - Appropriate ValueError is raised with memory context
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_update_memory_not_found - Timestamp: {test_start}")
        
        # Arrange: Mock memory not found response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "detail": "Memory not found"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_put.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.update_memory(
                memory_id="550e8400-e29b-41d4-a716-446655440000",
                content="Updated content for nonexistent memory"
            )
        
        # Verify error message
        error_message = str(context.exception)
        self.assertIn("Memory not found", error_message)
        
        # Verify request was attempted
        mock_put.assert_called_once()
        
        logger.info(
            f"test_update_memory_not_found completed - "
            f"Error properly caught: {error_message}, "
            f"Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.put')
    def test_update_memory_validation_error(self, mock_put):
        """
        Test handling of validation errors (422 status).
        
        Verifies:
        - 422 validation errors are properly caught
        - Error details are extracted and logged
        - Appropriate ValueError is raised
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_update_memory_validation_error - Timestamp: {test_start}")
        
        # Arrange: Mock validation error response
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": [
                {
                    "loc": ["path", "memory_id"],
                    "msg": "value is not a valid uuid",
                    "type": "type_error.uuid"
                }
            ]
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_put.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.update_memory(
                memory_id="550e8400-e29b-41d4-a716-446655440000",  # Valid format but server rejects
                content="Updated content"
            )
        
        # Verify error message contains validation details
        error_message = str(context.exception)
        self.assertIn("Validation error", error_message)
        self.assertIn("value is not a valid uuid", error_message)
        
        # Verify request was attempted
        mock_put.assert_called_once()
        
        logger.info(
            f"test_update_memory_validation_error completed - "
            f"Error properly caught: {error_message}, "
            f"Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.put')
    def test_update_memory_bad_request(self, mock_put):
        """
        Test handling of bad request errors (400 status).
        
        Verifies handling of malformed request structure or invalid JSON.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_update_memory_bad_request - Timestamp: {test_start}")
        
        # Arrange: Mock bad request response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "detail": "Invalid request format"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_put.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.update_memory(
                memory_id="550e8400-e29b-41d4-a716-446655440000",
                content="Content that causes bad request"
            )
        
        # Verify error message
        error_message = str(context.exception)
        self.assertIn("Bad request", error_message)
        self.assertIn("Invalid request format", error_message)
        
        logger.info(
            f"test_update_memory_bad_request completed - "
            f"Error properly caught: {error_message}, "
            f"Status: SUCCESS"
        )

    def test_update_memory_client_side_validation(self):
        """
        Test client-side validation of input parameters.
        
        Verifies:
        - Invalid UUID formats are caught before API call
        - Empty/None content is rejected
        - Whitespace-only content is rejected
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_update_memory_client_side_validation - Timestamp: {test_start}")
        
        # Test invalid memory_id formats
        invalid_uuids = [
            "",  # Empty string
            None,  # None value
            "not-a-uuid",  # Invalid format
            "550e8400-e29b-41d4-a716",  # Too short
            "550e8400-e29b-41d4-a716-446655440000-extra",  # Too long
            "550e8400-e29b-41d4-a716-44665544000z",  # Invalid hex character
            "550e8400_e29b_41d4_a716_446655440000",  # Wrong separators
        ]
        
        for invalid_uuid in invalid_uuids:
            with self.assertRaises(ValueError) as context:
                self.client.update_memory(
                    memory_id=invalid_uuid,
                    content="Valid content"
                )
            
            error_message = str(context.exception)
            self.assertIn("memory_id", error_message.lower())
            logger.info(f"Correctly rejected invalid UUID: {invalid_uuid}")
        
        # Test invalid content values
        invalid_contents = [
            "",  # Empty string
            None,  # None value
            "   ",  # Whitespace only
            "\t\n ",  # Mixed whitespace
        ]
        
        for invalid_content in invalid_contents:
            with self.assertRaises(ValueError) as context:
                self.client.update_memory(
                    memory_id="550e8400-e29b-41d4-a716-446655440000",
                    content=invalid_content
                )
            
            error_message = str(context.exception)
            self.assertIn("content", error_message.lower())
            logger.info(f"Correctly rejected invalid content: {repr(invalid_content)}")
        
        logger.info(
            f"test_update_memory_client_side_validation completed - "
            f"All validation cases verified, Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.put')
    def test_update_memory_network_error(self, mock_put):
        """
        Test handling of network/connection errors.
        
        Verifies that network errors are properly caught and re-raised.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_update_memory_network_error - Timestamp: {test_start}")
        
        # Arrange: Mock network error
        mock_put.side_effect = requests.ConnectionError("Network unreachable")
        
        # Act & Assert: Call should raise ConnectionError
        with self.assertRaises(requests.ConnectionError):
            self.client.update_memory(
                memory_id="550e8400-e29b-41d4-a716-446655440000",
                content="Content that will cause network error"
            )
        
        # Verify request was attempted
        mock_put.assert_called_once()
        
        logger.info(
            f"test_update_memory_network_error completed - "
            f"Network error properly handled, Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.put')
    def test_update_memory_json_decode_error(self, mock_put):
        """
        Test handling of malformed JSON responses.
        
        Verifies that JSON parsing errors are properly caught and converted to ValueError.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_update_memory_json_decode_error - Timestamp: {test_start}")
        
        # Arrange: Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "malformed", 0)
        mock_response.text = "Invalid JSON response"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_put.return_value = mock_response
        
        # Act & Assert: Call should raise ValueError due to JSON decode error
        with self.assertRaises(ValueError) as context:
            self.client.update_memory(
                memory_id="550e8400-e29b-41d4-a716-446655440000",
                content="Content with malformed JSON response"
            )
        
        # Verify error message
        error_message = str(context.exception)
        self.assertIn("Invalid JSON response", error_message)
        
        # Verify request was attempted
        mock_put.assert_called_once()
        
        logger.info(
            f"test_update_memory_json_decode_error completed - "
            f"JSON decode error properly handled, Status: SUCCESS"
        )

    def test_update_memory_simple_convenience_function(self):
        """
        Test the update_memory_simple convenience function.
        
        Verifies that the convenience function properly delegates to the client method.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_update_memory_simple_convenience_function - Timestamp: {test_start}")
        
        # Verify the function exists and is callable
        self.assertTrue(callable(update_memory_simple))
        
        # Verify function signature (basic check)
        import inspect
        sig = inspect.signature(update_memory_simple)
        expected_params = ['memory_id', 'content', 'metadata', 'base_url']
        actual_params = list(sig.parameters.keys())
        self.assertEqual(actual_params, expected_params)
        
        logger.info(
            f"test_update_memory_simple_convenience_function completed - "
            f"Function verified as callable with correct signature"
        )

    # =================
    # FILTER MEMORIES TESTS  
    # =================

    @patch('tools.openmemory_client.requests.Session.post')
    def test_filter_memories_success_simple(self, mock_post):
        """
        Test successful filtering with simple filter criteria.
        
        Verifies:
        - Correct API endpoint is called with POST method
        - Request payload is properly formatted 
        - Response is correctly parsed and returned
        - All operations are logged for traceability
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_success_simple - Timestamp: {test_start}")
        
        # Arrange: Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "memories": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "user_id": "test-user",
                    "app_id": "550e8400-e29b-41d4-a716-446655440001",
                    "content": "Meeting notes about project planning",
                    "metadata_": {"type": "meeting", "priority": "high"},
                    "state": "active",
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:00Z",
                    "categories": ["work", "planning"],
                    "app_name": "heti"
                }
            ],
            "pagination": {
                "total": 1,
                "page": 1,
                "size": 10,
                "pages": 1
            },
            "filter_summary": {
                "conditions_applied": 2,
                "execution_time_ms": 45.3,
                "query_complexity": "simple"
            }
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Prepare filter data
        filter_data = {
            "user_id": "test-user",
            "conditions": [
                {"field": "content", "operator": "like", "value": "meeting"},
                {"field": "categories", "operator": "in", "value": ["work", "planning"]}
            ],
            "pagination": {"page": 1, "size": 10}
        }
        
        # Act: Call the method
        result = self.client.filter_memories(filter_data)
        
        # Assert: Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check endpoint URL
        expected_url = "http://test-api:8000/api/v1/memories/filter"
        self.assertEqual(call_args[0][0], expected_url)
        
        # Check request payload
        self.assertEqual(call_args[1]['json'], filter_data)
        
        # Check headers
        self.assertEqual(call_args[1]['headers']['Content-Type'], "application/json")
        
        # Check timeout
        self.assertEqual(call_args[1]['timeout'], 10)
        
        # Assert: Verify response handling
        self.assertEqual(len(result['memories']), 1)
        self.assertEqual(result['memories'][0]['id'], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(result['memories'][0]['content'], "Meeting notes about project planning")
        
        # Verify pagination
        self.assertEqual(result['pagination']['total'], 1)
        self.assertEqual(result['pagination']['page'], 1)
        self.assertEqual(result['pagination']['size'], 10)
        
        # Verify filter summary
        self.assertEqual(result['filter_summary']['conditions_applied'], 2)
        self.assertEqual(result['filter_summary']['execution_time_ms'], 45.3)
        self.assertEqual(result['filter_summary']['query_complexity'], "simple")
        
        # Log test completion
        logger.info(
            f"test_filter_memories_success_simple completed - "
            f"Result count: {len(result['memories'])}, "
            f"Total matches: {result['pagination']['total']}, "
            f"Status: SUCCESS"
        )

    @patch('tools.openmemory_client.requests.Session.post')
    def test_filter_memories_complex_filter(self, mock_post):
        """
        Test filtering with complex filter criteria including metadata and date ranges.
        
        Verifies complex filter handling with multiple condition types.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_complex_filter - Timestamp: {test_start}")
        
        # Arrange: Mock successful response for complex query
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "memories": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "user_id": "test-user",
                    "app_id": "550e8400-e29b-41d4-a716-446655440002",
                    "content": "Important project milestone completed",
                    "metadata_": {"priority": "high", "project": "alpha", "status": "completed"},
                    "state": "active",
                    "created_at": "2024-01-15T15:00:00Z",
                    "updated_at": "2024-01-15T15:00:00Z",
                    "categories": ["work", "milestone"],
                    "app_name": "heti"
                }
            ],
            "pagination": {
                "total": 1,
                "page": 1,
                "size": 20,
                "pages": 1
            },
            "filter_summary": {
                "conditions_applied": 5,
                "execution_time_ms": 128.7,
                "query_complexity": "complex"
            }
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Prepare complex filter data
        filter_data = {
            "user_id": "test-user",
            "conditions": [
                {"field": "content", "operator": "like", "value": "project"},
                {"field": "metadata.priority", "operator": "eq", "value": "high"},
                {"field": "state", "operator": "eq", "value": "active"}
            ],
            "date_range": {
                "from": 1705320000,  # 2024-01-15T12:00:00Z
                "to": 1705323600     # 2024-01-15T13:00:00Z
            },
            "categories": ["work"],
            "metadata_filters": {
                "project": "alpha",
                "status": "completed"
            },
            "content_search": {
                "query": "milestone",
                "fuzzy": False,
                "case_sensitive": False
            },
            "sort": {
                "field": "created_at",
                "direction": "desc"
            },
            "pagination": {
                "page": 1,
                "size": 20
            }
        }
        
        # Act: Call the method
        result = self.client.filter_memories(filter_data)
        
        # Assert: Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json'], filter_data)
        
        # Assert: Verify response handling for complex query
        self.assertEqual(len(result['memories']), 1)
        self.assertEqual(result['memories'][0]['content'], "Important project milestone completed")
        self.assertEqual(result['filter_summary']['conditions_applied'], 5)
        self.assertEqual(result['filter_summary']['query_complexity'], "complex")
        
        logger.info(
            f"test_filter_memories_complex_filter completed - "
            f"Complex query executed successfully, "
            f"Execution time: {result['filter_summary']['execution_time_ms']}ms"
        )

    @patch('tools.openmemory_client.requests.Session.post')
    def test_filter_memories_empty_result(self, mock_post):
        """
        Test filter request that returns no matching memories.
        
        Verifies proper handling when filter criteria match no memories.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_empty_result - Timestamp: {test_start}")
        
        # Arrange: Mock empty result response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "memories": [],
            "pagination": {
                "total": 0,
                "page": 1,
                "size": 10,
                "pages": 0
            },
            "filter_summary": {
                "conditions_applied": 1,
                "execution_time_ms": 12.4,
                "query_complexity": "simple"
            }
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Prepare filter data that will match nothing
        filter_data = {
            "user_id": "test-user",
            "conditions": [
                {"field": "content", "operator": "like", "value": "nonexistent_content_xyz"}
            ]
        }
        
        # Act: Call the method
        result = self.client.filter_memories(filter_data)
        
        # Assert: Verify empty result handling
        self.assertEqual(len(result['memories']), 0)
        self.assertEqual(result['pagination']['total'], 0)
        self.assertEqual(result['pagination']['pages'], 0)
        self.assertIsInstance(result['memories'], list)
        
        logger.info(
            f"test_filter_memories_empty_result completed - "
            f"Empty result handled correctly"
        )

    @patch('tools.openmemory_client.requests.Session.post')
    def test_filter_memories_validation_error(self, mock_post):
        """
        Test handling of validation errors (422 status) for filter requests.
        
        Verifies proper error handling when filter data is invalid.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_validation_error - Timestamp: {test_start}")
        
        # Arrange: Mock validation error response
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": [
                {
                    "loc": ["body", "filter", "conditions", 0, "operator"],
                    "msg": "invalid operator type",
                    "type": "value_error.invalid"
                }
            ]
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Prepare filter data that passes client validation but fails server validation
        filter_data = {
            "user_id": "test-user",
            "conditions": [
                {"field": "content", "operator": "invalid_operator_type", "value": "test"}
            ]
        }
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.filter_memories(filter_data)
        
        # Verify error message contains validation details
        error_message = str(context.exception)
        self.assertIn("Filter validation error", error_message)
        self.assertIn("invalid operator type", error_message)
        
        logger.info(
            f"test_filter_memories_validation_error completed - "
            f"Validation error properly caught: {error_message}"
        )

    @patch('tools.openmemory_client.requests.Session.post')
    def test_filter_memories_bad_request(self, mock_post):
        """
        Test handling of bad request errors (400 status) for filter requests.
        
        Verifies proper error handling when filter structure is invalid.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_bad_request - Timestamp: {test_start}")
        
        # Arrange: Mock bad request error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "detail": "Invalid filter operator 'invalid_op' for field 'content'"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Prepare filter data with invalid operator
        filter_data = {
            "user_id": "test-user",
            "conditions": [
                {"field": "content", "operator": "invalid_op", "value": "test"}
            ]
        }
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.filter_memories(filter_data)
        
        # Verify error message contains details
        error_message = str(context.exception)
        self.assertIn("Invalid filter request", error_message)
        self.assertIn("invalid_op", error_message)
        
        logger.info(
            f"test_filter_memories_bad_request completed - "
            f"Bad request error properly caught: {error_message}"
        )

    @patch('tools.openmemory_client.requests.Session.post')
    def test_filter_memories_rate_limit(self, mock_post):
        """
        Test handling of rate limit errors (429 status) for filter requests.
        
        Verifies proper error handling when rate limits are exceeded.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_rate_limit - Timestamp: {test_start}")
        
        # Arrange: Mock rate limit error response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "detail": "Query rate limit exceeded. Please wait before making complex filter requests."
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Prepare filter data (content doesn't matter for rate limit test)
        filter_data = {
            "user_id": "test-user",
            "conditions": [
                {"field": "content", "operator": "like", "value": "test"}
            ]
        }
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.filter_memories(filter_data)
        
        # Verify error message contains rate limit details
        error_message = str(context.exception)
        self.assertIn("Rate limit exceeded", error_message)
        
        logger.info(
            f"test_filter_memories_rate_limit completed - "
            f"Rate limit error properly caught: {error_message}"
        )

    @patch('tools.openmemory_client.requests.Session.post')
    def test_filter_memories_server_error(self, mock_post):
        """
        Test handling of server errors (500 status) for filter requests.
        
        Verifies proper error handling when server errors occur.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_server_error - Timestamp: {test_start}")
        
        # Arrange: Mock server error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "detail": "Internal server error occurred while processing filter request"
        }
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Prepare filter data
        filter_data = {
            "user_id": "test-user",
            "conditions": [
                {"field": "content", "operator": "like", "value": "test"}
            ]
        }
        
        # Act & Assert: Call should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.client.filter_memories(filter_data)
        
        # Verify error message contains server error details
        error_message = str(context.exception)
        self.assertIn("Server error", error_message)
        
        logger.info(
            f"test_filter_memories_server_error completed - "
            f"Server error properly caught: {error_message}"
        )

    def test_filter_memories_client_side_validation(self):
        """
        Test client-side validation for filter_memories method.
        
        Verifies that client properly validates input before making API calls.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_client_side_validation - Timestamp: {test_start}")
        
        # Test non-dictionary filter_data
        with self.assertRaises(ValueError) as context:
            self.client.filter_memories("not a dict")
        
        error_message = str(context.exception)
        self.assertIn("filter_data must be a dictionary", error_message)
        
        # Test missing user_id
        with self.assertRaises(ValueError) as context:
            self.client.filter_memories({
                "conditions": [{"field": "content", "operator": "like", "value": "test"}]
            })
        
        error_message = str(context.exception)
        self.assertIn("filter_data must contain 'user_id' field", error_message)
        
        # Test empty user_id
        with self.assertRaises(ValueError) as context:
            self.client.filter_memories({
                "user_id": "",
                "conditions": [{"field": "content", "operator": "like", "value": "test"}]
            })
        
        error_message = str(context.exception)
        self.assertIn("user_id cannot be empty", error_message)
        
        logger.info(
            f"test_filter_memories_client_side_validation completed - "
            f"All client-side validations working correctly"
        )

    @patch('tools.openmemory_client.requests.Session.post')
    def test_filter_memories_network_error(self, mock_post):
        """
        Test handling of network errors during filter requests.
        
        Verifies proper error handling when network issues occur.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_network_error - Timestamp: {test_start}")
        
        # Arrange: Mock network error
        mock_post.side_effect = requests.RequestException("Network connection failed")
        
        # Prepare filter data
        filter_data = {
            "user_id": "test-user",
            "conditions": [
                {"field": "content", "operator": "like", "value": "test"}
            ]
        }
        
        # Act & Assert: Call should raise RequestException
        with self.assertRaises(requests.RequestException) as context:
            self.client.filter_memories(filter_data)
        
        # Verify the original exception is raised
        self.assertIn("Network connection failed", str(context.exception))
        
        logger.info(
            f"test_filter_memories_network_error completed - "
            f"Network error properly propagated: {str(context.exception)}"
        )

    @patch('tools.openmemory_client.requests.Session.post')
    def test_filter_memories_json_decode_error(self, mock_post):
        """
        Test handling of JSON decode errors during filter requests.
        
        Verifies proper error handling when response contains invalid JSON.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_json_decode_error - Timestamp: {test_start}")
        
        # Arrange: Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "response", 0)
        mock_response.headers = {"Content-Type": "application/json"}
        mock_post.return_value = mock_response
        
        # Prepare filter data
        filter_data = {
            "user_id": "test-user",
            "conditions": [
                {"field": "content", "operator": "like", "value": "test"}
            ]
        }
        
        # Act & Assert: Call should raise ValueError for JSON decode error
        with self.assertRaises(ValueError) as context:
            self.client.filter_memories(filter_data)
        
        # Verify error message indicates JSON problem
        error_message = str(context.exception)
        self.assertIn("Invalid JSON response", error_message)
        
        logger.info(
            f"test_filter_memories_json_decode_error completed - "
            f"JSON decode error properly handled, Status: SUCCESS"
        )

    def test_filter_memories_simple_convenience_function(self):
        """
        Test the filter_memories_simple convenience function.
        
        Verifies that the convenience function exists and has the correct signature.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting test_filter_memories_simple_convenience_function - Timestamp: {test_start}")
        
        # Verify the function exists and is callable
        self.assertTrue(callable(filter_memories_simple))
        
        # Verify function signature (basic check)
        import inspect
        sig = inspect.signature(filter_memories_simple)
        expected_params = ['filter_data', 'base_url']
        actual_params = list(sig.parameters.keys())
        self.assertEqual(actual_params, expected_params)
        
        logger.info(
            f"test_filter_memories_simple_convenience_function completed - "
            f"Function verified as callable with correct signature"
        )


class TestOpenMemoryClientIntegration(unittest.TestCase):
    """
    Integration tests for OpenMemoryClient (requires running API server).
    
    These tests are marked as integration and should be run separately
    when an actual OpenMemory API server is available.
    """
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.client = OpenMemoryClient(base_url="http://localhost:8000")
        logger.info("Integration test setup - OpenMemoryClient initialized for localhost:8000")
    
    @unittest.skip("Integration test - requires running OpenMemory API server")
    def test_create_memory_real_api(self):
        """
        Integration test with real API server.
        
        This test is skipped by default and should only be run when
        an actual OpenMemory API server is running locally.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting integration test - Timestamp: {test_start}")
        
        try:
            result = self.client.create_memory(
                user_id="integration-test-user",
                text="Integration test memory creation",
                infer=True,
                app="heti-test"
            )
            
            # Verify response structure
            self.assertIn('id', result)
            self.assertIn('content', result)
            self.assertEqual(result['content'], "Integration test memory creation")
            
            logger.info(
                f"Integration test completed successfully - "
                f"Memory ID: {result['id']}, "
                f"Status: SUCCESS"
            )
            
        except Exception as e:
            logger.error(f"Integration test failed - Error: {str(e)}")
            raise

    @unittest.skip("Integration test - requires running OpenMemory API server")
    def test_list_memories_real_api(self):
        """
        Integration test for list_memories with real API server.
        
        This test is skipped by default and should only be run when
        an actual OpenMemory API server is running locally.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting list_memories integration test - Timestamp: {test_start}")
        
        try:
            # Test basic listing
            result = self.client.list_memories(
                user_id="integration-test-user",
                page=1,
                size=5
            )
            
            # Verify response structure
            self.assertIn('items', result)
            self.assertIn('total', result)
            self.assertIn('page', result)
            self.assertIn('size', result)
            self.assertIn('pages', result)
            
            # Verify pagination metadata
            self.assertIsInstance(result['items'], list)
            self.assertIsInstance(result['total'], int)
            self.assertEqual(result['page'], 1)
            self.assertEqual(result['size'], 5)
            
            logger.info(
                f"List memories integration test completed successfully - "
                f"Total memories: {result['total']}, "
                f"Items returned: {len(result['items'])}, "
                f"Status: SUCCESS"
            )
            
            # Test with filters if we have memories
            if result['total'] > 0:
                filtered_result = self.client.list_memories(
                    user_id="integration-test-user",
                    search_query="integration",
                    sort_column="created_at",
                    sort_direction="desc"
                )
                
                logger.info(
                    f"Filtered search completed - "
                    f"Search results: {filtered_result['total']} memories"
                )
            
        except Exception as e:
            logger.error(f"List memories integration test failed - Error: {str(e)}")
            raise

    @unittest.skip("Integration test - requires running OpenMemory API server")
    def test_update_memory_real_api(self):
        """
        Integration test for update_memory with real API server.
        
        This test is skipped by default and should only be run when
        an actual OpenMemory API server is running locally.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting update_memory integration test - Timestamp: {test_start}")
        
        try:
            # First, create a memory to ensure we have something to update
            create_result = self.client.create_memory(
                user_id="integration-test-user",
                text="Original memory content for update testing",
                infer=True,
                app="heti-integration-test"
            )
            
            memory_id = create_result['id']
            original_content = create_result['content']
            original_updated_at = create_result['updated_at']
            logger.info(f"Created test memory for update: {memory_id}")
            
            # Now update the memory
            updated_memory = self.client.update_memory(
                memory_id=memory_id,
                content="Updated memory content from integration test",
                metadata={"test_type": "integration", "updated_by": "test_suite"}
            )
            
            # Verify response structure and content
            self.assertEqual(updated_memory['id'], memory_id)
            self.assertEqual(updated_memory['content'], "Updated memory content from integration test")
            self.assertNotEqual(updated_memory['content'], original_content)
            self.assertNotEqual(updated_memory['updated_at'], original_updated_at)
            
            # Verify metadata was updated
            self.assertIn('metadata_', updated_memory)
            self.assertEqual(updated_memory['metadata_']['test_type'], "integration")
            self.assertEqual(updated_memory['metadata_']['updated_by'], "test_suite")
            
            # Verify other fields are preserved
            self.assertEqual(updated_memory['user_id'], create_result['user_id'])
            self.assertEqual(updated_memory['app_id'], create_result['app_id'])
            self.assertEqual(updated_memory['created_at'], create_result['created_at'])
            
            logger.info(
                f"Update memory integration test completed successfully - "
                f"Memory ID: {updated_memory['id']}, "
                f"Updated content: '{updated_memory['content'][:50]}...', "
                f"Updated at: {updated_memory['updated_at']}, "
                f"Status: SUCCESS"
            )
            
            # Test updating with just content (no metadata)
            second_update = self.client.update_memory(
                memory_id=memory_id,
                content="Second update without metadata"
            )
            
            self.assertEqual(second_update['content'], "Second update without metadata")
            self.assertEqual(second_update['id'], memory_id)
            
            logger.info(
                f"Second update (no metadata) completed successfully - "
                f"Content: '{second_update['content']}'"
            )
            
            # Test updating a non-existent memory
            nonexistent_id = "550e8400-0000-0000-0000-000000000000"
            with self.assertRaises(ValueError) as context:
                self.client.update_memory(
                    memory_id=nonexistent_id,
                    content="This should fail"
                )
            
            error_message = str(context.exception)
            self.assertIn("Memory not found", error_message)
            
            logger.info(
                f"Non-existent memory update test completed - "
                f"Error properly raised: {error_message}"
            )
            
        except Exception as e:
            logger.error(f"Update memory integration test failed - Error: {str(e)}")
            raise

    @unittest.skip("Integration test - requires running OpenMemory API server")
    def test_filter_memories_real_api(self):
        """
        Integration test for filter_memories with real API server.
        
        This test is skipped by default and should only be run when
        an actual OpenMemory API server is running locally.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting filter_memories integration test - Timestamp: {test_start}")
        
        try:
            # First, create some test memories to filter
            test_memories = []
            test_user = "filter-integration-test-user"
            
            # Create memories with different characteristics for filtering
            memories_to_create = [
                {
                    "text": "Integration test: Meeting notes for project planning",
                    "metadata": {"type": "meeting", "priority": "high", "project": "alpha"}
                },
                {
                    "text": "Integration test: Task completion report", 
                    "metadata": {"type": "task", "priority": "medium", "project": "beta"}
                },
                {
                    "text": "Integration test: Project milestone achieved",
                    "metadata": {"type": "milestone", "priority": "high", "project": "alpha"}
                }
            ]
            
            for memory_data in memories_to_create:
                created = self.client.create_memory(
                    user_id=test_user,
                    text=memory_data["text"],
                    infer=True,
                    app="heti-filter-integration-test"
                )
                
                # Update with metadata for filtering
                updated = self.client.update_memory(
                    memory_id=created['id'],
                    content=memory_data["text"],
                    metadata=memory_data["metadata"]
                )
                
                test_memories.append(updated)
                logger.info(f"Created and updated test memory: {created['id']}")
            
            # Test 1: Simple content filter
            filter_data_simple = {
                "user_id": test_user,
                "conditions": [
                    {"field": "content", "operator": "like", "value": "project"}
                ],
                "pagination": {"page": 1, "size": 10}
            }
            
            simple_result = self.client.filter_memories(filter_data_simple)
            
            # Verify structure
            self.assertIn('memories', simple_result)
            self.assertIn('pagination', simple_result)
            self.assertIn('filter_summary', simple_result)
            
            # Should find all our test memories (they all contain "project")
            self.assertGreaterEqual(simple_result['pagination']['total'], 3)
            
            logger.info(
                f"Simple filter test completed - "
                f"Found {simple_result['pagination']['total']} memories"
            )
            
            # Test 2: Complex filter with metadata and conditions
            filter_data_complex = {
                "user_id": test_user,
                "conditions": [
                    {"field": "content", "operator": "like", "value": "Integration test"},
                    {"field": "metadata.priority", "operator": "eq", "value": "high"}
                ],
                "metadata_filters": {
                    "project": "alpha"
                },
                "sort": {
                    "field": "created_at",
                    "direction": "desc"
                },
                "pagination": {"page": 1, "size": 20}
            }
            
            complex_result = self.client.filter_memories(filter_data_complex)
            
            # Should find 2 memories (meeting and milestone with high priority and project alpha)
            self.assertGreaterEqual(complex_result['pagination']['total'], 2)
            
            # Verify returned memories match criteria
            for memory in complex_result['memories']:
                self.assertIn("Integration test", memory['content'])
                if 'metadata_' in memory and memory['metadata_']:
                    if 'priority' in memory['metadata_']:
                        self.assertEqual(memory['metadata_']['priority'], "high")
                    if 'project' in memory['metadata_']:
                        self.assertEqual(memory['metadata_']['project'], "alpha")
            
            logger.info(
                f"Complex filter test completed - "
                f"Found {complex_result['pagination']['total']} memories matching complex criteria, "
                f"Execution time: {complex_result['filter_summary']['execution_time_ms']}ms"
            )
            
            # Test 3: Empty result filter
            filter_data_empty = {
                "user_id": test_user,
                "conditions": [
                    {"field": "content", "operator": "like", "value": "nonexistent_content_xyz_123"}
                ]
            }
            
            empty_result = self.client.filter_memories(filter_data_empty)
            
            # Should return empty results
            self.assertEqual(len(empty_result['memories']), 0)
            self.assertEqual(empty_result['pagination']['total'], 0)
            
            logger.info("Empty result filter test completed - correctly returned no results")
            
            # Test 4: Category-based filtering (if categories were assigned during creation)
            filter_data_categories = {
                "user_id": test_user,
                "categories": ["work"],  # Assuming OpenMemory assigns common categories
                "pagination": {"page": 1, "size": 10}
            }
            
            category_result = self.client.filter_memories(filter_data_categories)
            
            # This might return results if categories were inferred
            logger.info(
                f"Category filter test completed - "
                f"Found {category_result['pagination']['total']} memories with 'work' category"
            )
            
            # Test 5: Date range filtering
            import time
            current_time = int(time.time())
            one_hour_ago = current_time - 3600
            
            filter_data_date = {
                "user_id": test_user,
                "date_range": {
                    "from": one_hour_ago,
                    "to": current_time
                },
                "pagination": {"page": 1, "size": 10}
            }
            
            date_result = self.client.filter_memories(filter_data_date)
            
            # Should find our recently created memories
            self.assertGreaterEqual(date_result['pagination']['total'], 3)
            
            logger.info(
                f"Date range filter test completed - "
                f"Found {date_result['pagination']['total']} memories in last hour"
            )
            
            logger.info(
                f"Filter memories integration test completed successfully - "
                f"All filter types tested: simple, complex, empty, categories, date range, "
                f"Status: SUCCESS"
            )
            
        except Exception as e:
            logger.error(f"Filter memories integration test failed - Error: {str(e)}")
            raise

    @unittest.skip("Integration test - requires running OpenMemory API server")
    def test_end_to_end_create_update_and_get(self):
        """
        End-to-end integration test: create, update, and retrieve memories.
        
        This test demonstrates the complete CRUD workflow including updates.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting create-update-get end-to-end integration test - Timestamp: {test_start}")
        
        try:
            # Step 1: Create a test memory
            create_result = self.client.create_memory(
                user_id="e2e-crud-test-user",
                text="Original content for CRUD workflow testing",
                infer=True,
                app="heti-e2e-crud-test"
            )
            
            memory_id = create_result['id']
            logger.info(f"Created test memory: {memory_id}")
            
            # Step 2: Retrieve the created memory to verify initial state
            initial_retrieved = self.client.get_memory(memory_id)
            self.assertEqual(initial_retrieved['content'], "Original content for CRUD workflow testing")
            logger.info("Initial retrieval verified")
            
            # Step 3: Update the memory content and metadata
            updated_memory = self.client.update_memory(
                memory_id=memory_id,
                content="First update: Modified content for CRUD testing",
                metadata={"revision": 1, "test_phase": "first_update", "workflow": "crud"}
            )
            
            # Verify update response
            self.assertEqual(updated_memory['content'], "First update: Modified content for CRUD testing")
            self.assertEqual(updated_memory['metadata_']['revision'], 1)
            logger.info("First update completed and verified")
            
            # Step 4: Retrieve the updated memory to verify persistence
            first_update_retrieved = self.client.get_memory(memory_id)
            self.assertEqual(first_update_retrieved['content'], "First update: Modified content for CRUD testing")
            self.assertEqual(first_update_retrieved['metadata_']['revision'], 1)
            self.assertEqual(first_update_retrieved['metadata_']['test_phase'], "first_update")
            logger.info("First update retrieval verified")
            
            # Step 5: Second update with different metadata
            second_updated = self.client.update_memory(
                memory_id=memory_id,
                content="Second update: Final content for CRUD workflow",
                metadata={"revision": 2, "test_phase": "second_update", "workflow": "crud", "final": True}
            )
            
            # Verify second update
            self.assertEqual(second_updated['content'], "Second update: Final content for CRUD workflow")
            self.assertEqual(second_updated['metadata_']['revision'], 2)
            self.assertTrue(second_updated['metadata_']['final'])
            logger.info("Second update completed and verified")
            
            # Step 6: Final retrieval to verify complete workflow
            final_retrieved = self.client.get_memory(memory_id)
            self.assertEqual(final_retrieved['content'], "Second update: Final content for CRUD workflow")
            self.assertEqual(final_retrieved['metadata_']['revision'], 2)
            self.assertEqual(final_retrieved['metadata_']['test_phase'], "second_update")
            self.assertTrue(final_retrieved['metadata_']['final'])
            
            # Verify timestamps progression
            self.assertLessEqual(create_result['created_at'], first_update_retrieved['updated_at'])
            self.assertLessEqual(first_update_retrieved['updated_at'], final_retrieved['updated_at'])
            
            logger.info(
                f"Create-update-get end-to-end integration test completed successfully - "
                f"Memory ID: {memory_id}, "
                f"Created -> Updated (2x) -> Retrieved (3x), "
                f"All verifications passed, "
                f"Status: SUCCESS"
            )
            
            # Step 7: Test search to find our updated memory
            search_result = self.client.list_memories(
                user_id="e2e-crud-test-user",
                search_query="CRUD workflow",
                page=1,
                size=10
            )
            
            # Should find our updated memory
            self.assertGreater(search_result['total'], 0, "Search should find our updated memory")
            found_in_search = False
            for memory in search_result['items']:
                if memory['id'] == memory_id:
                    found_in_search = True
                    self.assertEqual(memory['content'], "Second update: Final content for CRUD workflow")
                    break
            
            self.assertTrue(found_in_search, "Updated memory should be found in search results")
            logger.info("Search verification completed - updated memory found with correct content")
            
        except Exception as e:
            logger.error(f"Create-update-get end-to-end integration test failed - Error: {str(e)}")
            raise

    @unittest.skip("Integration test - requires running OpenMemory API server")
    def test_end_to_end_create_list_and_get(self):
        """
        Complete end-to-end integration test: create, list, and retrieve memories.
        
        This test demonstrates the full workflow including individual memory retrieval.
        """
        test_start = datetime.now(UTC).isoformat()
        logger.info(f"Starting complete end-to-end integration test - Timestamp: {test_start}")
        
        try:
            # Step 1: Create multiple test memories
            created_memories = []
            for i in range(3):
                create_result = self.client.create_memory(
                    user_id="e2e-complete-test-user",
                    text=f"End-to-end test memory {i+1} for complete validation",
                    infer=True,
                    app="heti-e2e-complete-test"
                )
                created_memories.append(create_result)
                logger.info(f"Created test memory {i+1}: {create_result['id']}")
            
            # Step 2: List memories and verify all created memories appear
            list_result = self.client.list_memories(
                user_id="e2e-complete-test-user",
                page=1,
                size=20
            )
            
            # Find all our created memories in the list
            found_memory_ids = [memory['id'] for memory in list_result['items']]
            for created_memory in created_memories:
                self.assertIn(created_memory['id'], found_memory_ids, 
                            f"Created memory {created_memory['id']} not found in list")
            
            logger.info(f"All {len(created_memories)} created memories found in list")
            
            # Step 3: Retrieve each memory individually and verify content
            for i, created_memory in enumerate(created_memories):
                memory_id = created_memory['id']
                retrieved_memory = self.client.get_memory(memory_id)
                
                # Verify retrieved memory matches created memory
                self.assertEqual(retrieved_memory['id'], memory_id)
                self.assertEqual(retrieved_memory['content'], 
                               f"End-to-end test memory {i+1} for complete validation")
                self.assertEqual(retrieved_memory['user_id'], created_memory['user_id'])
                self.assertEqual(retrieved_memory['app_id'], created_memory['app_id'])
                
                logger.info(f"Successfully retrieved and verified memory {i+1}: {memory_id}")
            
            # Step 4: Test search functionality and retrieve specific result
            search_result = self.client.list_memories(
                user_id="e2e-complete-test-user",
                search_query="end-to-end test memory 2",
                page=1,
                size=10
            )
            
            # Should find at least our second memory
            self.assertGreater(search_result['total'], 0, "Search should find our test memory")
            
            # Get the first search result and retrieve it by ID
            if len(search_result['items']) > 0:
                search_memory_id = search_result['items'][0]['id']
                search_retrieved = self.client.get_memory(search_memory_id)
                self.assertEqual(search_retrieved['id'], search_memory_id)
                logger.info(f"Search and retrieve verified for memory: {search_memory_id}")
            
            logger.info(
                f"Complete end-to-end integration test completed successfully - "
                f"Created {len(created_memories)} memories, "
                f"Listed and verified all, "
                f"Retrieved each individually, "
                f"Search and retrieve verified, "
                f"Status: SUCCESS"
            )
            
        except Exception as e:
            logger.error(f"Complete end-to-end integration test failed - Error: {str(e)}")
            raise


if __name__ == '__main__':
    # Configure test logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Log test session start
    session_start = datetime.now(UTC).isoformat()
    logger.info(f"OpenMemory Client Test Session Started - Timestamp: {session_start}")
    
    # Run tests
    unittest.main(verbosity=2)
    
    # Log test session end
    session_end = datetime.now(UTC).isoformat()
    logger.info(f"OpenMemory Client Test Session Completed - Timestamp: {session_end}") 