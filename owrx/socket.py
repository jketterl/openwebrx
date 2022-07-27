import socket


def getAvailablePort():
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port
