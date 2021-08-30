#!/usr/bin/env python3

from pathlib import Path
import OBR.setFunctions as sf
from OBR.OpenFOAMCase import OpenFOAMCase
import os
from subprocess import check_output


class DefaultPrepareEnviroment:
    def __init__(self):
        pass

    def set_up(self):
        pass

    def clean_up(self):
        pass


class PrepareOMPMaxThreads(DefaultPrepareEnviroment):
    """ Sets the enviroment variable for OMP
    """

    def __init__(self, max_processes=1, multi=2):
        self.processes = []
        self.current_state = 0
        proc = 1
        while proc <= max_processes:
            self.processes.append(proc)
            proc *= multi
        print("PrepareOMPMaxThreads", self.processes)

    def set_up(self):
        print("setup", self.current_state, self.processes)
        processes = self.processes[self.current_state]
        print(
            "PrepareOMPMaxThreads use ",
            self.current_state,
            processes,
            " threads")
        os.environ["OMP_NUM_THREADS"] = str(processes)
        self.current_state += 1
        return processes

    def clean_up(self):
        self.current_state = 0


class CachePrepare(DefaultPrepareEnviroment):
    """ copies cases from a base """

    def __init__(self, path):
        """ prepare a cache folder for the target folder in path """
        self.path = path
        self.alternative_cache_path_ = None

    @property
    def cache_path(self):
        """ append cache to the current path name """
        path = self.path
        if self.alternative_cache_path_:
            path = self.alternative_cache_path_

        base_path = Path(path.parent).parent
        variant_name = path.parent.name
        case_name = self.path.name
        return base_path / (variant_name + "-cache") / case_name

    def set_up(self):
        target_path = self.path.parent
        sf.ensure_path(self.cache_path.parent)
        if not os.path.exists(self.cache_path):
            print("cache does not exist")
            check_output(["cp", "-r", self.root, self.cache_path])
            self.set_up_cache()

        # check if cache_path exists otherwise copy
        print("copying from", self.cache_path, " to ", target_path)
        sf.ensure_path(target_path)
        check_output(["cp", "-r", self.cache_path, target_path])


class PrepareControlDict:
    """ prepares the control dict of a case """

    def __init__(self, case, cell_ratio, controlDictArgs):
        """ cell_ratio """
        self.case = case
        self.cell_ratio = cell_ratio
        self.controlDictArgs = controlDictArgs

    def set_up(self):
        sf.add_libOGL_so(self.case.controlDict)

        # adapt deltaT for instationary cases
        if not self.controlDictArgs["stationary"]:
            deltaT = sf.read_deltaT(self.case.controlDict)
            new_deltaT = deltaT / self.cell_ratio
            sf.set_deltaT(self.case.controlDict, new_deltaT)
        else:
            new_deltaT = 1
        endTime = new_deltaT * self.controlDictArgs["timeSteps"]

        sf.set_end_time(self.case.controlDict, endTime)
        sf.set_writeInterval(self.case.controlDict, 10000)


class DecomposePar(CachePrepare):
    """ """

    def __init__(self, path, meshArgs):
        self.path = path
        self.current_state = 0
        if meshArgs.get("number_of_subdomains", false):
            self.number_of_subdomains = [meshArgs["number_of_subdomains"]]
        else:
            self.number_of_subdomains = list(
                range(
                    meshArgs["max_subdomains"],
                    meshArgs["subdomain_steps"]))

    def set_number_of_subdomains(self):
        sf.set_number_of_subdomains(
            self.path / "system" / "decomposeParDict",
            self.number_of_subdomains)

    def call_decomposePar(self):
        check_output(["decomposePar"], cwd=self.path)

    def set_up(self):
        self.set_number_of_subdomains()
        self.call_decomposePar()
        return self.number_of_subdomains


class CellsPrepare(CachePrepare):
    """ sets the number of cells or copies from a base to avoid remeshing """

    # TODO factor clearing solvers to separate classes

    def __init__(self, path, fields, meshArgs, controlDictArgs):
        super().__init__(path=path)
        self.cells = Path(path.parent).name
        self.fields = fields
        print("meshArgs", meshArgs)

        self.meshArgs = meshArgs
        self.controlDictArgs = controlDictArgs

    def set_up_cacheMesh(self):
        from copy import deepcopy

        print("setup cache", self.path)
        self.cache_case = OpenFOAMCase(self.cache_path)

        orig_cells = sf.read_block(self.cache_case.blockMeshDict)
        orig_cells_str = " ".join(map(str, deepcopy(orig_cells)))

        new_cells = "{} {} {}".format(self.cells, self.cells, self.cells)
        self.cell_ratio = float(self.cells) / orig_cells[0]
        sf.set_cells(self.cache_case.blockMeshDict, orig_cells_str, new_cells)

        print("Meshing", self.cache_case.path)
        check_output(["blockMesh"], cwd=self.cache_case.path)

        if self.meshArgs["renumberMesh"]:
            check_output(["renumberMesh", "-overwrite"],
                         cwd=self.cache_case.path)

        # FIXME check if mpi executor
        if self.meshArgs["decomposeMesh"]:
            DecomposePar(self.cache_case.path, self.meshArgs).set_up()

    def set_up_cache(self):

        # Mesh part
        self.set_up_cacheMesh()

        PrepareControlDict(
            self.cache_case, self.cell_ratio, self.controlDictArgs
        ).set_up()

        for field in self.fields:
            sf.clear_solver_settings(self.cache_case.fvSolution, field)

    def set_up(self):
        target_path = self.path.parent
        sf.ensure_path(self.cache_path.parent)
        if not os.path.exists(self.cache_path):
            print("cache does not exist")
            check_output(["cp", "-r", Path(self.root), self.cache_path])
            self.set_up_cache()

        # check if cache_path exists otherwise copy
        print("copying from", self.cache_path, " to ", target_path)
        sf.ensure_path(target_path)
        check_output(["cp", "-r", self.cache_path, target_path])

    def clean_up(self):
        pass


class RefineMeshPrepare(CachePrepare):
    """ sets the number of cells or copies from a base to avoid remeshing """

    # TODO factor clearing solvers to separate classes

    def __init__(self, path, refinements, fields, meshArgs, controlDictArgs):
        super().__init__(path=path)
        self.cells = Path(path.parent).name
        self.fields = fields
        self.refinements = refinements
        self.meshArgs = meshArgs
        self.controlDictArgs = controlDictArgs

    def set_up_cacheMesh(self):
        print("setup cache", self.path)
        self.cache_case = OpenFOAMCase(self.cache_path)

        print("Refining Mesh", self.cache_case.path)
        for _ in range(self.refinements):
            check_output(["refineMesh", "-overwrite"],
                         cwd=self.cache_case.path)

    def set_up_cache(self):
        self.set_up_cacheMesh()

        factor = 2 ** self.meshArgs["dimensions"]

        PrepareControlDict(
            self.cache_case, max(
                1, self.refinements * factor), self.controlDictArgs).set_up()

        for field in self.fields:
            sf.clear_solver_settings(self.cache_case.fvSolution, field)

    def clean_up(self):
        pass


class PathPrepare(CachePrepare):
    """ sets the number of cells or copies from a base to avoid remeshing """

    def __init__(self, path, fields):
        super().__init__(path=path)
        self.cells = Path(path.parent).name
        self.fields = fields

    def set_up_cache(self):
        print("setup cache", self.path)
        cache_case = OpenFOAMCase(self.cache_path)
        sf.add_libOGL_so(cache_case.controlDict)
        for field in self.fields:
            sf.clear_solver_settings(cache_case.fvSolution, field)
        print("Meshing", cache_case.path)
        check_output(["blockMesh"], cwd=cache_case.path)

    def clean_up(self):
        pass
