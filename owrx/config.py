from owrx.property import PropertyManager, PropertyLayer
import importlib.util
import os
import logging
import json
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ConfigNotFoundException(Exception):
    pass


class ConfigError(object):
    def __init__(self, key, message):
        self.key = key
        self.message = message

    def __str__(self):
        return "Configuration Error (key: {0}): {1}".format(self.key, self.message)


class ConfigMigrator(ABC):
    @abstractmethod
    def migrate(self, config):
        pass

    def renameKey(self, config, old, new):
        if old in config and not new in config:
            config[new] = config[old]
            del config[old]


class ConfigMigratorVersion1(ConfigMigrator):
    def migrate(self, config):
        if "receiver_gps" in config:
            gps = config["receiver_gps"]
            config["receiver_gps"] = {"lat": gps[0], "lon": gps[1]}

        if "waterfall_auto_level_margin" in config:
            levels = config["waterfall_auto_level_margin"]
            config["waterfall_auto_level_margin"] = {"min": levels[0], "max": levels[1]}

        self.renameKey(config, "wsjt_queue_workers", "decoding_queue_workers")
        self.renameKey(config, "wsjt_queue_length", "decoding_queue_length")

        config["version"] = 2
        return config


class Config:
    sharedConfig = None
    currentVersion = 2
    migrators = {
        1: ConfigMigratorVersion1()
    }

    @staticmethod
    def _loadPythonFile(file):
        spec = importlib.util.spec_from_file_location("config_webrx", file)
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        pm = PropertyLayer()
        for name, value in cfg.__dict__.items():
            if name.startswith("__"):
                continue
            pm[name] = value
        return pm

    @staticmethod
    def _loadJsonFile(file):
        with open(file, "r") as f:
            pm = PropertyLayer()
            for k, v in json.load(f).items():
                pm[k] = v
            return pm

    @staticmethod
    def _loadConfig():
        for file in ["./settings.json", "/etc/openwebrx/config_webrx.py", "./config_webrx.py"]:
            try:
                if file.endswith(".py"):
                    return Config._loadPythonFile(file)
                elif file.endswith(".json"):
                    return Config._loadJsonFile(file)
                else:
                    logger.warning("unsupported file type: %s", file)
            except FileNotFoundError:
                pass
        raise ConfigNotFoundException("no usable config found! please make sure you have a valid configuration file!")

    @staticmethod
    def get():
        if Config.sharedConfig is None:
            Config.sharedConfig = Config._migrate(Config._loadConfig())
        return Config.sharedConfig

    @staticmethod
    def store():
        with open("settings.json", "w") as file:
            json.dump(Config.get().__dict__(), file, indent=4)

    @staticmethod
    def validateConfig():
        pm = Config.get()
        errors = [
            Config.checkTempDirectory(pm)
        ]

        return [e for e in errors if e is not None]

    @staticmethod
    def checkTempDirectory(pm: PropertyManager):
        key = "temporary_directory"
        if key not in pm or pm[key] is None:
            return ConfigError(key, "temporary directory is not set")
        if not os.path.exists(pm[key]):
            return ConfigError(key, "temporary directory doesn't exist")
        if not os.path.isdir(pm[key]):
            return ConfigError(key, "temporary directory path is not a directory")
        if not os.access(pm[key], os.W_OK):
            return ConfigError(key, "temporary directory is not writable")
        return None

    @staticmethod
    def _migrate(config):
        version = config["version"] if "version" in config else 1
        if version == Config.currentVersion:
            return config

        logger.debug("migrating config from version %i", version)
        migrator = Config.migrators[version]
        return migrator.migrate(config)
