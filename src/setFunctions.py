#!/usr/bin/env python3
import subprocess
import sys
from subprocess import check_output
import sys


def sed(fn, in_reg_exp, out_reg_exp, inline=True):
    """wrapper around sed"""
    if sys.platform == "darwin":
        ret = check_output(
            ["sed", "-i", "", "s/" + in_reg_exp + "/" + out_reg_exp + "/g", fn]
        )
    else:
        ret = check_output(
            ["sed", "-i", "s/" + in_reg_exp + "/" + out_reg_exp + "/g", fn]
        )


def clean_block_from_file(fn, block_starts, block_end, replace):
    """cleans everything from block_start to block_end and replace it"""
    with open(fn, "r") as f:
        lines = f.readlines()
    with open(fn, "w") as f:
        skip = False
        for line in lines:
            is_start = [block_start in line for block_start in block_starts]
            if any(is_start):
                skip = True
            if skip and block_end in line:
                skip = False
                f.write(replace)
            if not skip:
                f.write(line)


def read_block_from_file(fn, block_starts, block_end, excludes=None):
    ret = []
    with open(fn, "r") as f:
        lines = f.readlines()
        started = False
        for line in lines:
            is_start = [block_start in line for block_start in block_starts]
            if excludes:
                is_excluded = [exclude in line for exclude in excludes]
            if started:
                ret.append(line)
            if any(is_start) and not any(is_excluded):
                ret.append(line)
                started = True
            if started and block_end in line:
                return ret
    return []


def find_in_block(fn, field, keyword, default):
    block = read_block_from_file(fn, ['"' + field + '.*"', field + "\n"], "}")
    for line in block:
        for token in line.split(";"):
            if keyword in token:
                return token.split()[-1]
    return default


def get_executor(fn, field):
    return find_in_block(fn, field, "executor", "Serial")


def get_matrix_solver(fn, field):
    return find_in_block(fn, field, "solver", "unknown")


def get_preconditioner(fn, field):
    return find_in_block(fn, field, "preconditioner", "unknown")


def set_cells(blockMeshDict, old_cells, new_cells):
    """ """
    sed(blockMeshDict, old_cells, new_cells)


def set_mesh_boundary_type_to_wall(blockMeshDict):
    """ """
    print("DEPRECATED")
    sed(blockMeshDict, "type[  ]*cyclic", "type wall")


def set_p_init_value(p):
    """ """
    sed(p, "type[  ]*cyclic;", "type zeroGradient;")


def set_U_init_value(U):
    """ """
    sed(U, "type[  ]*cyclic;", "type fixedValue;value uniform (0 0 0);")


def add_libOGL_so(controlDict):
    with open(controlDict, "a") as ctrlDict_handle:
        ctrlDict_handle.write('libs ("libOGL.so");')


def get_process(cmd):
    try:
        return check_output(cmd).decode("utf-8")
    except Exception as e:
        print(e)


def get_end_time(controlDict):
    import re

    ret = check_output(["grep", "endTime", controlDict])
    ret = ret.decode("utf-8").replace(";", "").replace("\n", "")
    ret = re.compile(r"[.0-9]+").findall(ret)
    return ret[0]


def get_application_solver(controlDict):
    ret = check_output(["grep", "application", controlDict])
    return ret.decode("utf-8").split()[-1].replace(";", "")


def set_write_interval(controlDict, interval):
    sed(
        controlDict,
        "^writeInterval[ ]*[0-9.]*;",
        "writeInterval {};".format(interval),
    )


def set_number_of_subdomains(decomposeParDict, subDomains):
    print("setting number of subdomains", subDomains, decomposeParDict)
    sed(
        decomposeParDict,
        "numberOfSubdomains[ ]*[0-9.]*;",
        "numberOfSubdomains {};".format(subDomains),
    )


def set_end_time(controlDict, endTime):
    sed(controlDict, "^endTime[ ]*[0-9.]*;", "endTime {};".format(endTime))


def get_number_of_subDomains(case):
    import os

    _, folder, _ = next(os.walk(case))
    return len([f for f in folder if "processor" in f])


def read_block(blockMeshDict):
    import re

    ret = check_output(["grep", "hex", blockMeshDict]).decode("utf-8")
    num_cells = re.findall("[(][0-9 ]*[)]", ret)[1]
    return list(map(int, re.findall("[0-9]+", num_cells)))


def read_deltaT(controlDict):
    ret = (
        check_output(["grep", "deltaT", controlDict])
        .split()[-1]
        .decode("utf-8")
        .replace(";", "")
    )
    return float(ret)


def set_deltaT(controlDict, deltaT):
    sed(controlDict, "deltaT[ ]*[0-9.]*", "deltaT {}".format(deltaT))


def set_writeInterval(controlDict, writeInterval):
    sed(controlDict, "writeInterval[ ]*[0-9.]*", "writeInterval " + str(writeInterval))


def add_or_set_solver_settings(fvSolution, field, keyword, value, exclude=None):
    # TODO check if keyword is already present
    block = read_block_from_file(fvSolution, ['"' + field], "}", exclude)
    # clear_solver_settings(fvSolution, field)
    block.insert(1, "{} {};\n".format(keyword["name"], value))
    clean_block_from_file(fvSolution, [field + '.*"{'], "}\n", " ".join(block[:-1]))


def clear_solver_settings(fvSolution, field):
    clean_block_from_file(
        fvSolution,
        ["   {}\n".format(field), '"' + field + '.*"'],
        "  }\n",
        field + "{}\n",
    )


def ensure_path(path):
    print("creating", path)
    check_output(["mkdir", "-p", path])
