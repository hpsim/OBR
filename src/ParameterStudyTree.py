#!/usr/bin/env python3
import os
import ParameterStudyVariants as variants
import setFunctions as sf
from OpenFOAMCase import OpenFOAMCase
from pathlib import Path
from itertools import product
from subprocess import check_output
from copy import deepcopy
import json
import asyncio


class ParameterStudyTree:
    """class to construct the file system tree of the cases"""

    def __init__(
            self,
            root_dir,
            root_dict,
            input_dict,
            track_args,
            parent=None,
            base=None):
        """parent = the part of the tree above

        base = the base case on which the tree is based
        """
        self.parent = parent
        self.base = base
        self.input_dict = input_dict
        self.root_dir = root_dir
        self.case_dir = root_dir / "base"
        self.variation_dir = root_dir / ("Variation_" + input_dict["name"])
        self.variation_type = input_dict["type"]
        self.root_dict = root_dict

        # go through the top level
        # construct the type of variation
        self.cases = [
            getattr(
                variants,
                self.variation_type)(
                self.variation_dir,
                self.input_dict,
                variant_dict,
                deepcopy(track_args)) for variant_dict in product(
                *
                input_dict["variants"].values())]

        self.cases = [case for case in self.cases if case.valid]

        # check for further varations
        self.subvariations = []
        if input_dict.get("variation"):
            sub_variation_dicts = input_dict.get("variation")
            for sub_variation in sub_variation_dicts:
                for case in self.cases:
                    self.subvariations.append(
                        ParameterStudyTree(
                            self.variation_dir / case.name,
                            self.root_dict,
                            sub_variation,
                            case.track_args,
                            parent=self,
                        )
                    )

        # deduplicate files later

    def copy_base_to(self, case):
        # copy or link only if case.path doesn not exist
        if case.path.exists():
            return

        base_path = Path(case.base)
        base_constant = base_path / "constant"
        base_0 = base_path / "0"
        base_0org = base_path / "0.org"
        base_system = base_path / "system"
        if not case.link_mesh:
            # TODO copy zero if not linked
            dst = self.variation_dir / case.name / "base"
            cmd = ["mkdir", "-p", dst]
            check_output(cmd)

            if not case.map_fields:
                if os.path.exists(case.path / base_0):
                    cmd = ["cp", "-r", base_0, "."]
                else:
                    cmd = ["cp", "-r", base_0org, "."]
                check_output(cmd, cwd=case.path)

            cmd = ["cp", "-r", base_constant, "constant"]
            check_output(cmd, cwd=case.path)

            cmd = ["cp", "-r", base_system, "."]
            check_output(cmd, cwd=case.path)

            cmd = ["cp", "-r", base_system, "."]
            check_output(cmd, cwd=case.path)

            _, _, files = next(os.walk(case.path / base_path))
            for f in files:
                if "All" not in f:
                    continue
                cmd = ["cp", "-r", base_path / f, "."]
                check_output(cmd, cwd=case.path)
        else:
            dst = self.variation_dir / case.name / "base"
            cmd = ["mkdir", "-p", dst]
            check_output(cmd)

            dst = Path("constant")
            cmd = ["ln", "-s", base_constant, dst]
            check_output(cmd, cwd=case.path)

            cmd = ["cp", "-r", base_system, "."]
            check_output(cmd, cwd=case.path)

            dst = "0"
            cmd = ["ln", "-s", base_0, dst]
            check_output(cmd, cwd=case.path)

    def call_setup(self, case):
        case_dir = self.variation_dir / case.name
        sf.ensure_path(case_dir)
        self.copy_base_to(case)
        case.set_up()

    def set_up(self):
        """creates the tree of case variations"""

        sf.ensure_path(self.root_dir)
        if self.cases:
            sf.ensure_path(self.variation_dir)

        # copy the base case into the tree
        if self.base:
            self.base.copy_to(self.root_dir / "base")

        # execute build command
        if hasattr(self.base, "build"):
            for step in self.base.build:
                print(
                    check_output(
                        step.split(" "),
                        cwd=self.root_dir /
                        "base"))

        # We can use a with statement to ensure threads are cleaned up promptly
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Start the load operations and mark each future with its URL
            future_to_url = [
                executor.submit(self.call_setup, case) for case in self.cases
            ]
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    data = future.result()
                except Exception as exc:
                    print(exc)

        # descend one level to the subvariations
        if self.subvariations:
            for subvariation in self.subvariations:
                subvariation.set_up()

        # write run script if case still has no subvariations
        for case in self.cases:
            case_dir = self.variation_dir / case.name
            import os

            _, folder, _ = next(os.walk(case_dir))
            if len(folder) == 1:
                track_args = case.track_args
                track_args["exec"] = [self.root_dict["case"]["solver"]]
                jsonString = json.dumps(track_args)
                with open(case_dir / "base/obr.json", "w") as jsonFile:
                    jsonFile.write(jsonString)

                print("writing exec script", case_dir / "base")
