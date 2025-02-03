# settings.py
from configparser import ConfigParser
from pathlib import Path


class settings:

    def __init__(self):

        self.config = ConfigParser()

    def get(self, main: str, key: str, default_value=None, function=str):
        try:
            return function(self.config[main][key])
        except Exception:
            return function(default_value)

    def add_default(self, section: str, option: str, default_value):
        try:
            self.config.add_section(section)
        except Exception:
            pass

        self.config.set(section, option, default_value)

    def read(self, file_name):
        self.config.read(file_name)
