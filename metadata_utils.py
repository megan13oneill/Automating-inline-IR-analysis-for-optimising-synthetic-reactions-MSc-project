# querying the nodes on the IR to get the metadata of the reaction. 
from opcua import ua
from opcua.ua.uaerrors import UaStatusCodeError

from error_logger import log_error_to_file

def get_probe1_data (client, probe1_node_id):
    """ queries selected child nodes of Probe1 node and returns 
        their nodes and values.
    """
    # allowed_nodes = {
    #     "Probe Name", "Probe Description", "Probe Status", "Document Name",
    #     "Experiment Name", "Suffix", "User Name", "Project Name", "Sample Count",
    #     "Current Sampling Interval", "Last Sample Time", "Last Sample Raw Spectra",
    #     "Last Sample Background Spectra", "Last Sample Treated Spectra"
    # }

    probe1_results = []

    try:
        probe_node = client.get_node(probe1_node_id)
        child_nodes = probe_node.get_children()

        for child in child_nodes:
            try: 
                browse_name = child.get_browse_name().Name
                value_of_node = child.get_value()
                if isinstance(value_of_node, (list,tuple)) and len(value_of_node) > 10:
                    display_value = f"[{len(value_of_node)} values]"
                else:
                    display_value = value_of_node
                
                probe1_results.append((browse_name, value_of_node))

            except UaStatusCodeError as e:
                if e.status == ua.StatusCodes.BadAttributeIdInvalid:
                    log_error_to_file(
                        context_message=f"Child node '{child}' does not support attribute 'Value'. Skipped. (BadAttributeIdInvalid)",
                        exception=e
                    )
                else:
                    log_error_to_file(context_message=f"UaStatusCodeError when reading child node'{child}'",
                    exception=e
                    )
            except Exception as e:
                log_error_to_file(
                    context_message=f"Unexpected error while reading child node '{child}'",
                    exception=e
                )
    except Exception as e:
        log_error_to_file(
            context_message=f"Failed to read Probe 1 node '{probe1_node_id}'",
            exception=e
        )

    return probe1_results


    

        