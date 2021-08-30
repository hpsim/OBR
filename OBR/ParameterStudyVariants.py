# #!/usr/bin/env python3
from OBR.OpenFOAMCase import OpenFOAMCase
from subprocess import check_output
from . import MatrixSolver as ms
from . import EnviromentSetters as es
from .OpenFOAMCase import OpenFOAMCase
from . import setFunctions as sf


class Variant(OpenFOAMCase):  # At some point this inherits from Setter
    def __init__(self, root_dir, name, track_args):
        self.name = name
        super().__init__(root_dir / self.name / "base")
        self.valid = True
        self.track_args = track_args
        self.link_mesh = True


class MeshVariant(Variant):
    def __init__(
            self,
            root_dir,
            name,
            cell_ratio,
            controlDictArgs,
            track_args):
        super().__init__(root_dir, name, track_args)
        self.prepare_controlDict = es.PrepareControlDict(
            self, cell_ratio, controlDictArgs
        )
        self.link_mesh = False


class LinearSolverVariant(Variant):
    def __init__(self, root_dir, name, track_args):
        super().__init__(root_dir, name, track_args)


class RefineMesh(MeshVariant):
    """ class that calls refineMesh several times """

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict[0]
        name = str(self.value)
        cell_ratio = 4 ** self.value
        print(input_dict)
        super().__init__(
            root_dir, name, cell_ratio, input_dict["controlDict"], track_args
        )
        self.track_args["resolution"] = self.value

    def set_up(self):
        self.prepare_controlDict.set_up()
        for _ in range(self.value):
            check_output(["refineMesh", "-overwrite"], cwd=self.path)


class ReBlockMesh(MeshVariant):
    """ class to set cells and  calls blockMesh  """

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict[0]
        name = str(self.value)

        cell_ratio = self.value / float(input_dict["block"].split()[0])
        self.input_dict = input_dict
        super().__init__(
            root_dir, name, cell_ratio, input_dict["controlDict"], track_args
        )
        self.track_args["resolution"] = self.value

    def set_up(self):
        self.prepare_controlDict.set_up()
        sf.set_cells(
            self.blockMeshDict,
            self.input_dict["block"],
            "{x} {x} {x}".format(x=str(self.value)),
        )
        print("run blockMesh", self.path)
        check_output(["blockMesh"], cwd=self.path)

        #
        cmd = [
            "mapFields",
            "../../../base",
            "-consistent",
            "-sourceTime",
            "latestTime"]
        check_output(cmd, cwd=self.path)


class ChangeMatrixSolver(Variant):
    """ class that calls refineMesh several times """

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        print(input_dict, value_dict)
        self.value = value_dict
        name = str("_".join(self.value))
        super().__init__(root_dir, name, track_args)
        self.input_dict = input_dict
        self.solver_setter = getattr(ms, value_dict[0])(
            self.path, input_dict["fields"], input_dict["defaults"]
        )
        self.solver_setter.preconditioner = getattr(ms, value_dict[1])()
        self.solver_setter.executor = getattr(ms, value_dict[2])()

        # check whether preconditioner and executor combinations are
        # supported/valid
        backend = self.solver_setter.executor.backend
        if backend in self.solver_setter.avail_backend_handler.keys():
            support = self.solver_setter.avail_backend_handler[backend]
            if self.solver_setter.preconditioner.name not in support["preconditioner"]:
                self.valid = False
        else:
            self.valid = False

    def set_up(self):
        self.solver_setter.set_up()
