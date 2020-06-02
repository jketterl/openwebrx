from owrx.config import Config
from owrx.locator import Locator
from owrx.property import PropertyFilter


class ReceiverDetails(PropertyFilter):
    def __init__(self):
        super().__init__(
            Config.get(),
            "receiver_name",
            "receiver_location",
            "receiver_asl",
            "receiver_gps",
            "photo_title",
            "photo_desc",
        )

    def __dict__(self):
        receiver_info = super().__dict__()
        receiver_info["locator"] = Locator.fromCoordinates(receiver_info["receiver_gps"])
        return receiver_info
