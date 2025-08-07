import csv
import time
import os
from datetime import datetime
from opcua.ua.uaerrors import UaStatusCodeError
import numpy as np

from db_utils import insert_probe_sample_and_spectrum
from metadata_utils import get_probe1_data
from common_utils import get_current_timestamp_str, write_spectrum_csv
from error_logger import log_error_to_file


def raw_spectrum_logger (client,
                         probe_status_id,
                         raw_spectrum_id,
                         sampling_interval_id=None,
                         output_dir="logs",
                         default_delay=1.0,
                         wavenumber_start =4000,
                         wavenumber_end= 650,
                         db_path=None,
                         document_ids=None,
                         probe1_node_id=None,
                         error_log_path=None
):
    
    """ Continuously logs raw spectrum data while the probe is running at each sampling interval. """

    # make sure directory exists
    os.makedirs(output_dir, exist_ok=True)
    print("Waiting for probe to start ...")

    spectrum_counter = 0 

    try: 
        # wait for the probe status to be 'running' to start logging data.
        while True: 
            try:
                probe_status = client.get_node(probe_status_id).get_value()
                if isinstance(probe_status, str) and probe_status.lower() == "running":
                    print(" Probe is now running. Beginning data capture ...")
                    break
            except Exception as e:
                    error_message = "Error reading probe status before start"
                    print(f"{error_message}: {e}")
                    if error_log_path:
                        log_error_to_file(error_log_path, error_message, e)
            time.sleep(1)
        
        delay_seconds = default_delay
        # get the sampling interval if available.
        if sampling_interval_id:
            try:
                interval_ms = client.get_node(sampling_interval_id).get_value()
                delay_seconds = interval_ms / 1000.0
                print(f"Using sampling interval: {delay_seconds:.2f} seconds")
            except Exception as e:
                error_message = "Could not read sampling interval. Using default delay."
                print(f"{error_message}")
                if error_log_path:
                    log_error_to_file(error_log_path, error_message, e)

        # get one spectrum to determine its length
        initial_spectrum = client.get_node(raw_spectrum_id).get_value()
        num_points = len(initial_spectrum)
        # build descending wavenumber axis
        wavenumbers = np.linspace(wavenumber_start, wavenumber_end, num_points).round(2).tolist()

        if not initial_spectrum:
             raise ValueError ("Initial spectrum is empty. Cannot generate wavenumber axis.")

        print("Logging started. Press Ctrl+C to stop. \n")

        # loop data logger whilst probe is running. will stop when not running. 
        while True:
            try:
                probe_status = client.get_node(probe_status_id).get_value()
                if probe_status.lower() != "running":
                    print(f"Probe stopped. Final status: {probe_status}")
                    break
            
                # read the raw spectrum data.
                spectrum = client.get_node(raw_spectrum_id).get_value()
                timestamp_str = get_current_timestamp_str()
                
                run_dir = output_dir
                # os.makedirs(run_dir, exist_ok=True)
                spectrum_filename = f"raw_spectrum_{timestamp_str}.csv"
                raw_csv = os.path.join(run_dir, spectrum_filename)

                write_spectrum_csv(wavenumbers, spectrum, raw_csv)

                if probe1_node_id:
                    metadata = dict(get_probe1_data(client, probe1_node_id))

                    for label, data in metadata.items():
                        if label == "Last Sample Treated Spectra" in metadata:
                            treated_filename = f"treated_spectrum_{timestamp_str}.csv"
                            treated_csv = os.path.join(run_dir, treated_filename)
                            write_spectrum_csv(wavenumbers, metadata["Last Sample Treated Spectra"], treated_csv)
                
                if db_path and document_ids and probe1_node_id:
                        insert_probe_sample_and_spectrum(
                        db_path = db_path,
                        document_id = document_ids["DocumentID"],
                        metadata_dict = metadata,
                        spectrum_csv_path = raw_csv
                    )
                elif any([db_path, document_ids, probe1_node_id]):
                    print("Skipping DB insert - incomplete DB parameters.")

                spectrum_counter += 1
                print(f"Spectrum logged to {raw_csv} at {datetime.now().strftime('%H-%M-%S')}")

            except UaStatusCodeError as e:
                error_message = "OPC UA error while reading spectrum"
                print(f" {error_message}: {e}")
                if error_log_path:
                    log_error_to_file(error_log_path, error_message, e)

            except Exception as e:
                error_message = "Unexpected error during logging loop"
                print(f"{error_message}: {e}")
                if error_log_path:
                    log_error_to_file(error_log_path, error_message, e)

            time.sleep(delay_seconds)

    except Exception as e: 
        error_message = "Critical error during raw spectrum logging"
        print(f"{error_message}: {e}")
        if error_log_path:
                    log_error_to_file(error_log_path, error_message, e)

    print(f"\n Logging complete. {spectrum_counter} spectra saved in '{output_dir}'.")

