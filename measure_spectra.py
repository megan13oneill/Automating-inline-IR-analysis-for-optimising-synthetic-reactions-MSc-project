import csv
import time
import os
from datetime import datetime
from opcua.ua.uaerrors import UaStatusCodeError

def continuous_raw_spectrum_logger (client, probe_status_id, raw_spectrum_id, sampling_interval_id=None, output_dir="logs", default_delay=1.0):
    
    """ Continuously logs raw spectrum data while the probe is running. """

    os.makedirs(output_dir, exist_ok=True)
    timestamp_str = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    csv_filename = os.path.join(output_dir, f"raw_spectrum_{timestamp_str}.csv")

    print("Waiting for probe to start ...")

    try: 

        while True: 
            status = client.get_node(probe_status_id).get_value()
            if status.lower() == "running":
                print(" Probe is now running. Beginning data capture ...")
                break
            time.sleep(1)

        delay_seconds = default_delay
        if sampling_interval_id:
            try:
                interval_ms = client.get_node(sampling_interval_id).get_value()
                delay_seconds = interval_ms / 1000.0
                print(f"Using sampling intervaal: {delay_seconds:.2f} seconds")

            except Exception:
                print("Could not read sampling interval. Using default delay.")

        with open()
