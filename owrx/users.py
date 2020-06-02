from abc import ABC, abstractmethod
import json

import logging

logger = logging.getLogger(__name__)


class PasswordException(Exception):
    pass


class Password(ABC):
    @staticmethod
    def from_dict(d: dict):
        if "encoding" not in d:
            raise PasswordException("password encoding not set")
        if d["encoding"] == "string":
            return CleartextPassword(d)
        raise PasswordException("invalid passord encoding: {0}".format(d["type"]))

    def __init__(self, pwinfo: dict):
        self.pwinfo = pwinfo

    @abstractmethod
    def is_valid(self, inp: str):
        pass


class CleartextPassword(Password):
    def is_valid(self, inp: str):
        return self.pwinfo['value'] == inp


class User(object):
    def __init__(self, name: str, enabled: bool, password: Password):
        self.name = name
        self.enabled = enabled
        self.password = password


class UserList(object):
    sharedInstance = None

    @staticmethod
    def getSharedInstance():
        if UserList.sharedInstance is None:
            UserList.sharedInstance = UserList()
        return UserList.sharedInstance

    def __init__(self):
        self.users = self._loadUsers()

    def _loadUsers(self):
        for file in ["/etc/openwebrx/users.json", "users.json"]:
            try:
                f = open(file, "r")
                users_json = json.load(f)
                f.close()

                return {u.name: u for u in [self.buildUser(d) for d in users_json]}
            except FileNotFoundError:
                pass
            except json.JSONDecodeError:
                logger.exception("error while parsing users file %s", file)
                return {}
            except Exception:
                logger.exception("error while processing users from %s", file)
                return {}
        return {}

    def buildUser(self, d):
        if "user" in d and "password" in d and "enabled" in d:
            return User(d["user"], d["enabled"], Password.from_dict(d["password"]))

    def __getitem__(self, item):
        return self.users[item]

    def __contains__(self, item):
        return item in self.users
