# querying the nodes on the IR to get the metadata of the reaction. 

from opcua.ua.uaerrors import UaStatusCodeError

class AcquiredMetadata:
    def __init__(self, opcua_client, initial_config=None):
        """ Initialises the AcquiredMetadata. """
        self.opcua_client = opcua_client
        self.initial_config = initial_config or {}  # start with given config or empty dictionary.

        