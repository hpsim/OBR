#!/usr/bin/env python3
""" This module implements Runner needed to run cases and collect statistics """
from subprocess import check_output
import datetime
import sys
import Owls as ow
import OBR.setFunctions as sf


class CaseRunner:
    def __init__(self, solver, results_aggregator, arguments):
        self.results = results_aggregator
        self.arguments = arguments
        self.solver_prefix = None
        self.of_solver = solver
        self.time_runs = int(arguments["--time_runs"])
        self.min_runs = int(arguments["--min_runs"])
        self.continue_on_failure = arguments["--continue_on_failure"]
        self.test_run = arguments["--test-run"]
        self.fail = arguments["--fail_on_error"]
        self.include_log = arguments["--include_log"]

    def set_solver_prefix(self, prefix):
        self.solver_prefix = prefix
        self.of_solver = self.prefix + " " + self.of_solver

    def continue_running(self, accumulated_time, number_of_runs):
        if self.test_run and number_of_runs == 1:
            return False
        else:
            return accumulated_time < self.time_runs or number_of_runs < self.min_runs

    def run(self, case):

        processes = case.get_processes()
        print("start runs processes", processes)
        for process in processes:
            try:
                threads = case.others[0].domain.executor.enviroment_setter.set_up(
                )
            except Exception as e:
                threads = 1
                print(e)
                pass
            self.results.set_case(
                domain=case.query_attr("domain", "").name,
                executor=case.query_attr("domain", "").executor.name,
                solver=case.query_attr("get_solver", []),
                preconditioner=case.query_attr("preconditioner", "").name,
                resolution=case.query_attr("cells", ""),
                processes=threads,
            )
            # warm up run
            original_end_time = sf.get_end_time(case.controlDict)
            deltaT = sf.read_deltaT(case.controlDict)

            sf.set_end_time(case.controlDict, 1 * deltaT)

            # first warm up run
            check_output([self.of_solver], cwd=case.path, timeout=15 * 60)

            # timed warmup run
            start = datetime.datetime.now()
            check_output([self.of_solver], cwd=case.path, timeout=15 * 60)
            end = datetime.datetime.now()
            warm_up = (end - start).total_seconds()
            sf.set_end_time(case.controlDict, original_end_time)

            # timed runs
            accumulated_time = 0
            number_of_runs = 0
            ret = ""
            # on first run get number of iterations and write log if demanded
            iterations = 0
            while self.continue_running(accumulated_time, number_of_runs):
                number_of_runs += 1
                start = datetime.datetime.now()
                success = 0
                try:
                    ret = check_output(
                        [self.of_solver], cwd=case.path, timeout=15 * 60)
                    success = 1
                except Exception as e:
                    print(e)
                    if not self.continue_on_failure:
                        break
                    print("Exception running while running the case", e)
                    if self.fail:
                        sys.exit(1)
                    break

                end = datetime.datetime.now()
                if number_of_runs == 1:
                    try:
                        log_path = case.path / "log"
                        log_path = log_path.with_suffix("." + str(process))
                        log_str = ret.decode("utf-8")
                        with open(log_path, "w") as log_handle:
                            log_handle.write(log_str)
                        keys = {
                            "{}:  Solving for {}".format(s, f): [
                                "init_residual",
                                "final_residual",
                                "iterations",
                            ]
                            for f, s in zip(
                                self.results.fields, case.query_attr("get_solver", [])
                            )
                        }
                        ff = ow.read_log_str(log_str, keys)
                        print(ff)
                        iterations = int(ff["iterations"].sum())
                    except Exception as e:
                        print("Exception processing logs", e)
                        pass
                run_time = (end - start).total_seconds()  # - self.init_time
                accumulated_time += run_time
                self.results.add(warm_up, run_time, iterations)
        try:
            case.others[0].domain.executor.enviroment_setter.clean_up()
        except Exception as e:
            pass
