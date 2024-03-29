import re
import logging
import pandas as pd

from dataclasses import dataclass, field
from typing import Any, Union, Callable, Iterable
from copy import deepcopy
from signac.job import Job
from typing import TYPE_CHECKING, Union
from enum import Enum

if TYPE_CHECKING:
    from obr.signac_wrapper.operations import OpenFOAMProject

logger = logging.getLogger("OBR")


@dataclass
class query_result:
    id: str = field()
    result: list[dict] = field(default_factory=list[dict])
    sub_keys: list[list[str]] = field(default_factory=list[list[str]])

    def __repr__(self) -> str:
        return f"Job: {self.id}, result: {self.result}"


class Predicates(Enum):
    eq = "=="
    neq = "!="
    geq = ">="
    gt = ">"
    leq = "<="
    lt = "<"


@dataclass
class Query:
    key: str
    value: Any = None
    state: dict = field(default_factory=dict)
    predicate: str = "eq"
    # If negate is set to true this Query must not match
    # for a list of queries to be successful
    sub_keys: list = field(default_factory=list)
    negate: bool = False

    def execute(self, key, value):
        predicate_map = {
            "eq": lambda a, b: a == b,
            "neq": lambda a, b: a != b,
            "gt": lambda a, b: a > b,
            "lt": lambda a, b: a < b,
            "geq": lambda a, b: a >= b,
            "leq": lambda a, b: a <= b,
        }

        self.predicate_op = predicate_map[self.predicate]

        # case: wrong key during iteration
        if not self.key == key:
            self.state = (
                {}
            )  # NOTE I would like a more explicit "False" but type hint prefers a dict
            return

        # case: nonexistent value, existing key
        if self.value is None and key:
            # Set the state to whatever the value is, as long as the key exists
            self.state = {key: value}
            return

        # case: specific value, existent key. This is effectively a filter.
        try:
            # NOTE this sadly doesnt work when value is an integer, and self.value is a float
            # so, quickly convert value to a float to avoid casting errors
            if isinstance(value, (int, float)):
                value = float(value)
            # convert value to target type to avoid TypeErrors
            self.value = type(value)(self.value)
            if not self.state and self.predicate_op(
                value,
                self.value,
            ):
                self.state = {key: value}
        except TypeError as e:
            # After the prior type conversion, this case should not happen anymore.
            logger.error(f"{e}:")
            logger.error(
                f"\tTried to compare {self.value}({type(self.value)}) and"
                f" {value}({type(value)}) for {key=}."
            )
        except ValueError as e:
            # In case of a funky type conversion. Not expected behavior though.
            logger.warning(value)
            logger.error(e)

    def match(self):
        return self.state

    def __repr__(self) -> str:
        val = self.value or "Any"
        return "{} {} {}:".format(self.key, Predicates[self.predicate].value, val)


def input_to_query(inp: str) -> Query:
    """converts cli input str to a Query object"""
    # FIXME this fails if values are name value
    inp = (
        inp.replace("key", '"key"')
        .replace("value", '"value"')
        .replace("predicate", '"predicate"')
    )
    return Query(**eval(inp))


def input_to_queries(inp: str) -> list[Query]:
    """Convert a json string to list of queries"""
    inp_lst = re.findall(r"{[\w:\"'0-9,. ]*}", inp)
    return [input_to_query(x) for x in inp_lst]


def execute_query(query: Query, key, value, latest_only=True, track_keys=list) -> Query:
    if isinstance(value, list) and latest_only and value:
        value = value[-1]
    # descent one level down, statepoints and job documents might contain
    # subdicts which we want to descent into at the same time we need to track

    signac_attr_dict_str = "JSONAttrDict"

    if isinstance(value, dict) or type(value).__name__ == signac_attr_dict_str:
        track_keys.append(key)
        sub_results = [
            execute_query(deepcopy(query), sub_key, sub_value, latest_only, track_keys)
            for sub_key, sub_value in value.items()
        ]
        # if a query matched to any of the values we continue with this query
        for q in sub_results:
            if q.match():
                return q

    query.execute(key, value)
    # if we have a match store previous keys
    if query.match():
        query.sub_keys = track_keys
    return query


def flatten_jobs(
    jobs: "Union[OpenFOAMProject, list[Job]]",
) -> dict:
    """convert a list of jobs to a dictionary"""
    docs: dict = {}

    # merge job docs and statepoints
    for job in jobs:
        docs[job.id] = {}
        for key, value in job.doc.items():
            docs[job.id].update({key: value})
        docs[job.id].update(job.sp())
    return docs


def query_flat_jobs(
    jobs: dict[str, dict], queries: list[Query], output, latest_only, strict
) -> list[query_result]:
    """
    Execute queries over a dictionary where the job.id is the key and merged job.docs are the values

    Parameters:
    jobs -- a job dictionary ordered by job ids
    queries -- list of queries to run
    output -- Whether to print result to screen
    latest_only -- Take only latest value if resulting value is a list
    strict -- needs all queries to be successful to return a result
    """
    ret = []
    for job_id, doc in jobs.items():
        # scan through merged operations and statepoint values of a job
        # look for keys and values
        # and append if all queries have been matched
        tmp_qs: list[Query] = []
        all_required = True
        for q in queries:
            res_cache = {}
            for key, value in doc.items():
                q_tmp = deepcopy(q)
                res = execute_query(q_tmp, key, value, latest_only, [])
                if res.state:
                    # a filter query was hit
                    if res.negate:
                        all_required = False
                        break

                    res_cache = res.state
                    tmp_qs.append(res)

            # res.state could be from any key before
            if q.value and not res_cache:
                all_required = False

        # append if all required results are present
        res_tmp = query_result(job_id)
        for q in tmp_qs:
            # requests a value but not a state
            # is currently considered to be failed
            res_tmp.result.append(q.state)
            res_tmp.sub_keys.append(q.sub_keys)

        # in strict mode all queries need to have some result
        if strict:
            all_required = len(res_tmp.result) == len(queries)
            # if not all_required:
            #    raise Exception(res_tmp)

        # merge all results to a single dictionary
        res_tmp_dict = {}
        for d in res_tmp.result:
            res_tmp_dict.update(d)
        res_tmp.result = [res_tmp_dict]

        if all_required:
            ret.append(deepcopy(res_tmp))
    return ret


def query_to_dict(
    jobs: "Union[OpenFOAMProject, list[Job]]",
    queries: list[Query],
    output=False,
    latest_only=True,
    strict=False,
) -> list[query_result]:
    """Given a list jobs find all jobs for which a query matches

    Flattens list of jobs to a dictionary with merged statepoints and job document first
    """
    return query_flat_jobs(flatten_jobs(jobs), queries, output, latest_only, strict)


def query_impl(
    jobs: "Union[OpenFOAMProject, list[Job]]",
    queries: list[Query],
    output=False,
    latest_only=True,
) -> list[dict]:
    """Performs a query and returns a list of records ie for each job the query result"""
    res = query_to_dict(jobs, queries, output, latest_only)
    query_ids = {}
    for id_ in res:
        query_ids[id_.id] = id_.result[0]
    return query_ids


def query_to_records(
    jobs: "OpenFOAMProject",
    queries: list[Query],
    latest_only=True,
    strict=False,
) -> list[dict]:
    """Given a list jobs find all jobs for which a query matches

    Flattens list of jobs to a dictionary with merged statepoints and job document first
    """
    query_results = query_flat_jobs(
        flatten_jobs(jobs), queries, False, latest_only, strict
    )
    ret = []
    for q in query_results:
        for r in q.result:
            r.update({"jobid": q.id})
            ret.append(r)
    return ret


def query_to_dataframe(
    jobs: "OpenFOAMProject",
    queries: list[Query],
    latest_only=True,
    strict: bool = False,
    index: list[str] = [],
    post_pro: Union[Callable, None] = None,
) -> pd.DataFrame:
    """Given a list jobs find all jobs for which a query matches

    Flattens list of jobs to a dictionary with merged statepoints and job document first
    Args:
        index: A list of strings defining which columns should be used as index
        post_pro: Function to apply to the DataFrame before creating the index
    """
    ret = pd.DataFrame.from_records(
        query_to_records(jobs, queries, latest_only=latest_only, strict=strict)
    )
    if post_pro:
        ret = post_pro(ret)
    if index:
        return ret.set_index(index).sort_index()
    return ret


def build_filter_query(filters: Iterable[str]) -> list[Query]:
    """This function builds a list of filter queries, where filter queries are queries that request a specific value and has to conform a predicate"""
    q: list[Query] = []

    # avoid iterating over characters of one filter/query
    if not isinstance(filters, (list, tuple)):
        filters = [filters]
    for filter in filters:
        for predicate in Predicates:
            # check if predicates like =, >, <=.. are in the filter
            if predicate.value in filter:
                logger.debug(f"Found predicate {predicate} in {filter=}")
                lhs, rhs = filter.split(predicate.value)
                q.append(Query(key=lhs, value=rhs, predicate=predicate.name))
                break
        else:
            logger.debug(
                f"No applicable predicate found in {filter=}. Will assume '!= None'."
            )
            q.append(Query(key=filter, value=None, predicate=Predicates.neq.name))

    return q


def statepoint_get(statepoint: dict, key: str):
    """This function performs a basic recursive query of the statepoint dictionary
    if the key: value pair is not found in statepoint it recurses into statepoint["parent"] if present

    """
    val = statepoint.get(key)
    if val:
        return val
    else:
        if statepoint.get("parent"):
            return statepoint_get(statepoint["parent"], key)
    return False


def statepoint_query(statepoint: dict, key: str, value, predicate="=="):
    """This function performs a basic recursive query of the statepoint dictionary
    if the key: value pair is not found in statepoint it recurses into statepoint["parent"] if present

    """
    if statepoint.get(key):
        return statepoint[key] == value
    else:
        if statepoint.get("parent"):
            return statepoint_query(statepoint["parent"], key, value, predicate)
    return False


def filter_jobs(project, filter: Iterable[str], output: bool = False) -> list[Job]:
    """`filter` is expected to be a list, string or other iterable of strings in the form of <key><predicate><value>"""
    jobs: list[Job]

    if filter:
        if isinstance(filter, str):
            filter = [filter]
        queries = build_filter_query(filter)
        sel_jobs = query_impl(project, queries, output=output)
        jobs = [j for j in project if j.id in sel_jobs]
    else:
        jobs = [j for j in project]
    return jobs
