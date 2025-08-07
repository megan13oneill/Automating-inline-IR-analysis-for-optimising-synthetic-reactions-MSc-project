import os
import re
import time
import threading
import sqlite3
import pandas as pd
from datetime import datetime

from connect import try_connect
from metadata_utils import get_probe1_data
from spectrum_logger import raw_spectrum_logger
from processing_utils import process_and_store_data
from db_utils import create_new_document, start_trend_sampling, create_new_trend, end_trend
from error_logger import set_error_log_path, get_error_log_path, log_error_to_file

PROBE_1_NODE_ID = "ns=2;s=Local.iCIR.Probe1"
TREND_NODE_ID = "ns=2;s=Local.iCIR.Probe1.Trends"
RAW_SPECTRUM_ID = "ns=2;s=Local.iCIR.Probe1.SpectraRaw"
PROBE_STATUS_ID = "ns=2;s=Local.iCIR.Probe1.ProbeStatus"
SAMPLING_INTERVAL_ID = "ns=2;s=Local.iCIR.Probe1.CurrentSamplingInterval"

db_path = "ReactIR.db"
logs_dir = "logs"
output_dir = "logs"

# ---- Logging helpers ----

def log(msg, level="info"):
    icons = {
        "info": "[ℹ️]",
        "success": "[✅]",
        "warning": "[⚠️]",
        "error": "[❌]"
    }
    icon = icons.get(level, "[ℹ️]")
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{timestamp} {icon} {msg}")

def print_metadata(metadata):
    longest_key = max(len(k) for k, _ in metadata) if metadata else 0
    for k, v in metadata:
        print(f"  {k:<{longest_key}} : {v}")

def print_section_header(title):
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def main():
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    default_log_folder = os.path.join("logs", "startup")
    os.makedirs(default_log_folder, exist_ok=True)
    error_log_path = os.path.join(default_log_folder, f"error_log_{timestamp}.txt")

    set_error_log_path(error_log_path)
    log(f"The initial Error log file for this experiment is: {error_log_path}")

    try:
        client = try_connect(error_log_path=error_log_path)
        if not client:
            log("Failed to connect to OPC UA server.", level="error")
            return

        log("Waiting for experiment to fully initialise...")

        # wait for probe1 and child nodes to be fully initialised.
        max_attempts = 3
        delay_sec = 30
        trends_ready = False
        treated_node = client.get_node(TREND_NODE_ID)

        for attempt in range(1, max_attempts + 1):
            log(f"Waiting for Trend nodes to initialise... (Attempt {attempt}/{max_attempts})")
            time.sleep(delay_sec)
            try:
                children = treated_node.get_children()
                if children:
                    log(f"Trends node has {len(children)} children. Assuming node is ready.", level="success")
                    trends_ready = True
                    break
                else:
                    log(f"Trend node found but has no children yet.", level="warning")
            except Exception as e:
                log(f"Error checking Trend node: {e}", level="error")

        if not trends_ready:
            log(f"Trend node did not initialise after retries. Exiting.", level="error")
            return

        # Get probe metadata once connected
        probe_data = get_probe1_data(client, PROBE_1_NODE_ID)
        print_section_header("Probe 1 Metadata")
        print_metadata(probe_data)

        log("All metadata keys:")
        log([name for name, _ in probe_data])

        experiment_name = next((value for name, value in probe_data if name == "Experiment Name"), "Unknown_Experiment")

        # create log folder for the error logger.
        log_folder = os.path.join("logs", experiment_name)
        os.makedirs(log_folder, exist_ok=True)

        error_log_path = os.path.join(log_folder, f"error_log_{timestamp}.txt")
        set_error_log_path(error_log_path)
        log(f"Updated Error log file for this experiment: {error_log_path}")

        # Create folders for raw spectra and processed data
        spectrum_folder = os.path.join(log_folder, "spectra")
        os.makedirs(spectrum_folder, exist_ok=True)

        run_folder = os.path.join(spectrum_folder, f"spectrum_run_{timestamp}")
        os.makedirs(run_folder, exist_ok=True)

        processed_folder = os.path.join(log_folder, "processed", f"spectrum_run_{timestamp}")
        os.makedirs(processed_folder, exist_ok=True)

        # create document entry in DB.
        document_id = create_new_document(
            db_path,
            name=experiment_name,
            experiment_id=None,
            error_log_path=get_error_log_path())

        document_ids = {"DocumentID": document_id}
        peak_nodes = []
        children = treated_node.get_children()
        log(f"Found {len(children)} children in Probe1.Trends")

        for child in children:
            try:
                try:
                    label = child.get_display_name().Text
                except Exception as name_e:
                    label = str(child.nodeid.Identifier)
                    log(f"Could not get display name for child node {child}: {name_e}", level="warning")
                    log_error_to_file(error_log_path, f"Could not get name for child node", name_e)

                found_treated_value = False
                try:
                    grandchildren = child.get_children()
                except Exception as child_e:
                    log(f"Could not get children of node {label}: {child_e}", level="warning")
                    log_error_to_file(error_log_path, f"Could not get children of node {label}", child_e)
                    continue

                for grandchild in grandchildren:
                    try:
                        node_id_str = str(grandchild.nodeid.Identifier)
                        if node_id_str.endswith(".TreatedValue"):
                            peak_nodes.append((grandchild, label))
                            log(f"Found peak: {label}", level="success")
                            found_treated_value = True
                            break
                    except Exception as grandchild_e:
                        log(f"Error checking grandchild of {label}: {grandchild_e}", level="error")
                        log_error_to_file(error_log_path, f"Error checking grandchild of {label}")

                if not found_treated_value:
                    log(f"Skipped {label} — no .TreatedValue node found.", level="warning")

            except Exception as e:
                log(f"Unhandled error with trend child node: {e}", level="error")
                try:
                    log_error_to_file(error_log_path, f"Error reading trend child node {child}", e)
                except Exception as log_e:
                    log(f"Failed to log error: {log_e}", level="error")

        if not peak_nodes:
            log("No valid peak nodes found. Exiting.", level="error")
            return

        trend_id = create_new_trend(db_path, document_id, user_note="Automated trend collection")
        if trend_id == -1:
            log("Failed to create new trend entry.", level="error")
            return

        stop_event = threading.Event()

        def run_raw_logger():
            try:
                raw_spectrum_logger(
                    client=client,
                    probe_status_id=PROBE_STATUS_ID,
                    raw_spectrum_id=RAW_SPECTRUM_ID,
                    sampling_interval_id=SAMPLING_INTERVAL_ID,
                    output_dir=run_folder,
                    db_path=db_path,
                    document_ids=document_ids,
                    probe1_node_id=PROBE_1_NODE_ID,
                    error_log_path=error_log_path,
                    stop_event=stop_event,
                    default_delay=5.0
                )
            except Exception as e:
                try:
                    log_error_to_file(error_log_path, "Error in raw_spectrum_logger thread", e)
                except Exception as log_e:
                    log(f"Failed to log error in raw_logger thread: {log_e}", level="error")

        def run_trend_sampler():
            try:
                log("Starting trend sampling...")
                start_trend_sampling(
                    db_path=db_path,
                    trend_id=trend_id,
                    probe_node=client.get_node(PROBE_1_NODE_ID),
                    treated_node=treated_node,
                    probe_description="Probe 1",
                    peak_nodes=peak_nodes,
                    interval_sec=2,
                    batch_size=1,
                )
            except Exception as e:
                try:
                    log_error_to_file(error_log_path, "Error in trend sampling thread", e)
                except Exception as log_e:
                    log(f"Failed to log error in trend sampler thread: {log_e}", level="error")

        raw_thread = threading.Thread(target=run_raw_logger, daemon=True)
        trend_thread = threading.Thread(target=run_trend_sampler, daemon=True)

        raw_thread.start()
        trend_thread.start()

        log("Monitoring probe status...")
        probe_status_node = client.get_node(PROBE_STATUS_ID)
        while True:
            try:
                status = probe_status_node.get_value()
                log(f"Probe running: {status}")
                if not status:
                    log("Probe stopped. Waiting 10s to flush final data...")
                    time.sleep(10)
                    stop_event.set()
                    raw_thread.join()
                    trend_thread.join()
                    break
                time.sleep(5)
            except Exception as e:
                try:
                    log_error_to_file(error_log_path, "Error reading probe status", e)
                except Exception as log_e:
                    log(f"Failed to log error reading probe status: {log_e}", level="error")
                break

        log("Processing raw spectrum files...")
        processed_count = process_and_store_data(
            input_dir=run_folder,
            output_dir=processed_folder,
            smooth=True,
            window_length=11,
            polyorder=2
        )
        log(f"Processed {processed_count} spectrum files.", level="success")

    except KeyboardInterrupt:
        log("Logging interrupted by user (Ctrl+C).", level="warning")
        try:
            log_error_to_file(error_log_path, "User interrupted logging (Ctrl+C)")
        except Exception as log_e:
            log(f"Failed to log KeyboardInterrupt: {log_e}", level="error")
    except Exception as e:
        try:
            log_error_to_file(error_log_path, "Unhandled exception in main()", e)
        except Exception as log_e:
            log(f"Failed to log unhandled exception: {log_e}", level="error")
    finally:
        try:
            client.disconnect()
            log("Disconnected from OPC UA server.", level="info")
        except Exception as e:
            try:
                log_error_to_file(error_log_path, "Error during disconnection", e)
            except Exception as log_e:
                log(f"Failed to log error during disconnection: {log_e}", level="error")


def load_and_preview_db(file_path=db_path, num_rows=5):
    conn = sqlite3.connect(file_path)
    cursor = conn.cursor()

    # get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        log("No tables found in the database.", level="warning")
        return

    for table_name in tables:
        log(f"--- Table: {table_name} ---")
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        log("Header:")
        log(df.columns.to_list())
        log(f"Last {num_rows} rows:")
        print(df.tail(num_rows))
        log("-" * 40)

    conn.close()


if __name__ == "__main__":
    main()
    # db_path = 'ReactIR.db'
    # load_and_preview_db(db_path)
