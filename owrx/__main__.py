import logging

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from http.server import HTTPServer
from owrx.http import RequestHandler
from owrx.config import Config
from owrx.feature import FeatureDetector
from owrx.sdr import SdrService
from socketserver import ThreadingMixIn
from owrx.service import Services
from owrx.websocket import WebSocketConnection
from owrx.pskreporter import PskReporter
from owrx.version import openwebrx_version


class ThreadedHttpServer(ThreadingMixIn, HTTPServer):
    pass


def main():
    print(
        """

OpenWebRX - Open Source SDR Web App for Everyone!  | for license see LICENSE file in the package
_________________________________________________________________________________________________

Author contact info:    Jakob Ketterl, DD5JFK <dd5jfk@darc.de>
Documentation:          https://github.com/jketterl/openwebrx/wiki
Support and info:       https://groups.io/g/openwebrx

    """
    )

    logger.info("OpenWebRX version {0} starting up...".format(openwebrx_version))

    pm = Config.get()

    configErrors = Config.validateConfig()
    if configErrors:
        logger.error(
            "your configuration contains errors. please address the following errors:"
        )
        for e in configErrors:
            logger.error(e)
        return

    featureDetector = FeatureDetector()
    if not featureDetector.is_available("core"):
        logger.error(
            "you are missing required dependencies to run openwebrx. "
            "please check that the following core requirements are installed:"
        )
        logger.error(", ".join(featureDetector.get_requirements("core")))
        return

    # Get error messages about unknown / unavailable features as soon as possible
    SdrService.loadProps()

    Services.start()

    try:
        server = ThreadedHttpServer(("0.0.0.0", pm["web_port"]), RequestHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        WebSocketConnection.closeAll()
        Services.stop()
        PskReporter.stop()
