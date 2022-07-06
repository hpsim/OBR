#!/usr/bin/env python3

from OpenFOAMCase import OpenFOAMCase
from pathlib import Path


class Setter(OpenFOAMCase):
    """base class to set case properties"""

    def __init__(self, path):

        super().__init__(path=path)

    def set_enviroment_setter(self, enviroment_setter):
        # TODO support a list of enviroment setters
        self.enviroment_setter = enviroment_setter
        self.enviroment_setter.path = self.path

    def set_up(self):
        """delegate the set_up call to enviroment setters"""
        self.enviroment_setter.set_up()

    def clean_up(self):
        self.enviroment_setter.clean_up()
        for other in self.others:
            other.clean_up()

    def __repr__(self):
        return self.name
