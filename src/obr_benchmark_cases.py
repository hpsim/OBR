#!/usr/bin/env python3

from docopt import docopt
from metadata import versions
import setFunctions as sf
import CaseRunner as cr
import ResultsAggregator as ra
from pathlib import Path
import os
import json
import datetime
from subprocess import check_output


def benchmark_cases(arguments):
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

    results = ra.Results(arguments["results_folder"], arguments["report"])
    results.write_comment([str(metadata)])
    start = datetime.datetime.now()
    for root, folder, files in os.walk(Path(arguments["folder"]).expanduser()):
        # dont descend in processor folder
        exclude = "processor"
        folder[:] = [d for d in folder if exclude not in d]

        if arguments.get("filter"):
            filt = arguments.get("filter").split(",")
            filt = [f in root for f in filt]
            if any(filt):
                continue

        if arguments.get("select"):
            filt = arguments.get("select").split(",")
            filt = [f in root for f in filt]
            if not all(filt):
                continue

        if "obr.json" in files:
            case_runner = getattr(cr, arguments["runner"])(results, arguments)
            fn = Path(root) / "obr.json"
            with open(fn, "r") as parameters_handle:
                parameters_str = parameters_handle.read()
            solver_arguments = json.loads(parameters_str)
            case_parameter = solver_arguments.get("case_parameter", {})
            case_runner.run(root, solver_arguments, case_parameter)
    end = datetime.datetime.now()

    results.write_comment(
        ["total run time {} minutes".format((end - start).total_seconds() / 60)]
    )
