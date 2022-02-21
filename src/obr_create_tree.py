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
import os
import re

from pathlib import Path
import ParameterStudyTree as ps
import CaseOrigins as co
import setFunctions as sf
from metadata import versions


def parse_variables(in_str, args, domain):

    ocurrances = re.findall(r"\${{" + domain + "\.(\w+)}}", in_str)
    for inst in ocurrances:
        in_str = in_str.replace("${{" + domain + "." + inst + "}}", args.get(inst, ""))
    return in_str


def process_benchmark_description(fn, metadata, supported_file_version="0.3.0"):
    import sys
    from packaging import version

    # read benchmark description file
    fn = Path(fn).expanduser()
    with open(fn, "r") as parameters_handle:
        parameters_str = parameters_handle.read()

    lines = parameters_str.split("\n")

    for line in lines:
        if not line:
            continue
        line = parse_variables(line, os.environ, "env")

    parameters_str = "\n".join(lines)

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


def obr_create_tree(arguments):

    parameter_study_arguments = process_benchmark_description(
        arguments.get("parameters", "benchmark.json"), versions
    )

    track_args = {"case_parameter": {"resolution": 0, "processes": 1}}

    pst = ps.ParameterStudyTree(
        Path(arguments["folder"]),
        parameter_study_arguments,
        parameter_study_arguments["variation"],
        track_args,
        base=getattr(co, parameter_study_arguments["case"]["type"])(
            parameter_study_arguments["case"]
        ),
    )

    pst.set_up()
