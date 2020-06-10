from owrx.controllers.status import StatusController
from owrx.controllers.template import (
    IndexController,
    MapController,
    FeatureController
)
from owrx.controllers.assets import (
    OwrxAssetsController,
    AprsSymbolsController,
    CompiledAssetsController
)
from owrx.controllers.websocket import WebSocketController
from owrx.controllers.api import ApiController
from owrx.controllers.metrics import MetricsController
from owrx.controllers.settings import SettingsController, GeneralSettingsController, SdrSettingsController
from owrx.controllers.session import SessionController
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import re
from abc import ABC, abstractmethod
from http.cookies import SimpleCookie

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self.router = Router()
        super().__init__(request, client_address, server)

    def log_message(self, format, *args):
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)

    def do_GET(self):
        self.router.route(self, "GET")

    def do_POST(self):
        self.router.route(self, "POST")


class Request(object):
    def __init__(self, url, method, cookies):
        self.path = url.path
        self.query = parse_qs(url.query)
        self.matches = None
        self.method = method
        self.cookies = cookies

    def setMatches(self, matches):
        self.matches = matches


class Route(ABC):
    def __init__(self, controller, method="GET", options=None):
        self.controller = controller
        self.controllerOptions = options if options is not None else {}
        self.method = method

    @abstractmethod
    def matches(self, request):
        pass


class StaticRoute(Route):
    def __init__(self, route, controller, method="GET", options=None):
        self.route = route
        super().__init__(controller, method, options)

    def matches(self, request):
        return request.path == self.route and self.method == request.method


class RegexRoute(Route):
    def __init__(self, regex, controller, method="GET", options=None):
        self.regex = re.compile(regex)
        super().__init__(controller, method, options)

    def matches(self, request):
        matches = self.regex.match(request.path)
        # this is probably not the cleanest way to do it...
        request.setMatches(matches)
        return matches is not None and self.method == request.method


class Router(object):
    def __init__(self):
        self.routes = [
            StaticRoute("/", IndexController),
            StaticRoute("/status.json", StatusController),
            RegexRoute("/static/(.+)", OwrxAssetsController),
            RegexRoute("/compiled/(.+)", CompiledAssetsController),
            RegexRoute("/aprs-symbols/(.+)", AprsSymbolsController),
            StaticRoute("/ws/", WebSocketController),
            RegexRoute("(/favicon.ico)", OwrxAssetsController),
            StaticRoute("/map", MapController),
            StaticRoute("/features", FeatureController),
            StaticRoute("/api/features", ApiController),
            StaticRoute("/api/receiverdetails", ApiController, options={"action": "receiverDetails"}),
            StaticRoute("/metrics", MetricsController),
            StaticRoute("/settings", SettingsController),
            StaticRoute("/generalsettings", GeneralSettingsController),
            StaticRoute("/generalsettings", GeneralSettingsController, method="POST", options={"action": "processFormData"}),
            StaticRoute("/sdrsettings", SdrSettingsController),
            StaticRoute("/login", SessionController, options={"action": "loginAction"}),
            StaticRoute("/login", SessionController, method="POST", options={"action": "processLoginAction"}),
            StaticRoute("/logout", SessionController, options={"action": "logoutAction"}),
        ]

    def find_route(self, request):
        for r in self.routes:
            if r.matches(request):
                return r

    def route(self, handler, method):
        url = urlparse(handler.path)
        cookies = SimpleCookie()
        if "Cookie" in handler.headers:
            cookies.load(handler.headers["Cookie"])
        request = Request(url, method, cookies)
        route = self.find_route(request)
        if route is not None:
            controller = route.controller
            controller(handler, request, route.controllerOptions).handle_request()
        else:
            handler.send_error(404, "Not Found", "The page you requested could not be found.")
