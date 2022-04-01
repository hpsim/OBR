# #!/usr/bin/env python3
from OpenFOAMCase import OpenFOAMCase
from subprocess import check_output
import multiprocessing
import MatrixSolver as ms
import EnviromentSetters as es
import setFunctions as sf


class Variant(OpenFOAMCase):  # At some point this inherits from Setter
    def __init__(self, root_dir, name, track_args, variant_of):
        self.name = name
        super().__init__(root_dir / self.name / "base")
        self.base = "../../../base"
        if variant_of:
            self.valid = False
            for variant in variant_of:
                if variant in str(root_dir):
                    self.valid = True
        else:
            self.valid = True
        self.track_args = track_args
        self.link_mesh = True


class MeshVariant(Variant):
    def __init__(
        self, root_dir, name, cell_ratio, controlDictArgs, track_args, variant_of
    ):
        super().__init__(root_dir, name, track_args, variant_of)
        self.prepare_controlDict = es.PrepareControlDict(
            self, cell_ratio, controlDictArgs
        )
        self.link_mesh = False
        self.map_fields = True


class ExistingCaseVariants(Variant):
    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict[0][1]
        name = str(self.value)
        self.build = input_dict.get("build", False)
        self.prepare_controlDict = es.PrepareControlDict(
            self, 1, input_dict["controlDict"]
        )
        super().__init__(
            root_dir,
            name,
            track_args,
            variant_of=input_dict.get("variant_of", False),
        )
        self.track_args["case_parameter"]["resolution"] = self.value
        self.link_mesh = False
        self.map_fields = False
        self.base = "../../../base/" + value_dict[0][0]

    def set_up(self):
        self.prepare_controlDict.set_up()

        # execute build command
        print("track args", self.track_args)
        if self.build:
            for step in self.build:
                try:
                    print(check_output(step.split(" "), cwd=self.path))
                except:
                    pass


class InitCase(Variant):
    """class that calls refineMesh several times"""

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict[0]
        input_dict["controlDict"]["write_last_timeStep"] = True
        self.blockMesh = input_dict.get("blockMesh")
        self.prepare_controlDict = es.PrepareControlDict(
            self, 1, input_dict["controlDict"]
        )
        name = str(self.value)
        super().__init__(
            root_dir,
            name,
            track_args,
            variant_of=input_dict.get("variant_of", False),
        )
        self.link_mesh = False
        self.map_fields = False

    def set_up(self):

        self.prepare_controlDict.set_up()
        # TODO dont hardcode
        if self.blockMesh:
            cmd = ["blockMesh"]

            print("running blockMesh for initial run")
            check_output(cmd, cwd=self.path)

        cmd = sf.get_application_solver(self.controlDict)
        print("running initial case")
        check_output(cmd, cwd=self.path)


class RefineMesh(MeshVariant):
    """class that calls refineMesh several times"""

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict[0]
        name = str(self.value)
        cell_ratio = 4 ** self.value
        self.link_mesh = False
        self.map_fields = True
        super().__init__(
            root_dir,
            name,
            cell_ratio,
            input_dict["controlDict"],
            track_args,
            variant_of=input_dict.get("variant_of", False),
        )
        self.track_args["case_parameter"]["resolution"] = self.value

    def set_up(self):
        self.prepare_controlDict.set_up()
        for _ in range(self.value):
            check_output(["refineMesh", "-overwrite"], cwd=self.path)

        # TODO check if mapFields is requested
        cmd = [
            "mapFields",
            "../../../base",
            "-consistent",
            "-sourceTime",
            "latestTime",
        ]

        print("mapping field")
        check_output(cmd, cwd=self.path)


class ReBlockMesh(MeshVariant):
    """class to set cells and  calls blockMesh"""

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict[0]
        name = str(self.value)

        cell_ratio = self.value / float(input_dict["block"].split()[0])
        self.input_dict = input_dict
        super().__init__(
            root_dir,
            name,
            cell_ratio,
            input_dict["controlDict"],
            track_args,
            variant_of=input_dict.get("variant_of", False),
        )
        self.track_args["case_parameter"]["resolution"] = self.value

    def set_up(self):
        self.prepare_controlDict.set_up()
        sf.set_cells(
            self.blockMeshDict,
            self.input_dict["block"],
            "{x} {x} {x}".format(x=str(self.value)),
        )
        print("run blockMesh", self.path)
        check_output(["blockMesh"], cwd=self.path)

        # TODO check if mapFields is requested

        if self.input_dict["mapFields"]:
            cmd = [
                "mapFields",
                "../../../base",
                "-consistent",
                "-sourceTime",
                "latestTime",
            ]
            print("mapping field")
        else:
            print("copying zero folder")
            cmd = ["cp", "-r", "../../../base/0", "."]

        check_output(cmd, cwd=self.path)


class ChangeMatrixSolver(Variant):
    """class that calls refineMesh several times"""

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict
        name = str("_".join(self.value))
        super().__init__(
            root_dir,
            name,
            track_args,
            variant_of=input_dict.get("variant_of", False),
        )
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
        field = input_dict["fields"][0]
        self.track_args["case_parameter"]["solver_" + field] = self.value[0]
        self.track_args["case_parameter"]["preconditioner_" + field] = self.value[1]
        self.track_args["case_parameter"]["executor_" + field] = self.value[2]

    def set_up(self):
        self.solver_setter.set_up()


# TODO this is a lot of duplicated boilerplate
class ChangeMatrixSolverProperties(Variant):
    """class that calls refineMesh several times"""

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict
        name = str(self.value[0])
        super().__init__(
            root_dir,
            name,
            track_args,
            variant_of=input_dict.get("variant_of", False),
        )
        self.input_dict = input_dict
        self.field = input_dict["field"]
        self.exclude = input_dict.get("exclude", "final")
        self.track_args["case_parameter"][input_dict["name"]] = self.value[0]

    def set_up(self):
        sf.add_or_set_solver_settings(
            self.fvSolution, self.field, self.input_dict, self.value[0], self.exclude
        )


class ChangeNumberOfSubdomains(Variant):
    """class that calls refineMesh several times"""

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict
        self.number_cores = self.value[0]
        if isinstance(self.number_cores, str):
            if self.number_cores == "fullNode":
                self.number_cores = int(multiprocessing.cpu_count() / 2)
        name = str(self.number_cores)
        super().__init__(
            root_dir,
            name,
            track_args,
            variant_of=input_dict.get("variant_of", False),
        )
        self.input_dict = input_dict
        self.track_args["case_parameter"][input_dict["name"]] = self.value[0]

    def set_up(self):

        sf.set_number_of_subdomains(self.decomposeParDict, self.number_cores)
