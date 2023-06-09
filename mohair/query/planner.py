#!/usr/bin/env python

# ------------------------------
# License

# Copyright 2023 Aldrin Montana
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# ------------------------------
# Module Docstring
"""
The plan definition and planning portion of query processing for decomposable queries.
"""


# ------------------------------
# Dependencies

# >> Standard libs
import logging

from functools import singledispatch
from dataclasses import dataclass

# >> Third-party libs

#   |> substrait types
from mohair.substrait.plan_pb2 import Plan

from mohair.substrait.algebra_pb2 import Rel
from mohair.substrait.algebra_pb2 import ( ReadRel  , ExtensionLeafRel
                                          
                                          # unary relations
                                          ,FilterRel,  FetchRel, AggregateRel, SortRel
                                          ,ProjectRel, ExtensionSingleRel

                                          # n-ary relations
                                          ,JoinRel, SetRel, ExtensionMultiRel
                                          ,HashJoinRel, MergeJoinRel
                                         )

# >> Internal 

#   |> Logging
from mohair import AddConsoleLogHandler
from mohair import default_loglevel

#   |> classes
from mohair.query.operators import MohairPlan

#   |> functions
from mohair.query.operators import MohairFrom


# ------------------------------
# Module Variables

# >> Logging
logger = logging.getLogger(__name__)
logger.setLevel(default_loglevel)
AddConsoleLogHandler(logger)


# ------------------------------
# Classes

@dataclass
class QueryPlan:
    """
    Wrapper class that references the root of a substrait plan as well as the root of a
    mohair plan. The mohair plan only maintains references to operators in the substrait
    plan, so this class allows us to re-access the entirety of the substrait plan when
    necessary.
    """

    plan_msg      : bytes
    substrait_plan: Plan
    mohair_plan   : MohairPlan = None


    @classmethod
    def FromBytes(cls, plan_bytes: bytes) -> int:
        return MohairPlan.FromBytes(plan_bytes)

    @classmethod
    def ToBytes(cls, plan_hash: int) -> bytes:
        return MohairPlan.ToBytes(plan_hash)

    def __hash__(self):
        plan_hash = hash(self.mohair_plan)
        logger.debug(f'Hash of QueryPlan: {plan_hash}')
        return plan_hash


# ------------------------------
# Functions (translation)

def TranslateSubstrait(substrait_msg: bytes) -> QueryPlan:
    substrait_plan = Plan()
    substrait_plan.ParseFromString(substrait_msg)

    mohair_plan = None
    for plan_ndx, plan_root in enumerate(substrait_plan.relations):
        logger.debug(f'translating plan {plan_ndx}')

        if plan_root.HasField('root'):
            # A query plan should have only 1 `root`, even if it has many trees
            assert mohair_plan == None

            mohair_plan = MohairFrom(plan_root.root.input)

    # Very confusing if a query plan did not have any `root`
    assert mohair_plan is not None

    return QueryPlan(substrait_msg, Plan(), mohair_plan)


# ------------------------------
# Main logic

if __name__ == '__main__':
    # parse sample protobuf from a file, then translate it
    with open('average-expression.substrait', 'rb') as file_handle:
        query_plan = TranslateSubstrait(file_handle.read())

    logger.debug(f'Mohair Plan:')
    # logger.debug(f'\t{query_plan.substrait_plan}')
    logger.debug(f'\t{query_plan.mohair_plan}')
