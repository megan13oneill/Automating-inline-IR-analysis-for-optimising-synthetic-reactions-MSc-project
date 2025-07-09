from opcua import Client
import time

SERVER_URL = "opc.tcp://localhost:62552/iCOpcUaServer"

def try_connect(server_url, max_retries=3, delay=2):
    client = Client(server_url)
    
    for attempt in range(1, max_retries + 1):
        try:
            client.connect()
            print(f"Connected to OPC UA server at {server_url} (Attempt {attempt})")
            return client
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(delay)
            else:
                print("All connection attempts failed.")
    return None

# Connect to the server
client = try_connect(SERVER_URL)
