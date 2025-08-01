# querying the nodes on the IR to get the metadata of the reaction. 
from opcua import Client
from opcua.ua.uaerrors import UaStatusCodeError

def get_probe1_data (client, probe1_node_id):
    """ queries selected child nodes of Probe1 node and returns 
        their nodes and values.
    """
    allowed_nodes = {
        "Probe Name", "Probe Description", "Probe Status", "Document Name",
        "Experiment Name", "Suffix", "User Name", "Project Name", "Sample Count",
        "Current Sampling Interval", "Last Sample Time", "Last Sample Raw Spectra",
        "Last Sample Background Spectra", "Last Sample Treated Spectra"
    }

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


    

        