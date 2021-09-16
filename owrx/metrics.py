import threading
from owrx.client import ClientRegistry


class Metric(object):
    def getValue(self):
        return 0


class CounterMetric(Metric):
    def __init__(self):
        self.counter = 0

    def inc(self, increment=1):
        self.counter += increment

    def getValue(self):
        return {"count": self.counter}


class DirectMetric(Metric):
    def __init__(self, getter):
        self.getter = getter

    def getValue(self):
        return self.getter()


class Metrics(object):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with Metrics.creationLock:
            if Metrics.sharedInstance is None:
                Metrics.sharedInstance = Metrics()
        return Metrics.sharedInstance

    def __init__(self):
        self.metrics = {}
        self.addMetric("openwebrx.users", DirectMetric(ClientRegistry.getSharedInstance().clientCount))

    def addMetric(self, name, metric):
        name = name.replace(' ','_') 
        self.metrics[name] = metric

    def hasMetric(self, name):
        return name in self.metrics

    def getMetric(self, name):
        if not self.hasMetric(name):
            return None
        return self.metrics[name]

    def getFlatMetrics(self):
        return self.metrics

    def getHierarchicalMetrics(self):
        result = {}

        for (key, metric) in self.metrics.items():
            partial = result
            keys = key.split(".")
            for keypart in keys[0:-1]:
                if not keypart in partial:
                    partial[keypart] = {}
                partial = partial[keypart]
            partial[keys[-1]] = metric.getValue()

        return result
