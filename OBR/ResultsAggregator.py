#!/usr/bin/env python3

from pathlib import Path
from OBR import setFunctions as sf
from subprocess import check_output
import os


class Results:
    """ A class to collect results and writ to a csv file """

    def __init__(self, fold, fn):
        self.fn = Path(fold) / fn
        self.log_fold = Path(fold) / "Logs"
        check_output(["mkdir", "-p", self.log_fold])

        self.columns = [
            "executor_p",
            "solver_p",
            "preconditioner_p",
            "executor_U",
            "solver_U",
            "preconditioner_U",
            "resolution",
            "omp_threads",
            "mpi_ranks",
            "node",
            "log_id",
            "setup_time",
            "run_time",
            "number_of_iterations_p",
            "number_of_iterations_U",
            "init_linear_solve_p",
            "linear_solve_p",
            "init_linear_solve_U",
            "linear_solve_U",
        ]

        self.current_col_vals = []
        self.report_handle = open(self.fn, "w", 1)
        self.report_handle.write(",".join(self.columns) + "\n")

    def write_comment(self, comment, prefix=""):
        for line in comment:
            self.report_handle.write("#" + line + "\n")

    def get_solver(self, case):
        return [
            sf.get_solver(case.fvSolution, "p"),
            sf.get_solver(case.fvSolution, "U"),
        ]

    def set_case(self, case, args):
        import socket

        self.current_col_vals = [
            sf.get_executor(case.fvSolution, "p"),
            sf.get_matrix_solver(case.fvSolution, "p"),
            sf.get_preconditioner(case.fvSolution, "p"),
            sf.get_executor(case.fvSolution, "U"),
            sf.get_matrix_solver(case.fvSolution, "U"),
            sf.get_preconditioner(case.fvSolution, "U"),
            args["resolution"],
            os.getenv("OMP_NUM_THREADS"),
            sf.get_number_of_subDomains(case.path),
            # args["processes"],
            socket.gethostname(),
        ]
        print(self.current_col_vals)

    def add(
        self,
        log,
        warm_up,
        run,
        iterations_p,
        iterations_U,
        init_time_p,
        init_time_u,
        linear_p,
        linear_U,
    ):
        """ Add results and success status of a run and write to file """
        outp = self.current_col_vals + [
            log,
            warm_up,
            run,
            iterations_p,
            iterations_U,
            init_time_p,
            init_time_u,
            linear_p,
            linear_U,
        ]
        outps = ",".join(map(str, outp))
        print("writing to report", outps)
        self.report_handle.write(outps + "\n")

    def close_file(self):
        close(self.report_handle)
