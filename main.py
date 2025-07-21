from connect import try_connect
from metadata_utils import get_probe1_data
from spectrum_logger import raw_spectrum_logger
from processing_utils import process_and_store_data
from db_utils import create_new_document

PROBE_1_NODE_ID = "ns=2;s=Local.iCIR.Probe1"
db_path = "ReactIR.db"

def main():
    with try_connect() as client:
        if not client: 
            print("Failed to connect to OPC UA server.")
            return
        
        # Get probe metadata once connected
        probe_data = get_probe1_data(client, PROBE_1_NODE_ID)
        print("\nProbe 1 Metadata:")
        for name, value in probe_data:
            print(f"{name}: {value}")

        document_id = create_new_document(db_path, description="Real-time logging session")
        document_ids = {"DocumentID": document_id}

        # Start logging raw spectrum data
        raw_spectrum_logger(
            client,
            probe_status_id="ns=2;s=Local.iCIR.Probe1.ProbeStatus",
            raw_spectrum_id="ns=2;s=Local.iCIR.Probe1.SpectraRaw",
            sampling_interval_id="ns=2;s=Local.iCIR.Probe1.CurrentSamplingInterval",
            output_dir="logs",
            db_path="ReactIR.db",
            document_ids=document_ids,
            probe1_node_id=PROBE_1_NODE_ID
        )

        # Process and store the logged data
        processed_count = process_and_store_data(
            input_dir="logs",
            output_dir="processed",
            smooth=True,
            window_length=11,
            polyorder=2
        )
        print(f"Successfully processed {processed_count} spectrum files.")

if __name__ == "__main__":
    main()
