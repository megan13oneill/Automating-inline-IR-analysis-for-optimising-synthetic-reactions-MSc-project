import os
import time
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
db_path = "ReactIR.db"
logs_dir = "logs"

def main():
    timestamp = datetime.now().strftime("%d-%m-%Y_%H:%M:%S")
    os.makedirs("logs", exist_ok=True)
    fallback_log_path = os.path.join("logs", "error_log_fallback.txt")

    try:
        with try_connect(error_log_path=fallback_log_path) as client:
            if not client: 
                print("Failed to connect to OPC UA server.")
                return
            
            print(f"Waiting for experiment to fully initialise...")
            time.sleep(10) # Delay to allow cloned experiment to populate nodes.
        
            # Get probe metadata once connected
            probe_data = get_probe1_data(client, PROBE_1_NODE_ID)
            print("\nProbe 1 Metadata:")
            for name, value in probe_data:
                print(f"{name}: {value}")

            # create document entry in DB.
            document_id = create_new_document(db_path, description="Automated logging session")
            document_ids = {"DocumentID": document_id}
            # set error_log_path with doc IDs
            error_log_path = os.path.join("logs", f"error_log_{timestamp}.txt")

            # get treated node
            treated_node = client.get_node(TREND_NODE_ID)
            peak_nodes = []

            for child in treated_node.get_children():
                try:
                    peak_value_node = child.get_child("2:PeakValue")
                    label_node = child.get_child("2:Name")
                    label = label_node.get_value()
                    peak_nodes.append((peak_value_node, label))
                    print(f"Found peak: {label}")
                except Exception as e:
                    log_error_to_file(error_log_path, f"Error reading trend child node {child}", e)

            if not peak_nodes:
                print("No peak nodes found. Exiting.")
                return
            
            trend_id = create_new_trend(db_path, document_id, user_note="Automated trend collection")
            if trend_id == -1:
                print("Failed to create new trend entry.")
                return

            print("Starting trend sampling...")
            start_trend_sampling(
                db_path=db_path,
                trend_id=trend_id,
                probe_node=client.get_node(PROBE_1_NODE_ID),
                treated_node=treated_node,
                probe_description="Probe 1",
                peak_nodes=peak_nodes,
                interval_sec=2,
                batch_size=10
            )

    except KeyboardInterrupt:
        print("Logging intrrupted by user (Ctrl+C).")
    except Exception as e: 
        log_error_to_file(fallback_log_path, "Unhandled exception in main()", e)


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

