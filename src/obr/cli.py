"""
Module that contains the command line app.

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -mobr` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``obr.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``obr.__main__`` in ``sys.modules``.

  Also see (1) from http://click.pocoo.org/5/setuptools/#setuptools-integration
"""
import click
import yaml
import os
import re
import time

from signac_labels import *
from signac_operations import *


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx, debug):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-p", "--pretend", default=False)
@click.option("-o", "--operation")
@click.option("--bundling", default=None)
@click.option("--bundling_match", default=True)
@click.pass_context
def submit(ctx, **kwargs):
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject().init_project()
    project._entrypoint = {"executable": "", "path": "obr"}
    # OpenFOAMProject().main()
    # print(dir(project.operations["runParallelSolver"]))
    # TODO find a signac way to do that
    bundling_key = kwargs["bundling"]
    if bundling_key:
        non_matching_jobs = [
            j for j in project if not bundling_key in list(j.sp.keys())
        ]
        bundling_set_vals = set(
            [j.sp[bundling_key] for j in project if bundling_key in list(j.sp.keys())]
        )

        if not kwargs["bundling_match"]:
            print("submit non matching jobs", non_matching_jobs)
            print(
                project.submit(
                    jobs=non_matching_jobs,
                    bundle_size=len(non_matching_jobs),
                    names=[kwargs.get("operation")],
                    **{"partition": "cpuonly", "pretend": kwargs["pretend"]},
                )
            )

        if kwargs["bundling_match"]:
            print("submit matching jobs", non_matching_jobs)
            for bundle in bundling_set_vals:
                jobs = [j for j in project if bundle in list(j.sp.values())]
                print(len(jobs))

                print(
                    project.submit(
                        jobs=jobs,
                        bundle_size=len(jobs),
                        names=[kwargs.get("operation")],
                        **{"partition": "cpuonly", "pretend": kwargs["pretend"]},
                    )
                )
                time.sleep(15)
    else:
        print("submit all jobs")
        print(
            project.submit(
                names=[kwargs.get("operation")],
                **{"partition": "cpuonly", "pretend": kwargs["pretend"]},
            )
        )

    # print(project.scheduler_jobs(TestEnvironment.get_prefix(runSolver)))
    # print(list(project.scheduler_jobs(TestEnvironment.get_scheduler())))


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-o", "--operations", default="")
@click.option("-j", "--job")
@click.option("--args", default="")
@click.option("-t", "--tasks", default=-1)
@click.option("-a", "--aggregate", default=False)
@click.pass_context
def run(ctx, **kwargs):
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject().init_project()
    # print(generate)
    jobs = (
        [j for j in project if kwargs.get("job") == j.id]
        if kwargs.get("job")
        # else project
        else [j for j in project]
    )
    # project._reregister_aggregates()
    # print(project.groups)
    # val = list(project._groups.values())[0]
    # agg = project._group_to_aggregate_store[val]
    # print(type(project._group_to_aggregate_store[val]))
    # print(agg._aggregates_by_id)
    # jobs = project.groups["generate"]
    # print(list(project.groupby("doc.is_base")))
    if not kwargs.get("aggregate"):
        project.run(
            jobs=jobs,  # project.groupby("doc.is_base"),
            names=kwargs.get("operations").split(","),
            np=kwargs.get("tasks", -1),
        )
    else:
        # calling for aggregates does not work with jobs
        project.run(
            names=kwargs.get("operations").split(","),
            np=kwargs.get("tasks", -1),
        )


def parse_variables(in_str, args, domain):
    ocurrances = re.findall(r"\${{" + domain + "\.(\w+)}}", in_str)
    for inst in ocurrances:
        in_str = in_str.replace("${{" + domain + "." + inst + "}}", args.get(inst, ""))
    expr = re.findall(r"\${{([ 0-9()*+]*)}}", in_str)
    for inst in expr:
        in_str = in_str.replace("${{" + inst + "}}", str(eval(inst)))
    return in_str


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-e", "--execute", default=False)
@click.option("-c", "--config")
@click.option("-t", "--tasks", default=-1)
@click.option("-u", "--url", default=None)
@click.pass_context
def init(ctx, **kwargs):
    import obr_create_tree
    import urllib.request

    if kwargs.get("url"):
        with urllib.request.urlopen(kwargs["url"]) as f:
            config_str = f.read().decode("utf-8")
    else:
        config_file = kwargs["config"]
        with open(config_file, "r") as config_handle:
            config_str = config_handle.read()

    config = yaml.safe_load(parse_variables(config_str, os.environ, "env"))

    project = OpenFOAMProject.init_project(root=kwargs["folder"])
    obr_create_tree.obr_create_tree(project, config, kwargs)


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-d", "--detailed", default=False)
@click.pass_context
def status(ctx, **kwargs):
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject.get_project()
    project.print_status(detailed=kwargs["detailed"], pretty=True)


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-d", "--detailed", default=False)
@click.option("-s", "--state")
@click.option("-g", "--groups")
@click.option("-o", "--operation")
@click.pass_context
def find(ctx, **kwargs):
    # TODO refactor
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject.get_project()
    detailed = kwargs.get("detailed")
    for job in project:
        if not job.doc.get("obr"):
            continue
        for operation, data in job.doc.obr.items():
            state = kwargs.get("state")
            if state:
                # TODO Make history available
                if data[-1]["state"] == state:
                    print(
                        f"operation {operation} state is {state} for job"
                        f" {job.path} with {job.sp}{os.linesep}"
                    )
                    if detailed:
                        print(f"{data[-1]['log']}")
            get_operation = kwargs.get("operation")
            if get_operation:
                if operation == get_operation:
                    print(f"job {job.path} {job.sp} operation {operation}{os.linesep}")
                    if detailed:
                        print(f"{data[-1]['log']}")
            # using the job.id we can find jobs which have this job as child
            # print(job.doc, list(job.doc.obr.keys()), job.sp)


def main():
    cli(obj={})


if __name__ == "__main__":
    cli(obj={})
