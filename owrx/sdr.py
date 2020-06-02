from owrx.config import Config
from owrx.property import PropertyLayer
from owrx.feature import FeatureDetector, UnknownFeatureException

import logging

logger = logging.getLogger(__name__)


class SdrService(object):
    sdrProps = None
    sources = {}
    lastPort = None

    @staticmethod
    def loadProps():
        if SdrService.sdrProps is None:
            pm = Config.get()
            featureDetector = FeatureDetector()

            def loadIntoPropertyManager(dict: dict):
                propertyManager = PropertyLayer()
                for (name, value) in dict.items():
                    propertyManager[name] = value
                return propertyManager

            def sdrTypeAvailable(value):
                try:
                    if not featureDetector.is_available(value["type"]):
                        logger.error(
                            'The SDR source type "{0}" is not available. please check requirements.'.format(
                                value["type"]
                            )
                        )
                        return False
                    return True
                except UnknownFeatureException:
                    logger.error(
                        'The SDR source type "{0}" is invalid. Please check your configuration'.format(value["type"])
                    )
                    return False

            # transform all dictionary items into PropertyManager object, filtering out unavailable ones
            SdrService.sdrProps = {
                name: loadIntoPropertyManager(value) for (name, value) in pm["sdrs"].items() if sdrTypeAvailable(value)
            }
            logger.info(
                "SDR sources loaded. Available SDRs: {0}".format(
                    ", ".join(map(lambda x: x["name"], SdrService.sdrProps.values()))
                )
            )

    @staticmethod
    def getFirstSource():
        sources = SdrService.getSources()
        if not sources:
            return None
        # TODO: configure default sdr in config? right now it will pick the first one off the list.
        return sources[list(sources.keys())[0]]

    @staticmethod
    def getSource(id):
        SdrService.loadProps()
        sources = SdrService.getSources()
        if not sources:
            return None
        if not id in sources:
            return None
        return sources[id]

    @staticmethod
    def getSources():
        SdrService.loadProps()
        for id in SdrService.sdrProps.keys():
            if not id in SdrService.sources:
                props = SdrService.sdrProps[id]
                sdrType = props["type"]
                className = "".join(x for x in sdrType.title() if x.isalnum()) + "Source"
                module = __import__("owrx.source.{0}".format(sdrType), fromlist=[className])
                cls = getattr(module, className)
                SdrService.sources[id] = cls(id, props)
        return {key: s for key, s in SdrService.sources.items() if not s.isFailed()}
