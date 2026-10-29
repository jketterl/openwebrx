from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from owrx.controllers.imageupload import ImageUploadController


class ImageUploadTest(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "uploads"
        self.root.mkdir()
        self.outside = Path(self.directory.name) / "outside.txt"
        self.outside.write_bytes(b"synthetic private data")
        config_patch = patch("owrx.controllers.imageupload.CoreConfig")
        config = config_patch.start()
        self.addCleanup(config_patch.stop)
        config.return_value.get_temporary_directory.return_value = str(self.root)
        self.controller = ImageUploadController.__new__(ImageUploadController)
        self.controller.file = None
        self.controller.handler = SimpleNamespace(headers={})
        self.controller.send_response = Mock()

    def assertNotFound(self, filename):
        self.controller.file = filename
        self.controller.send_response.reset_mock()
        self.controller.indexAction()
        self.assertEqual(self.controller.send_response.call_args[1].get("code", 200), 404)

    def testRejectsPathsOutsideUploadDirectory(self):
        for filename in [
            "../outside.txt", "..\\outside.txt", str(self.outside),
            "../../outside.txt", "", ".", "..", "invalid\x00.png",
        ]:
            with self.subTest(filename=filename):
                self.assertNotFound(filename)

    def testRejectsUnrelatedTemporaryFiles(self):
        (self.root / "credentials.json").write_bytes(b"unrelated temporary file")
        self.assertNotFound("credentials.json")

    def testMissingFileReturnsNotFound(self):
        self.assertNotFound(None)
        self.assertNotFound("receiver_avatar-" + "a" * 32 + ".png")

    def testUploadedImagesCanBePreviewed(self):
        headers = {
            "png": b"\x89PNG\r\n\x1a\n",
            "jpg": b"\xff\xd8\xff",
            "webp": b"RIFF\x00\x00\x00\x00WEBP",
        }
        for image_id in self.controller.max_sizes:
            for extension, header in headers.items():
                with self.subTest(image_id=image_id, extension=extension):
                    contents = header + b"synthetic image"
                    self.controller.request = SimpleNamespace(query={"id": [image_id]})
                    self.controller.get_body = Mock(return_value=contents)
                    self.controller.processImage()
                    self.assertTrue(self.controller.file.endswith("." + extension))
                    self.controller.send_response.reset_mock()
                    self.controller.indexAction()
                    self.assertEqual(self.controller.send_response.call_args[0][0], contents)

    def testRejectsSymlinkOutsideUploadDirectory(self):
        filename = "receiver_avatar-" + "a" * 32 + ".png"
        try:
            (self.root / filename).symlink_to(self.outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable")
        self.assertNotFound(filename)
