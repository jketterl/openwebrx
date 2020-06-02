from .template import WebpageController
from .session import SessionStorage
from owrx.config import Config
from urllib import parse

import logging

logger = logging.getLogger(__name__)


class Authentication(object):
    def isAuthenticated(self, request):
        if "owrx-session" in request.cookies:
            session = SessionStorage.getSharedInstance().getSession(request.cookies["owrx-session"].value)
            return session is not None
        return False


class AdminController(WebpageController):
    def __init__(self, handler, request, options):
        self.authentication = Authentication()
        super().__init__(handler, request, options)

    def handle_request(self):
        config = Config.get()
        if "webadmin_enabled" not in config or not config["webadmin_enabled"]:
            self.send_response("Web Admin is disabled", code=403)
            return
        if self.authentication.isAuthenticated(self.request):
            super().handle_request()
        else:
            target = "/login?{0}".format(parse.urlencode({"ref": self.request.path}))
            self.send_redirect(target)
