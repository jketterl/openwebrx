from . import Controller
from owrx.websocket import WebSocketConnection
from owrx.connection import WebSocketMessageHandler


class WebSocketController(Controller):
    def indexAction(self):
        conn = WebSocketConnection(self.handler, WebSocketMessageHandler())
        # enter read loop
        conn.handle()
