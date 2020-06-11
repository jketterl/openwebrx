from abc import ABC, abstractmethod


class CommandMapper(object):
    def __init__(self, base=None, mappings=None, static=None):
        self.base = base
        self.mappings = {} if mappings is None else mappings
        self.static = static

    def map(self, values):
        args = [self.mappings[k].map(v) for k, v in values.items() if k in self.mappings]
        args = [a for a in args if a != ""]
        options = " ".join(args)
        command = "{0} {1}".format(self.base, options)
        command = command.format(p=values)
        if self.static is not None:
            command += " " + self.static
        return command

    def setMapping(self, key, mapping):
        self.mappings[key] = mapping
        return self

    def setMappings(self, mappings):
        for k, v in mappings.items():
            self.setMapping(k, v)
        return self

    def setBase(self, base):
        self.base = base
        return self

    def setStatic(self, static):
        self.static = static
        return self

    def keys(self):
        return self.mappings.keys()


class CommandMapping(ABC):
    @abstractmethod
    def map(self, value):
        pass


class Flag(CommandMapping):
    def __init__(self, flag):
        self.flag = flag

    def map(self, value):
        if value is not None and value:
            return self.flag
        else:
            return ""


class Option(CommandMapping):
    def __init__(self, option):
        self.option = option
        self.spacer = " "

    def map(self, value):
        if value is not None:
            if isinstance(value, str) and " " in value:
                template = '{option}{spacer}"{value}"'
            else:
                template = "{option}{spacer}{value}"
            return template.format(option=self.option, spacer=self.spacer, value=value)
        else:
            return ""

    def setSpacer(self, spacer):
        self.spacer = spacer
        return self
