#!/usr/bin/env python3


class CG:
    name = "GKOCG"
    symmetric = True
    option_defaults = {}


class NoPrecond:
    name = "none"
    symmetric = True
    option_defaults = {}


class Reference:
    name = "reference"


class OMP:
    name = "omp"

    def __init__(self, max_processes=4):
        self.max_processes = max_processes


class CUDA:
    name = "cuda"


class HIP:
    name = "hip"


class DPCPP:
    name = "dpcpp"
