#!/usr/bin/env python3

from Setter import Setter
from EnviromentSetters import PrepareOMPMaxThreads
from pathlib import Path
import setFunctions as sf


class SolverSetter(Setter):
    def __init__(self, backend, path, fields, defaults):

        super().__init__(
            path=path,
        )
        self.fields = fields
        self.defaults = defaults
        self.backend = backend

    def set_up(self):
        for field in [self.fields]:
            raw_solver_str = self.backend.emit_solver_dict()

            sf.clear_solver_settings(self.fvSolution, field)
            sf.set_block(self.fvSolution, field +
                         "{", "}", raw_solver_str, ["Final"])


class Backend:
    def __init__(
        self,
        solver_template,
    ):
        self.solver_template = solver_template

    def set_up(self):
        pass


class PETSC(Backend):
    name = "PETSC"
    option_defaults = {}
    valid_ = True

    def __init__(self, solver, preconditioner, executor, options=None):
        super().__init__(
            solver_template="""
    solver petsc;
    preconditioner petsc;

    petsc
    {{
        options
        {{
                ksp_type {solver};
                pc_type bjacobi;
                sub_pc_type {preconditioner};
        }}

        caching
        {{
                matrix
                {{
                    update always;
                }}

                preconditioner
                {{
                    update always;
                }}
        }}
    }}
    {options}
""",
        )
        import PETSC.solver as petscsolver

        self.solver = (getattr(petscsolver, solver)()
                       if solver in dir(petscsolver) else None)

        self.preconditioner = (
            getattr(petscsolver, preconditioner)()
            if preconditioner in dir(petscsolver)
            else None
        )

        if (not self.solver) or (not self.preconditioner):
            self.valid_ = False

        self.options_str = ""
        if options:
            self.options_str = "\n".join(
                ["\t{} {};".format(key, value) for key, value in options.items()]
            )

    def is_valid(self):
        return self.valid_

    def emit_solver_dict(self):
        return self.solver_template.format(
            solver=self.solver.name,
            preconditioner=self.preconditioner.name,
            options=self.options_str,
        )


class Ginkgo(Backend):
    name = "Ginkgo"
    option_defaults = {}
    valid_ = True

    def __init__(self, solver, preconditioner, executor, options=None):
        super().__init__(
            solver_template="""
    solver {solver};
    preconditioner
    {{
        preconditioner {preconditioner};
        {preconditioner_options}
    }}
    {options}
    executor {executor};
    verbose 1;
""",
        )
        import Ginkgo.solver as gkosolver

        self.solver = getattr(gkosolver, solver)(
        ) if solver in dir(gkosolver) else None

        self.preconditioner = (
            getattr(gkosolver, preconditioner)()
            if preconditioner in dir(gkosolver)
            else None
        )

        self.executor = (getattr(gkosolver, executor)()
                         if executor in dir(gkosolver) else None)

        if (not self.solver) or (not self.preconditioner) or (not self.executor):
            self.valid_ = False

        self.options_str = ""
        if options:
            self.options_str = "\n".join(
                ["\t{} {};".format(key, value) for key, value in options.items()]
            )

    def is_valid(self):
        return self.valid_

    def emit_solver_dict(self):
        return self.solver_template.format(
            solver=self.solver.name,
            preconditioner=self.preconditioner.name,
            executor=self.executor.name,
            preconditioner_options="",
            options=self.options_str,
        )


class OpenFOAM(Backend):
    name = "OpenFOAM"
    option_defaults = {}
    valid_ = True

    def __init__(self, solver, preconditioner, executor, options=None):
        super().__init__(
            solver_template="""
    solver {solver};
    preconditioner
    {{
        preconditioner {preconditioner};
        {preconditioner_options}
    }}
    {options}
""",
        )
        import OpenFOAM.solver as ofsolver

        self.solver = getattr(ofsolver, solver)(
        ) if solver in dir(ofsolver) else None

        self.preconditioner = (
            getattr(ofsolver, preconditioner)()
            if preconditioner in dir(ofsolver)
            else None
        )

        self.executor = (getattr(ofsolver, executor)()
                         if executor in dir(ofsolver) else None)

        if (not self.solver) or (not self.preconditioner):
            self.valid_ = False

        self.options_str = ""
        if options:
            self.options_str = "\n".join(
                ["\t{} {};".format(key, value) for key, value in options.items()]
            )

    def is_valid(self):
        return self.valid_

    def emit_solver_dict(self):
        return self.solver_template.format(
            solver=self.solver.name,
            preconditioner=self.preconditioner.name,
            preconditioner_options="",
            options=self.options_str,
        )
