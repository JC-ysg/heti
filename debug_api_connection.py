import requests
import time
import sys
import socket
import datetime

# Configuration
API_BASE_URL = "http://localhost:8765"
API_CHECK_ENDPOINT = "/api/v1/memories?limit=1&user_id=heti-user"
MAX_RETRIES = 10
RETRY_DELAY = 5  # seconds

def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def check_port_open(host, port):
    """Check if the specified port is open on the host."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

def check_api_connection():
    """Check the API connection with detailed diagnostics."""
    url = f"{API_BASE_URL}{API_CHECK_ENDPOINT}"
    
    log_message(f"Checking API connection at: {url}")
    
    # First check if the port is open
    port_open = check_port_open("localhost", 8765)
    if not port_open:
        log_message("Port 8765 is not open. The OpenMemory API server is not running or not listening on this port.")
        return False
    
    log_message("Port 8765 is open. Attempting API request...")
    
    try:
        response = requests.get(url, timeout=10)
        log_message(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            log_message("API connection successful!")
            try:
                # Try to parse the response as JSON
                data = response.json()
                log_message(f"Response contains {len(data.get('memories', []))} memories")
            except Exception as e:
                log_message(f"Warning: Could not parse response as JSON: {str(e)}")
            return True
        else:
            log_message(f"API returned non-200 status code: {response.status_code}")
            log_message(f"Response content: {response.text[:500]}")
            return False
    except requests.exceptions.ConnectionError as e:
        log_message(f"Connection error: {str(e)}")
        return False
    except requests.exceptions.Timeout as e:
        log_message(f"Connection timeout: {str(e)}")
        return False
    except Exception as e:
        log_message(f"Unexpected error: {str(e)}")
        return False

def main():
    log_message("Starting API connection diagnostics")
    
    # Try multiple times with a delay
    for attempt in range(1, MAX_RETRIES + 1):
        log_message(f"Connection attempt {attempt} of {MAX_RETRIES}...")
        
        if check_api_connection():
            log_message("✅ Connection successful!")
            return 0
        
        if attempt < MAX_RETRIES:
            log_message(f"Connection failed. Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
    
    log_message("❌ All connection attempts failed.")
    return 1

if __name__ == "__main__":
    sys.exit(main()) 