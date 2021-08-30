#!/usr/bin/env python3

from OBR.Setter import Setter
from OBR.EnviromentSetters import PrepareOMPMaxThreads
from pathlib import Path
import OBR.setFunctions as sf


class SolverSetter(Setter):
    def __init__(self, path, solver_name, fields, defaults):

        super().__init__(
            path=path,
        )
        self.fields = fields
        self.solver = solver_name
        self.defaults = defaults
        self.supported_keys = [
            "tolerance",
            "relTol",
            "minIter",
            "maxIter",
            "smoother",
            "sort",
            "updateSysMatrix",
            "preconditioner",
            "executor",
        ]

    def set_up(self):
        for field in self.fields:
            if field == "U" and self.solver == "CG":
                solver = "BiCGStab"
            else:
                solver = self.solver

            matrix_solver = (
                self.avail_backend_handler[self.executor.backend]["prefix"] + solver
            )

            raw_solver_str = "solver " + matrix_solver + ";"
            for key in self.supported_keys:
                sub_dict = self.defaults[field]
                if key in sub_dict.keys():
                    raw_solver_str += "{} {};".format(key, str(sub_dict[key]))
                else:
                    try:
                        attr = getattr(self, key).name
                        raw_solver_str += "{} {};".format(key, attr)
                    except BaseException:
                        pass

            raw_solver_str = '"' + field + '.*"{ ' + raw_solver_str
            print(raw_solver_str)

            sf.clear_solver_settings(self.fvSolution, field)
            sf.sed(self.fvSolution, field + "{}", raw_solver_str)


# Executor


class Executor:
    """An Executor holds its own name and can be queried by the case runner from the case
    additionally might prepare the Case/Enviroment before the case is run
    """

    def __init__(self, name, backend):
        self.name = name
        self.backend = backend


class OFExecutor(Executor):
    def __init__(self, name):
        super().__init__(name, "OF")


class GKOExecutor(Executor):
    def __init__(self, name):
        super().__init__(name, "GKO")


class MPI(OFExecutor):
    def __init__(self):
        super().__init__(name="mpi")
        # self.num_ranks = num_ranks
        # self.enviroment_setter = DecomposePar(max_num_ranks)


class Reference(GKOExecutor):
    def __init__(self):
        super().__init__(name="reference")


class Serial(OFExecutor):
    def __init__(self):
        super().__init__(name="reference")


class OMP(GKOExecutor):
    def __init__(self, max_processes=4):
        super().__init__(name="omp")
        # self.enviroment_setter = PrepareOMPMaxThreads(max_processes)


class CUDA(GKOExecutor):
    def __init__(self):
        super().__init__(name="cuda")


class HIP(GKOExecutor):
    def __init__(self):
        super().__init__(name="hip")


# Preconditioner


class BJ:
    name = "BJ"


class DIC:
    name = "DIC"


class DILU:
    name = "DILU"


class FDIC:
    name = "FDIC"


class GAMG:
    name = "GAMG"


class Diag:
    name = "diagonal"


class NoPrecond:
    name = "none"


# Backend handler


class OF:

    name = "OF"
    executor_support = ["MPI", "Ref"]
    executor = None

    def __init__(self, prefix="P"):
        self.prefix = prefix


class GKO:

    name = "GKO"
    prefix = "GKO"
    executor_support = ["OMP", "CUDA", "Ref", "HIP"]
    executor = None

    def __init__(self):
        pass


# Solver


class CG(SolverSetter):
    def __init__(self, path, fields, defaults):
        super().__init__(path, "CG", fields, defaults)
        self.avail_backend_handler = {
            "OF": {
                "preconditioner": ["DIC", "FDIC", "GAMG", "Diag", "none"],
                "prefix": "P",
            },
            "GKO": {
                "preconditioner": ["BJ", "none"],
                "prefix": "GKO",
            },
        }


class BiCGStab(SolverSetter):
    def __init__(self, path, fields, defaults):
        super().__init__(path, "BiCGStab", fields, defaults)
        self.avail_backend_handler = {
            "OF": {
                "preconditioner": ["DIC", "FDIC", "GAMG", "Diag", "none"],
                "prefix": "P",
            },
            "GKO": {
                "preconditioner": ["BJ", "none"],
                "prefix": "GKO",
            },
        }


class smooth(SolverSetter):
    def __init__(
        self,
        base_path,
        field,
        case_name,
        solver_stub,
    ):
        name = "smooth"
        super().__init__(
            base_path=base_path,
            solver=name,
            field=field,
            case_name=case_name,
            solver_stub=solver_stub,
        )
        self.avail_backend_handler = {
            "OF": {"backend": OF(prefix=""), "preconditioner": []},
        }


class IR(SolverSetter):
    def __init__(self, path, fields, defaults):
        super().__init__(path, "IR", fields, defaults)
        self.avail_backend_handler = {
            "GKO": {
                "preconditioner": ["none"],
                "prefix": "GKO",
            },
        }
