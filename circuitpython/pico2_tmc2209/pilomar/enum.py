#-----------------------------------------------------------------------------------------------
# Emulate Enum for Circuit Python
#-----------------------------------------------------------------------------------------------

class FakeEnumType(type):
    def __init__(self, name, bases, namespace):
        # print("FakeEnumType.__init__", self, name, bases)
        #self.enumclass = type(name, (FakeEnum,), {})
        super().__init__(name, bases, namespace)
    def __setattr__(self, name, value):
        # print("FakeEnumType.__setattr__")
        if not name.startswith('_'):
            raise AttributeError("Cannot reassign enum members")
        super().__setattr__(name, value)
    def __getattribute__(self, __name: str):
        # print("FakeEnumType.__getattribute__")
        if __name.startswith('_'):
            return super().__getattribute__(__name)
        return self(self.__dict__[__name])
    def __contains__(self, item):
        return item in self.__iter__()
    def __iter__(self):
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            try:
                yield self(value)
            except (TypeError, ValueError):
                pass    # Not a valid enum value


class Enum(FakeEnumType):

    def __init__(self, value):
        if isinstance(value, self.__class__):
            value = value.value
        else:
            self.value = value
        # print("FakeEnum.__init__")

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.value == other.value
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __repr__(self):
        return f"{self.__class__.__name__} {self.value}"
