from . import Controller
from owrx.config import Config
from datetime import datetime
import mimetypes
import os
import pkg_resources
from abc import ABCMeta, abstractmethod


class AssetsController(Controller, metaclass=ABCMeta):
    def getModified(self, file):
        return datetime.fromtimestamp(os.path.getmtime(self.getFilePath(file)))

    def openFile(self, file):
        return open(self.getFilePath(file), "rb")

    @abstractmethod
    def getFilePath(self, file):
        pass

    def serve_file(self, file, content_type=None):
        try:
            modified = self.getModified(file)

            if modified is not None and "If-Modified-Since" in self.handler.headers:
                client_modified = datetime.strptime(
                    self.handler.headers["If-Modified-Since"], "%a, %d %b %Y %H:%M:%S %Z"
                )
                if modified <= client_modified:
                    self.send_response("", code=304)
                    return

            f = self.openFile(file)
            data = f.read()
            f.close()

            if content_type is None:
                (content_type, encoding) = mimetypes.MimeTypes().guess_type(file)
            self.send_response(data, content_type=content_type, last_modified=modified, max_age=3600)
        except FileNotFoundError:
            self.send_response("file not found", code=404)

    def indexAction(self):
        filename = self.request.matches.group(1)
        self.serve_file(filename)


class OwrxAssetsController(AssetsController):
    def getFilePath(self, file):
        return pkg_resources.resource_filename("htdocs", file)


class AprsSymbolsController(AssetsController):
    def __init__(self, handler, request, options):
        pm = Config.get()
        path = pm["aprs_symbols_path"]
        if not path.endswith("/"):
            path += "/"
        self.path = path
        super().__init__(handler, request, options)

    def getFilePath(self, file):
        return self.path + file


class CompiledAssetsController(Controller):
    profiles = {
        "receiver.js": [
            "openwebrx.js",
            "lib/jquery-3.2.1.min.js",
            "lib/jquery.nanoscroller.js",
            "lib/Header.js",
            "lib/Demodulator.js",
            "lib/DemodulatorPanel.js",
            "lib/BookmarkBar.js",
            "lib/BookmarkDialog.js",
            "lib/AudioEngine.js",
            "lib/ProgressBar.js",
            "lib/Measurement.js",
            "lib/FrequencyDisplay.js",
            "lib/Js8Threads.js",
            "lib/Modes.js",
        ],
        "map.js": [
            "lib/jquery-3.2.1.min.js",
            "lib/chroma.min.js",
            "lib/Header.js",
            "map.js",
        ],
        "settings.js": [
            "lib/jquery-3.2.1.min.js",
            "lib/Header.js",
            "lib/settings/Input.js",
            "lib/settings/SdrDevice.js",
            "settings.js",
        ]
    }

    def indexAction(self):
        profileName = self.request.matches.group(1)
        if profileName not in CompiledAssetsController.profiles:
            self.send_response("profile not found", code=404)
            return

        files = CompiledAssetsController.profiles[profileName]
        files = [pkg_resources.resource_filename("htdocs", f) for f in files]

        modified = self.getModified(files)

        if modified is not None and "If-Modified-Since" in self.handler.headers:
            client_modified = datetime.strptime(
                self.handler.headers["If-Modified-Since"], "%a, %d %b %Y %H:%M:%S %Z"
            )
            if modified <= client_modified:
                self.send_response("", code=304)
                return

        contents = [self.getContents(f) for f in files]

        (content_type, encoding) = mimetypes.MimeTypes().guess_type(profileName)
        self.send_response("\n".join(contents), content_type=content_type, last_modified=modified, max_age=3600)

    def getContents(self, file):
        with open(file) as f:
            return f.read()

    def getModified(self, files):
        modified = [datetime.fromtimestamp(os.path.getmtime(f)) for f in files]
        return max(*modified)
