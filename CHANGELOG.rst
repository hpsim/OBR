
Changelog
=========

0.4.0 (Unreleased)
- Add grouping of jobs: `obr status --summarize N`, see https://github.com/hpsim/OBR/pull/200.

0.3.0 (2024-03-03)
------------------
- Add common notation see https://github.com/hpsim/OBR/pull/146
- Make numberOfSubdomains argument in yaml consistent see https://github.com/hpsim/OBR/pull/148
- Fix missing of groups in `obr run --list-operations` view, see https://github.com/hpsim/OBR/pull/159.
- Make view folders relative see https://github.com/hpsim/OBR/pull/164
- Use cached version of git repo instead of cloning, see https://github.com/hpsim/OBR/pull/166
- Bump signac version, see https://github.com/hpsim/OBR/pull/169
- Validate simulation state after runSerial|ParallelSolver, see https://github.com/hpsim/OBR/pull/168
- Improve obr submit, see https://github.com/hpsim/OBR/pull/170, https://github.com/hpsim/OBR/pull/193, https://github.com/hpsim/OBR/pull/195
- Fix broken test badge, see https://github.com/hpsim/OBR/pull/178
- Fix decomposePar issues with non ESI versions of OF, see https://github.com/hpsim/OBR/issues/185
- Automatically create temporary 0 folder before decomposePar, see https://github.com/hpsim/OBR/pull/186
- Fix logfile location for shell commands, see https://github.com/hpsim/OBR/pull/184
- Add statepoint dependant filter for create_tree, see https://github.com/hpsim/OBR/pull/187
- Add 'obr apply' mode, see https://github.com/hpsim/OBR/pull/188
- Add 'obr --version', see https://github.com/hpsim/OBR/pull/188
- Add template block generators, see https://github.com/hpsim/OBR/pull/18://github.com/hpsim/OBR/pull/190
- Add 'validateState' operation, see https://github.com/hpsim/OBR/pull/189
- Improve 'run*Solver' launch speed, see https://github.com/hpsim/OBR/pull/189
- Add '--generate' flag to 'obr init', see https://github.com/hpsim/OBR/pull/191
- Add 'obr reset' mode, see https://github.com/hpsim/OBR/pull/192
- Improve cli output, https://github.com/hpsim/OBR/pull/198


0.2.0 (2023-09-14)
------------------
- Add --json=file.json option to obr query, which writes the result of the query to a json file.
- Add --validate=file.json option to obr query. If the query results are not identical to the provided json file it will return with a failure exit code.
  For validation either raw json files can be used or json schema, cf. json-schema.org
- Fixes Issue #144 of non working obr run command
- Make -t=1 the default option for obr run -o runParallelSolver

0.0.0 (2022-01-13)
------------------

* First release on PyPI.
