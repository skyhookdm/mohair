#!/usr/bin/env python

# ------------------------------
# License

# Copyright 2022 Aldrin Montana
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
Convenience classes and functions for processing relational operators.
"""


# ------------------------------
# Dependencies

# >> Standard libs
from typing import Any

from functools import singledispatch
from dataclasses import dataclass, field

# >> Substrait definitions
#   |> relation types for common, leaf, unary, and N-ary relations
from mohair.substrait.algebra_pb2 import Rel
from mohair.substrait.algebra_pb2 import ReadRel, ExtensionLeafRel
from mohair.substrait.algebra_pb2 import (FilterRel,  FetchRel, AggregateRel, SortRel,
                                          ProjectRel, ExtensionSingleRel)
from mohair.substrait.algebra_pb2 import (JoinRel, SetRel, ExtensionMultiRel,
                                          HashJoinRel, MergeJoinRel)

# >> Mohair definitions
#   |> leaf relation types
from mohair.mohair.algebra_pb2 import SkyRel, QueryRel


# ------------------------------
# Classes

# >> Operator structure

@dataclass
class MohairOp: pass

#   |> Unary relational classes
@dataclass
class Projection(MohairOp):
    plan_op: ProjectRel

    def __str__(self):
        return 'Projection()'

@dataclass
class Selection(MohairOp):
    plan_op: FilterRel

    def __str__(self):
        return 'Selection()'

@dataclass
class Aggregation(MohairOp):
    plan_op: AggregateRel

    def __str__(self):
        return 'Aggregation()'

@dataclass
class Limit(MohairOp):
    plan_op: FetchRel

    def __str__(self):
        return 'Limit()'


#   |> Leaf relational classes
@dataclass
class Read(MohairOp):
    plan_op: ReadRel
    name   : str = None

    def __post_init__(self):
        # grab the name of the table; otherwise just its type for now
        if self.plan_op.HasField('named_table'):
            self.name = '/'.join(self.plan_op.named_table.names)

        else:
            # TODO: we will eventually want a more robust name than the type of ReadRel
            self.name = self.plan_op.WhichOneof('read_type')

    def __str__(self):
        read_type = self.plan_op.WhichOneof('read_type')

        return f'Read({read_type})'

# NOTE: this should integrate a skytether partition and a SkyRel message
@dataclass
class SkyPartition(MohairOp):
    plan_op: SkyRel
    name   : str = None

    def __post_init__(self):
        self.name = f'{self.plan_op.domain}/{self.plan_op.partition}'

    def __str__(self):
        return f'SkyPartition({self.name})'


#   |>  Concrete relational classes (joins)
@dataclass
class Join(MohairOp):
    plan_op: JoinRel
    name   : str = None

    def __str__(self):
        return f'Join({self.name})'

@dataclass
class HashJoin(MohairOp):
    plan_op: HashJoinRel

    def __str__(self):
        return f'HashJoin()'

@dataclass
class MergeJoin(MohairOp):
    plan_op: MergeJoinRel

    def __str__(self):
        return f'MergeJoin()'


#   |>  Concrete relational classes (N-ary)
@dataclass
class SetOp(MohairOp):
    plan_op: SetRel


# >> High-level plan structure
@dataclass
class MohairPlan: pass

@dataclass
class PlanPipeline(MohairPlan):
    """
    Represents a holistic plan that has a list of pipelined ops that can be applied to the
    result of a subplan. If the subplan is None, then this should be a pipeline with a
    single data source as input.
    """

    op_pipeline: list[MohairOp]   = field(default_factory=list)
    name       : str              = None
    subplans   : list[MohairPlan] = field(default_factory=list)

    def __str__(self):
        return self.Print()

    def Print(self, indent=''):
        return (
              f'{indent}PlanPipeline({self.name})\n'
            + f'{indent}[' + '\n\t'.join([str(op) for op in self.op_pipeline]) + ']'
            + f'\n{indent}|> subplans:\n'
            + '\n'.join([
                  subplan.Print(indent + '\t')
                  for subplan in self.subplans
              ])
        )

    def add_op(self, new_op: MohairOp):
        self.op_pipeline.append(new_op)
        return self

    def add_ops(self, new_ops: list[MohairOp]):
        self.op_pipeline.extend(new_ops)
        return self

@dataclass
class PlanBreak(MohairPlan):
    """
    Represents a holistic plan that has a list of pipelined ops that can be applied to the
    result of each subplan. This means that each subplan must be grouped first (or streamed
    over in some appropriate manner) and the pipeline operations can be applied to tuples
    as they flow through the result of the grouping operation (i.e. join or a set
    operator).
    """

    plan_op  : MohairOp
    name     : str              = None
    subplans : list[MohairPlan] = field(default_factory=list)

    def __post_init__(self):
        self.name = '.'.join([sub_root.name for sub_root in self.subplans])

    def __str__(self):
        return self.Print()

    def Print(self, indent=''):
        return (
              f'{indent}PlanBreak({self.name}) <{self.plan_op}>\n'
            + f'{indent}>> subplans:\n'
            + '\n'.join([
                  subplan.Print(indent + '\t')
                  for subplan in self.subplans
              ])
        )


# ------------------------------
# Functions
@singledispatch
def MohairFrom(plan_op) -> Any:
    raise NotImplementedError(f'No implementation for operator: {plan_op}')

@MohairFrom.register
def _from_rel(plan_op: Rel) -> Any:
    """
    Translation function that propagates through the generic 'Rel' message.
    """

    op_rel = getattr(plan_op, plan_op.WhichOneof('rel_type'))

    print(f'translating <Rel: {type(op_rel)}>')
    return MohairFrom(op_rel, plan_op)

# >> Translations for unary relations
@MohairFrom.register
def _from_filter(filter_op: FilterRel, base_rel: Rel) -> Any:
    print('translating <Filter>')

@MohairFrom.register
def _from_fetch(fetch_op: FetchRel, base_rel: Rel) -> Any:
    print('translating <Fetch>')

@MohairFrom.register
def _from_sort(sort_op: SortRel, base_rel: Rel) -> Any:
    print('translating <Sort>')

@MohairFrom.register
def _from_project(project_op: ProjectRel, base_rel: Rel) -> Any:
    print('translating <Project>')

    mohair_subplan = MohairFrom(project_op.input)
    # mohair_op      = Projection(project_op, base_rel)
    mohair_op      = Projection(project_op)

    if mohair_subplan is PlanPipeline:
        print('\t>> extending pipeline')

        mohair_subplan.add_op(mohair_op)
        return mohair_subplan

    return PlanPipeline([mohair_op], mohair_subplan.name, [mohair_subplan])


@MohairFrom.register
def _from_aggregate(aggregate_op: AggregateRel, base_rel: Rel) -> Any:
    print('translating <Aggregate>')

    mohair_subplan  = MohairFrom(aggregate_op.input)
    # mohair_op       = Aggregation(aggregate_op, base_rel)
    mohair_op       = Aggregation(aggregate_op)

    return PlanBreak(mohair_op, mohair_subplan.name, [mohair_subplan])


# >> Translations for leaf relations

@MohairFrom.register
def _from_readrel(read_op: ReadRel, base_rel: Rel) -> Any:
    print('translating <Read>')

    # mohair_op = Read(read_op, base_rel)
    mohair_op = Read(read_op)
    return PlanPipeline([mohair_op], mohair_op.name)

@MohairFrom.register
def _from_skyrel(sky_op: SkyRel, base_rel: Rel) -> Any:
    print('translating <SkyPartition>')

    # mohair_op = SkyPartition(base_rel, sky_op)
    mohair_op = SkyPartition(sky_op)
    return PlanPipeline([mohair_op], mohair_op.name)

# >> Translations for join and n-ary relations

@MohairFrom.register
def _from_joinrel(join_op: JoinRel, base_rel: Rel) -> Any:
    print('translating <Join>')

    left_subplan    = MohairFrom(join_op.left)
    right_subplan   = MohairFrom(join_op.right)
    # mohair_op       = Join(join_op, base_rel)
    mohair_op       = Join(join_op)

    return PlanBreak(mohair_op, subplans=[left_subplan, right_subplan])