#!/usr/bin/env python3
import flow
import os
import sys
import obr.core.caseOrigins as caseOrigins
import traceback
import logging
import json
import shutil

from pathlib import Path
from subprocess import check_output
from signac.job import Job
from typing import Union, Literal
from datetime import datetime

from .labels import owns_mesh, final, finished
from ..core.core import (
    execute_shell,
    GLOBAL_INIT_COUNT,
    map_view_folder_to_job_id,
)  # noqa
from obr.OpenFOAM.case import OpenFOAMCase
from obr.core.queries import filter_jobs, query_impl, Query, statepoint_get
from obr.core.caseOrigins import instantiate_origin_class

logger = logging.getLogger("OBR")


class OpenFOAMProject(flow.FlowProject):
    filtered_jobs: list[Job] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def print_operations(self):
        ops = sorted(self.groups.keys())
        logger.info("Available operations are:\n\t" + "\n\t".join(ops))
        return

    def filter_jobs(self, filters: list[str]) -> list[Job]:
        """`filter_jobs` accepts a list of filters.

        The filters will be applied to all jobs inside the `OpenFOAMProject` instance and the filtered jobs will be returned as a list.
        """
        self.filtered_jobs = (
            filter_jobs(self, filters) if filters else [j for j in self]
        )
        return self.filtered_jobs

    def query(self, jobs: list[Job], query: list[Query]) -> list[dict]:
        """return list of job ids as result of `Query`."""
        return query_impl(jobs, query, output=True)

    def set_entrypoint(self, entrypoint: dict):
        """Sets the entrypoint for a project, this is useful for submit so that
        submit writes scripts that call obr run -o <args> instead of the default signac run -o <args>
        call
        """
        self._entrypoint = entrypoint

    def group_jobs(self, jobs, view_id_map: dict[str, str], summarize: int = 0) -> dict[str, list[str]]:
        """Returns the list of jobs of the given OpenFOAMProject where the last `summarize` levels are grouped together at the corresponding parent view.
        Returns a `dict[str, list[str]]` which maps the view path to a list of child jobs. 
        """
        group: dict[str, list] = dict()
        for job in jobs:
            jobid = job.id
            p_view = view_id_map.get(jobid)
            if not p_view:
                continue
            # "traverse" the view tree bottom up -> remove the last n parts
            p_view = p_view.rsplit("/", summarize)[0]
            if p_view not in group:
                group[p_view] = []
            group[p_view].append(job)
        return group


generate = OpenFOAMProject.make_group(name="generate")
simulate = OpenFOAMProject.make_group("execute")


def is_case(job: Job) -> bool:
    has_ctrlDict = job.isfile("case/system/controlDict")
    return has_ctrlDict


def is_job(job: Job) -> bool:
    """checks OBR_JOB is set to the current job.id used to prevent multiple
    execution of jobs if --job=id is set"""
    skip_job = os.environ.get("OBR_JOB")
    if skip_job and not str(job.id) == skip_job:
        return False
    return True


def operation_complete(job: Job, operation: str) -> bool:
    """An operation is considered to be complete if an entry in the job document with same arguments exists and state is success"""
    if job.doc["state"].get("global") == "ready":
        return True
    else:
        return False


def basic_eligible(job: Job, operation: str) -> bool:
    """Dispatches to standard checks if operations are eligible for given job

    this includes:
      - check for lock, to avoid running operations when calling 'obr run'
        before operation is finished
      - check if parent case is ready
      - operation has been requested for job
      - copy and link files and folder
    """

    if (
        is_locked(job)
        or not operation == job.sp().get("operation")
        or not parent_job_is_ready(job) == "ready"
        or not initialize_if_required(
            job
        )  # keep this here start initialization only if operation is requested
        or not is_case(job)
    ):
        # For Debug purposes
        if False and (operation == job.sp().get("operation")):
            logger.info(f"check if job {job.id} is eligible is False")
            if is_locked(job):
                logger.info(f"\tis_locked=True, should be False")
            if not parent_job_is_ready(job) == "ready":
                state = parent_job_is_ready(job)
                logger.info(f"\tparent_job_is_ready={state} should be ready")
            if not initialize_if_required(job):
                logger.info(f"\tinitialize_if_required=False should be True")
            if not is_case(job):
                logger.info("\tis_case=False should be True")
        return False
    return True


def parent_job_is_ready(job: Job) -> str:
    """Checks whether the parent of the given job is ready"""
    if parent_id := job.sp().get("parent_id"):
        project = OpenFOAMProject.get_project(path=job.path + "/../..")
        with open(job.path + f"/../{parent_id}/signac_job_document.json", "r") as jh:
            parent_job_dict = json.load(jh)
            return parent_job_dict["state"].get("global", "")
    return ""


def _link_path(base: Path, dst: Path, parent_id: str, copy_instead_link: bool):
    """creates file tree under dst with same folder structure as base but all
    files are relative symlinks
    """
    # NOTE if copy instead linking is requested we
    # just copy the full tree and are done
    if copy_instead_link:
        if dst.exists():
            shutil.rmtree(f"{dst}")
        shutil.copytree(src=f"{base}", dst=f"{dst}", symlinks=False)
        return

    # ensure dst path exists
    check_output(["mkdir", "-p", str(dst)])
    for root, folder, files in os.walk(Path(base)):
        relative_path = Path(root).relative_to(base)

        # NOTE Treat processor folder separately
        # Dont recurse into processor folders for now since that can
        # become very costly. Instead we copy all processor folder
        # entirely and pop the folder from the folder list
        if "processor0" in folder:
            for fold in folder:
                if not fold.startswith("processor"):
                    continue
                proc_root, proc_folder, _ = next(os.walk(f"{base}/{fold}"))
                # NOTE The constant folder is linked
                # to reduce the resulting folder size
                trgt_proc_fold = f"{dst}/{fold}"
                for proc_cont in proc_folder:
                    if proc_cont == "constant":
                        check_output(["mkdir", "-p", trgt_proc_fold])
                        check_output(
                            [
                                "ln",
                                "-s",
                                # we can use this folder format here because
                                # we know where the parent job lies relative
                                # to this one in the workspace
                                f"../../../{parent_id}/case/{fold}/constant",
                            ],
                            cwd=trgt_proc_fold,
                        )
                    else:
                        shutil.copytree(
                            src=f"{proc_root}/{proc_cont}",
                            dst=f"{trgt_proc_fold}/{proc_cont}",
                            symlinks=False,
                        )
            # pop all processor folder to avoid recursing
            pop_idx = [i for i, f in enumerate(folder) if f.startswith("processor")]
            for i in sorted(pop_idx, reverse=True):
                del folder[i]

        for fold in folder:
            src = Path(root) / fold
            dst_ = dst / relative_path / fold
            if not dst_.exists():
                check_output(
                    [
                        "mkdir",
                        fold,
                    ],
                    cwd=dst / relative_path,
                )

        for fn in files:
            src = Path(root) / fn
            dst_ = Path(dst) / relative_path / fn
            if not dst_.exists():
                check_output(
                    [
                        "ln",
                        "-s",
                        str(os.path.relpath(src, dst / relative_path)),
                    ],
                    cwd=dst / relative_path,
                )


def needs_initialization(job: Job) -> bool:
    """Check if this job has been initialized already, without performing the initialization"""
    if parent_id := job.sp().get("parent_id"):
        if job.doc["state"].get("is_initialized"):
            return False
    return True


def initialize_if_required(job: Job) -> bool:
    """check if this job has been already linked to

    The default strategy is to link all files. If a file is modified
    the modifying operations are responsible for unlinking and copying
    """
    if parent_id := job.sp().get("parent_id"):
        if job.doc["state"].get("is_initialized"):
            return True
        global GLOBAL_INIT_COUNT
        GLOBAL_UNINIT_COUNT = os.environ.get("GLOBAL_UNINIT_COUNT")

        GLOBAL_INIT_COUNT += 1
        base_path = Path(job.path).parent / parent_id / "case"
        dst_path = Path(job.path) / "case"
        # logger.info(f"linking {base_path} to {dst_path}")
        # shell scripts might change files as side effect hence we copy all files
        # instead of linking to avoid side effects in future it might make sense to
        # specify the files which are modified in the yaml file
        copy_instead_link = job.sp().get("operation") == "shell"
        _link_path(base_path, dst_path, parent_id, copy_instead_link)
        job.doc["state"]["is_initialized"] = True
        if GLOBAL_UNINIT_COUNT:
            logger.info(
                "Done initialization of case"
                f" {job.id} [{GLOBAL_INIT_COUNT}/{int(GLOBAL_UNINIT_COUNT)}]\r"
            )
        return True
    else:
        return False


def get_args(job: Job, args: Union[dict, str]) -> Union[dict, str]:
    """operation can get args either via function call or it statepoint
    if no args are passed via function the args from the statepoint are taken

    also args can be just a str in case of shell scripts
    """
    if isinstance(args, dict):
        return (
            {key: value for key, value in args.items()}
            if args
            else {key: job.sp()[key] for key in job.sp().get("keys", [])}
        )
    else:
        return args


def execute_operation(job: Job, operation_name: str, operations) -> Literal[True]:
    """check whether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary

    """
    if not operations:
        return True
    for operation in operations:
        try:
            if isinstance(operation, str):
                getattr(sys.modules[__name__], operation)(job)
            else:
                func = list(operation.keys())[0]
                getattr(sys.modules[__name__], func)(job, operation.get(func))
        except Exception as e:
            tb = traceback.format_exc()
            logger.info(tb)
            logger.error(e)
            job.doc["state"]["global"] == "failure"
    return True


def execute_post_build(operation_name: str, job: Job):
    """check whether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary
    """
    operations = job.sp.get("post_build", [])
    execute_operation(job, operation_name, operations)


def execute_pre_build(operation_name: str, job: Job):
    """check whether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary
    """
    operations = job.sp.get("pre_build", [])
    execute_operation(job, operation_name, operations)


def start_job_state(_, job: Job) -> None:
    current_state = job.doc["state"].get("global")
    if not current_state:
        job.doc["state"]["global"] = "started"
    elif current_state == "started":
        # job has been started but not finished yet
        job.doc["state"]["global"] = "tmp_lock"


def end_job_state(_, job: Job) -> Literal[True]:
    job.doc["state"]["global"] = "ready"
    return True


def dispatch_pre_hooks(operation_name: str, job: Job):
    """just forwards to start_job_state and execute_pre_build"""
    start_job_state(operation_name, job)
    execute_pre_build(operation_name, job)


def dispatch_post_hooks(operation_name: str, job: Job):
    """Forwards to `execute_post_build`, performs md5sum calculation of case files and finishes with `end_job_state`"""
    execute_post_build(operation_name, job)
    case = OpenFOAMCase(str(job.path) + "/case", job)
    case.perform_post_md5sum_calculations()
    end_job_state(operation_name, job)


def set_failure(operation_name: str, error, job: Job):
    """just forwards to start_job_state and execute_pre_build"""
    job.doc["state"]["global"] = "failure"


def copy_on_uses(args: dict, job: Job, path: str, target: str):
    """copies the file specified in args['uses'] to path/target"""
    if isinstance(args, str):
        return
    if uses := args.pop("uses", False):
        if path:
            check_output([
                "cp",
                "{}/case/{}/{}".format(job.path, path, uses),
                "{}/case/{}/{}".format(job.path, path, target),
            ])
        else:
            src_path = "{}/case/{}".format(job.path, uses)
            trg_path = "{}/case/{}".format(job.path, target)
            # It should be alright if the source path does not exists
            # as long as the target path exists
            if not Path(trg_path).exists() and Path(src_path).exists():
                check_output(["cp", "-r", src_path, trg_path])


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "controlDict"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "controlDict"))
@OpenFOAMProject.operation
def controlDict(job: Job, args={}):
    """sets up the controlDict"""
    # TODO gets args either from function arguments if function
    # was called directly from a pre/post build or from sp
    # if this was a variation. In any case this could be a decorator
    args = get_args(job, args)
    copy_on_uses(args, job, "system", "controlDict")
    OpenFOAMCase(str(job.path) + "/case", job).controlDict.set(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: job.sp().get("operation") == "MultiCase")
@OpenFOAMProject.post(lambda job: operation_complete(job, "MultiCase"))
@OpenFOAMProject.operation
def MultiCase(job: Job, args={}):
    """Dummy operation to generate multiple cases"""
    args = get_args(job, args)
    copy_on_uses(args, job, "system", "controlDict")
    if not args.get("type"):
        raise AssertionError(
            "Please specify a type for the MultiCase. Valid types: GitRepo, CaseOnDisk,"
            " OpenFOAMTutorialCase"
        )
    if not (Path(job.path) / "case").exists():
        instantiate_origin_class(args["type"], args).init(job.path)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "blockMesh"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "blockMesh"))
@OpenFOAMProject.operation
def blockMesh(job: Job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).blockMesh(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "shell"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "shell"))
@OpenFOAMProject.operation
def shell(job: Job, args={}):
    args = get_args(job, args)
    # if called from post build args are just a string
    if isinstance(args, dict):
        steps = [f"{k} {v}".replace("_dot_", ".") for k, v in args.items()]
    else:
        steps = [args]
    execute_shell(steps, job)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "zero"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "zero"))
@OpenFOAMProject.operation
def initialConditions(job: Job, args={}):
    """A special operation to allow copying from 0.orig folders"""
    args = get_args(job, args)
    copy_on_uses(args, job, "", "0")


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "fvSolution"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "fvSolution"))
@OpenFOAMProject.operation
def fvSolution(job: Job, args={}):
    args = get_args(job, args)
    copy_on_uses(args, job, "system", "fvSolution")
    if args:
        OpenFOAMCase(str(job.path) + "/case", job).fvSolution.set(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "fvSchemes"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "fvSchemes"))
@OpenFOAMProject.operation
def fvSchemes(job: Job, args={}):
    args = get_args(job, args)
    copy_on_uses(args, job, "system", "fvSchemes")
    if args:
        OpenFOAMCase(str(job.path) + "/case", job).fvSchemes.set(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "transportProperties"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "transportProperties"))
@OpenFOAMProject.operation
def transportProperties(job: Job, args={}):
    args = get_args(job, args)
    copy_on_uses(args, job, "constant", "transportProperties")
    if args:
        OpenFOAMCase(str(job.path) + "/case", job).transportProperties.set(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "turbulenceProperties"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "turbulenceProperties"))
@OpenFOAMProject.operation
def turbulenceProperties(job: Job, args={}):
    args = get_args(job, args)
    copy_on_uses(args, job, "constant", "turbulenceProperties")
    if args:
        OpenFOAMCase(str(job.path) + "/case", job).turbulenceProperties.set(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "setKeyValuePair"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "setKeyValuePair"))
@OpenFOAMProject.operation
def setKeyValuePair(job: Job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).setKeyValuePair(args)


def has_mesh(job: Job) -> bool:
    """Check whether all mesh files are files (owning) or symlinks (non-owning)

    TODO check also for .obr files for state of operation"""
    fn = Path(job.path) / "case/constant/polyMesh"
    if not fn.exists():
        return False
    for f in ["boundary", "faces", "neighbour", "owner", "points"]:
        if not (fn / f).exists():
            return False
    return True


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "decomposePar"))
@OpenFOAMProject.pre(has_mesh)
@OpenFOAMProject.post(lambda job: operation_complete(job, "decomposePar"))
@OpenFOAMProject.operation
def decomposePar(job: Job, args={}):
    args = get_args(job, args)

    # NOTE don't try anything smart about reusing existing decompositions
    # if decompositions should be reused place decompositions in front
    # of your workflow file
    workspace_folder = Path(job.path) / "../"
    root, job_paths, _ = next(os.walk(workspace_folder))

    target_case = OpenFOAMCase(str(job.path) + "/case", job)
    target_case.decomposePar(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: not bool(job.sp().get("parent_id")))
@OpenFOAMProject.post(is_case)
@OpenFOAMProject.operation
def fetchCase(job: Job, args={}):
    args = get_args(job, args)
    if args["type"] == "MultiCase":
        return

    uses = args.pop("uses", [])
    case_type = job.sp["type"]
    fetch_case_handler = caseOrigins.instantiate_origin_class(case_type, args)
    if fetch_case_handler is None:  # invalid type was specified in yaml
        return
    fetch_case_handler.init(path=job.path)

    # if we find any entries in the list of 'uses' forward it to the
    # corresponding operation. This means we call the corresponding operation
    # with that specific value ie. uses: controlDict: controlDict.RANS will call
    # the controlDict operation with  {uses: controlDict.RANS} as arguments
    for entry in uses:
        for k, v in entry.items():
            getattr(sys.modules[__name__], k)(job, {"uses": v})


def is_locked(job: Job) -> bool:
    """Cases that are already started are set to tmp_lock
    dont try to execute them
    """
    return job.doc["state"].get("global") == "tmp_lock"


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "refineMesh"))
@OpenFOAMProject.pre(has_mesh)
@OpenFOAMProject.post(lambda job: operation_complete(job, "refineMesh"))
@OpenFOAMProject.operation
def refineMesh(job: Job, args={}):
    args = get_args(job, args)
    for _ in range(args.get("value")):
        OpenFOAMCase(str(job.path) + "/case", job).refineMesh(args)


@OpenFOAMProject.pre(parent_job_is_ready)
@OpenFOAMProject.pre(owns_mesh)
@OpenFOAMProject.operation
def allClean(job: Job, args={}):
    args = get_args(job, args)
    allCleanPath = Path(job.path) / "case/Allclean"
    if allCleanPath.exists():
        check_output(["./Allclean"], cwd=str(job.path) + "/case")


@OpenFOAMProject.pre(parent_job_is_ready)
@OpenFOAMProject.pre(owns_mesh)
@OpenFOAMProject.operation
def checkMesh(job: Job, args={}):
    args = get_args(job, args)
    log = OpenFOAMCase(str(job.path) + "/case", job).checkMesh(args)

    cells = (
        check_output(["grep", "cells:", Path(job.path) / "case" / log])
        .decode("utf-8")
        .split()[-1]
    )
    job.doc["cache"]["nCells"] = int(cells)


def get_number_of_procs(job: Job) -> int:
    """Deduces the number of processors
    For performance reasons the cache is used to store the number of subdomains
    """
    np = statepoint_get(job.sp(), "numberOfSubdomains")
    if np:
        return int(np)
    np = job.doc["cache"].get("numberOfSubdomains", False)
    if np:
        return int(np)
    # Reading from numberOfSubdomains from the decomposeParDict should
    # be the last resort since it is very expensive
    np = int(
        OpenFOAMCase(str(job.path) + "/case", job).decomposeParDict.get(
            "numberOfSubdomains"
        )
    )
    if np:
        job.doc["cache"]["numberOfSubdomains"] = np
    return np


def get_values(jobs: list, key: str) -> set:
    """find all different statepoint values"""
    values = [job.sp().get(key) for job in jobs if job.sp().get(key)]
    return set(values)


def run_cmd_builder(job: Job, cmd_format: str, args: dict) -> str:
    """Builds the cli command to run a OpenFOAM application"""

    skip_complete = os.environ.get("OBR_SKIP_COMPLETE")
    if skip_complete and finished(job):
        logger.info(f"Skipping Job {job.id} since it is completed.")
        return "true"

    case = OpenFOAMCase(str(job.path) + "/case", job)

    # if the case folder contains any modified files skip execution
    # if case.is_tree_modified():
    #     logging.info(f"Skipping Job {job.id} since it is has modified files.")
    #     job.doc["state"]["global"] = "dirty"
    #     return "true"

    solver = case.controlDict.get("application")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")

    res = job.doc["history"]

    cli_args = {
        "solver": solver,
        "path": job.path,
        "timestamp": timestamp,
        "np": get_number_of_procs(job),
    }
    cmd_str = cmd_format.format(**cli_args)
    res.append({
        "cmd": cmd_str,
        "type": "shell",
        "log": f"{solver}_{timestamp}.log",
        "state": "started",
        "timestamp": timestamp,
        "user": os.environ.get("USER"),
        "hostname": os.environ.get("HOST"),
    })
    job.doc["history"] = res

    cli_args = {
        "solver": solver,
        "path": job.path,
        "timestamp": timestamp,
        "np": get_number_of_procs(job),
    }
    preflight = os.environ.get("OBR_PREFLIGHT")
    if preflight:
        preflight_cmd = f"{preflight} > {job.path}/case/preflight_{timestamp}.log && "
        cmd_format = preflight_cmd + cmd_format

    postflight_cmd = f" && echo $? > {job.path}/case/solverExitCode.log "

    job.doc["state"]["global"] = "started"

    # NOTE we add || true such that the command never fails
    # otherwise if one execution would fail OBR exits and
    # the following solver runs would be discarded
    return cmd_format.format(**cli_args) + "|| true" + postflight_cmd


def validate_state_impl(_: str, job: Job) -> None:
    """Perform a detailed update of the job state"""
    case = OpenFOAMCase(Path(job.path) / "case", job)
    case.detailed_update()


@OpenFOAMProject.pre(parent_job_is_ready)
@OpenFOAMProject.pre(final)
@OpenFOAMProject.pre(is_job)
@OpenFOAMProject.operation
def resetCase(job: Job, args={}) -> None:
    """Dummy operation that calls resetCase"""
    case = OpenFOAMCase(Path(job.path) / "case", job)
    case.reset_case()


@OpenFOAMProject.pre(parent_job_is_ready)
@OpenFOAMProject.pre(final)
@OpenFOAMProject.pre(is_job)
@OpenFOAMProject.operation
def validateState(job: Job, args={}) -> None:
    """Dummy operation which forwards to validate_state_impl. The reason for keeping this function
    is that it can be called from the cli to force a detailed update"""
    validate_state_impl(job)


@simulate
@OpenFOAMProject.pre(final)
@OpenFOAMProject.pre(is_job)
@OpenFOAMProject.operation(
    cmd=True, directives={"np": lambda job: get_number_of_procs(job)}
)
@OpenFOAMProject.operation_hooks.on_exit(validate_state_impl)
def runParallelSolver(job: Job, args={}) -> str:
    env_run_template = os.environ.get("OBR_RUN_CMD")
    solver_cmd = (
        env_run_template
        if env_run_template
        else (
            "mpirun -np {np} {solver} -parallel -case {path}/case >"
            " {path}/case/{solver}_{timestamp}.log 2>&1"
        )
    )
    return run_cmd_builder(job, solver_cmd, args)


@simulate
@OpenFOAMProject.pre(final)
@OpenFOAMProject.pre(is_job)
@OpenFOAMProject.operation(cmd=True)
@OpenFOAMProject.operation_hooks.on_exit(validate_state_impl)
def runSerialSolver(job: Job, args={}):
    env_run_template = os.environ.get("OBR_SERIAL_RUN_CMD")
    solver_cmd = (
        env_run_template
        if env_run_template
        else "{solver} -case {path}/case > {path}/case/{solver}_{timestamp}.log 2>&1"
    )
    return run_cmd_builder(job, solver_cmd, args)


@OpenFOAMProject.operation
def archive(job: Job, args={}) -> Literal[True]:
    root, _, files = next(os.walk(Path(job.path) / "case"))
    fp = os.environ.get("OBR_CALL_ARGS", "")
    for fn in files:
        if fp not in fn:
            continue
        if (Path(root) / fn).is_symlink():
            continue
        check_output(["cp", "-r", f"{job.path}/case/{fn}", f"obr_store/{job.id}_{fn}"])
    return True


@OpenFOAMProject.operation(aggregator=flow.aggregator())
def apply(*jobs, args={}):
    import importlib.util

    fp = Path(os.environ.get("OBR_APPLY_FILE"))
    spec = importlib.util.spec_from_file_location("apply_func", fp)
    apply_functor = importlib.util.module_from_spec(spec)
    # sys.modules["apply_func"] = apply_functor
    spec.loader.exec_module(apply_functor)
    apply_functor.call(jobs)
