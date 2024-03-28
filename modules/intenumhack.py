import enum

class IntEnumHack(enum.IntEnum):
    def __new__(cls, value, attrs: dict = None):
        self = int.__new__(cls, value)
        self._value_ = value
        # Add additional attributes
        if isinstance(attrs, dict):
            for key, value in attrs.items():
                setattr(self, key, value)
        return self
    def __init__(self, *args, **kwargs):
        cls = type(self)
        # Add index for use with _member_names_
        self._index_ = len(cls._member_names_)  # self is added later, so the length is up to the previous item, so not len() - 1
        # Replace spaces with _, - with __ and add _ in front if starting with a number. Allows using Enum._1_special__name in code for "1 special-name"
        new_name = "_" * self._name_[0].isdigit() + self._name_.replace(" ", "_").replace("-", "__")
        if new_name != self._name_:
            setattr(cls, new_name, self)
