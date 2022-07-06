import setFunctions as sf
import CaseRunner as cr
import ResultsAggregator as ra
import os
import json
import datetime
from metadata import versions
from OpenFOAMCase import OpenFOAMCase
from pathlib import Path
from subprocess import check_output


def can_be_symlinked(path):
    path = Path(path)
    num_procs = path.parts[-2]
    variation_root = path / "../../../.."
    _, dirs, _ = next(os.walk(variation_root))
    for d in dirs:
        variation = variation_root / d / "mpiRank" / num_procs / "base" / "processor0"
        if variation.exists():
            return variation.parents[0].resolve()
    return False


def symlink_all_procs(link_base, current):
    link_base = Path(link_base)
    current = Path(current)
    _, dirs, _ = next(os.walk(link_base))
    procs = [proc for proc in dirs if "processor" in proc]
    if link_base == current:
        print("link_base is current target, skipping")
        return
    try:
        for proc in procs:
            Path(current / proc).symlink_to(link_base / proc, True)
    except Exception as e:
        print("can not symlink: ", e)


def decompose_tree(arguments):
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
    start = datetime.datetime.now()
    for root, folder, files in os.walk(Path(arguments["folder"]).expanduser()):
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
        if "mpiRank" not in root:
            continue
        if "obr.json" in files:
            symlink_base = can_be_symlinked(root)
            if ("processor0" in folder) and not arguments.get("force"):
                continue
            if symlink_base:
                print("symlinking", root, "to", symlink_base)
                symlink_all_procs(symlink_base, root)
            else:
                print("decomposing", root)
                ret = sf.check_output(["decomposePar", "-force"], cwd=root)
                with open("decompose.log", "w") as log_handle:
                    log_handle.write(ret.decode("utf-8"))

    end = datetime.datetime.now()
    print(
        "run all selected cases in {} minutes".format(
            (end - start).total_seconds() / 60
        )
    )
