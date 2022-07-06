#!/usr/bin/env python3
import subprocess
import sys
from subprocess import check_output
import sys
import math


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


def clean_block_from_file(fn, block_starts, block_end, replace, excludes=None):
    """cleans everything from block_start to block_end and replace it"""
    with open(fn, "r") as f:
        lines = f.readlines()
    is_excluded_block = False
    skip = False
    with open(fn, "w") as f:
        for line in lines:
            is_start = [block_start in line for block_start in block_starts]
            if excludes:
                is_excluded_block = any(
                    [exclude in line for exclude in excludes])
            if any(is_start) and not is_excluded_block:
                skip = True
            if not skip:
                f.write(line)
            if skip and block_end in line:
                if not is_excluded_block:
                    f.write(replace)
                    f.write("\t}\n")
                skip = False
                is_excluded_block = False


def set_block(fn, block_start, block_end, replace, excludes=None):
    """cleans everything from block_start to block_end and replace it"""
    with open(fn, "r") as f:
        lines = f.readlines()
    is_excluded_block = False
    skip = False
    with open(fn, "w") as f:
        for line in lines:
            is_start = block_start in line
            if excludes:
                is_excluded_block = any(
                    [exclude in line for exclude in excludes])
            if is_start and not is_excluded_block:
                skip = True
            if not skip:
                f.write(line)
            if skip and block_end in line:
                if not is_excluded_block:
                    f.write(block_start + replace)
                    f.write("\t}\n")
                skip = False
                is_excluded_block = False


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


def add_libs(controlDict, libs):
    with open(controlDict, "r") as f:
        lines = f.readlines()

    has_libs = any(["libs" in l for l in lines])

    with open(controlDict, "w") as ctrlDict_handle:
        for line in lines[:-1]:
            ctrlDict_handle.write(line)

        if not has_libs:
            ctrlDict_handle.write("libs (")
            for lib in libs:
                ctrlDict_handle.write('"' + lib + '" ')
            ctrlDict_handle.write(");")


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


def calculate_simple_partition(nSubDomains, decomp):

    def domains(x): return x[0] * x[1] * x[2]
    def remainder(x): return nSubDomains - domains(x)

    def next_position(x):
        if x[0] == x[1]:
            return 0
        if x[1] == x[2]:
            return 1
        return 2

    def isPrime(n):
        for i in range(2, n):
            if n % i == 0:
                return False, i  # i at this iteration is equal to the smallest factor
        return True, n

    i = next_position(decomp)
    is_prime, factor = isPrime(nSubDomains)

    if is_prime:
        decomp[i] *= factor
        return decomp
    if nSubDomains > 0:
        decomp[i] *= factor
        return calculate_simple_partition(int(nSubDomains / factor), decomp)
    else:
        return decomp


def set_number_of_subdomains_simple(decomposeParDict, subDomains):
    decomp = [1, 1, 1]
    partition = calculate_simple_partition(subDomains, decomp)
    partition.sort(reverse=True)
    partition = tuple(partition)
    print(
        "setting number of subdomains for simple decomposition",
        subDomains,
        partition,
        decomposeParDict,
    )
    sed(
        decomposeParDict,
        "numberOfSubdomains[ ]*[0-9.]*;",
        "numberOfSubdomains {};".format(subDomains),
    )
    sed(
        decomposeParDict,
        "method[ ]*[A-Za-z]*;",
        "method {};".format("simple"),
    )
    sed(
        decomposeParDict,
        "n[ ]*([0-9 ]*);",
        "n {};".format(str(partition).replace(",", " ")),
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
    sed(controlDict, "writeInterval[ ]*[0-9.]*",
        "writeInterval " + str(writeInterval))


def add_or_set_solver_settings(
        fvSolution,
        field,
        keyword,
        value,
        exclude=None):
    # TODO check if keyword is already present
    block = read_block_from_file(fvSolution, [field], "}", exclude)
    # clear_solver_settings(fvSolution, field)
    block_length = len(block)
    # TODO pop old value if exists
    old_key_pos = -1
    for i, keys in enumerate(block):
        if keyword["name"] in keys:
            old_key_pos = i
    if i >= 0:
        block.pop(old_key_pos)

    new_key_pos = old_key_pos if old_key_pos >= 1 else block_length - 1

    block.insert(new_key_pos, "{} {};\n".format(keyword["name"], value))
    clean_block_from_file(
        fvSolution, [field], "}\n", "\n".join(block[:-1]), exclude)


def clear_solver_settings(fvSolution, field):
    clean_block_from_file(
        fvSolution,
        ["   {}\n".format(field), '"' + field + '.*"'],
        "}\n",
        field + "{\n",
    )


def ensure_path(path):
    print("[OBR] creating", path)
    check_output(["mkdir", "-p", path])
