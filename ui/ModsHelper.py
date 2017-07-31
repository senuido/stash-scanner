import json
import re

from lib.ModFilter import ModFilterType
from lib.ModFilterGroup import PSEUDO_MODS


class ModsHelper:
    MODS_FNAME = 'res\\mods.json'
    MOD_TEXT_REGEX = re.compile('\(([^()]+)\)\s+(.*)')

    def __init__(self):
        self.mod_list = None
        self.mod_set = None

    def load(self):
        mod_set = set()
        mod_list = []

        cat_ordered = ['[pseudo] mods', '[total] mods', 'explicit', 'crafted', 'implicit', 'enchantments',
                       'unique explicit', 'map mods', 'prophecies', 'leaguestone']
        cat_ignore = []

        with open(self.MODS_FNAME) as f:
            data = json.load(f)

        for cat in cat_ordered:

            if cat in cat_ignore:
                continue

            cat_mods = []

            for mod in data['mods'][cat]:
                mod_type, text = self.textToMod(mod)
                if mod_type == ModFilterType.Pseudo and text not in PSEUDO_MODS:
                    # convert mod to a non-psuedo if it has another tag
                    inner_tag, inner_text = self._getTagText(text)
                    if inner_tag is None:
                        continue
                    mod = text

                cat_mods.append(mod)

            for mod in sorted(cat_mods):
                mod_set.add(mod)
                if len(mod_set) > len(mod_list):
                    mod_list.append(mod)

        self.mod_list = mod_list
        self.mod_set = mod_set

    def modToText(self, mod_type, expr):
        if mod_type == ModFilterType.Pseudo:
            pat = expr
        else:
            pat = expr.replace('([0-9]+)', '#')
            pat = pat.replace('\+', '+')  # un-escape characters
            if pat.endswith('$'):
                pat = pat[:-1]

        if mod_type == ModFilterType.Explicit:
            return pat
        return '({}) {}'.format(mod_type.value, pat)

    def isCustom(self, mod_type, expr):
        return self.modToText(mod_type, expr) not in self.mod_set

    def isPredefined(self, mod_text):
        return mod_text in self.mod_set

    def textToMod(self, mod_text):
        tag, text = self._getTagText(mod_text)
        if tag is None:
            mod_type = ModFilterType.Explicit
        else:
            mod_type = ModFilterType(tag)

        expr = text
        if expr and mod_type != ModFilterType.Pseudo:
            expr = expr.replace('+', '\+')  # escape characters
            expr = expr.replace('#', '([0-9]+)') + '$'

        return mod_type, expr

    def _getTagText(self, text):
        match = self.MOD_TEXT_REGEX.match(text)
        if match:
            return match.groups()
        return None, text

    def stripTags(self, mod_text):
        while True:
            tag, mod_text = self._getTagText(mod_text)
            if tag is None:
                return mod_text

mod_helper = ModsHelper()