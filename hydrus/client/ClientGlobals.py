import typing

if typing.TYPE_CHECKING:
    
    from hydrus.client import ClientController
    

client_controller: "ClientController.Controller" = None

NO_QT_MULTIMEDIA = False

# the Client API's port, and whether other computers can connect to it, from the command line. they win over its settings, just for this session
CLIENT_API_PORT_COMMAND_LINE: int | None = None
CLIENT_API_ALLOW_NON_LOCAL_CONNECTIONS_COMMAND_LINE = False
