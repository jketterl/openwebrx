from unittest import TestCase
from unittest.mock import Mock
from owrx.property import PropertyLayer, PropertyFilter


class PropertyFilterTest(TestCase):

    def testPassesProperty(self):
        pm = PropertyLayer()
        pm["testkey"] = "testvalue"
        pf = PropertyFilter(pm, "testkey")
        self.assertEqual(pf["testkey"], "testvalue")

    def testMissesPropert(self):
        pm = PropertyLayer()
        pm["testkey"] = "testvalue"
        pf = PropertyFilter(pm, "other_key")
        self.assertFalse("testkey" in pf)
        with self.assertRaises(KeyError):
            x = pf["testkey"]

    def testForwardsEvent(self):
        pm = PropertyLayer()
        pf = PropertyFilter(pm, "testkey")
        mock = Mock()
        pf.wire(mock.method)
        pm["testkey"] = "testvalue"
        mock.method.assert_called_once_with("testkey", "testvalue")

    def testForwardsPropertyEvent(self):
        pm = PropertyLayer()
        pf = PropertyFilter(pm, "testkey")
        mock = Mock()
        pf.wireProperty("testkey", mock.method)
        pm["testkey"] = "testvalue"
        mock.method.assert_called_once_with("testvalue")

    def testForwardsWrite(self):
        pm = PropertyLayer()
        pf = PropertyFilter(pm, "testkey")
        pf["testkey"] = "testvalue"
        self.assertTrue("testkey" in pm)
        self.assertEqual(pm["testkey"], "testvalue")

    def testOverwrite(self):
        pm = PropertyLayer()
        pm["testkey"] = "old value"
        pf = PropertyFilter(pm, "testkey")
        pf["testkey"] = "new value"
        self.assertEqual(pm["testkey"], "new value")
        self.assertEqual(pf["testkey"], "new value")
