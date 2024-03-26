import json
import logging
import os
import sys
from copy import deepcopy
from pathlib import Path
from subprocess import check_output
from typing import Optional, Union, Any

from git.repo import Repo
from signac.job import Job

from .core.logger_setup import setup_logging
from .core.queries import Query, build_filter_query
from .signac_wrapper.operations import OpenFOAMProject

logger = logging.getLogger("OBR")


def query_impl(
    project: OpenFOAMProject,
    input_queries: tuple[str],
    filters: list[str],
    quiet: bool,
    json_file: str,
    validation_file: str,
):
    if input_queries == "":
        logger.warning("--query argument cannot be empty!")
        return
    queries: list[Query] = build_filter_query(input_queries)
    jobs = project.filter_jobs(filters=list(filters))
    query_results = project.query(jobs=jobs, query=queries)
    if not quiet:
        for job_id, query_res in deepcopy(query_results).items():
            out_str = f"{job_id}:"
            for k, v in query_res.items():
                out_str += f" {k}: {v}"
            logger.info(out_str)

    if json_file:
        with open(json_file, "w") as outfile:
            # json_data refers to the above JSON
            json.dump(query_results, outfile)
    if validation_file:
        with open(validation_file, "r") as infile:
            # json_data refers to the above JSON
            validation_dict = json.load(infile)
            if validation_dict.get("$schema"):
                logger.info("Using json schema for validation")
                from jsonschema import validate

                validate(query_results, validation_dict)
            else:
                from deepdiff import DeepDiff

                logger.info("Using deepdiff for validation")
                difference_dict = DeepDiff(validation_dict, query_results)

                if difference_dict:
                    logger.warn("Validation failed!")
                    logger.warn(difference_dict)
                    sys.exit(1)
            logger.success("Validation successful")


def check_cli_operations(
    project: OpenFOAMProject, operations: list[str], list_operations: Optional[Any]
) -> bool:
    """list available operations if none are specified or given the click option or an incorrect op is given"""
    if operations == ["generate"]:
        return True
    if list_operations:
        project.print_operations()
        return False
    elif not operations:
        logger.warning("No operation(s) specified.")
        project.print_operations()
        logger.warning("Syntax: obr run [-o|--operation] <operation>(,<operation>)+")
        return False
    elif any((false_op := op) not in project.operations for op in operations):
        logger.warning(f"Specified operation {false_op} is not a valid operation.")
        project.print_operations()
        return False
    return True


def is_valid_workspace(filters: list = []) -> bool:
    """This function checks if:
    - the `workspace` folder is not empty, and
    - applying filters would return an empty list
    """
    project: OpenFOAMProject = OpenFOAMProject.get_project()
    jobs: list[Job] = project.filter_jobs(filters=filters)
    if len(jobs) == 0:
        if filters == []:
            logger.warning("No jobs found in workspace folder!")
            return False
        logger.warning(
            f"Found no jobs that satisfy the given filter(s) {' and '.join(filters)}!"
        )
        return False
    return True


def cli_cmd_setup(kwargs: dict) -> tuple[OpenFOAMProject, list[Job]]:
    """This function performs the common pattern of checking project folders for existence and creating the project and extracting the jobs."""
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])
        # ensure .obr exists
        Path(".obr").mkdir(parents=True, exist_ok=True)
    setup_logging()
    project = OpenFOAMProject.get_project()
    filters: list[str] = kwargs.get("filter", [])
    if len(filters) > 0 and kwargs.get("job"):
        raise AssertionError("Filters and job flags are mutually exclusive")

    if sel := kwargs.get("job"):
        jobs = [job for job in project if sel == job.id]
    else:
        jobs = project.filter_jobs(filters=filters)

    # check if given path points to valid project
    if not is_valid_workspace(filters):
        logger.warning("Workspace is not valid! Exiting.")
        sys.exit(1)
    return project, jobs


def copy_to_archive(
    repo: Union[Repo, None], use_git_repo: bool, src_file: Path, target_file: Path
) -> None:
    """Copies files to archive repo"""
    # ensure target directory exists()
    target_path = target_file.parents[0]
    if not target_path.exists():
        target_path.mkdir(parents=True)
    logger.debug(f"cp \\\n\t{src_file}\n\t{target_file.resolve()}")
    if src_file.is_symlink():
        src_file = Path(os.path.realpath(src_file))
    check_output(["cp", src_file, target_file])
    if use_git_repo and repo:
        repo.git.add(target_file)  # NOTE do _not_ do repo.git.add(all=True)
