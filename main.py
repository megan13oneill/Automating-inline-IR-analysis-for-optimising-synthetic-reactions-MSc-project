import argparse
from datetime import datetime
import os
import sqlite3
import pandas as pd

from connect import try_connect
from metadata_utils import get_probe1_data
from spectrum_logger import raw_spectrum_logger
from processing_utils import process_and_store_data
from db_utils import create_new_document, start_trend_sampling, create_new_trend, end_trend
from error_logger import log_error_to_file

PROBE_1_NODE_ID = "ns=2;s=Local.iCIR.Probe1"
db_path = "ReactIR.db"

def main():
    parser = argparse.ArgumentParser(description='Infrared Spectrum Logger CLI')
    parser.add_argument('--log', action='store_true', help="Log raw spectra from OPC UA")
    parser.add_argument('--process', action='store_true', help="Process and plot spectra")
    parser.add_argument('--no-db', action='store_true', help="Skip database insert")
    parser.add_argument('--output-dir', type=str, default='logs', help="Directory for spectra")
    args = parser.parse_args()

    # New CLI args for dynamic OPC UA nodes
    parser.add_argument('--treated-node', type=str, help="Node ID for treated temperature")
    parser.add_argument('--peak-node', action='append', help="Peak node(s) in format 'NodeID:Label'")

    args = parser.parse_args()

    db_insert_enabled = not args.no_db
    timestamp = datetime.now().strftime("%d-%m-%Y_%H:%M:%S")
    error_log_path = os.path.join("logs", f"error_log_{timestamp}.txt")

    try:
        with try_connect() as client:
            if not client: 
                print("Failed to connect to OPC UA server.")
                return
        
        try:
            # Get probe metadata once connected
            probe_data = get_probe1_data(client, PROBE_1_NODE_ID)
            print("\nProbe 1 Metadata:")
            for name, value in probe_data:
                print(f"{name}: {value}")

            document_id = create_new_document(db_path, description="CLI logging session")
            document_ids = {"DocumentID": document_id}
        
        except Exception as e:
            log_error_to_file(error_log_path, "Failed during probe metadata retrieval or document creation", e)
            return


        if args.log:
            try:
                # Start logging raw spectrum data
                raw_spectrum_logger(
                    client,
                    probe_status_id="ns=2;s=Local.iCIR.Probe1.ProbeStatus",
                    raw_spectrum_id="ns=2;s=Local.iCIR.Probe1.SpectraRaw",
                    sampling_interval_id="ns=2;s=Local.iCIR.Probe1.CurrentSamplingInterval",
                    output_dir=args.output_dir,
                    db_path=db_path,
                    document_ids=document_ids,
                    probe1_node_id=PROBE_1_NODE_ID,
                    error_log_path=error_log_path
                )
            except Exception as e:
                log_error_to_file(error_log_path, "Error during raw spectrum logging", e)

        if args.trend:
            try:
                if not args.treated_node or not args.peak_node:
                    print(f"--treated_node and at least one --peak-node are required for --trend")
                    return
                
                treated_node = client.get_node(args.treated_node)

                peak_nodes = []
                for item in args.peak_node:
                    try:
                        node_id, label = item.split(":", 1)
                        peak_nodes.append((client.get_node(node_id.strip()), label.strip()))
                    except ValueError:
                        log_error_to_file(error_log_path, f"Invalid --peak-node format: {item}")
                        return
                    
                trend_id = create_new_trend(db_path, document_id, user_note="Started from CLI")
                if trend_id == -1:
                    print("Failed to create new trend.")
                    return
                
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

            except Exception as e:
                log_error_to_file(error_log_path, "Error during trend sampling", e)

        if args.process:
            try:
                # Process and store the logged data
                processed_count = process_and_store_data(
                    input_dir=args.output_dir,
                    output_dir="processed",
                    smooth=True,
                    window_length=11,
                    polyorder=2
                )
                print(f"Successfully processed {processed_count} spectrum files.")
            except Exception as e:
                log_error_to_file(error_log_path, "Unhandled exception in main()", e)

    except  Exception as e:
        log_error_to_file(error_log_path, "Unhandled exception in main()", e)

def load_and_preview_db(file_path, num_rows=5):
    conn = sqlite3.connect(db_path)
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

