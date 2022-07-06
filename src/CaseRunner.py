#!/usr/bin/env python3
""" This module implements Runner needed to run cases and collect statistics """
import time
from pathlib import Path
from subprocess import check_output
import datetime
import sys
import os
import setFunctions as sf
from OpenFOAMCase import OpenFOAMCase
import hashlib
from copy import deepcopy


class TemplatedCaseRunner:
    def __init__(self, results_aggregator, arguments):
        self.results = results_aggregator
        self.arguments = arguments
        self.p = arguments["partition"]
        self.t = arguments["time"]
        self.task_per_node = int(arguments.get("ntasks_per_node", 1))

    def run(self, path, execution_parameter, case_parameter):

        run_path = Path(path)

        mem = self.arguments.get("mem")
        case = OpenFOAMCase(run_path)
        sub_domains = sf.get_number_of_subDomains(case.path)
        submit_args = {
            "sub_domains": sub_domains,
            "number_nodes": max(int(sub_domains / self.task_per_node), 1),
            "tasks": min(sub_domains, self.task_per_node),
            "mem": mem,
        }

        run_env = ("SlurmRunTemplateGPU" if self.p ==
                   "accelerated" else "SlurmRunTemplateCPU")

        submit_env = (
            "SlurmSubmitTemplateGPU"
            if self.p == "accelerated"
            else "SlurmSubmitTemplateCPU"
        )

        run_template = os.environ[run_env]
        submit_template = os.environ[submit_env]

        print("[OBR] writing run.sh to", run_path)
        with open(run_path / "run.sh", "w+") as fh:
            fh.write("#!/bin/bash\n")
            fh.write(
                run_template.format(
                    executable=execution_parameter["exec"][0]))

        sbatch_cmd = submit_template.format(**submit_args).split(" ")

        print("[OBR] call", sbatch_cmd)
        try:
            check_output(sbatch_cmd, cwd=run_path)
        except Exception as e:
            print(e)
            return


class ResultsCollector:
    def __init__(self, results_aggregator, arguments):
        self.results = results_aggregator
        self.arguments = arguments
        self.log_name = arguments["log_name"]

    def get_slurm_log(self, path):
        slurm_logs = ""
        _, _, files = next(os.walk(path))
        for f in files:
            if "slurm-" in f and ".out" in f:
                with open(path / f, encoding="utf-8") as fh:
                    slurm_logs += fh.read()
        return slurm_logs

    def sanitize_log(self, log):
        log_lines = log.split("\n")
        if "Finalising parallel run" in log_lines[-1]:
            return log
        log_end = ["", "End", "", "Finalising parallel run"]

        try:
            # find last ExecutionTime and discard last incomplete timestep
            for i, log_line in enumerate(log_lines[::-1]):
                if "ExecutionTime" in log_line:
                    break

            log_lines = log_lines[: -i - 1]
            log_lines += log_end
            return "\n".join(log_lines)
        except BaseException:
            print("Failed to sanitize log")
            return ""

    def hash_and_store_log(self, ret, path, log_fold):
        log_hash = hashlib.md5(ret.encode("utf-8")).hexdigest()
        log_path = path / self.log_name
        log_path = log_path.with_suffix(".log")
        log_str = ret  # self.sanitize_log(ret)
        log_file = log_fold / self.log_name
        slurm_log = False  # self.get_slurm_log(path)
        with open(log_file, "a") as log_handle:
            print("writing to log", log_file, type(log_str))
            log_str_ = "hash: {}\n{}{}\n".format(log_hash, log_str, "=" * 80)
            if slurm_log:
                log_handle.write(slurm_log)
            log_handle.write(log_str_)
        return log_hash

    def run(self, path, execution_parameter, case_parameter):
        import time
        from pathlib import Path

        run_path = Path(path)

        case = OpenFOAMCase(run_path)
        sub_domains = sf.get_number_of_subDomains(case.path)

        log_file = run_path / "log"
        if not log_file.exists():
            return

        print("[OBR] processing ", log_file)
        with open(log_file, "r", encoding="utf-8") as fh:
            ret = fh.read()
        print("[OBR] hashing ", log_file)
        log_hash = self.hash_and_store_log(
            ret, case.path, self.results.log_fold)

        self.results.set_case(case, execution_parameter, case_parameter)

        print("[OBR] adding log ", log_file)
        self.results.add(
            timestamp=str(datetime.datetime.utcnow()),
            log_id=log_hash,
            run_time=0,
        )
        print("[OBR] done processing log ", log_file)


class LocalCaseRunner:
    def __init__(self, results_aggregator, arguments):
        self.results = results_aggregator
        self.arguments = arguments
        self.time_runs = int(arguments["time_runs"])
        self.min_runs = int(arguments["min_runs"])
        self.continue_on_failure = arguments["continue_on_failure"]
        self.test_run = arguments["single_run"]
        self.fail = arguments["fail_on_error"]
        self.log_name = arguments["log_name"]
        self.mpi_flags = arguments["mpi_flags"]

    def continue_running(self, accumulated_time, number_of_runs):
        if self.test_run and number_of_runs == 1:
            return False
        else:
            return accumulated_time < self.time_runs or number_of_runs < self.min_runs

    def hash_and_store_log(self, ret, path, log_fold):
        log_hash = hashlib.md5(ret).hexdigest()
        log_path = path / self.log_name
        log_path = log_path.with_suffix(".log")
        log_str = ret.decode("utf-8")
        log_file = log_fold / self.log_name
        with open(log_file, "a") as log_handle:
            print("writing to log", log_file, type(log_str))
            log_str_ = "hash: {}\n{}{}\n".format(log_hash, log_str, "=" * 80)
            log_handle.write(log_str_)
        return log_hash

    def run(self, path, execution_parameter, case_parameter):
        import time
        from pathlib import Path

        run_path = Path(path)

        case = OpenFOAMCase(run_path)
        sub_domains = sf.get_number_of_subDomains(case.path)
        if sub_domains:
            execution_parameter["prefix"] = [
                "mpirun",
                "--bind-to",
                "core",
                "-np",
                str(sub_domains),
            ]
            execution_parameter["flags"] = ["-parallel"]
        app_cmd_prefix = execution_parameter.get("prefix", [])
        app_cmd_flags = execution_parameter.get("flags", [])
        app_cmd = app_cmd_prefix + execution_parameter["exec"] + app_cmd_flags

        self.results.set_case(case, execution_parameter, case_parameter)

        # timed runs
        accumulated_time = 0
        number_of_runs = 0
        ret = ""

        # on first run get number of iterations and write log if demanded
        iterations = 0
        print("running", app_cmd, case.path)
        while self.continue_running(accumulated_time, number_of_runs):
            number_of_runs += 1
            try:
                start = datetime.datetime.now()
                ret = check_output(app_cmd, cwd=case.path, timeout=180 * 60)
                end = datetime.datetime.now()
                run_time = (end - start).total_seconds()  # - self.init_time
                accumulated_time += run_time
            except Exception as e:
                print(e)
                if not self.continue_on_failure:
                    break
                print("Exception running while running the case", e)
                if self.fail:
                    sys.exit(1)
                break

            log_hash = self.hash_and_store_log(
                ret, case.path, self.results.log_fold)

            self.results.add(
                timestamp=str(datetime.datetime.utcnow()),
                log_id=log_hash,
                run_time=run_time,
            )
