from typing import List
from z3.z3 import ArithRef, BoolRef, ModelRef, is_algebraic_value, is_int_value, is_rational_value, is_true, sat, PbEq, PbLe, PbGe, And, Or, Implies, Not, String
from z3.z3 import AtMost, AtLeast
from my_solver import MySolver
from config import Config
import graphviz

NT = 5
NUM_EVENTS = NT*2

class Event:
    def __init__(self, o : MySolver, id : str):
        self.o = o
        self.id = id

        # Algorithm Input
        self.ready_tasks = [o.Bool(f'{id}_ready_t={i}') for i in range(NT)] # 
        self.lengths = [o.Real(f'{id}_len_t={i}') for i in range(NT)]

        # System State
        self.time = o.Real(f'{id}_time')
        self.finished = [o.Bool(f'{id}_finished_t={i}') for i in range(NT)]

        # Algorithm Output
        self.next_task = [o.Bool(f'{id}_next_t={i}') for i in range(NT)]

class Workload:
    def __init__(self, o: MySolver, id = ""):
        self.o = o

        self.ready_time = [o.Real(f'{id}_ready_time_t={i}') for i in range(NT)]
        self.lengths = [o.Real(f'{id}_length_t={i}') for i in range(NT)]
    
    def add_constraints(self):
        o = self.o

        for t in range(NT):
            o.add(self.ready_time[t] >= 0)
            o.add(self.lengths[t] > 0)


def sjf(o : MySolver, event : Event, w : Workload):
    shortest_task = []
    for t in range(NT):
        constraint = And(event.ready_tasks[t],
            *[Implies(event.ready_tasks[t2], w.lengths[t2] >= w.lengths[t]) for t2 in range(NT)])
        shortest_task.append(constraint)

    o.add(AtMost(*event.next_task, 1))
    o.add(Implies(Or(*event.ready_tasks), Or(*event.next_task)))

    # next task should be the shortest task
    for t in range(NT):
        o.add(Implies(event.next_task[t], shortest_task[t]))

def opt(o : MySolver, event : Event, w : Workload):
    o.add(AtMost(*event.next_task, 1))
    o.add(Implies(Or(*event.ready_tasks), Or(*event.next_task)))
    o.add(And(*[Implies(event.next_task[t], event.ready_tasks[t]) for t in range(NT)]))

def add_system(o : MySolver, w : Workload, cur_event : Event, next_event : Event): 
    for t in range(NT):
        o.add(next_event.finished[t] == Or(cur_event.finished[t], cur_event.next_task[t]))
    
    all_finished = And(*next_event.finished)
    o.add(Implies(all_finished, And(next_event.time == cur_event.time,
                                    Not(Or(*next_event.ready_tasks)))))
    
    end_time_of_last_sched_task = o.Real(f'{cur_event.id}_end_time_last_sched_task')
    for t in range(NT):
        o.add(Implies(cur_event.next_task[t], end_time_of_last_sched_task == cur_event.time + w.lengths[t]))
    
    ready_not_finished = [
        And(w.ready_time[t] <= end_time_of_last_sched_task, Not(next_event.finished[t])) for t in range(NT)
    ]
    atleast_one = Or(*ready_not_finished)

    o.add(Implies(And(Not(all_finished), atleast_one), And(next_event.time == end_time_of_last_sched_task,
                                                                       *[ready_not_finished[t] == next_event.ready_tasks[t] for t in range(NT)])))

    min_time_of_next_ready_task = o.Real(f'{cur_event.id}_min_time_of_next_ready_task')
    o.add(Implies(Not(all_finished), Or(*[And(min_time_of_next_ready_task == w.ready_time[t], Not(next_event.finished[t])) for t in range(NT)])))
    o.add(And(*[Implies(Not(next_event.finished[t]), min_time_of_next_ready_task <= w.ready_time[t]) for t in range(NT)]))

    ready_not_finished_at_new_time = [
        And(w.ready_time[t] <= min_time_of_next_ready_task, Not(next_event.finished[t])) for t in range(NT)
    ]

    o.add(Implies(And(Not(all_finished), Not(atleast_one)), And(next_event.time == min_time_of_next_ready_task,
                                                                       *[ready_not_finished_at_new_time[t] == next_event.ready_tasks[t] for t in range(NT)])))

def init(o : MySolver, w : Workload, first_event : Event):
    o.minimum(first_event.time, w.ready_time)
    o.add(And(*[first_event.ready_tasks[t] == (w.ready_time[t] <= first_event.time) for t in range(NT)]))
    o.add(Not(Or(*first_event.finished)))

def get_total_time(o : MySolver, w : Workload, events : [Event], prefix : str):
    start_time = [o.Real(f"{prefix}_start_time_t={i}") for i in range(NT)]

    for e in events:
        o.add(And(*[Implies(e.next_task[t], start_time[t] == e.time + w.lengths[t]) for t in range(NT)]))
    
    total_wait_time = o.Real(f"{prefix}_total_time")
    o.add(total_wait_time == sum([start_time[t] - w.ready_time[t] for t in range(NT)]))
    return total_wait_time


def get_events(o : MySolver, prefix : str):
    events = [Event(o, f"{prefix}_event{i}") for i in range(NUM_EVENTS)]

    for i in range(NUM_EVENTS-1):
        o.add(events[i].time <= events[i+1].time)

    return events

if __name__ == "__main__":
    o = MySolver()
    w = Workload(o)
    w.add_constraints()
    print(o.check())

    events = get_events(o, "sjf")
    print(o.check())

    for e in events:
        sjf(o, e, w)
    init(o, w, events[0])

    for i in range(0, NUM_EVENTS-1):
        add_system(o, w, events[i], events[i+1])

    print(o.check())

    events_opt = get_events(o, "opt")
    for e in events_opt:
        opt(o, e, w)
    init(o, w, events_opt[0])

    for i in range(0, NUM_EVENTS-1):
        add_system(o, w, events_opt[i], events_opt[i+1])
    print(o.check())

    tt_sjf = get_total_time(o, w, events, "sjf")
    tt_opt = get_total_time(o, w, events_opt, "opt")
    o.add(tt_sjf > 2*tt_opt)
    print(o.check())
    m = o.model()

    strs = []
    for k in m:
        strs.append(f"{k}={m[k]}")

    for s in sorted(strs):
        print(s)