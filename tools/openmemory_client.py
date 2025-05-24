"""
OpenMemory API Client for Heti

This module provides a client interface for interacting with the OpenMemory API,
specifically focused on memory creation and management operations.

Integration points:
- Used by Heti agent for memory storage operations
- Logs all requests/responses for traceability per Heti project rules
- Handles authentication and error scenarios
"""

import logging
import requests
import json
from datetime import datetime, UTC
from typing import Dict, Any, Optional, List, Union
from uuid import UUID
from urllib.parse import urlencode

# Configure logging for full traceability
logger = logging.getLogger(__name__)

class OpenMemoryClient:
    """
    Client for OpenMemory API operations with comprehensive logging.
    
    Follows Heti project rule @logs for full traceability of all operations.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        """
        Initialize OpenMemory client.
        
        Args:
            base_url: Base URL for OpenMemory API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
        logger.info(f"OpenMemoryClient initialized with base_url={base_url}, timeout={timeout}")
    
    def create_memory(
        self, 
        user_id: str, 
        text: str, 
        infer: bool = True, 
        app: str = "heti"
    ) -> Dict[str, Any]:
        """
        Create a new memory via POST /api/v1/memories endpoint.
        
        Args:
            user_id: User identifier (required)
            text: Memory content to store (required)
            infer: Whether to auto-infer categories (default: True)
            app: App identifier (default: "heti")
            
        Returns:
            Dict containing the created memory object with ID and metadata
            
        Raises:
            requests.RequestException: For network/HTTP errors
            ValueError: For validation errors or malformed responses
            
        Example:
            >>> client = OpenMemoryClient()
            >>> memory = client.create_memory("user123", "Meeting notes from today")
            >>> print(memory['id'])  # UUID of created memory
        """
        endpoint = f"{self.base_url}/api/v1/memories"
        
        # Prepare request payload
        payload = {
            "user_id": user_id,
            "text": text,
            "infer": infer,
            "app": app
        }
        
        # Log request details for traceability
        request_timestamp = datetime.now(UTC).isoformat()
        logger.info(
            f"OpenMemory API Request - Timestamp: {request_timestamp}, "
            f"Module: openmemory_client, "
            f"Endpoint: POST {endpoint}, "
            f"Payload: {json.dumps(payload, default=str)}"
        )
        
        try:
            # Make the HTTP request
            response = self.session.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            
            # Log response details
            response_timestamp = datetime.now(UTC).isoformat()
            logger.info(
                f"OpenMemory API Response - Timestamp: {response_timestamp}, "
                f"Status: {response.status_code}, "
                f"Headers: {dict(response.headers)}"
            )
            
            # Handle different response scenarios
            if response.status_code == 200:
                # Success case
                memory_data = response.json()
                logger.info(
                    f"Memory created successfully - "
                    f"ID: {memory_data.get('id')}, "
                    f"User: {user_id}, "
                    f"App: {app}, "
                    f"Content length: {len(text)}"
                )
                return memory_data
                
            elif response.status_code == 404:
                # User not found
                error_detail = response.json().get('detail', 'User not found')
                logger.error(f"User not found error - user_id: {user_id}, detail: {error_detail}")
                raise ValueError(f"User not found: {error_detail}")
                
            elif response.status_code == 403:
                # App paused
                error_detail = response.json().get('detail', 'App is paused')
                logger.error(f"App paused error - app: {app}, detail: {error_detail}")
                raise ValueError(f"App access denied: {error_detail}")
                
            elif response.status_code == 422:
                # Validation error
                error_details = response.json().get('detail', [])
                logger.error(f"Validation error - details: {error_details}")
                raise ValueError(f"Validation error: {error_details}")
                
            else:
                # Other HTTP errors
                logger.error(
                    f"Unexpected HTTP error - "
                    f"Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                response.raise_for_status()
                
        except requests.RequestException as e:
            # Network/connection errors
            logger.error(
                f"Network error during memory creation - "
                f"user_id: {user_id}, "
                f"endpoint: {endpoint}, "
                f"error: {str(e)}"
            )
            raise
            
        except json.JSONDecodeError as e:
            # Invalid JSON response
            logger.error(
                f"Invalid JSON response - "
                f"endpoint: {endpoint}, "
                f"status: {response.status_code}, "
                f"error: {str(e)}"
            )
            raise ValueError(f"Invalid JSON response: {str(e)}")
            
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"Unexpected error during memory creation - "
                f"user_id: {user_id}, "
                f"error: {str(e)}, "
                f"type: {type(e).__name__}"
            )
            raise

    def list_memories(
        self,
        user_id: str,
        app_id: Optional[Union[str, UUID]] = None,
        search_query: Optional[str] = None,
        categories: Optional[Union[str, List[str]]] = None,
        from_date: Optional[int] = None,
        to_date: Optional[int] = None,
        page: int = 1,
        size: int = 10,
        sort_column: Optional[str] = None,
        sort_direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List memories via GET /api/v1/memories endpoint with filtering and pagination.
        
        Args:
            user_id: User identifier (required)
            app_id: Filter by specific app UUID (optional)
            search_query: Text search within memory content (optional)
            categories: Category names to filter by - string or list (optional)
            from_date: Unix timestamp - memories created after this date (optional)
            to_date: Unix timestamp - memories created before this date (optional)
            page: Page number for pagination (default: 1, minimum: 1)
            size: Items per page (default: 10, minimum: 1, maximum: 100)
            sort_column: Column to sort by: "memory", "categories", "app_name", "created_at" (optional)
            sort_direction: Sort direction: "asc" or "desc" (optional)
            
        Returns:
            Dict containing paginated memories with metadata:
            {
                "items": [...],     # List of memory objects
                "total": int,       # Total count across all pages
                "page": int,        # Current page number
                "size": int,        # Items per page
                "pages": int        # Total number of pages
            }
            
        Raises:
            requests.RequestException: For network/HTTP errors
            ValueError: For validation errors, user not found, or invalid parameters
            
        Example:
            >>> client = OpenMemoryClient()
            >>> result = client.list_memories("user123", page=1, size=20)
            >>> print(f"Found {result['total']} memories")
            >>> for memory in result['items']:
            ...     print(f"Memory: {memory['content'][:50]}...")
        """
        endpoint = f"{self.base_url}/api/v1/memories"
        
        # Build query parameters
        params = {
            "user_id": user_id,
            "page": page,
            "size": size
        }
        
        # Add optional filters
        if app_id is not None:
            params["app_id"] = str(app_id)
        if search_query is not None:
            params["search_query"] = search_query
        if categories is not None:
            if isinstance(categories, list):
                params["categories"] = ",".join(categories)
            else:
                params["categories"] = categories
        if from_date is not None:
            params["from_date"] = from_date
        if to_date is not None:
            params["to_date"] = to_date
        if sort_column is not None:
            params["sort_column"] = sort_column
        if sort_direction is not None:
            params["sort_direction"] = sort_direction
        
        # Build complete URL with query parameters
        query_string = urlencode(params)
        full_url = f"{endpoint}?{query_string}"
        
        # Log request details for traceability
        request_timestamp = datetime.now(UTC).isoformat()
        logger.info(
            f"OpenMemory API Request - Timestamp: {request_timestamp}, "
            f"Module: openmemory_client, "
            f"Endpoint: GET {full_url}, "
            f"Parameters: {json.dumps(params, default=str)}"
        )
        
        try:
            # Make the HTTP request
            response = self.session.get(
                endpoint,
                params=params,
                timeout=self.timeout
            )
            
            # Log response details
            response_timestamp = datetime.now(UTC).isoformat()
            logger.info(
                f"OpenMemory API Response - Timestamp: {response_timestamp}, "
                f"Status: {response.status_code}, "
                f"Headers: {dict(response.headers)}"
            )
            
            # Handle different response scenarios
            if response.status_code == 200:
                # Success case
                response_data = response.json()
                logger.info(
                    f"Memories retrieved successfully - "
                    f"User: {user_id}, "
                    f"Total: {response_data.get('total', 0)}, "
                    f"Page: {response_data.get('page', page)}, "
                    f"Items returned: {len(response_data.get('items', []))}"
                )
                return response_data
                
            elif response.status_code == 404:
                # User not found
                error_detail = response.json().get('detail', 'User not found')
                logger.error(f"User not found error - user_id: {user_id}, detail: {error_detail}")
                raise ValueError(f"User not found: {error_detail}")
                
            elif response.status_code == 400:
                # Bad request - invalid parameters
                error_detail = response.json().get('detail', 'Invalid parameters')
                logger.error(
                    f"Invalid parameters error - "
                    f"user_id: {user_id}, "
                    f"params: {params}, "
                    f"detail: {error_detail}"
                )
                raise ValueError(f"Invalid parameters: {error_detail}")
                
            elif response.status_code == 422:
                # Validation error
                error_details = response.json().get('detail', [])
                logger.error(f"Validation error - details: {error_details}")
                raise ValueError(f"Validation error: {error_details}")
                
            else:
                # Other HTTP errors
                logger.error(
                    f"Unexpected HTTP error - "
                    f"Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                response.raise_for_status()
                
        except requests.RequestException as e:
            # Network/connection errors
            logger.error(
                f"Network error during memory listing - "
                f"user_id: {user_id}, "
                f"endpoint: {endpoint}, "
                f"params: {params}, "
                f"error: {str(e)}"
            )
            raise
            
        except json.JSONDecodeError as e:
            # Invalid JSON response
            logger.error(
                f"Invalid JSON response - "
                f"endpoint: {endpoint}, "
                f"status: {response.status_code}, "
                f"error: {str(e)}"
            )
            raise ValueError(f"Invalid JSON response: {str(e)}")
            
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"Unexpected error during memory listing - "
                f"user_id: {user_id}, "
                f"error: {str(e)}, "
                f"type: {type(e).__name__}"
            )
            raise

    def get_memory(self, memory_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific memory by its unique ID via GET /api/v1/memories/{memory_id} endpoint.
        
        Args:
            memory_id: UUID string of the memory to retrieve (required)
            
        Returns:
            Dict containing the memory object with all fields
            
        Raises:
            ValueError: For invalid UUID format, memory not found, or validation errors
            requests.RequestException: For network/HTTP errors
            
        Example:
            >>> client = OpenMemoryClient()
            >>> memory = client.get_memory("550e8400-e29b-41d4-a716-446655440000")
            >>> print(memory['content'])  # Memory text content
        """
        # Validate memory_id parameter
        if not memory_id or not isinstance(memory_id, str):
            raise ValueError("memory_id must be a non-empty string")
        
        # Basic UUID format validation (36 characters with dashes)
        if len(memory_id) != 36 or memory_id.count('-') != 4:
            raise ValueError("memory_id must be a valid UUID format")
        
        # Additional UUID format validation (check positions of dashes)
        expected_dash_positions = [8, 13, 18, 23]
        actual_dash_positions = [i for i, char in enumerate(memory_id) if char == '-']
        if actual_dash_positions != expected_dash_positions:
            raise ValueError("memory_id must be a valid UUID format")
        
        # Check if all non-dash characters are valid hexadecimal
        hex_parts = memory_id.split('-')
        for part in hex_parts:
            try:
                int(part, 16)  # This will raise ValueError if not valid hex
            except ValueError:
                raise ValueError("memory_id must be a valid UUID format")
        
        endpoint = f"{self.base_url}/api/v1/memories/{memory_id}"
        
        # Log request details for traceability
        request_timestamp = datetime.now(UTC).isoformat()
        logger.info(
            f"OpenMemory API Request - Timestamp: {request_timestamp}, "
            f"Module: openmemory_client, "
            f"Endpoint: GET {endpoint}, "
            f"Memory ID: {memory_id}"
        )
        
        try:
            # Make the HTTP request
            response = self.session.get(
                endpoint,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            
            # Log response details
            response_timestamp = datetime.now(UTC).isoformat()
            logger.info(
                f"OpenMemory API Response - Timestamp: {response_timestamp}, "
                f"Status: {response.status_code}, "
                f"Memory ID: {memory_id}, "
                f"Headers: {dict(response.headers)}"
            )
            
            # Handle different response scenarios
            if response.status_code == 200:
                # Success case
                memory_data = response.json()
                content_length = len(memory_data.get('content', ''))
                logger.info(
                    f"Memory retrieved successfully - "
                    f"ID: {memory_data.get('id')}, "
                    f"State: {memory_data.get('state')}, "
                    f"App: {memory_data.get('app_name')}, "
                    f"Content length: {content_length}"
                )
                return memory_data
                
            elif response.status_code == 404:
                # Memory not found
                error_detail = response.json().get('detail', 'Memory not found')
                logger.error(f"Memory not found error - memory_id: {memory_id}, detail: {error_detail}")
                raise ValueError(f"Memory not found: {error_detail}")
                
            elif response.status_code == 422:
                # Validation error (invalid UUID format)
                error_details = response.json().get('detail', [])
                logger.error(f"UUID validation error - memory_id: {memory_id}, details: {error_details}")
                raise ValueError(f"Invalid memory ID format: {error_details}")
                
            else:
                # Other HTTP errors
                logger.error(
                    f"Unexpected HTTP error - "
                    f"Memory ID: {memory_id}, "
                    f"Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                response.raise_for_status()
                
        except requests.RequestException as e:
            # Network/connection errors
            logger.error(
                f"Network error during memory retrieval - "
                f"memory_id: {memory_id}, "
                f"endpoint: {endpoint}, "
                f"error: {str(e)}"
            )
            raise
            
        except json.JSONDecodeError as e:
            # Invalid JSON response
            logger.error(
                f"Invalid JSON response - "
                f"endpoint: {endpoint}, "
                f"memory_id: {memory_id}, "
                f"status: {response.status_code}, "
                f"error: {str(e)}"
            )
            raise ValueError(f"Invalid JSON response: {str(e)}")
            
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"Unexpected error during memory retrieval - "
                f"memory_id: {memory_id}, "
                f"error: {str(e)}, "
                f"type: {type(e).__name__}"
            )
            raise

    def update_memory(
        self, 
        memory_id: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing memory via PUT /api/v1/memories/{memory_id} endpoint.
        
        Args:
            memory_id: UUID string of the memory to update (required)
            content: New memory content text to replace existing content (required)
            metadata: Additional metadata to associate with memory (optional)
            
        Returns:
            Dict containing the updated memory object with all fields
            
        Raises:
            ValueError: For invalid UUID format, memory not found, empty content, or validation errors
            requests.RequestException: For network/HTTP errors
            
        Example:
            >>> client = OpenMemoryClient()
            >>> updated_memory = client.update_memory(
            ...     "550e8400-e29b-41d4-a716-446655440000",
            ...     "Updated memory content",
            ...     {"category": "updated", "priority": "high"}
            ... )
            >>> print(updated_memory['content'])  # Updated content
        """
        # Validate memory_id parameter
        if not memory_id or not isinstance(memory_id, str):
            raise ValueError("memory_id must be a non-empty string")
        
        # Basic UUID format validation (36 characters with dashes)
        if len(memory_id) != 36 or memory_id.count('-') != 4:
            raise ValueError("memory_id must be a valid UUID format")
        
        # Additional UUID format validation (check positions of dashes)
        expected_dash_positions = [8, 13, 18, 23]
        actual_dash_positions = [i for i, char in enumerate(memory_id) if char == '-']
        if actual_dash_positions != expected_dash_positions:
            raise ValueError("memory_id must be a valid UUID format")
        
        # Check if all non-dash characters are valid hexadecimal
        hex_parts = memory_id.split('-')
        for part in hex_parts:
            try:
                int(part, 16)  # This will raise ValueError if not valid hex
            except ValueError:
                raise ValueError("memory_id must be a valid UUID format")
        
        # Validate content parameter
        if not content or not isinstance(content, str):
            raise ValueError("content must be a non-empty string")
        
        # Check for empty content after trimming whitespace
        if not content.strip():
            raise ValueError("content must not be empty or whitespace-only")
        
        # Prepare request payload
        payload = {
            "content": content.strip(),
            "metadata": metadata or {}
        }
        
        endpoint = f"{self.base_url}/api/v1/memories/{memory_id}"
        
        # Log request details for traceability
        request_timestamp = datetime.now(UTC).isoformat()
        logger.info(
            f"OpenMemory API Request - Timestamp: {request_timestamp}, "
            f"Module: openmemory_client, "
            f"Endpoint: PUT {endpoint}, "
            f"Memory ID: {memory_id}, "
            f"Content length: {len(content)}, "
            f"Metadata keys: {list(metadata.keys()) if metadata else []}"
        )
        
        try:
            # Make the HTTP request
            response = self.session.put(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            
            # Log response details
            response_timestamp = datetime.now(UTC).isoformat()
            logger.info(
                f"OpenMemory API Response - Timestamp: {response_timestamp}, "
                f"Status: {response.status_code}, "
                f"Memory ID: {memory_id}, "
                f"Headers: {dict(response.headers)}"
            )
            
            # Handle different response scenarios
            if response.status_code == 200:
                # Success case
                memory_data = response.json()
                updated_content_length = len(memory_data.get('content', ''))
                logger.info(
                    f"Memory updated successfully - "
                    f"ID: {memory_data.get('id')}, "
                    f"State: {memory_data.get('state')}, "
                    f"App: {memory_data.get('app_name')}, "
                    f"Updated content length: {updated_content_length}, "
                    f"Updated at: {memory_data.get('updated_at')}"
                )
                return memory_data
                
            elif response.status_code == 404:
                # Memory not found
                error_detail = response.json().get('detail', 'Memory not found')
                logger.error(f"Memory not found error - memory_id: {memory_id}, detail: {error_detail}")
                raise ValueError(f"Memory not found: {error_detail}")
                
            elif response.status_code == 422:
                # Validation error (invalid UUID format, content validation, etc.)
                error_details = response.json().get('detail', [])
                logger.error(f"Validation error - memory_id: {memory_id}, details: {error_details}")
                raise ValueError(f"Validation error: {error_details}")
                
            elif response.status_code == 400:
                # Bad request (malformed JSON, invalid structure)
                error_detail = response.json().get('detail', 'Invalid request format')
                logger.error(f"Bad request error - memory_id: {memory_id}, detail: {error_detail}")
                raise ValueError(f"Bad request: {error_detail}")
                
            else:
                # Other HTTP errors
                logger.error(
                    f"Unexpected HTTP error - "
                    f"Memory ID: {memory_id}, "
                    f"Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                response.raise_for_status()
                
        except requests.RequestException as e:
            # Network/connection errors
            logger.error(
                f"Network error during memory update - "
                f"memory_id: {memory_id}, "
                f"endpoint: {endpoint}, "
                f"error: {str(e)}"
            )
            raise
            
        except json.JSONDecodeError as e:
            # Invalid JSON response
            logger.error(
                f"Invalid JSON response - "
                f"endpoint: {endpoint}, "
                f"memory_id: {memory_id}, "
                f"status: {response.status_code}, "
                f"error: {str(e)}"
            )
            raise ValueError(f"Invalid JSON response: {str(e)}")
            
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"Unexpected error during memory update - "
                f"memory_id: {memory_id}, "
                f"error: {str(e)}, "
                f"type: {type(e).__name__}"
            )
            raise

    def filter_memories(self, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter memories via POST /api/v1/memories/filter endpoint with complex filtering.
        
        Accepts complex filter objects for searching memories by multiple fields, logical 
        operators, ranges, metadata, and other advanced criteria.
        
        Args:
            filter_data: Complex filter object containing search criteria
                Required fields:
                - user_id (str): User identifier for security filtering
                Optional fields:
                - conditions (List[Dict]): Array of filter conditions with field, operator, value
                - date_range (Dict): from/to timestamps for date filtering  
                - categories (List[str]): Category names to filter by
                - metadata_filters (Dict): Key-value pairs for metadata filtering
                - content_search (Dict): Text search configuration (query, fuzzy, case_sensitive)
                - sort (Dict): Sorting configuration (field, direction)
                - pagination (Dict): Page and size settings
                
        Returns:
            Dict containing:
            - memories: List of matching memory objects
            - pagination: Pagination information (total, page, size, pages)
            - filter_summary: Execution metadata (conditions_applied, execution_time_ms, query_complexity)
            
        Raises:
            requests.RequestException: For network/HTTP errors
            ValueError: For validation errors or malformed responses
            
        Example:
            >>> client = OpenMemoryClient()
            >>> filter_obj = {
            ...     "user_id": "user123",
            ...     "conditions": [
            ...         {"field": "content", "operator": "like", "value": "meeting"},
            ...         {"field": "categories", "operator": "in", "value": ["work", "planning"]}
            ...     ],
            ...     "pagination": {"page": 1, "size": 20}
            ... }
            >>> result = client.filter_memories(filter_obj)
            >>> print(f"Found {result['pagination']['total']} memories")
        """
        endpoint = f"{self.base_url}/api/v1/memories/filter"
        
        # Client-side validation
        if not isinstance(filter_data, dict):
            raise ValueError("filter_data must be a dictionary")
            
        if "user_id" not in filter_data:
            raise ValueError("filter_data must contain 'user_id' field")
            
        if not filter_data["user_id"]:
            raise ValueError("user_id cannot be empty")
        
        # Log request details for traceability
        request_timestamp = datetime.now(UTC).isoformat()
        logger.info(
            f"OpenMemory Filter API Request - Timestamp: {request_timestamp}, "
            f"Module: openmemory_client, "
            f"Endpoint: POST {endpoint}, "
            f"User: {filter_data.get('user_id')}, "
            f"Filter conditions: {len(filter_data.get('conditions', []))}, "
            f"Payload size: {len(json.dumps(filter_data, default=str))} bytes"
        )
        
        try:
            # Make the HTTP request
            response = self.session.post(
                endpoint,
                json=filter_data,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            
            # Log response details
            response_timestamp = datetime.now(UTC).isoformat()
            logger.info(
                f"OpenMemory Filter API Response - Timestamp: {response_timestamp}, "
                f"Status: {response.status_code}, "
                f"Headers: {dict(response.headers)}"
            )
            
            # Handle different response scenarios
            if response.status_code == 200:
                # Success case
                result_data = response.json()
                
                # Extract summary information for logging
                memories_count = len(result_data.get('memories', []))
                total_count = result_data.get('pagination', {}).get('total', 0)
                execution_time = result_data.get('filter_summary', {}).get('execution_time_ms', 0)
                query_complexity = result_data.get('filter_summary', {}).get('query_complexity', 'unknown')
                
                logger.info(
                    f"Filter request successful - "
                    f"User: {filter_data.get('user_id')}, "
                    f"Results returned: {memories_count}, "
                    f"Total matches: {total_count}, "
                    f"Execution time: {execution_time}ms, "
                    f"Query complexity: {query_complexity}"
                )
                
                return result_data
                
            elif response.status_code == 400:
                # Bad request - invalid filter structure
                error_detail = response.json().get('detail', 'Invalid filter request')
                logger.error(
                    f"Bad filter request - "
                    f"user_id: {filter_data.get('user_id')}, "
                    f"detail: {error_detail}"
                )
                raise ValueError(f"Invalid filter request: {error_detail}")
                
            elif response.status_code == 422:
                # Validation error
                error_details = response.json().get('detail', [])
                logger.error(
                    f"Filter validation error - "
                    f"user_id: {filter_data.get('user_id')}, "
                    f"details: {error_details}"
                )
                raise ValueError(f"Filter validation error: {error_details}")
                
            elif response.status_code == 429:
                # Rate limiting
                error_detail = response.json().get('detail', 'Rate limit exceeded')
                logger.error(
                    f"Filter rate limit exceeded - "
                    f"user_id: {filter_data.get('user_id')}, "
                    f"detail: {error_detail}"
                )
                raise ValueError(f"Rate limit exceeded: {error_detail}")
                
            elif response.status_code == 500:
                # Server error
                error_detail = response.json().get('detail', 'Internal server error')
                logger.error(
                    f"Server error during filter request - "
                    f"user_id: {filter_data.get('user_id')}, "
                    f"detail: {error_detail}"
                )
                raise ValueError(f"Server error: {error_detail}")
                
            else:
                # Other HTTP errors
                logger.error(
                    f"Unexpected HTTP error during filter request - "
                    f"Status: {response.status_code}, "
                    f"Response: {response.text}"
                )
                response.raise_for_status()
                
        except requests.RequestException as e:
            # Network/connection errors
            logger.error(
                f"Network error during filter request - "
                f"user_id: {filter_data.get('user_id')}, "
                f"endpoint: {endpoint}, "
                f"error: {str(e)}"
            )
            raise
            
        except json.JSONDecodeError as e:
            # Invalid JSON response
            logger.error(
                f"Invalid JSON response from filter endpoint - "
                f"endpoint: {endpoint}, "
                f"user_id: {filter_data.get('user_id')}, "
                f"status: {response.status_code}, "
                f"error: {str(e)}"
            )
            raise ValueError(f"Invalid JSON response: {str(e)}")
            
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"Unexpected error during filter request - "
                f"user_id: {filter_data.get('user_id')}, "
                f"error: {str(e)}, "
                f"type: {type(e).__name__}"
            )
            raise

    def _make_request(self, method: str, endpoint: str, json_data: dict = None) -> dict:
        """
        Make a custom HTTP request to the OpenMemory API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path, with or without leading slash
            json_data: Optional JSON payload for the request
            
        Returns:
            Dict containing the API response
            
        Raises:
            requests.RequestException: For network/HTTP errors
            ValueError: For validation errors or malformed responses
        """
        # Normalize endpoint to remove leading slash if present
        if endpoint.startswith('/'):
            endpoint = endpoint[1:]
        
        # Construct full URL
        url = f"{self.base_url}/{endpoint}"
        
        # Log request details for traceability
        request_timestamp = datetime.now(UTC).isoformat()
        logger.info(
            f"OpenMemory API Request - Timestamp: {request_timestamp}, "
            f"Module: openmemory_client, "
            f"Endpoint: {method} {url}, "
            f"Payload: {json.dumps(json_data, default=str) if json_data else 'None'}"
        )
        
        try:
            # Make the HTTP request
            response = self.session.request(
                method=method,
                url=url,
                json=json_data,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            
            # Log response details
            response_timestamp = datetime.now(UTC).isoformat()
            logger.info(
                f"OpenMemory API Response - Timestamp: {response_timestamp}, "
                f"Status: {response.status_code}, "
                f"Headers: {dict(response.headers)}"
            )
            
            # Handle response
            if response.status_code < 200 or response.status_code >= 300:
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', 'Unknown error')
                    logger.error(f"API error: {error_detail}")
                    raise ValueError(f"API error: {error_detail}")
                except json.JSONDecodeError:
                    logger.error(f"API error: {response.text}")
                    raise ValueError(f"API error: {response.status_code} {response.reason}")
            
            # Return response data
            try:
                return response.json()
            except json.JSONDecodeError:
                if response.status_code == 204:  # No Content
                    return {"success": True}
                return {"text": response.text}
                
        except requests.RequestException as e:
            # Network or timeout errors
            logger.error(f"Request error: {str(e)}")
            raise


def create_memory_simple(user_id: str, text: str, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """
    Simple convenience function for creating a memory.
    
    Args:
        user_id: User identifier
        text: Memory content
        base_url: OpenMemory API base URL
        
    Returns:
        Created memory object
        
    Example:
        >>> memory = create_memory_simple("heti-user", "Important task completed")
    """
    client = OpenMemoryClient(base_url)
    return client.create_memory(user_id, text)


def list_memories_simple(user_id: str, base_url: str = "http://localhost:8000", **kwargs) -> Dict[str, Any]:
    """
    Simple convenience function for listing memories.
    
    Args:
        user_id: User identifier
        base_url: OpenMemory API base URL
        **kwargs: Additional parameters for filtering/pagination (app_id, search_query, categories, etc.)
        
    Returns:
        Paginated memories response with items, total, page, size, and pages
        
    Example:
        >>> memories = list_memories_simple("heti-user", search_query="meeting", page=1, size=5)
        >>> print(f"Found {memories['total']} memories")
    """
    client = OpenMemoryClient(base_url)
    return client.list_memories(user_id, **kwargs)


def get_memory_simple(memory_id: str, base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """
    Simple convenience function for retrieving a specific memory by ID.
    
    Args:
        memory_id: UUID string of the memory to retrieve
        base_url: OpenMemory API base URL
        
    Returns:
        Memory object with all fields
        
    Example:
        >>> memory = get_memory_simple("550e8400-e29b-41d4-a716-446655440000")
        >>> print(memory['content'])
    """
    client = OpenMemoryClient(base_url)
    return client.get_memory(memory_id)


def update_memory_simple(
    memory_id: str, 
    content: str, 
    metadata: Optional[Dict[str, Any]] = None, 
    base_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """
    Simple convenience function for updating a specific memory by ID.
    
    Args:
        memory_id: UUID string of the memory to update
        content: New memory content text to replace existing content
        metadata: Additional metadata to associate with memory (optional)
        base_url: OpenMemory API base URL
        
    Returns:
        Updated memory object with all fields
        
    Example:
        >>> updated_memory = update_memory_simple(
        ...     "550e8400-e29b-41d4-a716-446655440000",
        ...     "Updated content from simple function",
        ...     {"category": "updated"}
        ... )
        >>> print(updated_memory['content'])
    """
    client = OpenMemoryClient(base_url)
    return client.update_memory(memory_id, content, metadata)


def filter_memories_simple(
    filter_data: Dict[str, Any], 
    base_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """
    Simple convenience function for filtering memories with complex criteria.
    
    Args:
        filter_data: Complex filter object containing search criteria
        base_url: OpenMemory API base URL
        
    Returns:
        Filter results with memories, pagination, and filter_summary
        
    Example:
        >>> filter_obj = {
        ...     "user_id": "heti-user",
        ...     "conditions": [
        ...         {"field": "content", "operator": "like", "value": "meeting"}
        ...     ],
        ...     "pagination": {"page": 1, "size": 20}
        ... }
        >>> result = filter_memories_simple(filter_obj)
        >>> print(f"Found {result['pagination']['total']} memories")
    """
    client = OpenMemoryClient(base_url)
    return client.filter_memories(filter_data)


if __name__ == "__main__":
    # Example usage for testing
    logging.basicConfig(level=logging.INFO)
    
    client = OpenMemoryClient()
    try:
        # Example 1: Create a memory
        result = client.create_memory(
            user_id="test-user",
            text="Test memory creation from Python client"
        )
        print(f"Created memory: {result}")
        
        # Example 2: List memories with basic pagination
        memories = client.list_memories(
            user_id="test-user",
            page=1,
            size=10
        )
        print(f"Found {memories['total']} memories on page {memories['page']}")
        
        # Example 3: List memories with filtering
        filtered_memories = client.list_memories(
            user_id="test-user",
            search_query="test",
            sort_column="created_at",
            sort_direction="desc"
        )
        print(f"Found {filtered_memories['total']} memories matching 'test'")
        
        # Example 4: Retrieve a specific memory by ID (if available)
        if memories['total'] > 0 and len(memories['items']) > 0:
            memory_id = memories['items'][0]['id']
            specific_memory = client.get_memory(memory_id)
            print(f"Retrieved specific memory: {specific_memory['id']} - '{specific_memory['content'][:50]}...'")
            
            # Example 5: Update the memory we just retrieved
            updated_memory = client.update_memory(
                memory_id=memory_id,
                content="Updated content from example script",
                metadata={"updated_by": "example_script", "version": "2.0"}
            )
            print(f"Updated memory: {updated_memory['id']} - Updated at: {updated_memory.get('updated_at')}")
        
    except Exception as e:
        print(f"Error: {e}") 