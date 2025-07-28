from opcua import Client
import time
from contextlib import contextmanager

# OPC UA server endpoint for the Mettler Toldeo IR Flow cell. 
SERVER_URL = "opc.tcp://localhost:62552/iCOpcUaServer"

@contextmanager
def try_connect(server_url=SERVER_URL, max_retries=3, delay=2):

    """ Will attempt to connect to the OPC UA server. Will either return connected if successful 
        or will say connection has failed. 
    """

    client = Client(server_url)
    connected = False 
    try:
        for attempt in range(1, max_retries + 1):
            try:
                client.connect()
                connected = True
                print(f"Connected to OPC UA server at {server_url} (Attempt {attempt})")
                yield client
                break
            except Exception as e:
                print(f"Attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    time.sleep(delay)   # wait before next attempt
                else:
                    print("All connection attempts failed.")
                    yield None
            else:
                yield None
    finally:
        if connected:
            try:
                client.disconnect()
                print("Disconnected from OPC UA server.")
            except Exception:
                pass
    


