#!/usr/bin/env python3
"""
    run ogl benchmarks

    Usage:
        obr_run_cases.py [options]

    Options:
        -h --help           Show this screen
        -v --version        Print version and exit
        --np=<nd>           Number of sub domains.
        --folder=<folder>   Target folder  [default: Test].
        --filter=<json> pass the parameters for given parameter study
"""


from docopt import docopt
from OBR.metadata import versions
from OBR import setFunctions as sf
from OBR import CaseRunner as cr
from OBR import ResultsAggregator as ra
from OBR.OpenFOAMCase import OpenFOAMCase
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

    start = datetime.datetime.now()
    for root, folder, files in os.walk(
            Path(arguments["--folder"]).expanduser()):
        if arguments.get("--filter"):
            filt = arguments.get("--filter").split(",")
            filt = [f in root for f in filt]
            if any(filt):
                continue
        if "obr.json" in files:
            sf.set_number_of_subdomains(
                Path(root) / "system/decomposeParDict",
                arguments["--np"])
            sf.check_output(["decomposePar", "-force"], cwd=root)
    end = datetime.datetime.now()
    print(
        "run all selected cases in {} minutes".format(
            (end - start).total_minutes()))
