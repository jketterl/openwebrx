from unittest import TestCase
from unittest.mock import Mock
from owrx.property import PropertyLayer, PropertyStack


class PropertyStackTest(TestCase):
    def testLayer(self):
        om = PropertyStack()
        pm = PropertyLayer()
        pm["testkey"] = "testvalue"
        om.addLayer(1, pm)
        self.assertEqual(om["testkey"], "testvalue")

    def testHighPriority(self):
        om = PropertyStack()
        low_pm = PropertyLayer()
        high_pm = PropertyLayer()
        low_pm["testkey"] = "low value"
        high_pm["testkey"] = "high value"
        om.addLayer(1, low_pm)
        om.addLayer(0, high_pm)
        self.assertEqual(om["testkey"], "high value")

    def testPriorityFallback(self):
        om = PropertyStack()
        low_pm = PropertyLayer()
        high_pm = PropertyLayer()
        low_pm["testkey"] = "low value"
        om.addLayer(1, low_pm)
        om.addLayer(0, high_pm)
        self.assertEqual(om["testkey"], "low value")

    def testLayerRemoval(self):
        om = PropertyStack()
        low_pm = PropertyLayer()
        high_pm = PropertyLayer()
        low_pm["testkey"] = "low value"
        high_pm["testkey"] = "high value"
        om.addLayer(1, low_pm)
        om.addLayer(0, high_pm)
        self.assertEqual(om["testkey"], "high value")
        om.removeLayer(high_pm)
        self.assertEqual(om["testkey"], "low value")

    def testPropertyChange(self):
        layer = PropertyLayer()
        stack = PropertyStack()
        stack.addLayer(0, layer)
        mock = Mock()
        stack.wire(mock.method)
        layer["testkey"] = "testvalue"
        mock.method.assert_called_once_with("testkey", "testvalue")

    def testPropertyChangeEventPriority(self):
        low_layer = PropertyLayer()
        high_layer = PropertyLayer()
        low_layer["testkey"] = "initial low value"
        high_layer["testkey"] = "initial high value"
        stack = PropertyStack()
        stack.addLayer(1, low_layer)
        stack.addLayer(0, high_layer)
        mock = Mock()
        stack.wire(mock.method)
        low_layer["testkey"] = "modified low value"
        mock.method.assert_not_called()
        high_layer["testkey"] = "modified high value"
        mock.method.assert_called_once_with("testkey", "modified high value")

    def testPropertyEventOnLayerAdd(self):
        low_layer = PropertyLayer()
        low_layer["testkey"] = "low value"
        stack = PropertyStack()
        stack.addLayer(1, low_layer)
        mock = Mock()
        stack.wireProperty("testkey", mock.method)
        mock.reset_mock()
        high_layer = PropertyLayer()
        high_layer["testkey"] = "high value"
        stack.addLayer(0, high_layer)
        mock.method.assert_called_once_with("high value")

    def testNoEventOnExistingValue(self):
        low_layer = PropertyLayer()
        low_layer["testkey"] = "same value"
        stack = PropertyStack()
        stack.addLayer(1, low_layer)
        mock = Mock()
        stack.wireProperty("testkey", mock.method)
        mock.reset_mock()
        high_layer = PropertyLayer()
        high_layer["testkey"] = "same value"
        stack.addLayer(0, high_layer)
        mock.method.assert_not_called()

    def testEventOnLayerWithNewProperty(self):
        low_layer = PropertyLayer()
        low_layer["existingkey"] = "existing value"
        stack = PropertyStack()
        stack.addLayer(1, low_layer)
        mock = Mock()
        stack.wireProperty("newkey", mock.method)
        high_layer = PropertyLayer()
        high_layer["newkey"] = "new value"
        stack.addLayer(0, high_layer)
        mock.method.assert_called_once_with("new value")

    def testEventOnLayerRemoval(self):
        low_layer = PropertyLayer()
        high_layer = PropertyLayer()
        stack = PropertyStack()
        stack.addLayer(1, low_layer)
        stack.addLayer(0, high_layer)
        low_layer["testkey"] = "low value"
        high_layer["testkey"] = "high value"

        mock = Mock()
        stack.wireProperty("testkey", mock.method)
        mock.method.assert_called_once_with("high value")
        mock.reset_mock()
        stack.removeLayer(high_layer)
        mock.method.assert_called_once_with("low value")

    def testNoneOnKeyRemoval(self):
        low_layer = PropertyLayer()
        high_layer = PropertyLayer()
        stack = PropertyStack()
        stack.addLayer(1, low_layer)
        stack.addLayer(0, high_layer)
        low_layer["testkey"] = "low value"
        high_layer["testkey"] = "high value"
        high_layer["unique key"] = "unique value"

        mock = Mock()
        stack.wireProperty("unique key", mock.method)
        mock.method.assert_called_once_with("unique value")
        mock.reset_mock()
        stack.removeLayer(high_layer)
        mock.method.assert_called_once_with(None)

    def testReplaceLayer(self):
        first_layer = PropertyLayer()
        first_layer["testkey"] = "old value"
        second_layer = PropertyLayer()
        second_layer["testkey"] = "new value"

        stack = PropertyStack()
        stack.addLayer(0, first_layer)

        mock = Mock()
        stack.wireProperty("testkey", mock.method)
        mock.method.assert_called_once_with("old value")
        mock.reset_mock()

        stack.replaceLayer(0, second_layer)
        mock.method.assert_called_once_with("new value")

    def testUnwiresEventsOnRemoval(self):
        layer = PropertyLayer()
        layer["testkey"] = "before"
        stack = PropertyStack()
        stack.addLayer(0, layer)
        mock = Mock()
        stack.wire(mock.method)
        stack.removeLayer(layer)
        mock.method.assert_called_once_with("testkey", None)
        mock.reset_mock()

        layer["testkey"] = "after"
        mock.method.assert_not_called()

    def testReplaceLayerNoEventWhenValueUnchanged(self):
        fixed = PropertyLayer()
        fixed["testkey"] = "fixed value"
        first_layer = PropertyLayer()
        first_layer["testkey"] = "same value"
        second_layer = PropertyLayer()
        second_layer["testkey"] = "same value"

        stack = PropertyStack()
        stack.addLayer(1, fixed)
        stack.addLayer(0, first_layer)
        mock = Mock()
        stack.wire(mock.method)
        mock.method.assert_not_called()

        stack.replaceLayer(0, second_layer)
        mock.method.assert_not_called()
