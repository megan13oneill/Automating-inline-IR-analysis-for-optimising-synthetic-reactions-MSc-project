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
from error_logger import log_error_to_file

PROBE_1_NODE_ID = "ns=2;s=Local.iCIR.Probe1"
TREND_NODE_ID = "ns=2;s=Local.iCIR.Probe1.Trends"
RAW_SPECTRUM_ID = "ns=2;s=Local.iCIR.Probe1.SpectraRaw"
PROBE_STATUS_ID = "ns=2;s=Local.iCIR.Probe1.ProbeStatus"
SAMPLING_INTERVAL_ID = "ns=2;s=Local.iCIR.Probe1.CurrentSamplingInterval"


db_path = "ReactIR.db"
logs_dir = "logs"
output_dir = "logs"

def main():
    timestamp = datetime.now().strftime("%d-%m-%Y_%H:%M:%S")
    os.makedirs("logs", exist_ok=True)
    fallback_log_path = os.path.join("logs", "error_log_fallback.txt")
    error_log_path = os.path.join("logs", f"error_log_{timestamp}.txt")

    try: 
        client = try_connect(error_log_path=fallback_log_path)
        if not client: 
            print("Failed to connect to OPC UA server.")
            return
                
        print(f"Waiting for experiment to fully initialise...")
        
        # wait for probe1 and child nodes to be fully initialised.
        max_attempts = 3
        delay_sec = 30
        trends_ready= False
        treated_node = client.get_node(TREND_NODE_ID)

        for attempt in range (1, max_attempts + 1):
            print(f"Waiting for Trend nodes to initialise... (Attempt {attempt}/{max_attempts})")
            time.sleep(delay_sec)
            try:
                children = treated_node.get_children()
                if children:
                    print(f"Trends node has {len(children)} children. Assuming node is ready.")
                    trends_ready = True
                    break 
                else:
                    print(f"Trend node found but has no children yet.")
            except Exception as e:
                print(f"Error checking Trend node: {e}")

        if not trends_ready:
            print(f"Trend node did not initialise after retries. Exiting.")
            return

        # Get probe metadata once connected
        probe_data = get_probe1_data(client, PROBE_1_NODE_ID)
        print("\nProbe 1 Metadata:")
        for name, value in probe_data:
            print(f"{name}: {value}")

        print("\nAll metadata keys:")
        print([name for name, _ in probe_data])

        experiment_name = next((value for name, value in probe_data if name == "Experiment Name"), "Unknown_Experiment")

        # create document entry in DB.
        document_id = create_new_document(
            db_path,
            name=experiment_name,
            experiment_id=None)
        
        document_ids = {"DocumentID": document_id}

        peak_nodes = []
        children = treated_node.get_children()
        print(f"Found {len(children)} children in Probe1.Trends")

        for child in children:
            try: 
                # debug print children of child node
                label = child.get_display_name().Text
                grandchildren = child.get_children()
                found_treated_value = False

                for grandchild in grandchildren:
                    if grandchild.nodeid.Identifier.endswith(".TreatedValue"):
                        peak_nodes.append((grandchild, label))
                        print(f"✓ Found peak: {label}")
                        found_treated_value = True
                        break

                if not found_treated_value:
                    print(f"✗ Skipped {label} — no .TreatedValue node found.")

            except Exception as e:
                print(f"⚠️ Error reading node {child}: {e}")
                try:
                    log_error_to_file(error_log_path, f"Error reading trend child node {child}", e)
                except Exception as log_e:
                    print(f"Failed to log error: {log_e}")

        if not peak_nodes:
            print("No valid peak nodes found. Exiting.")
            return

        trend_id = create_new_trend(db_path, document_id, user_note="Automated trend collection")
        if trend_id == -1:
            print("Failed to create new trend entry.")
            return

        stop_event = threading.Event()

        def run_raw_logger():
            try:
                raw_spectrum_logger(
                    client=client,
                    probe_status_id=PROBE_STATUS_ID,
                    raw_spectrum_id=RAW_SPECTRUM_ID,
                    sampling_interval_id=SAMPLING_INTERVAL_ID,
                    output_dir=output_dir,
                    db_path=db_path,
                    document_ids=document_ids,
                    probe1_node_id=PROBE_1_NODE_ID,
                    error_log_path=error_log_path,
                    stop_event=stop_event
                )
            except Exception as e:
                try:
                    log_error_to_file(error_log_path, "Error in raw_spectrum_logger thread", e)
                except Exception as log_e:
                    print(f"Failed to log error in raw_logger thread: {log_e}")
        
        def run_trend_sampler():
            try:
            
                print("Starting trend sampling...")
                start_trend_sampling(
                    db_path=db_path,
                    trend_id=trend_id,
                    probe_node=client.get_node(PROBE_1_NODE_ID),
                    treated_node=treated_node,
                    probe_description="Probe 1",
                    peak_nodes=peak_nodes,
                    interval_sec=2,
                    batch_size=1,
                    stop_event=stop_event
                )
            except Exception as e: 
                try:
                    log_error_to_file(error_log_path, "Error in trend sampling thread", e)
                except Exception as log_e:
                    print(f"Failed to log error in trend sampler thread: {log_e}")

        raw_thread = threading.Thread(target=run_raw_logger, daemon=True)
        trend_thread = threading.Thread(target=run_trend_sampler, daemon=True)

        raw_thread.start()
        trend_thread.start()

        print("Monitoring probe status...")
        probe_status_node = client.get_node(PROBE_STATUS_ID)
        while True:
            try:
                status = probe_status_node.get_value()
                print(f"Probe running: {status}")
                if not status:
                    print("Probe stopped. Waiting 10s to flush final data...")
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
                    print(f"Failed to log error reading probe status: {log_e}")
                break

        print("Processing raw spectrum files...")
        processed_count = process_and_store_data(
            input_dir=logs_dir,
            output_dir="processed",
            smooth=True,
            window_length=11,
            polyorder=2
        )
        print(f"Processed {processed_count} spectrum files.")

    except KeyboardInterrupt:
        print("Logging intrrupted by user (Ctrl+C).")
    except Exception as e: 
        try:
            log_error_to_file(fallback_log_path, "Unhandled exception in main()", e)
        except Exception as log_e:
            print(f"Failed to log unhandled exception: {log_e}")
    finally:
        try:
            client.disconnect()
            print("Disconnected from OPC UA server.")
        except Exception as e:
            try:
                log_error_to_file(error_log_path, "Error during disconnection", e)
            except Exception as log_e:
                print(f"Failed to log error during disconnection: {log_e}")


def load_and_preview_db(file_path=db_path, num_rows=5):
    conn = sqlite3.connect(file_path)
    cursor = conn.cursor()

    # get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables: 
        print("No tables found in the database.")
        return
    
    for table_name in tables: 
        print(f"\n--- Table: {table_name} ---")

        # load db into a df 
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

        # print the headers
        print("Header:")
        print(df.columns.to_list())

        # print last N rows 
        print(f"\nLast {num_rows} rows:")
        print(df.tail(num_rows))

        print("-" * 40)

    conn.close()


if __name__ == "__main__":
    main()
    #db_path = 'ReactIR.db'
    #load_and_preview_db(db_path)
