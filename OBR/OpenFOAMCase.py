#!/usr/bin/env python3

from pathlib import Path
from . import setFunctions as sf


class OpenFOAMCase:
    """ A class for simple access to typical OpenFOAM files"""

    def __init__(self, path):
        self.path_ = Path(path)

    @property
    def path(self):
        return self.path_

    @property
    def system_folder(self):
        return self.path / "system"

    @property
    def zero_folder(self):
        return self.path / "0"

    @property
    def init_p(self):
        return self.zero_folder / "p"

    @property
    def init_U(self):
        return self.zero_folder / "U.orig"

    @property
    def controlDict(self):
        return self.system_folder / "controlDict"

    @property
    def blockMeshDict(self):
        return self.system_folder / "blockMeshDict"

    @property
    def fvSolution(self):
        return self.system_folder / "fvSolution"

    @property
    def endTime(self):
        return sf.get_end_time(self.controlDict)

    @property
    def deltaT(self):
        return sf.read_deltaT(self.controlDict)
