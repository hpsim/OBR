#!/usr/bin/env python3
from OBR.EnviromentSetters import DefaultPrepareEnviroment
from itertools import product
from pathlib import Path
from subprocess import check_output
from copy import deepcopy
from OBR.Setter import Setter
from OBR.MatrixSolver import SolverSetter
from OBR.EnviromentSetters import CellsPrepare, PathPrepare, RefineMeshPrepare

from . import setFunctions as sf


class Remesh(Setter):
    def __init__(self, base_path, refinement, case_name, root, fields):
        self.cells = refinement
        self.root = root
        super().__init__(
            base_path=base_path,
            variation_name="{}".format(refinement),
            case_name=case_name,
        )

    def set_mesh_modifier(self, remesh):

        prepare_mesh = remesh
        prepare_mesh.root = self.root.path
        super().set_enviroment_setter(prepare_mesh)

    @property
    def cache_path(self):
        return self.enviroment_setter.base_path(
            str(self.cells)) / self.root.case


class ReBlockMesh(Remesh):
    """ class to set cells and  calls blockMesh  """

    def __init__(
        self,
        base_path,
        cells,
        case_name,
        root,
        fields,
        meshArgs,
        controlDictArgs,
    ):
        super().__init__(
            base_path,
            cells,
            case_name,
            root,
            fields,
        )

        self.set_mesh_modifier(
            CellsPrepare(
                self.path,
                fields,
                meshArgs,
                controlDictArgs,
            )
        )


class RefineMesh(Remesh):
    """ class that calls refineMesh several times """

    def __init__(
        self,
        base_path,
        refinements,
        case_name,
        root,
        fields,
        meshArgs,
        controlDictArgs,
    ):
        super().__init__(
            base_path,
            refinements,
            case_name,
            root,
            fields,
        )

        self.set_mesh_modifier(
            RefineMeshPrepare(
                self.path,
                refinements,
                fields,
                meshArgs,
                controlDictArgs,
            )
        )


class PathSetter(Setter):
    def __init__(self, base_path, path, case_name, root, fields):
        super().__init__(
            base_path=base_path,
            variation_name="{}".format(path),
            case_name=case_name,
        )
        prepare_mesh = PathPrepare(self.path, fields)
        prepare_mesh.root = root.path
        super().set_enviroment_setter(prepare_mesh)

    @property
    def cache_path(self):
        return self.enviroment_setter.base_path(
            str(self.cells)) / self.root.case


def construct(
    base_path,
    case_name,
    field,
    solver_stubs,
    extra_args,
    solver,
    domain,
    executor,
    preconditioner,
):
    """
    construct case variant from string arguments

    usage:
       solver = construct("CG", "GKO", "OMP")
    """
    from OBR.MatrixSolver import CUDAExecutor, RefExecutor, OMPExecutor, MPIExecutor
    import OBR.MatrixSolver as ms

    executor_inst = None
    if executor == "Ref":
        executor_inst = RefExecutor()
    if executor == "OMP":
        executor_inst = OMPExecutor(**extra_args[executor])
    if executor == "CUDA":
        executor_inst = CUDAExecutor()
    if executor == "MPI":
        executor_inst = MPIExecutor()

    solver_setter = getattr(
        ms,
        solver)(
        base_path,
        field,
        case_name,
        solver_stubs)
    try:
        # try to set domain this fails if the domain is not in the map
        # of domains which implement the given solver
        solver_setter.set_domain(domain)
        # try to set preconditioner this fails if the preconditioner is not in the map
        # of preconditioners domains which implement the given solver
        solver_setter.set_preconditioner(domain, preconditioner)
        if executor not in solver_setter.domain.executor_support:
            0 / 0
        solver_setter.set_executor(executor_inst)
        return True, solver_setter
    except Exception as e:
        return False, None


class OpenFOAMTutorialCase:
    def __init__(self, tutorial_domain, solver, case):
        self.tutorial_domain = tutorial_domain
        self.solver = solver
        self.case = case

    @property
    def path(self):
        import os

        foam_tutorials = Path(os.environ["FOAM_TUTORIALS"])
        return Path(
            foam_tutorials /
            self.tutorial_domain /
            self.solver /
            self.case)


class OpenFOAMExternalCase:
    def __init__(self, path, solver, case):
        self.path = path
        self.solver = solver
        self.case = case


class TestCase:
    def __init__(self, path, solver):
        self.path_ = path
        self.solver = solver

    @property
    def path(self):
        return Path(self.path_)


def combine(setters):
    """ combines a tuple of setters """
    primary = deepcopy(setters[0])
    primary.combine(setters[1])
    return primary


class ParameterStudy:
    """A class to create a range of cases and potentially run them

    Here parameter studies are created the following way. First,
    a set of cases is defined via
    """

    def __init__(self, test_path, results_aggregator, setters, runner):
        self.test_path = test_path
        self.results_aggregator = results_aggregator
        self.setters = setters
        self.runner = runner

    def build_parameter_study(self):
        # test_path, results, executor, setter, arguments):
        cases = product(*self.setters)
        cases_combined = map(combine, cases)
        for case in cases_combined:
            print("setting up", case)
            case.set_up()
            skip = False
            # clean = arguments["--clean"]
            # if exist and clean:
            #     shutil.rmtree(path)
            #     skip = False
            # if exist and not clean:
            #     skip = True
            # is_base_case = False
            # base_case_path = (
            #     test_path / Path("base") / Path("p-" + s.name) / str(n.value)
            # )
            self.runner.run(case)
