import os
import time
import traceback
import pandas as pd
from datetime import datetime
from opcua.ua.uaerrors import UaStatusCodeError
import numpy as np

from db_utils import insert_probe_sample_and_spectrum
from metadata_utils import get_probe1_data
from common_utils import get_current_timestamp_str, write_spectrum_csv
from error_logger import log_error_to_file


def raw_spectrum_logger(
    client,
    probe_status_id,
    raw_spectrum_id,
    sampling_interval_id=None,
    output_dir="logs",
    wavenumber_start=4000,
    wavenumber_end=650,
    db_path=None,
    document_ids=None,
    probe1_node_id=None,
    error_log_path=None,
    stop_event=None,
    default_delay = 5.0
):
    """ Continuously logs raw spectrum data while the probe is running at each sampling interval. """

    os.makedirs(output_dir, exist_ok=True)
    print("Waiting for probe to start ...")

    spectrum_counter = 0

    try:
        # Wait for the probe to be 'running'
        while True:
            if stop_event and stop_event.is_set():
                print("Stop event triggered before probe started. Exiting.")
                return
            try:
                probe_status = client.get_node(probe_status_id).get_value()
                if isinstance(probe_status, str) and probe_status.lower() == "running":
                    print("Probe is now running. Beginning data capture ...")
                    break
            except Exception as e:
                error_message = "Error reading probe status before start"
                print(f"{error_message}: {e}")
                if error_log_path:
                    log_error_to_file(error_log_path, error_message, e)
            time.sleep(1)

        delay_seconds = default_delay  # fallback

        if sampling_interval_id:
            try:
                interval_ms = client.get_node(sampling_interval_id).get_value()
                if interval_ms and isinstance(interval_ms, (int, float)) and interval_ms > 0:
                    delay_seconds = interval_ms
            except Exception as e:
                error_message = "Could not read sampling interval. Using default delay."
                print(error_message)
                if error_log_path:
                    log_error_to_file(error_log_path, error_message, e)

        # Read initial spectrum
        initial_spectrum = client.get_node(raw_spectrum_id).get_value()
        print(f"Initial spectrum (sample): {initial_spectrum[:5]}")  # DEBUG

        if not initial_spectrum:
            raise ValueError("Initial spectrum is empty. Cannot generate wavenumber axis.")

        num_points = len(initial_spectrum)
        print(f"Number of points in spectrum: {num_points}")  # DEBUG

        wavenumbers = np.linspace(wavenumber_start, wavenumber_end, num_points).round(2).tolist()
        print(f"Wavenumber axis (sample): {wavenumbers[:5]}")  # DEBUG

        print("Logging started. Press Ctrl+C to stop. \n")

        # 🔁 Main data logging loop
        while True:
            # ✅ Check for external stop
            if stop_event and stop_event.is_set():
                print("Stop event triggered. Exiting logging loop.")
                break

            try:
                probe_status = client.get_node(probe_status_id).get_value()
                if probe_status.lower() != "running":
                    print(f"Probe stopped. Final status: {probe_status}")
                    break

                spectrum = client.get_node(raw_spectrum_id).get_value()
                print(f"Read spectrum (sample): {spectrum[:5]}")  # DEBUG

                timestamp_str = get_current_timestamp_str()

                run_dir = output_dir
                spectrum_filename = f"raw_spectrum_{timestamp_str}.csv"
                raw_csv = os.path.join(run_dir, spectrum_filename)

                print(f"Attempting to write spectrum to: {os.path.abspath(raw_csv)}")  # DEBUG
                write_spectrum_csv(wavenumbers, spectrum, raw_csv)
                print(f"Spectrum CSV written successfully.")  # DEBUG

                metadata = {}
                if probe1_node_id:
                    metadata = dict(get_probe1_data(client, probe1_node_id))
                    print(f"Probe metadata keys: {list(metadata.keys())}")  # DEBUG

                    if "Last Sample Treated Spectra" in metadata:
                        treated_filename = f"treated_spectrum_{timestamp_str}.csv"
                        treated_csv = os.path.join(run_dir, treated_filename)
                        print(f"Writing treated spectrum to: {os.path.abspath(treated_csv)}")  # DEBUG
                        write_spectrum_csv(wavenumbers, metadata["Last Sample Treated Spectra"], treated_csv)

                if db_path and document_ids and probe1_node_id:
                    print("Inserting data into DB...")  # DEBUG
                    insert_probe_sample_and_spectrum(
                        db_path=db_path,
                        document_id=document_ids["DocumentID"],
                        metadata_dict=metadata,
                        spectrum_csv_path=raw_csv
                    )
                elif any([db_path, document_ids, probe1_node_id]):
                    print("Skipping DB insert - incomplete DB parameters.")  # DEBUG

                spectrum_counter += 1
                print(f"Spectrum logged to {raw_csv} at {datetime.now().strftime('%H-%M-%S')}")

            except UaStatusCodeError as e:
                error_message = "OPC UA error while reading spectrum"
                print(f"{error_message}: {e}")
                if error_log_path:
                    log_error_to_file(error_log_path, error_message, e)

            except Exception as e:
                error_message = "Unexpected error during logging loop"
                print(f"{error_message}: {e}")
                if error_log_path:
                    log_error_to_file(error_log_path, error_message, e)

            print(f"Sleeping for {delay_seconds} seconds...")
            time.sleep(delay_seconds)

    except Exception as e:
        error_message = "Critical error during raw spectrum logging"
        print(f"{error_message}: {e}")
        if error_log_path:
            log_error_to_file(error_log_path, error_message, e)

    print(f"\nLogging complete. {spectrum_counter} spectra saved in '{output_dir}'.")
