import re
import logging
from owrx.config import Config

logger = logging.getLogger(__name__)


keyRegex = re.compile("^([a-zA-Z]+)-([0-9a-f]{32})-([0-9a-f]{64})$")
keyChallengeRegex = re.compile("^([a-zA-Z]+)-([0-9a-f]{32})-([0-9a-f]{32})$")
headerRegex = re.compile("^ReceiverId (.*)$")


class KeyException(Exception):
    pass


class Key(object):
    def __init__(self, keyString):
        matches = keyRegex.match(keyString)
        if not matches:
            raise KeyException("invalid key format")
        self.source = matches.group(1)
        self.id = matches.group(2)
        self.secret = matches.group(3)


class KeyChallenge(object):
    def __init__(self, challengeString):
        matches = keyChallengeRegex.match(challengeString)
        if not matches:
            raise KeyException("invalid key challenge format")
        self.source = matches.group(1)
        self.id = matches.group(2)
        self.challenge = matches.group(3)


class KeyResponse(object):
    def __str__(self):
        return "TODO"


class ReceiverId(object):
    @staticmethod
    def getResponseHeader(requestHeader):
        matches = headerRegex.match(requestHeader)
        if not matches:
            raise KeyException("invalid authorization header")
        challenge = KeyChallenge(matches.group(1))
        key = ReceiverId.findKey(challenge)
        # TODO sign challenge and respond

    @staticmethod
    def findKey(challenge):
        def parseKey(keyString):
            try:
                return Key(keyString)
            except KeyError as e:
                logger.error(e)
        keys = [key for key in (parseKey(keyString) for keyString in Config.get()['receiver_keys']) if key is not None]
        matching_keys = [key for key in keys if key.source == challenge.source and key.id == challenge.id]
        if matching_keys:
            return matching_keys[0]
        return None
