#!/usr/bin/python
"""
    run ogl benchmarks

    Usage:
        runBenchmark.py [options]

    Options:
        -h --help           Show this screen
        -v --version        Print version and exit
        --folder=<folder>   Target folder  [default: Test].
        --report=<filename> Target file to store stats [default: report.csv].
        --omp_max_threads=<n>   Set the number of omp threads [default: 1].
        --mpi_max_processes=<n> Set the number of mpi s [default: 1].
        --clean             Remove existing cases [default: False].
        --backend=BACKENDS  Select desired backends (e.g. OF,GKO)
        --solver=SOLVER     Select desired solvers (e.g. CG,BiCGStab,IR,smooth)
        --executor=EXECUTOR Select desired executor (e.g. CUDA,Ref,OMP,MPI)
        --preconditioner=PRECONDS  Select desired preconditioner (e.g. BJ,DIC)
        --mpi_max_procs=<n>  Set the number of mpi processes [default: 1].
        --field=FIELD       Set the field name to apply setup
        --test-run          Run every case only once [default: False]
        --min_runs=<n>      Number of applications runs [default: 5].
        --time_runs=<s>     Time to applications runs [default: 60].
        --fail_on_error     exit benchmark script when a run fails [default: False].
        --continue_on_failure continue running benchmark and timing even on failure [default: False].
        --project_path=<folder> Path to library which is benchmarked
        --include_log       Include log in report files [default: True].
        --parameters=<json> pass the parameters for given parameter study
        --renumber          Renumber mesh before running [default: False]
"""

from docopt import docopt
from subprocess import check_output
from pathlib import Path
import os
import shutil
import datetime
import json
from itertools import product, starmap
from functools import partial

from pathlib import Path
from OBR import ParameterStudy as ps
from OBR import CaseRunner as cr
from OBR import ResultsAggregator as ra


def parameter_study(test_path, matrix_solver, runner, fields, params):

    parameter_range = params["variation"]["range"]

    # TODO get case_name from Setter
    case_name = params["openfoam"]["case"]

    root_case = getattr(ps, params["openfoam"]["type"])(
        params["openfoam"]["origin"], runner.of_solver, case_name
    )

    # TODO make changing of boundary conditions non default
    # in CellSetter non default
    case_paths = [
        getattr(ps, params["variation"]["type"])(
            test_path,
            p,
            case_name,
            root_case,
            fields,
            params["variation"],
            params["openfoam"]["controlDict"],
        )
        for p in parameter_range
    ]

    parameter_study = ps.ParameterStudy(
        test_path, results, [case_paths, matrix_solver], runner
    )

    parameter_study.build_parameter_study()


if __name__ == "__main__":

    arguments = docopt(__doc__, version="runBench 0.1")
    print(arguments)

    solver = arguments["--solver"].split(",")
    backends = arguments["--backend"].split(",")
    preconditioner = arguments["--preconditioner"].split(",")
    executor = arguments["--executor"].split(",")
    fields = arguments["--field"].split(",")

    extra_args = {
        "OMP": {
            "max_processes": int(
                arguments["--omp_max_threads"])}}

    # for do a partial apply field="p"
    test_path = Path(arguments.get("--folder", "Test"))

    # read benchmark description file
    with open(
        arguments.get("--parameters", "benchmark.json"), "r"
    ) as parameters_handle:
        parameters_str = parameters_handle.read()

    # parse file
    parameter_study_arguments = json.loads(parameters_str)

    renumber = arguments.get("--renumber", False)

    parameter_study_arguments["variation"]["renumberMesh"] = renumber

    results = ra.Results(
        arguments.get("--report", "report.csv"),
        fields,
    )

    metadata = {
        "OBR_VERSION": "0.0.1",
        "renumbered": renumber,
    }

    results.write_comment([str(metadata)])

    runner = cr.CaseRunner(
        solver=parameter_study_arguments["openfoam"]["solver"],
        results_aggregator=results,
        arguments=arguments,
    )

    case_name = parameter_study_arguments["openfoam"]["case"]
    solver_stubs = parameter_study_arguments["openfoam"]["solver_stubs"]
    construct = partial(
        ps.construct, test_path, case_name, fields, solver_stubs, extra_args
    )

    # construct returns a tuple where  the first element is bool
    # indicating a valid combination of Domain and Solver and Executor
    # invalid combinations are filtered out here
    valid_solvers_tuples = filter(
        lambda x: x[0],
        starmap(
            construct,
            product(solver, backends, executor, preconditioner),
        ),
    )

    # just unpack the solver setters to a list
    matrix_solver = map(lambda x: x[1], valid_solvers_tuples)

    parameter_study(
        test_path,
        matrix_solver,
        runner,
        fields,
        parameter_study_arguments)
