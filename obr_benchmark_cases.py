#!/usr/bin/env python3
"""
    run ogl benchmarks

    Usage:
        obr_run_cases.py [options]

    Options:
        -h --help           Show this screen
        -v --version        Print version and exit
        --clean             Remove existing cases [default: False].
        --filter=<json> pass the parameters for given parameter study
        --folder=<folder>   Target folder  [default: Test].
        --test-run          Run every case only once [default: False]
        --min_runs=<n>      Number of applications runs [default: 3].
        --time_runs=<s>     Time to applications runs [default: 20].
        --fail_on_error     exit benchmark script when a run fails [default: False].
        --continue_on_failure continue running benchmark and timing even on failure [default: False].
        --report=<filename> Target file to store stats [default: report.csv].
        --results_folder=<foldername> Target folder to store stats and logs [default: .].
"""


from docopt import docopt
from OBR.metadata import versions
from OBR import setFunctions as sf
from OBR import CaseRunner as cr
from OBR import ResultsAggregator as ra
from pathlib import Path
import os
import json
import datetime
from subprocess import check_output

if __name__ == "__main__":
    metadata = {
        "node_data": {
            "host": sf.get_process(["hostname"]),
            "top": sf.get_process(["top", "-bn1"]).split("\n")[:15],
            "uptime": sf.get_process(["uptime"]),
            "libOGL.so": sf.get_process(
                ["md5sum", os.getenv("FOAM_USER_LIBBIN") + "/libOGL.so"]
            ),
        },
    }
    metadata.update(versions)
    print(metadata)

    arguments = docopt(__doc__, version=metadata["OBR_VERSION"])

    results = ra.Results(arguments["--results_folder"], arguments["--report"])
    results.write_comment([str(metadata)])
    start = datetime.datetime.now()
    for root, folder, files in os.walk(
            Path(arguments["--folder"]).expanduser()):

        if arguments.get("--filter"):
            filt = arguments.get("--filter").split(",")
            filt = [f in root for f in filt]
            if any(filt):
                continue
        if "obr.json" in files:
            case_runner = cr.CaseRunner(results, arguments)
            fn = Path(root) / "obr.json"
            with open(fn, "r") as parameters_handle:
                parameters_str = parameters_handle.read()
            solver_arguments = json.loads(parameters_str)
            case_runner.run(root, solver_arguments)
    end = datetime.datetime.now()

    results.write_comment(
        ["total run time {} minutes".format((end - start).total_seconds() / 60)]
    )
