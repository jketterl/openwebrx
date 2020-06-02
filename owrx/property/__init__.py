from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class Subscription(object):
    def __init__(self, subscriptee, name, subscriber):
        self.subscriptee = subscriptee
        self.name = name
        self.subscriber = subscriber

    def getName(self):
        return self.name

    def call(self, *args, **kwargs):
        self.subscriber(*args, **kwargs)

    def cancel(self):
        self.subscriptee.unwire(self)


class PropertyManager(ABC):
    def __init__(self):
        self.subscribers = []

    @abstractmethod
    def __getitem__(self, item):
        pass

    @abstractmethod
    def __setitem__(self, key, value):
        pass

    @abstractmethod
    def __contains__(self, item):
        pass

    @abstractmethod
    def __dict__(self):
        pass

    @abstractmethod
    def __delitem__(self, key):
        pass

    @abstractmethod
    def keys(self):
        pass

    def filter(self, *props):
        return PropertyFilter(self, *props)

    def wire(self, callback):
        sub = Subscription(self, None, callback)
        self.subscribers.append(sub)
        return sub

    def wireProperty(self, name, callback):
        sub = Subscription(self, name, callback)
        self.subscribers.append(sub)
        if name in self:
            sub.call(self[name])
        return sub

    def unwire(self, sub):
        try:
            self.subscribers.remove(sub)
        except ValueError:
            # happens when already removed before
            pass
        return self

    def _fireCallbacks(self, name, value):
        for c in self.subscribers:
            try:
                if c.getName() is None:
                    c.call(name, value)
                elif c.getName() == name:
                    c.call(value)
            except Exception as e:
                logger.exception(e)


class PropertyLayer(PropertyManager):
    def __init__(self):
        super().__init__()
        self.properties = {}

    def __contains__(self, name):
        return name in self.properties

    def __getitem__(self, name):
        return self.properties[name]

    def __setitem__(self, name, value):
        if name in self.properties and self.properties[name] == value:
            return
        self.properties[name] = value
        self._fireCallbacks(name, value)

    def __dict__(self):
        return {k: v for k, v in self.properties.items()}

    def __delitem__(self, key):
        return self.properties.__delitem__(key)

    def keys(self):
        return self.properties.keys()


class PropertyFilter(PropertyManager):
    def __init__(self, pm: PropertyManager, *props: str):
        super().__init__()
        self.pm = pm
        self.props = props
        self.pm.wire(self.receiveEvent)

    def receiveEvent(self, name, value):
        if name not in self.props:
            return
        self._fireCallbacks(name, value)

    def __getitem__(self, item):
        if item not in self.props:
            raise KeyError(item)
        return self.pm.__getitem__(item)

    def __setitem__(self, key, value):
        if key not in self.props:
            raise KeyError(key)
        return self.pm.__setitem__(key, value)

    def __contains__(self, item):
        if item not in self.props:
            return False
        return self.pm.__contains__(item)

    def __dict__(self):
        return {k: v for k, v in self.pm.__dict__().items() if k in self.props}

    def __delitem__(self, key):
        if key not in self.props:
            raise KeyError(key)
        return self.pm.__delitem__(key)

    def keys(self):
        return [k for k in self.pm.keys() if k in self.props]


class PropertyStack(PropertyManager):
    def __init__(self):
        super().__init__()
        self.layers = []

    def addLayer(self, priority: int, pm: PropertyManager):
        """
        highest priority = 0
        """
        self._fireChanges(self._addLayer(priority, pm))

    def _addLayer(self, priority: int, pm: PropertyManager):
        changes = {}
        for key in pm.keys():
            if key not in self or self[key] != pm[key]:
                changes[key] = pm[key]

        def eventClosure(name, value):
            self.receiveEvent(pm, name, value)

        sub = pm.wire(eventClosure)

        self.layers.append({"priority": priority, "props": pm, "sub": sub})

        return changes

    def removeLayer(self, pm: PropertyManager):
        for layer in self.layers:
            if layer["props"] == pm:
                self._fireChanges(self._removeLayer(layer))

    def _removeLayer(self, layer):
        layer["sub"].cancel()
        self.layers.remove(layer)
        changes = {}
        pm = layer["props"]
        for key in pm.keys():
            if key in self:
                if self[key] != pm[key]:
                    changes[key] = self[key]
            else:
                changes[key] = None
        return changes

    def replaceLayer(self, priority: int, pm: PropertyManager):
        layers = [x for x in self.layers if x["priority"] == priority]

        originalState = self.__dict__()

        changes = self._removeLayer(layers[0]) if layers else {}
        changes = {**changes, **self._addLayer(priority, pm)}
        changes = {k: v for k, v in changes.items() if k not in originalState or originalState[k] != v}

        self._fireChanges(changes)

    def _fireChanges(self, changes):
        for k, v in changes.items():
            self._fireCallbacks(k, v)

    def receiveEvent(self, layer, name, value):
        if layer != self._getTopLayer(name):
            return
        self._fireCallbacks(name, value)

    def _getTopLayer(self, item):
        layers = [la["props"] for la in sorted(self.layers, key=lambda l: l["priority"])]
        for m in layers:
            if item in m:
                return m
        # return top layer by default
        if layers:
            return layers[0]

    def __getitem__(self, item):
        layer = self._getTopLayer(item)
        return layer.__getitem__(item)

    def __setitem__(self, key, value):
        layer = self._getTopLayer(key)
        return layer.__setitem__(key, value)

    def __contains__(self, item):
        layer = self._getTopLayer(item)
        if layer:
            return layer.__contains__(item)
        return False

    def __dict__(self):
        return {k: self.__getitem__(k) for k in self.keys()}

    def __delitem__(self, key):
        for layer in self.layers:
            layer["props"].__delitem__(key)

    def keys(self):
        return set([key for l in self.layers for key in l["props"].keys()])
