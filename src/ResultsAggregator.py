#!/usr/bin/env python3

from pathlib import Path
import setFunctions as sf
from subprocess import check_output
import os


class Results:
    """A class to collect results and write to a csv file"""

    def __init__(self, fold, fn):
        self.fn = Path(fold) / fn
        self.log_fold = Path(fold) / "Logs"
        check_output(["mkdir", "-p", self.log_fold])

        self.current_col_vals = []
        self.comments = []

    def write_comment(self, comments, prefix="#"):
        for comment in comments:
            self.comments.append(prefix + comment + "\n")

    def get_solver(self, case):
        return [
            sf.get_matrix_solver(case.fvSolution, "p"),
            sf.get_matrix_solver(case.fvSolution, "U"),
        ]

    def set_case(self, case, execution_parameter, case_parameter):
        import socket

        self.current_col_vals.append(case_parameter)
        current = self.current_col_vals[-1]
        current["node"] = socket.gethostname()
        current["omp_threads"] = os.getenv("OMP_NUM_THREADS")
        current["mpi_ranks"] = sf.get_number_of_subDomains(case.path)

    def add(self, **kwargs):
        """Add results and success status of a run and write to file"""
        self.current_col_vals[-1].update(kwargs)
        self.write_to_disk()

    def write_to_disk(self):
        with open(self.fn, "w") as report_handle:

            default_header = [
                "executor_p",
                "solver_p",
                "preconditioner_p",
                "resolution",
                "omp_threads",
                "mpi_ranks",
                "node",
            ]

            default_data_columns = [
                "timestamp",
                "log_id",
                "run_time",
            ]

            header = []
            for vals in self.current_col_vals:
                for key in vals.keys():
                    header.append(key)
            header_all = set(header)
            extra_header = (set(header_all) - set(default_header)) - set(
                default_data_columns
            )

            for eh in extra_header:
                default_header.append(eh)

            for data_column in default_data_columns:
                default_header.append(data_column)

            data = []
            for vals in self.current_col_vals:
                data.append([vals.get(key, 0) for key in default_header])

            report_handle.write(",".join(default_header) + "\n")
            report_handle.write("".join(self.comments))

            for d in data:
                report_handle.write(",".join(map(str, d)) + "\n")

            print("[OBR] writing to report", data[-1])
