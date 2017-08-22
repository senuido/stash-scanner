import json
from itertools import chain
from lib.ItemClass import ItemClass
from lib.Utility import AppException


class ItemCollection:
    BASE_TYPES_FNAME = 'res\\BaseItemTypes.json'

    base_types = {}
    base_type_to_id = {}
    SIX_LINK_EXCEPTIONS = ('The Goddess Unleashed Eternal Sword', 'Tabula Rasa Simple Robe', 'Skin of the Loyal Simple Robe', 'Skin of the Lords Simple Robe')

    @classmethod
    def init(cls):
        try:
            with open(cls.BASE_TYPES_FNAME) as f:
                data = json.load(f)

            cls.base_types = data
            cls.base_type_to_id = {base_type: class_id for class_id in data for base_type in data[class_id]}
        except Exception as e:
            raise AppException('Failed loading item base types.\n{}\n'
                               'Make sure the file are valid and in place.'.format(e))

    @classmethod
    def get_base_types_by_class(cls, item_class):
        classes = {iclass.name for iclass in ItemClass if item_class & iclass == iclass}
        bases = [cls.base_types.get(iclass, []) for iclass in classes]
        return list(chain.from_iterable(bases))
