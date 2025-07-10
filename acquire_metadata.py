# querying the nodes on the IR to get the metadata of the reaction. 
from opcua import Client
from opcua.ua.uaerrors import UaStatusCodeError

# class AcquiredMetadata:
#     def __init__(self, opcua_client, initial_config=None):
#         """ Initialises the AcquiredMetadata. """
#         self.opcua_client = opcua_client
#         self.initial_config = initial_config or {}  # start with given config or empty dictionary.

def get_probe1_data (client, probe1_node_id):
    """ queries all child nodes of Probe1 node and returns 
        their nodes and values.
    """
    
    probe1_results = []

    try:
        probe_node = client.get_node(probe1_node_id)
        child_nodes = probe_node.get_children()

        for child in child_nodes:
            try: 
                browse_name = child.get_browse_name().Name
                value_of_node = child.get_value()
                probe1_results.append((browse_name, value_of_node))
            except UaStatusCodeError as e:
                print(f"Error reading child node: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

    except Exception as e:
        print(f"Failed to read Probe 1 node: {e}")

    return probe1_results


    

        