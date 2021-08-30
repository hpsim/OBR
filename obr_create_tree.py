#!/usr/bin/python
"""
    run ogl benchmarks

    Usage:
        runBenchmark.py [options]

    Options:
        -h --help           Show this screen
        -v --version        Print version and exit
        --clean             Remove existing cases [default: False].
        --parameters=<json> pass the parameters for given parameter study
        --folder=<folder>   Target folder  [default: Test].
        --init=<ts>         Run the base case for ts timesteps [default: 100].
"""

from docopt import docopt
import json

from pathlib import Path
from OBR import ParameterStudyTree as ps
from OBR import CaseOrigins as co
from OBR import setFunctions as sf
from OBR.metadata import versions


def process_benchmark_description(
        fn, metadata, supported_file_version="0.1.0"):
    import sys
    from packaging import version

    # read benchmark description file
    with open(fn, "r") as parameters_handle:
        parameters_str = parameters_handle.read()

    # parse file
    parameter_study_arguments = json.loads(parameters_str)

    if parameter_study_arguments["obr"]["OBR_MIN_VERSION"] > metadata["OBR_VERSION"]:
        print("The benchmark file needs a more recent version of OBR")
        sys.exit(-1)
    if (
        parameter_study_arguments["obr"]["BENCHMARK_FILE_VERSION"]
        < supported_file_version
    ):
        print("The benchmark file version is no longer supported")
        sys.exit(-1)
    return parameter_study_arguments


if __name__ == "__main__":
    metadata = versions

    arguments = docopt(__doc__, version=metadata["OBR_VERSION"])

    parameter_study_arguments = process_benchmark_description(
        arguments.get("--parameters", "benchmark.json"), metadata
    )

    track_args = {"resolution": 0, "processes": 1}

    pst = ps.ParameterStudyTree(
        Path(arguments["--folder"]),
        parameter_study_arguments,
        parameter_study_arguments["variation"],
        track_args,
        arguments.get("--init", 100),
        base=getattr(co, parameter_study_arguments["case"]["type"])(
            parameter_study_arguments["case"]
        ),
    )

    pst.set_up()
