import base64
import hashlib
import json
from multiprocessing import Pipe
import select
import threading

import logging

logger = logging.getLogger(__name__)

OPCODE_TEXT_MESSAGE = 0x01
OPCODE_BINARY_MESSAGE = 0x02
OPCODE_CLOSE = 0x08
OPCODE_PING = 0x09
OPCODE_PONG = 0x0A


class WebSocketException(Exception):
    pass


class IncompleteRead(WebSocketException):
    pass


class Drained(WebSocketException):
    pass


class WebSocketClosed(WebSocketException):
    pass


class WebSocketConnection(object):
    connections = []

    @staticmethod
    def closeAll():
        for c in WebSocketConnection.connections:
            try:
                c.close()
            except:
                logger.exception("exception while shutting down websocket connections")

    def __init__(self, handler, messageHandler):
        self.handler = handler
        self.handler.connection.setblocking(0)
        self.setMessageHandler(messageHandler)
        (self.interruptPipeRecv, self.interruptPipeSend) = Pipe(duplex=False)
        self.open = True
        self.sendLock = threading.Lock()

        headers = {key.lower(): value for key, value in self.handler.headers.items()}
        if not "upgrade" in headers:
            raise WebSocketException("Upgrade header not found")
        if headers["upgrade"].lower() != "websocket":
            raise WebSocketException("Upgrade header does not contain expected value")
        if not "sec-websocket-key" in headers:
            raise WebSocketException("Websocket key not provided")

        ws_key = headers["sec-websocket-key"]
        shakey = hashlib.sha1()
        shakey.update("{ws_key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11".format(ws_key=ws_key).encode())
        ws_key_toreturn = base64.b64encode(shakey.digest())
        self.handler.wfile.write(
            "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {0}\r\nCQ-CQ-de: HA5KFU\r\n\r\n".format(
                ws_key_toreturn.decode()
            ).encode()
        )
        self.pingTimer = None
        self.resetPing()

    def setMessageHandler(self, messageHandler):
        self.messageHandler = messageHandler

    def get_header(self, size, opcode):
        ws_first_byte = 0b10000000 | (opcode & 0x0F)
        if size > 2 ** 16 - 1:
            # frame size can be increased up to 2^64 by setting the size to 127
            # anything beyond that would need to be segmented into frames. i don't really think we'll need more.
            return bytes(
                [
                    ws_first_byte,
                    127,
                    (size >> 56) & 0xFF,
                    (size >> 48) & 0xFF,
                    (size >> 40) & 0xFF,
                    (size >> 32) & 0xFF,
                    (size >> 24) & 0xFF,
                    (size >> 16) & 0xFF,
                    (size >> 8) & 0xFF,
                    size & 0xFF,
                ]
            )
        elif size > 125:
            # up to 2^16 can be sent using the extended payload size field by putting the size to 126
            return bytes([ws_first_byte, 126, (size >> 8) & 0xFF, size & 0xFF])
        else:
            # 125 bytes binary message in a single unmasked frame
            return bytes([ws_first_byte, size])

    def send(self, data):
        if not self.open:
            raise WebSocketClosed()
        # convenience
        if type(data) == dict:
            # allow_nan = False disallows NaN and Infinty to be encoded. Browser JSON will not parse them anyway.
            data = json.dumps(data, allow_nan=False)

        # string-type messages are sent as text frames
        if type(data) == str:
            header = self.get_header(len(data), OPCODE_TEXT_MESSAGE)
            data_to_send = header + data.encode("utf-8")
        # anything else as binary
        else:
            header = self.get_header(len(data), OPCODE_BINARY_MESSAGE)
            data_to_send = header + data

        self._sendBytes(data_to_send)

    def _sendBytes(self, data_to_send):
        def chunks(l, n):
            """Yield successive n-sized chunks from l."""
            for i in range(0, len(l), n):
                yield l[i : i + n]

        try:
            with self.sendLock:
                for chunk in chunks(data_to_send, 1024):
                    (_, write, _) = select.select([], [self.handler.wfile], [], 10)
                    if self.handler.wfile in write:
                        written = self.handler.wfile.write(chunk)
                        if written != len(chunk):
                            logger.error("incomplete write! closing socket!")
                            self.close()
                    else:
                        logger.debug("socket not returned from select; closing")
                        self.close()
        # these exception happen when the socket is closed
        except OSError:
            logger.exception("OSError while writing data")
            self.close()
        except ValueError:
            logger.exception("ValueError while writing data")
            self.close()

    def interrupt(self):
        self.interruptPipeSend.send(bytes(0x00))

    def handle(self):
        WebSocketConnection.connections.append(self)
        try:
            self.read_loop()
        finally:
            logger.debug("websocket loop ended; shutting down")

            self.messageHandler.handleClose()
            self.cancelPing()

            logger.debug("websocket loop ended; sending close frame")

            header = self.get_header(0, OPCODE_CLOSE)
            self._sendBytes(header)

            try:
                WebSocketConnection.connections.remove(self)
            except ValueError:
                pass

    def read_loop(self):
        def protected_read(num):
            data = self.handler.rfile.read(num)
            if data is None:
                raise Drained()
            if len(data) != num:
                raise IncompleteRead()
            return data

        self.open = True
        while self.open:
            (read, _, _) = select.select([self.interruptPipeRecv, self.handler.rfile], [], [], 15)
            if self.handler.rfile in read:
                available = True
                self.resetPing()
                while self.open and available:
                    try:
                        header = protected_read(2)
                        opcode = header[0] & 0x0F
                        length = header[1] & 0x7F
                        mask = (header[1] & 0x80) >> 7
                        if length == 126:
                            header = protected_read(2)
                            length = (header[0] << 8) + header[1]
                        if mask:
                            masking_key = protected_read(4)
                        data = protected_read(length)
                        if mask:
                            data = bytes([b ^ masking_key[index % 4] for (index, b) in enumerate(data)])
                        if opcode == OPCODE_TEXT_MESSAGE:
                            message = data.decode("utf-8")
                            try:
                                self.messageHandler.handleTextMessage(self, message)
                            except Exception:
                                logger.exception("Exception in websocket handler handleTextMessage()")
                        elif opcode == OPCODE_BINARY_MESSAGE:
                            try:
                                self.messageHandler.handleBinaryMessage(self, data)
                            except Exception:
                                logger.exception("Exception in websocket handler handleBinaryMessage()")
                        elif opcode == OPCODE_PING:
                            self.sendPong()
                        elif opcode == OPCODE_PONG:
                            # since every read resets the ping timer, there's nothing to do here.
                            pass
                        elif opcode == OPCODE_CLOSE:
                            logger.debug("websocket close frame received; closing connection")
                            self.open = False
                        else:
                            logger.warning("unsupported opcode: {0}".format(opcode))
                    except Drained:
                        available = False
                    except IncompleteRead:
                        logger.warning("incomplete read on websocket; closing connection")
                        self.open = False
                    except OSError:
                        logger.exception("OSError while reading data; closing connection")
                        self.open = False

    def close(self):
        self.open = False
        self.interrupt()

    def cancelPing(self):
        if self.pingTimer:
            self.pingTimer.cancel()

    def resetPing(self):
        self.cancelPing()
        if not self.open:
            logger.debug("resetPing() while closed. passing...")
            return
        self.pingTimer = threading.Timer(30, self.sendPing)
        self.pingTimer.start()

    def sendPing(self):
        header = self.get_header(0, OPCODE_PING)
        self._sendBytes(header)
        self.resetPing()

    def sendPong(self):
        header = self.get_header(0, OPCODE_PONG)
        self._sendBytes(header)
