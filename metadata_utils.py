# querying the nodes on the IR to get the metadata of the reaction. 
from opcua import ua
import traceback
from opcua.ua.uaerrors import UaStatusCodeError
from opcua.ua import uaerrors

from error_logger import log_error_to_file

def get_probe1_data (client, probe1_node_id):
    """ queries selected child nodes of Probe1 node and returns 
        their nodes and values.
    """

    probe1_results = []

    try:
        probe_node = client.get_node(probe1_node_id)
        child_nodes = probe_node.get_children()

        for child in child_nodes:
            try: 
                display_name = child.get_display_name().Text
                value_of_node = child.get_value()

                display_value = value_of_node
                
                probe1_results.append((display_name, display_value))

            except uaerrors.BadAttributeIdInvalid as e:
                log_error_to_file(
                    context_message=f"Child node '{child}' does not support attribute 'Value'. Skipped. (BadAttributeIdInvalid)",
                    exception=e
                )
            except UaStatusCodeError as e:
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
            exception=e,
            trace=traceback.format_exc()
        )

    return probe1_results
