import threading
import time
from owrx.config import Config
from urllib import request, parse

import logging

logger = logging.getLogger(__name__)


class ListingUpdater(threading.Thread):
    def __init__(self):
        self.doRun = True
        super().__init__(daemon=True)

    def update(self):
        pm = Config.get().filter("server_hostname", "web_port", "listing_key")
        data = parse.urlencode({
            "url": "http://{server_hostname}:{web_port}".format(**pm.__dict__()),
            "key": pm["listing_key"]
        }).encode()

        res = request.urlopen("http://kiwisdr.com/php/update.php", data=data)
        if res.getcode() < 200 or res.getcode() >= 300:
            logger.warning('rx.kiwisdr.com update failed with error code %i', res.getcode())
            return 2

        returned = res.read().decode("utf-8")
        if "UPDATE:" not in returned:
            logger.warning("Update failed, your receiver cannot be listed on rx.kiwisdr.com!")
            return 2

        value = returned.split("UPDATE:")[1].split("\n", 1)[0]
        if value.startswith("SUCCESS"):
            logger.info("Update succeeded!")
        else:
            logger.warning("Update failed, your receiver cannot be listed on rx.kiwisdr.com! Reason: %s", value)
        return 20

    def run(self):
        while self.doRun:
            retrytime_mins = self.update()
            time.sleep(60 * retrytime_mins)
