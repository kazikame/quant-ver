from typing import List
from z3.z3 import ArithRef, BoolRef, ModelRef, is_algebraic_value, is_int_value, is_rational_value, is_true, sat, PbEq, PbLe, PbGe, And, Or, Implies, Not, String
from z3.z3 import AtMost, AtLeast
from my_solver import MySolver
from config import Config
import graphviz

NT = 5
NP = 3


class Workload:
    o: MySolver

    def __init__(self, o: MySolver) -> None:
        self.o = o

        self.exec_t = [o.Real(f"exec_t({t})") for t in range(NT)]
        self.join = [[o.Bool(f"join({t1}, {t2})") for t1 in range(NT)]
                     for t2 in range(NT)]

        self.seq = [[o.Bool(f"seq({t1}, {t2})") for t1 in range(NT)]
                    for t2 in range(NT)]

        self.parent = [[o.Bool(f"parent({t1}, {t2})") for t1 in range(NT)]
                       for t2 in range(NT)]

    def add_constraints(self):
        o = self.o
        v = self

        '''
        ExecutionTime is bounded from below
        '''
        for t in range(NT):
            o.add(v.exec_t[t] >= 0)

        '''
        Edge Validity: there can be atmost one edge between two tasks
        '''
        for t1 in range(NT):
            # o.add(Not(v.join[t1][t1]))
            for t2 in range(NT):
                o.add(Implies(v.seq[t1][t2], o.Not(v.join[t1][t2])))
                # o.add(Implies(v.join[t1][t2], o.Not(v.seq[t1][t2])))

        '''
        Seq Edge Validity: there can be atmost one outgoing seq edge from every task
        '''
        for t in range(NT):
            # o.add(Not(v.seq[t][t]))
            o.add(PbLe([(v.seq[t][t2], 1) for t2 in range(NT)], 1))

        '''
        parent: ensure there is topological ordering, so that cycles are not allowed
        '''
        for t1 in range(NT):
            for t2 in range(NT):
                o.add(v.parent[t1][t2] == o.Or(v.seq[t1][t2], v.join[t1][t2]))
                if t2 <= t1:
                    o.add(Not(v.parent[t1][t2]))


class Event:
    def __init__(self, o: MySolver, id: str):
        self.o = o
        self.id = id

        # Algo Input
        self.queues = [[o.Bool(f'{id}_que_p={p}_t={t}')
                        for t in range(NT)] for p in range(NP)]
        self.free = [o.Bool(f'{id}_free_p={p}') for p in range(NP)]
        self.ready_times = [o.Real(f'{id}_ready_time_t={t}')
                            for t in range(NT)]

        # Algo Output
        self.map = [[o.Bool(f'{id}_map_p={p}_t={t}')
                     for t in range(NT)] for p in range(NP)]

        # System State
        self.time = o.Real(f'{id}_time')

        # which proc is running what task
        self.sched = [[o.Bool(f'{id}_sched_p={p}_t={t}')
                       for t in range(NT)] for p in range(NP)]
        self.finished = [o.Bool(f'{id}_finished_t={t}') for t in range(NT)]
        self.start_times = [o.Real(f'{id}_start_time_t={t}')
                            for t in range(NT)]
        self.origin_proc = [
            [o.Bool(f'{id}_origin_p={p}_t={t}') for t in range(NT)] for p in range(NP)]
        # for context switch cost
        # keep track of last executed task of each processor
        #


def work_stealing(free_procs, queues):
  mapping = {}
  for p in free_procs:
    cur_q = queues.find(p)
    if len(my_queue) > 0:
      mapping[p] = cur_q.pop_back()
    else:
      for q in queues:
        if q.proc in free_procs and len(q) > 1:
          mapping[p] = q.pop_front()
          break
        if len(q) > 0:
          mapping[p] = q.pop_front()
          break

  return mapping


def sys(state_t, w, state_t1):

  state_t1.start = state_t.start
  for new_task in state_t.mapping.values():
    state_t1.start[new_task] = state_t.time
  # ...
  active = state_t.running + state_t.mapping.values()
  finish_time = {}
  for task in active:
    finish_time[task] = state_t1.start[task] + w[task].length
  
  tasks_finished_now = state_t.finished
  for task in sorted(active, key=lambda t: finish_time[t]):

    if any_new_task_ready()

    tasks_finished_now.add()

def transition(cur_event: Event, w: Workload, next_event: Event):
    in_prog_or_done = [
        Or(cur_event.finished[t],
           *[Or(cur_event.map[p][t], cur_event.sched[p][t]) for p in range(NP)])
        for t in range(NT)
    ]

    all_finished = And(*in_prog_or_done)
    o.add(Implies(all_finished, And(next_event.time == cur_event.time,
                                    Not(Or(*next_event.free_procs)),
                                    ...)))

    cur_sched_tasks = sched or mapping

    # start_time
    # if finished or sched, use old
    # if mapping, use cur_event.time

    end_time_of_cur_sched_tasks = [
        o.Real(f'{cur_event.id}_end_time_t={t}') for t in range(NT)]
    # ...using cur_sched, set end_time = start + length
    # set others to 0

    # Time
    # pick earliest end_time_of_cur_sched_tasks such that atleast one task is ready
    # find tasks whose dependency is only in_prog_or_done and themselves not in_prog_or_done
    # find ready_time of tasks whose dependency is only in_prog_or_done and themselves not in_prog_or_done <- pot_ready
    # next_time should be ending time of some cur_sched_task
    # next_time should be smaller than ending time of all cur_sched_task which is after ready_time of above

    # finished
    # 1. if finished before
    # 2. if curr_sched_tasks, and next_event.time >= end_time_of_cur_sched_tasks

    # free_proc
    # And(Implies(curr_event.sched[p][t] or curr_event.mapping[p][t], next_event.time >= end_time[t]))

    # sched
    # curr_event.sched[p][t] or mapping[p][t], not next_event.free_proc[p]

    # origin_proc
    # 1. if true previously, true now
    # 2. exactly one proc can be origin
    # 2. else, [p][t] => (pot_ready[t] and next_event.time == pot_ready_time[t] and exists t2 parent[t2][t] and (sched[p][t2] or mapping[p][t2]))

    # queues
    # 1. every task can be in queue of exactly one proc (AtMost 1)
    # 2. if ready (pot_ready time <= next_event.time), and origin[p][t] => queues[p][t]
