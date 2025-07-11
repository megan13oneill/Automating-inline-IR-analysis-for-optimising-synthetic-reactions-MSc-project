from connect import try_connect
from acquire_metadata import AcquiredMetadata
from nodes_config import nodes_config

# if __name__ == "__main__":
#     client = try_connect()
#     if client is None:
#         print("Exiting due to connection failure.")
#         exit(1)

#     extractor = AcquiredMetadata(client, nodes_config)
#     metadata = extractor.extract_all()

#     print("\n📋 Experiment Metadata:")
#     for key, value in metadata.items():
#         print(f"{key}: {value}")

#     client.disconnect()

from connect import try_connect
from acquire_metadata import get_probe1_data

PROBE_1_NODE_ID = "ns=2;s=Local.iCIR.Probe1"

if __name__ == "__main__":
    client = try_connect()
    if not client:
        exit(1)

    probe_data = get_probe1_data(client, PROBE_1_NODE_ID)

    print("\n Probe 1 Metadata:")
    for name, value in probe_data:
        print(f"{name}: {value}")

    client.disconnect()
