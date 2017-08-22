import copy
import json
import re
from datetime import datetime
from enum import IntEnum
from json import JSONEncoder

import jsonschema

from lib.CurrencyManager import cm
from lib.ItemClass import ItemClass
from lib.ModFilter import ModFilter, ModFilterType
from lib.ModFilterGroup import FilterGroupFactory, FilterGroupType, ModFilterGroup
from lib.Utility import AppException, get_verror_msg, RE_COMPILED_TYPE

_ITEM_TYPE = {0: 'normal',
              1: 'magic',
              2: 'rare',
              3: 'unique',
              4: 'gem',
              5: 'currency',
              6: 'divination card',
              7: 'quest item',
              8: 'prophecy',
              9: 'relic'}

_NAME_TO_TYPE = dict(map(reversed, _ITEM_TYPE.items()))


FILTER_VALIDATION_ERROR = "Error validating filter: {}"
FILTER_SCHEMA_ERROR = "Filter schema is invalid: {}"

class FilterPriority(IntEnum):
    Min = -10
    AutoBase = 0
    UserBase = 10
    Max = 50

class Filter:
    FILTER_SCHEMA_FNAME = "res\\filter.schema.json"
    FILTER_INVALID_PRICE = "Invalid price '{}' in filter {}"
    FILTER_INVALID_PRICE_BASE = "Invalid price in filter: {}. Expected filter ot have a base"
    FILTER_INVALID_REGEX = "Invalid regex: '{}' in filter {}. Error while compiling: {}"

    _FILTER_PRICE_REGEX = re.compile('\s*([+\-*/]?)\s*(.+)')
    _NUMBER_REGEX = re.compile('[0-9]+(?:\.[0-9]+)?$')

    schema_validator = None

    def __init__(self, title, criteria=None, enabled=True, category='', id='', base_id='', desc='',
                 priority=FilterPriority.UserBase.value):
        self.title = title
        self.criteria = criteria if criteria is not None else {}
        self.enabled = enabled
        self.category = category
        self.priority = priority
        self.description = desc

        self.id = id
        self.baseId = base_id

    @classmethod
    def init(cls):
        try:
            with open(Filter.FILTER_SCHEMA_FNAME) as f:
                schema = json.load(f)

            jsonschema.validate({}, schema)
        except jsonschema.ValidationError:
            cls.schema_validator = jsonschema.Draft4Validator(schema)
        except jsonschema.SchemaError as e:
            raise AppException('Failed loading filter validation schema.\n{}'.format(FILTER_SCHEMA_ERROR.format(e)))
        # except FileNotFoundError as e:
        except Exception as e:
            raise AppException('Failed loading filter validation schema.\n{}\n'
                               'Make sure the file are valid and in place.'.format(e))

    def validate(self):
        try:
            data = self.toDict()
            self.schema_validator.validate(data)
        except jsonschema.ValidationError as e:
            raise AppException(FILTER_VALIDATION_ERROR.format(get_verror_msg(e, data)))

        if self.criteria:
            for price in ('price_min', 'price_max'):
                if not self.baseId and price in self.criteria:
                    if not cm.isOverridePriceValid(self.criteria[price]):
                        raise AppException(Filter.FILTER_INVALID_PRICE.format(self.criteria[price], self.title))

                    if cm.isPriceRelative(self.criteria[price]):
                        raise AppException(Filter.FILTER_INVALID_PRICE_BASE.format(self.criteria[price]))

            try:
                fgs = [FilterGroupFactory.create(FilterGroupType(fg['type']), fg) for fg in self.criteria.get('fgs', [])]
                for fg in fgs:
                    for mf in fg.mfs:
                        if mf.type != ModFilterType.Pseudo:
                            re.compile(mf.expr)

            except re.error as e:
                raise AppException(Filter.FILTER_INVALID_REGEX.format(e.pattern, self.title, e))

            #TODO rairty/iclass validate?

    def compile(self, base={}):
        crit = self.criteria

        comp = dict(base)

        for key in crit:
            # if key == 'type':
            #     types = []
            #     for itype in crit['type']:
            #         for id in _ITEM_TYPE:
            #             if itype == _ITEM_TYPE[id]:
            #                 types.append(id)
            #                 break
            #     comp['type'] = types
            if key == 'rarity':
                comp[key] = [_NAME_TO_TYPE[itype] for itype in crit[key]]
            elif key == 'iclass':
                comp[key] = ItemClass[crit[key]]
            elif key == 'name':
                comp['name'] = [name.lower() for name in crit[key]]

            elif key in ('price_min', 'price_max'):
                comp[key] = cm.compilePrice(crit[key], comp.get(key, None))

            elif key == 'fgs':
                fgs = [FilterGroupFactory.create(FilterGroupType(fg['type']), fg) for fg in crit[key]]

                for fg in fgs:
                    for mf in fg.mfs:
                        if mf.type != ModFilterType.Pseudo:
                            mf.expr = re.compile(mf.expr)
                comp[key] = fgs
            else:
                comp[key] = crit[key]

        return comp

    @property
    def isChild(self):
        return self.baseId and self.baseId.lower() != self.id.lower()

    def isChildOf(self, fltr):
        return self.isChild and self.baseId.lower() == fltr.id.lower()

    def toDict(self):
        return {
                'title': self.title,
                'enabled': self.enabled,
                'category': self.category,
                'id': self.id,
                'baseid': self.baseId,
                'priority': self.priority,
                'description': self.description,
                'criteria': self.criteria}

    @classmethod
    def fromDict(cls, data):
        return cls(
            data.get('title', data.get('id', '')),
            data.get('criteria', {}),
            data.get('enabled', True),
            data.get('category', 'user'),
            data.get('id', ''),
            data.get('baseid', ''),
            data.get('description', ''),
            data.get('priority', FilterPriority.UserBase.value))

class FilterEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, RE_COMPILED_TYPE):
            return o.pattern
        if isinstance(o, (ModFilterGroup, Filter, ModFilter)):
            return o.toDict()
        if isinstance(o, FilterGroupType):
            return o.value
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


