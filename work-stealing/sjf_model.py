from typing import List
from z3.z3 import ArithRef, BoolRef, ModelRef, is_algebraic_value, is_int_value, is_rational_value, is_true, sat, PbEq, PbLe, PbGe, And, Or, Implies, Not, String
from z3.z3 import AtMost, AtLeast
from my_solver import MySolver
from config import Config
import graphviz

NT = 4
NUM_EVENTS = NT*2

class Event:
    def __init__(self, o : MySolver, id : str):
        self.o = o

        self.time = o.Real(f'{id}_time')
        self.task_id = [o.Bool(f'{id}_task_id={i}') for i in range(NT)]
        self.ready_tasks = [o.Bool(f'{id}_ready_t={i}') for i in range(NT)]
        self.lengths = [o.Real(f'{id}_len_t={i}') for i in range(NT)]

        # Output
        self.next_task = [o.Bool(f'{id}_next_t={i}') for i in range(NT)]
    
    def add_constraints(self):
        o = self.o

        o.add(Atmost(next_task, 1))

def get_events(o : MySolver, prefix : str):
    events = [Event(o, f"{prefix}_event"+str(i)) for i in range(NUM_EVENTS)]

    for i in range(NUM_EVENTS-1):
        o.add(events[i].time <= events[i+1].time)

    return events

def sjf(o : MySolver, events : [Event]):
    for e in range(NUM_EVENTS):
        event = events[e]
        shortest_task = []
        for t in range(NT):
            constraint = And(event.ready_tasks[t],
                *[Implies(event.ready_tasks[t2], event.lengths[t2] >= event.lengths[t]) for t2 in range(NT)])
            shortest_task.append(constraint)

        # if there's a ready task, there should be a next task
        o.add(Implies(Or(*event.ready_tasks), Or(*event.next_task)))

        # next task should be the shortest task
        for t in range(NT):
            o.add(Implies(event.next_task[t], shortest_task[t]))

class Workload:
    def __init__(self, o: MySolver, id = ""):
        self.o = o

        self.ready_time = [o.Real(f'{id}_ready_time_t={i}') for i in range(NT)]
        self.lengths = [o.Real(f'{id}_length_t={i}') for i in range(NT)]
    
    def add_constraints(self):
        o = self.o

        for t in range(NT):
            o.add(self.ready_time[t] >= 0)
            o.add(self.lengths[t] >= 0)


def add_system(o : MySolver, w : Workload, events : [Event], id : str):
    # Time requires end_time and ready_time
    end_time = [o.Real(f'{id}_end_time_t={i}') for i in range(NT)]
    ready_time = w.ready_time

    for e in range(NUM_EVENTS):
        o.add(o.ExactlyK(events[e].task_id, 1))

    for t in range(NT):
        o.add(Or(*[And(e.time == end_time[t], e.task_id[t]) for e in events]))
        o.add(Or(*[And(e.time == ready_time[t], e.task_id[t]) for e in events]))
    
    # end_time depends on lengths and when it was scheduled
    for t in range(NT):
        o.add(And(*[Implies(e.next_task[t], end_time[t] == e.time + e.lengths[t]) for e in events]))

    # lengths should be consistent and positive
    for i in range(NUM_EVENTS):
        o.add(And(*[events[i].lengths[t] == w.lengths[t] for t in range(NT)]))

    # Ready Tasks: task which are ready and have not been scheduled yet
    for e in range(NUM_EVENTS):
        for t in range(NT):
            o.add(events[e].ready_tasks[t] == And(ready_time[t] <= events[e].time, 
                                                  Not(Or(*[events[prev].next_task[t] for prev in range(0, e)]))))

    # Next task must be ready
    for e in range(NUM_EVENTS):
        o.add(And(*[Implies(events[e].next_task[t], events[e].time >= ready_time[t]) for t in range(NT)]))   

    # Every task must be scheduled
    for t in range(NT):
        o.add(Or(*[e.next_task[t] for e in events]))   

def get_total_time(o : MySolver, w : Workload, events : [Event], prefix : str):
    start_time = [o.Real(f"{prefix}_start_time_t={i}") for i in range(NT)]

    for e in events:
        o.add(And(*[Implies(e.next_task[t], start_time[t] == e.time) for t in range(NT)]))
    
    total_wait_time = o.Real(f"{prefix}_total_time")
    o.add(total_wait_time == sum([start_time[t] - w.ready_time[t] for t in range(NT)]))
    return total_wait_time

if __name__ == "__main__":
    o = MySolver()
    w = Workload(o)
    w.add_constraints()

    events = get_events(o, "sjf")
    sjf(o, events)
    add_system(o, w, events, "sjf")

    print(o.check())

    events_opt = get_events(o, "opt")
    add_system(o, w, events_opt, "opt")

    print(o.check())

    tt_sjf = get_total_time(o, w, events, "sjf")
    tt_opt = get_total_time(o, w, events_opt, "opt")
    o.add(tt_sjf > tt_opt)
    print(o.check())
    print(o.model())
