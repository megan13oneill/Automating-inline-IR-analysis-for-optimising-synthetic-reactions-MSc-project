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

def main():
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    default_log_folder = os.path.join("logs", "startup")
    os.makedirs(default_log_folder, exist_ok=True)
    error_log_path = os.path.join(default_log_folder, f"error_log_{timestamp}.txt")

    set_error_log_path(error_log_path)
    print(f"\n📁 Initial Error log file: {error_log_path}")

    try:
        client = try_connect(error_log_path=error_log_path)
        if not client:
            print("❌ Failed to connect to OPC UA server.")
            return

        print("\n⏳ Waiting for experiment to fully initialise...")

        max_attempts = 3
        delay_sec = 30
        trends_ready = False
        treated_node = client.get_node(TREND_NODE_ID)

        for attempt in range(1, max_attempts + 1):
            print(f"🔄 Attempt {attempt}/{max_attempts}: Checking Trend node...")
            time.sleep(delay_sec)
            try:
                children = treated_node.get_children()
                if children:
                    print(f"✅ Trends node ready with {len(children)} children.")
                    trends_ready = True
                    break
                else:
                    print("⚠️ Trend node found but has no children yet.")
            except Exception as e:
                print(f"❌ Error checking Trend node: {e}")

        if not trends_ready:
            print("❌ Trend node did not initialise after retries. Exiting.")
            return

        probe_data = get_probe1_data(client, PROBE_1_NODE_ID)
        print("\n📱 Probe 1 Metadata")
        print("-" * 50)
        for name, value in probe_data:
            if isinstance(value, (list, tuple)) and len(value) > 10:
                display_value = f"{value[:5]} ... {value[-5:]} (len={len(value)})"
            elif isinstance(value, str) and len(value) > 100:
                display_value = f"{value[:100]}... (len={len(value)})"
            else:
                display_value = value
            print(f"{name:<30}: {display_value}")
        print("-" * 50)

        experiment_name = next((value for name, value in probe_data if name == "Experiment Name"), "Unknown_Experiment")

        log_folder = os.path.join("logs", experiment_name)
        os.makedirs(log_folder, exist_ok=True)

        error_log_path = os.path.join(log_folder, f"error_log_{timestamp}.txt")
        set_error_log_path(error_log_path)
        print(f"\n📝 Updated Error log path: {error_log_path}")

        spectrum_folder = os.path.join(log_folder, "spectra")
        os.makedirs(spectrum_folder, exist_ok=True)

        run_folder = os.path.join(spectrum_folder, f"spectrum_run_{timestamp}")
        os.makedirs(run_folder, exist_ok=True)

        processed_folder = os.path.join(log_folder, "processed", f"spectrum_run_{timestamp}")
        os.makedirs(processed_folder, exist_ok=True)

        document_id = create_new_document(
            db_path,
            name=experiment_name,
            experiment_id=None,
            error_log_path=get_error_log_path())

        document_ids = {"DocumentID": document_id}
        peak_nodes = []
        children = treated_node.get_children()
        print(f"\n📊 Found {len(children)} children in Probe1.Trends")

        found_peaks = []
        for child in children:
            try:
                label = child.get_display_name().Text
                grandchildren = child.get_children()
                for grandchild in grandchildren:
                    node_id_str = str(grandchild.nodeid.Identifier)
                    if node_id_str.endswith(".TreatedValue"):
                        peak_nodes.append((grandchild, label))
                        found_peaks.append(label)
                        break
            except Exception as e:
                log_error_to_file(error_log_path, f"Error with trend child node {child}", e)

        if not peak_nodes:
            print("❌ No valid peak nodes found. Exiting.")
            return

        print("\n📈 Peaks Detected:")
        for peak in found_peaks:
            print(f"• {peak}")

        trend_id = create_new_trend(db_path, document_id, user_note="Automated trend collection")
        if trend_id == -1:
            print("❌ Failed to create new trend entry.")
            return

        stop_event = threading.Event()

        def run_raw_logger():
            try:
                sample_number = 0

                def callback(data):
                    nonlocal sample_number
                    sample_number += 1
                    timestamp = data.get("timestamp")
                    treated = data.get("treated_spectrum", [])[:5]
                    raw_csv = data.get("raw_csv_path", "<not saved>")
                    treated_csv = data.get("treated_csv_path", "<not saved>")
                    doc_id = data.get("document_id", "?")

                    print(f"\n📝 Logged spectrum #{sample_number} at {timestamp}")
                    print(f"• Saved raw     : {raw_csv}")
                    print(f"• Saved treated : {treated_csv}")
                    print(f"• DB Entry      : Inserted spectrum for DocumentID {doc_id}")
                    print(f"• Sample preview: {treated} ... (len={len(data.get('treated_spectrum', []))})")
                    print("-" * 50)

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
                    default_delay=5.0,
                   # callback=callback
                )
            except Exception as e:
                log_error_to_file(error_log_path, "Error in raw_spectrum_logger thread", e)

        def run_trend_sampler():
            try:
                print("\n🚀 Starting trend sampling...")
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
                log_error_to_file(error_log_path, "Error in trend sampling thread", e)

        raw_thread = threading.Thread(target=run_raw_logger, daemon=True)
        trend_thread = threading.Thread(target=run_trend_sampler, daemon=True)

        raw_thread.start()
        trend_thread.start()

        print("\n🔍 Monitoring probe status...")
        probe_status_node = client.get_node(PROBE_STATUS_ID)
        last_status = None

        while True:
            try:
                status = probe_status_node.get_value()
                if status != last_status:
                    print(f"\n🟢 Probe status changed: {'Running' if status else 'Stopped'}")
                    last_status = status
                if not status:
                    print("\n⏸️ Probe stopped. Waiting 10s to flush final data...")
                    time.sleep(10)
                    stop_event.set()
                    raw_thread.join()
                    trend_thread.join()
                    break
                time.sleep(5)
            except Exception as e:
                log_error_to_file(error_log_path, "Error reading probe status", e)
                break

        print("\n🧪 Processing raw spectrum files...")
        processed_count = process_and_store_data(
            input_dir=run_folder,
            output_dir=processed_folder,
            smooth=True,
            window_length=11,
            polyorder=2
        )
        print(f"\n✅ Processed {processed_count} spectrum files.")

    except KeyboardInterrupt:
        print("\n❗ Logging interrupted by user (Ctrl+C).")
        log_error_to_file(error_log_path, "User interrupted logging (Ctrl+C)")
    except Exception as e:
        log_error_to_file(error_log_path, "Unhandled exception in main()", e)
    finally:
        try:
            client.disconnect()
            print("\n🔌 Disconnected from OPC UA server.")
        except Exception as e:
            log_error_to_file(error_log_path, "Error during disconnection", e)


def load_and_preview_db(file_path=db_path, num_rows=5):
    conn = sqlite3.connect(file_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        print("No tables found in the database.")
        return

    for table_name in tables:
        print(f"\n--- Table: {table_name} ---")
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        print("Header:")
        print(df.columns.to_list())
        print(f"Last {num_rows} rows:")
        print(df.tail(num_rows))
        print("-" * 40)

    conn.close()


if __name__ == "__main__":
    main()
    # Uncomment to preview database
    # load_and_preview_db()
