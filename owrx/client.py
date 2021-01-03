from owrx.config import Config
import threading

import logging

logger = logging.getLogger(__name__)


class TooManyClientsException(Exception):
    pass


class ClientRegistry(object):
    sharedInstance = None
    creationLock = threading.Lock()
    log_client_connected = "disable"
    @staticmethod
    def getSharedInstance():
        with ClientRegistry.creationLock:
            if ClientRegistry.sharedInstance is None:
                ClientRegistry.sharedInstance = ClientRegistry()
        return ClientRegistry.sharedInstance

    def __init__(self):
        cfg_file = Config.get()
        self.log_client_connected = str(cfg_file["log_client_connected"])
        self.clients = []
        super().__init__()

    def broadcast(self):
        n = self.clientCount()
        if (self.log_client_connected == "enable"): 
            msg = "Total client connected " + str(n)
            logger.info(msg)
        for c in self.clients:
            c.write_clients(n)

    def addClient(self, client):
        pm = Config.get()
        if len(self.clients) >= pm["max_clients"]:
            raise TooManyClientsException()
        self.clients.append(client)
        self.broadcast()

    def clientCount(self):
        return len(self.clients)

    def removeClient(self, client):
        try:
            self.clients.remove(client)
        except ValueError:
            pass
        self.broadcast()
