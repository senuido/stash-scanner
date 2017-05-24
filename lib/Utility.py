import os
from configparser import ConfigParser


class AppException(Exception):
    pass


class AppConfiguration(object):
    CONFIG_FNAME = "cfg\\app.cfg"
    section_names = ['Settings']
    defaults = {'league': 'Legacy',
                'request_delay': 0.5,
                'request_ahead_delay': 1,
                'notification_duration': 4}

    def __init__(self):
        parser = ConfigParser()
        #parser.optionxform = str  # make option names case sensitive
        found = parser.read(AppConfiguration.CONFIG_FNAME)

        if not found or AppConfiguration.section_names[0] not in parser.sections():
            parser[AppConfiguration.section_names[0]] = AppConfiguration.defaults
        else:
            values = dict(AppConfiguration.defaults)
            values.update(parser[AppConfiguration.section_names[0]])
            parser[AppConfiguration.section_names[0]] = values

        for section in parser.sections():
            if section not in AppConfiguration.section_names:
                parser.remove_section(section)

        os.makedirs(os.path.dirname(AppConfiguration.CONFIG_FNAME), exist_ok=True)
        with open(AppConfiguration.CONFIG_FNAME, mode="w") as f:
            parser.write(f)

        for name in AppConfiguration.section_names:
            self.__dict__.update(parser.items(name))

config = AppConfiguration()
