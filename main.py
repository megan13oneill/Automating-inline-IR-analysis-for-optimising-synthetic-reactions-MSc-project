from connect import try_connect
from metadata_extractor import MetadataExtractor
from nodes_config import nodes_config

if __name__ == "__main__":
    client = try_connect()
    if client is None:
        print("Exiting due to connection failure.")
        exit(1)

    extractor = MetadataExtractor(client, nodes_config)
    metadata = extractor.extract_all()

    print("\n📋 Experiment Metadata:")
    for key, value in metadata.items():
        print(f"{key}: {value}")

    client.disconnect()
