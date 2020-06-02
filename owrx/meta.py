from owrx.config import Config
from urllib import request
import json
from datetime import datetime, timedelta
import logging
import threading
from owrx.map import Map, LatLngLocation
from owrx.parser import Parser

logger = logging.getLogger(__name__)


class DmrCache(object):
    sharedInstance = None

    @staticmethod
    def getSharedInstance():
        if DmrCache.sharedInstance is None:
            DmrCache.sharedInstance = DmrCache()
        return DmrCache.sharedInstance

    def __init__(self):
        self.cache = {}
        self.cacheTimeout = timedelta(seconds=86400)

    def isValid(self, key):
        if not key in self.cache:
            return False
        entry = self.cache[key]
        return entry["timestamp"] + self.cacheTimeout > datetime.now()

    def put(self, key, value):
        self.cache[key] = {"timestamp": datetime.now(), "data": value}

    def get(self, key):
        if not self.isValid(key):
            return None
        return self.cache[key]["data"]


class DmrMetaEnricher(object):
    def __init__(self):
        self.threads = {}

    def downloadRadioIdData(self, id):
        cache = DmrCache.getSharedInstance()
        try:
            logger.debug("requesting DMR metadata for id=%s", id)
            res = request.urlopen("https://www.radioid.net/api/dmr/user/?id={0}".format(id), timeout=30).read()
            data = json.loads(res.decode("utf-8"))
            cache.put(id, data)
        except json.JSONDecodeError:
            cache.put(id, None)
        del self.threads[id]

    def enrich(self, meta):
        if not Config.get()["digital_voice_dmr_id_lookup"]:
            return None
        if not "source" in meta:
            return None
        id = meta["source"]
        cache = DmrCache.getSharedInstance()
        if not cache.isValid(id):
            if not id in self.threads:
                self.threads[id] = threading.Thread(target=self.downloadRadioIdData, args=[id], daemon=True)
                self.threads[id].start()
            return None
        data = cache.get(id)
        if "count" in data and data["count"] > 0 and "results" in data:
            return data["results"][0]
        return None


class YsfMetaEnricher(object):
    def __init__(self, parser):
        self.parser = parser

    def enrich(self, meta):
        if "source" in meta and "lat" in meta and "lon" in meta:
            # TODO parsing the float values should probably happen earlier
            loc = LatLngLocation(float(meta["lat"]), float(meta["lon"]))
            Map.getSharedInstance().updateLocation(meta["source"], loc, "YSF", self.parser.getBand())
        return None


class MetaParser(Parser):
    def __init__(self, handler):
        super().__init__(handler)
        self.enrichers = {"DMR": DmrMetaEnricher(), "YSF": YsfMetaEnricher(self)}

    def parse(self, meta):
        fields = meta.split(";")
        meta = {v[0]: "".join(v[1:]) for v in map(lambda x: x.split(":"), fields) if v[0] != ""}

        if "protocol" in meta:
            protocol = meta["protocol"]
            if protocol in self.enrichers:
                additional_data = self.enrichers[protocol].enrich(meta)
                if additional_data is not None:
                    meta["additional"] = additional_data
        self.handler.write_metadata(meta)
