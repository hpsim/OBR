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


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx, debug):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug


@cli.command()
@click.option("--folder")
@click.option("--filter", default=None)
@click.option("--select", default=None)
@click.option("--force", default=False)
@click.pass_context
def decompose(ctx, **kwargs):
    import obr_decompose_tree

    obr_decompose_tree.decompose_tree(kwargs)


@cli.command()
@click.option("--folder", default="cases")
@click.option("--results_folder", default="results",
              help="folder to store results")
@click.option("--report", default="report.csv")
@click.option("--filter", default=None)
@click.option("--select", default=None)
@click.option("--continue_on_failure", default=True)
@click.option("--time_runs", default=3600)
@click.option("--min_runs", default=1)
@click.option("--single_run", default=True)
@click.option("--fail_on_error", default=False)
@click.option("--log_name", default="logs")
@click.option("--mpi_flags", default="logs")
@click.pass_context
def benchmark(ctx, **kwargs):
    import obr_benchmark_cases

    obr_benchmark_cases.benchmark_cases(kwargs)


@cli.command()
@click.option("--folder", default="cases")
@click.option("--parameters", default="base")
@click.pass_context
def create(ctx, **kwargs):
    import obr_create_tree

    obr_create_tree.obr_create_tree(kwargs)


def main():
    cli(obj={})


if __name__ == "__main__":
    cli(obj={})
