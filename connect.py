from opcua import Client
import time
from contextlib import contextmanager

from error_logger import log_error_to_file

# OPC UA server endpoint for the Mettler Toldeo IR Flow cell. 
SERVER_URL = "opc.tcp://localhost:62552/iCOpcUaServer"

@contextmanager
def try_connect(server_url=SERVER_URL, max_retries=3, delay=2, error_log_path=None):

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
                message = f"Attempt {attempt} failed to connect to {server_url}"
                print(f"{message}: {e}")
                if error_log_path:
                    log_error_to_file(error_log_path, message, e)

                if attempt < max_retries:
                    time.sleep(delay)   # wait before next attempt
                else:
                    print("All connection attempts failed.")
                    yield None
    finally:
        if connected:
            try:
                client.disconnect()
                print("Disconnected from OPC UA server.")
            except Exception as e:
                if error_log_path:
                    log_error_to_file(error_log_path, "Error during OPC UA disconnection", e)


