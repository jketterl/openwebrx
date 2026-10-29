from owrx.controllers import BodySizeError
from owrx.controllers.assets import AssetsController
from owrx.controllers.admin import AuthorizationMixin
from owrx.config.core import CoreConfig
from owrx.form.input.gfx import AvatarInput, TopPhotoInput
import uuid
import json
import os
import re


class ImageUploadController(AuthorizationMixin, AssetsController):
    # max upload filesizes
    max_sizes = {
        # not the best idea to instantiate inputs, but i didn't want to duplicate the sizes here
        "receiver_avatar": AvatarInput("id", "label").getMaxSize(),
        "receiver_top_photo": TopPhotoInput("id", "label").getMaxSize(),
    }

    def __init__(self, handler, request, options):
        super().__init__(handler, request, options)
        self.file = request.query["file"][0] if "file" in request.query else None

    def getFilePath(self, file=None):
        if self.file is None:
            raise FileNotFoundError("missing filename")
        pattern = r"(?:{})-[0-9a-f]{{32}}\.(?:png|jpg|webp)".format(
            "|".join(re.escape(image_id) for image_id in self.max_sizes)
        )
        if re.fullmatch(pattern, self.file) is None:
            raise FileNotFoundError("invalid image filename")
        temporary_directory = os.path.realpath(CoreConfig().get_temporary_directory())
        image_path = os.path.realpath(os.path.join(temporary_directory, self.file))
        # A valid upload name must not follow a symlink outside the temporary directory.
        if os.path.dirname(image_path) != temporary_directory:
            raise FileNotFoundError("invalid image path")
        return image_path

    def indexAction(self):
        self.serve_file(None)

    def _is_png(self, contents):
        return contents[0:8] == bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])

    def _is_jpg(self, contents):
        return contents[0:3] == bytes([0xFF, 0xD8, 0xFF])

    def _is_webp(self, contents):
        return contents[0:4] == bytes([0x52, 0x49, 0x46, 0x46]) and contents[8:12] == bytes([0x57, 0x45, 0x42, 0x50])

    def processImage(self):
        if "id" not in self.request.query:
            self.send_json_response({"error": "missing id"}, code=400)
            return
        file_id = self.request.query["id"][0]

        if file_id not in ImageUploadController.max_sizes:
            self.send_json_response({"error": "unexpected image id"}, code=400)
            return

        try:
            contents = self.get_body(ImageUploadController.max_sizes[file_id])
        except BodySizeError:
            self.send_json_response({"error": "file size too large"}, code=400)
            return

        filetype = None
        if self._is_png(contents):
            filetype = "png"
        elif self._is_jpg(contents):
            filetype = "jpg"
        elif self._is_webp(contents):
            filetype = "webp"
        if filetype is None:
            self.send_json_response({"error": "unsupported file type"}, code=400)
            return

        self.file = "{id}-{uuid}.{ext}".format(
            id=file_id,
            uuid=uuid.uuid4().hex,
            ext=filetype,
        )
        with open(self.getFilePath(), "wb") as f:
            f.write(contents)
        self.send_json_response({"file": self.file}, code=200)

    def send_json_response(self, obj, code):
        self.send_response(json.dumps(obj), code=code, content_type="application/json")
