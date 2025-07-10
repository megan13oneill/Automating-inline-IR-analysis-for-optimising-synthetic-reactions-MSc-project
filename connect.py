from opcua import Client
import time

# OPC UA server endpoint for the Mettler Toldeo IR Flow cell. 
SERVER_URL = "opc.tcp://localhost:62552/iCOpcUaServer"

def try_connect(server_url=SERVER_URL, max_retries=3, delay=2):

    """ Will attempt to connect to the OPC UA server. Will either return connected if successful 
        or will say connection has failed. 
    """

    client = Client(server_url)
    for attempt in range(1, max_retries + 1):
        try:
            client.connect()
            print(f"Connected to OPC UA server at {server_url} (Attempt {attempt})")
            return client
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(delay)   # wait before next attempt
            else:
                print("All connection attempts failed.")
    return None

