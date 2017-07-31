import copy
import re
from enum import Enum

from lib.Utility import RE_COMPILED_TYPE


class ModFilterType(Enum):
    Total = 'total'
    Implicit = 'implicit'
    Explicit = 'explicit'
    Crafted = 'crafted'
    Enchant = 'enchant'
    Prophecy = 'prophecy'
    Leaguestone = 'leaguestone'
    Pseudo = 'pseudo'

    # @classmethod
    # def fromName(cls, name):
    #     return _nameToType[name]

# _nameToType = {
#     'total': ModFilterType.Total,
#     'implicit': ModFilterType.Implicit,
#     'explicit': ModFilterType.Explicit,
#     'crafted': ModFilterType.Crafted,
#     'prophecy': ModFilterType.Prophecy,
#     'leaguestone': ModFilterType.Leaguestone
# }
#
# _typeToName = dict(reversed(item) for item in _nameToType.items())

class ModFilter:
    __slots__ = ['type', 'expr', 'min', 'max']

    def __init__(self, mod_type=ModFilterType.Total, expr='', min_val=None, max_val=None):
        self.type = mod_type
        self.expr = expr
        self.min = float(min_val) if min_val is not None else min_val
        self.max = float(max_val) if max_val is not None else max_val

    @classmethod
    def fromData(cls, data):
        return cls(ModFilterType(data['type']), data['expr'], data.get('min', None), data.get('max', None))

    def toDict(self):
        return {
            'type': self.type.value,
            'expr': self.expr,
            'min': self.min,
            'max': self.max
        }

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result

        for k in self.__slots__:
            v = getattr(self, k)
            if k == 'expr' and isinstance(v, RE_COMPILED_TYPE):
                setattr(result, k, re.compile(v.pattern))
            else:
                setattr(result, k, copy.deepcopy(v))
        return result
