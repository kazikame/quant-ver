from typing import List
from z3.z3 import ArithRef, BoolRef, ModelRef, is_algebraic_value, is_int_value, is_rational_value, is_true, sat, PbEq, PbLe, PbGe, And, Or, Implies, Not, String, AtMost
from my_solver import MySolver
from config import Config
import graphviz

class Workload:
    c : Config
    o : MySolver

    def __init__(self, c : Config, o : MySolver) -> None:
        self.c = c
        self.o = o

        self.exec_t = [o.Real(f"exec_t({t})") for t in range(c.NUM_TASKS)]
        self.join = [[o.Bool(f"join({t1}, {t2})") for t1 in range(c.NUM_TASKS)]
                                                  for t2 in range(c.NUM_TASKS)]

        self.seq = [[o.Bool(f"seq({t1}, {t2})") for t1 in range(c.NUM_TASKS)]
                                                  for t2 in range(c.NUM_TASKS)]

        self.parent = [[o.Bool(f"parent({t1}, {t2})") for t1 in range(c.NUM_TASKS)]
                                                    for t2 in range(c.NUM_TASKS)]

    
    def add_constraints(self):
        c = self.c
        o = self.o
        v = self

        '''
        ExecutionTime is bounded from below
        '''
        atleast_one = []
        for t in range(c.NUM_TASKS):
            atleast_one.append(v.exec_t[t] > 0)
            o.add(v.exec_t[t] >= 0)
        o.add(Or(*atleast_one))
        
        '''
        Edge Validity: there can be atmost one edge between two tasks
        '''
        for t1 in range(c.NUM_TASKS):
            # o.add(Not(v.join[t1][t1]))
            for t2 in range(c.NUM_TASKS):
                o.add(Implies(v.seq[t1][t2], o.Not(v.join[t1][t2])))
                # o.add(Implies(v.join[t1][t2], o.Not(v.seq[t1][t2])))
        
        '''
        Seq Edge Validity: there can be atmost one outgoing seq edge from every task
        '''
        for t in range(c.NUM_TASKS):
            # o.add(Not(v.seq[t][t]))
            o.add(AtMost(*v.seq[t], 1))

        '''
        parent: ensure there is topological ordering, so that cycles are not allowed
        '''
        for t1 in range(c.NUM_TASKS):
            for t2 in range(c.NUM_TASKS):
                o.add(v.parent[t1][t2] == o.Or(v.seq[t1][t2], v.join[t1][t2]))
                if t2 <= t1:
                    o.add(Not(v.parent[t1][t2]))


class Schedule:
    c : Config
    o : MySolver
    dag : Workload

    def __init__(self, dag : Workload, pre : str) -> None:
        self.dag = dag
        self.c = dag.c
        self.o = dag.o

        c = dag.c
        o = dag.o

        self.ready_t = [o.Real(f"{pre}_ready_t({t})") for t in range(c.NUM_TASKS)]
        self.start_t = [o.Real(f"{pre}_start_t({t})") for t in range(c.NUM_TASKS)]
        self.end_t = [o.Real(f"{pre}_end_t({t})") for t in range(c.NUM_TASKS)]

        self.sched = [[o.Bool(f"{pre}_sched(t={t}, p={p})") for p in range(c.NUM_PROC)] for t in range(c.NUM_TASKS)]
        self.time_taken = o.Real(f"{pre}_TimeTaken")

        '''
        WS state
        '''
        self.origin = [[o.Bool(f"{pre}_OriginProcessor(t={t}, p={p})") for p in range(c.NUM_PROC)] for t in range(c.NUM_TASKS)]
        self.stolen = [o.Bool(f"{pre}_Stolen(t={t})") for t in range(c.NUM_TASKS)]


    def add_constraints(self) -> None:
        c = self.c
        o = self.o
        v = self
        dag = self.dag

        '''
        ReadyTime: The earliest time an instruction can be executed
        1. Children are Ready after Parents are done: Parent(t1, t2) => StartTime(t1) + ExecTime(t1) <= ReadyTime(t2)  
        2. Children are ready immediately after the last parent completes
        3. If no parent, the node is ready at time = 0
        '''
        for t in range(c.NUM_TASKS):
            expr = []
            has_parent = []
            for t2 in range(c.NUM_TASKS):
                o.add(o.Implies(dag.parent[t2][t],
                                        self.end_t[t2] <= self.ready_t[t]))
                expr.append(o.And(dag.parent[t2][t],
                                    self.ready_t[t] == self.end_t[t2]))

                has_parent.append(dag.parent[t2][t])

            o.add(o.Implies(o.Or(*has_parent), o.Or(*expr)))
            o.add(o.Implies(o.Not(o.Or(*has_parent)), self.ready_t[t] == 0))
        
        print("Ready Time", o.check())

        '''
        StartTime >= 0
        EndTime = StartTime + ExecutionTime + ContextShiftTime
        '''
        for t in range(c.NUM_TASKS):
            o.add(v.start_t[t] >= 0)
            o.add(v.end_t[t] == (v.start_t[t] + dag.exec_t[t]))
        
        print("Start and End Time", o.check())
        
        '''
        Total time taken
        '''
        o.add(o.And(*[v.time_taken >= v.end_t[t] for t in range(c.NUM_TASKS)]))
        o.add(o.Or(*[v.time_taken == v.end_t[t] for t in range(c.NUM_TASKS)]))
        o.add(v.time_taken > 0)
        print("Total Time", o.check())

        '''
        Schedule: every task must be scheduled on EXACTLY one processor
        '''
        for t in range(c.NUM_TASKS):
            o.add(PbEq([(v.sched[t][p], 1) for p in range(c.NUM_PROC)], 1))
        
        print("Schedule", o.check())

        '''
        Premption is not allowed
        '''
        for t1 in range(c.NUM_TASKS):
            for t2 in range(c.NUM_TASKS):
                if t1 != t2:
                    for p in range(c.NUM_PROC):
                        o.add(o.Implies(o.And(v.sched[t1][p], v.sched[t2][p], v.start_t[t1] <= v.start_t[t2]),
                                        v.end_t[t1] <= v.start_t[t2]))
        
        print("Pre-emption", o.check())

        '''
        edges
        '''
        for t1 in range(c.NUM_TASKS):
            for t2 in range(c.NUM_TASKS):
                o.add(o.Implies(dag.parent[t1][t2], v.end_t[t1] <= v.start_t[t2]))
        
        '''
        Origin Processor : Which proc's queue did the instruction enter first?
        1. Exactly one processor can be the origin processor
        2. If instruction has a parent, then its origin proc must be the schedule proc of one of the parents.
        3. For every pair of parents (p1, p2) of instruction (T, i), if Schedule(p1) != Schedule(p2)
           AND
           Schedule(p1) == Origin(T, i), then
           StartTime(p1) + ExecutionTime(p1) >= StartTime(p2) + ExecutionTime(p2)
            (Done w/ Ready Time)
        4. if Schedule(T, i, P) AND !Origin(T, i+1, P) => OR(StartTime(T, i, P) + ExecutionTime(T, i, P) < StartTime(T2, j, P) + ExecTime(T2, j, P)
        '''
        for t in range(c.NUM_TASKS):
            o.add(PbEq([(v.origin[t][p], 1) for p in range(c.NUM_PROC)], 1))

        print("Origin Processor 1", o.check())

        for t in range(c.NUM_TASKS):
            has_parent = []
            expr = []
            # For every inst (T1, i), if (T2, j) is its parent, then Schedule(T2, j) can be Origin(T1, i)
            for t2 in range(c.NUM_TASKS):
                has_parent.append(dag.parent[t2][t])
                
                expr.append(o.And(dag.parent[t2][t],
                                        *[orig_proc == sched_proc for orig_proc, sched_proc in zip(v.origin[t], v.sched[t2])]))

            o.add(o.Implies(o.Or(*has_parent), o.Or(*expr)))

        print("Origin Processor 2", o.check())



        '''
        Stolen
        '''
        # Helper expression: True if origin proc of t1 is the same as executed proc of t2
        def origin_same_as_execution(t1, t2):
            return o.Or(*[o.And(v.origin[t1][P], v.sched[t2][P]) for P in range(c.NUM_PROC)])
        
        for t in range(c.NUM_TASKS):
            o.add(v.stolen[t] == o.Not(origin_same_as_execution(t, t)))
        
        print("Stolen", o.check())
        

    
    @classmethod
    def get_num(cls, num):
        if is_int_value(num):
            return float(num.as_long())
        elif is_rational_value(num):
            return float(num.as_fraction())
        elif is_algebraic_value(num):
            return float(num.approx(2))
        print(f"Error: number {num} is invalid")
    
    def visualize(self, m: ModelRef, name: str = "graph"):
        c = self.c
        v = self
        dag = self.dag

        dot = graphviz.Digraph(comment="Scheduling Algorithm", format='jpg')
        dot.graph_attr['rankdir'] = 'LR'

        # Add nodes + Seq
        for t in range(c.NUM_TASKS):
            P = -1
            for proc in range(c.NUM_PROC):
                if is_true(m[v.sched[t][proc]]):
                    P = proc
                    break
            start_time = self.get_num(m[v.start_t[t]])
            end_time = self.get_num(m[v.end_t[t]])
            exec_time = self.get_num(m[dag.exec_t[t]])
            cs_delay = 0
            # cs_delay = self.get_num(m[dag.cs_delay_per_thread[T][i]])

            dot.node(name=f"(t={t})", label=f"(t={t}, {exec_time}, {cs_delay:.2f})\\n{start_time:.2f}-{end_time:.2f}, P{P}")

        # Add Join and seq edges
        for t1 in range(c.NUM_TASKS):
            for t2 in range(c.NUM_TASKS):
                if is_true(m[dag.seq[t1][t2]]):
                    dot.edge(f"(t={t1})", f"(t={t2})")
                if is_true(m[dag.join[t1][t2]]):
                    dot.edge(f"(t={t1})", f"(t={t2})", color='green')

        dot.render(f"graphs/{name}", view=False)
        return dot


class Trigger:
    c : Config
    o : MySolver
    time : ArithRef
    tasks : [BoolRef]
    procs : [BoolRef]
    seq : [BoolRef]
    join : [BoolRef]
    def __init__(self, v : Schedule, pre):
        self.c = v.c
        self.o = v.o
        c = self.c
        o = self.o

        self.time = o.Real(f"{pre}_trigger_time")

        # Type and id of trigger. These two uniquely identify a trigger
        self.type = {
            'RT': o.Bool(f"{pre}_type=RT"), 
            'ET': o.Bool(f"{pre}_type=ET")
        }
        o.add(PbEq([(t, 1) for t in self.type.values()], 1))
        self.id = [o.Bool(f"{pre}_id={t}") for t in range(c.NUM_TASKS)]
        o.add(PbEq([(t, 1) for t in self.id], 1))


        self.available_tasks = [o.Bool(f"{pre}_available_task={t}") for t in range(c.NUM_TASKS)] # which task
        self.free_procs = [o.Bool(f"{pre}_free_proc={p}") for p in range(c.NUM_PROC)]

        # Task that is scheduled next
        self.next_task = [o.Bool(f"{pre}_next_task={t}") for t in range(c.NUM_TASKS)]
        o.add(PbLe([(task, 1) for task in self.next_task], 1))
        self.next_task_et = o.Real(f"{pre}_next_task_end_time")
        self.next_task_rt = o.Real(f"{pre}_next_task_ready_time")
        for t in range(c.NUM_TASKS):
            o.add(o.Implies(self.next_task[t], self.next_task_et == v.end_t[t]))
            o.add(o.Implies(self.next_task[t], self.next_task_rt == v.ready_t[t]))
        
        # Proc on which the next task is scheduled
        self.next_proc = [o.Bool(f"{pre}_next_proc{p}") for p in range(c.NUM_PROC)]
        o.add(PbLe([(proc, 1) for proc in self.next_proc], 1))
        
        print(f"Trigger {pre} done", o.check())

def get_triggers(v : Schedule) -> [Trigger]:
    c = v.c
    o = v.o
    NUM_TRIGGERS = 2*c.NUM_TASKS
    triggers = [Trigger(v, num) for num in range(NUM_TRIGGERS)]

    '''
    Triggers
    1. End Time Trigger: for every task, there exists a trigger with that id=task_id, type=ET, time=end_t
    2. Ready Time Trigger: for every task, there exists a trigger with that id=task_id, type=ET, time=end_t
    3. Triggers are ordered in time
        a. to break ties, ready triggers MUST occur before end triggers
    '''
    for t in range(c.NUM_TASKS):
        o.add(Or(*[And(
            trigger.id[t],
            trigger.type['ET'],
            trigger.time == v.end_t[t]
        ) for trigger in triggers]))
        o.add(Or(*[And(
            trigger.id[t],
            trigger.type['RT'],
            trigger.time == v.ready_t[t]
        ) for trigger in triggers]))

    for i in range(NUM_TRIGGERS-1):
        o.add(triggers[i].time <= triggers[i+1].time)
        o.add(Implies(triggers[i].time == triggers[i+1].time, Not(And(triggers[i].type['ET'], triggers[i+1].type['RT']))))

    for i in range(NUM_TRIGGERS):
        trigger = triggers[i]

        # Available Tasks
        for t in range(c.NUM_TASKS):
            o.add(trigger.available_tasks[t] == And(v.ready_t[t] <= trigger.time,
                                                    *[Not(triggers[j].next_task[t]) for j in range(0, i)]))

        # Free Processors
        for p in range(c.NUM_PROC):
            o.add(trigger.free_procs[p] == And(*[Implies(triggers[j].next_proc[p], triggers[j].next_task_et <= trigger.time) for j in range(0, i)]))
    
    print("All Triggers done", o.check())
    return triggers

def work_stealing(v : Schedule, triggers : [Trigger]) -> None:
    o = v.o
    c = v.c

    # schedule this `task` next for the current processor
    def schedule_next(trigger : Trigger, task : int, proc : int):
        return And(v.start_t[task] == trigger.time, v.sched[task][proc], trigger.next_task[task], trigger.next_proc[proc])

    # For each trigger
    for trigger in triggers:

        '''
        RT: task 't' is ready 
        1. if origin proc is free => schedule on that
        2. if origin proc is not free, and there exists a free proc with no available tasks in its queue ==> schedule on ANY of these
        3. otherwise, do not schedule (next_task == [False], next_proc == [False])
        '''
        cond1 = []
        for t in range(c.NUM_TASKS):
            for p in range(c.NUM_PROC):
                cond = And(v.origin[t][p], trigger.free_procs[p], trigger.id[t])
                o.add(Implies(trigger.type['RT'],
                    Implies(cond, schedule_next(trigger, t, p))
                ))
                cond1.append(cond)
        cond1 = Or(*cond1)

        cond2 = []
        possible_procs = []
        for p in range(c.NUM_PROC):
            available_task_in_queue = Or(*[And(trigger.available_tasks[task], v.origin[task][p]) for task in range(c.NUM_TASKS)])
            for t in range(c.NUM_TASKS):
                cond = And(trigger.free_procs[p], Not(available_task_in_queue))
                possible_procs.append(And(cond, schedule_next(trigger, t, p)))
                cond2.append(cond)

        cond2 = Or(*cond2)
        o.add(Implies(trigger.type['RT'], 
                      Implies(And(Not(cond1), cond2), Or(*possible_procs))))

        o.add(Implies(trigger.type['RT'],
                      Implies(And(Not(cond1), Not(cond2)), 
                              And(*[Not(trigger.next_task[t]) for t in range(c.NUM_TASKS)], 
                                  *[Not(trigger.next_proc[p]) for p in range(c.NUM_PROC)]))))
        
        print("RT Triggers", o.check())

        '''
        ET:
        1. if exists available_task that originated here ==> pick the latest ready one
        2. if exists available_task such that (origin proc is not free or this task is not the youngest in origin proc's queue)
            ==> pick the oldest amongst a particular queue
        3. otherwise, do not schedule
        '''
        # Helper: finds the proc of current task
        curr_proc = []
        for p in range(c.NUM_PROC):
            curr_proc.append(And(*[Implies(trigger.id[t], v.sched[t][p]) for t in range(c.NUM_TASKS)]))
        
        for p in range(c.NUM_PROC):
            # Check if the trigger is an End Time Trigger for processor p
            is_et_trigger_for_p = o.And(trigger.type['ET'], curr_proc[p])

            # Condition a
            tasks_originating_on_p = [
                o.And(trigger.available_tasks[t], v.origin[t][p]) for t in range(c.NUM_TASKS)
            ]

            latest_ready_task_on_p = [
                o.And(
                    tasks_originating_on_p[t],
                    *[o.Implies(tasks_originating_on_p[t2], v.ready_t[t] >= v.ready_t[t2]) for t2 in range(c.NUM_TASKS) if t2 != t]
                ) for t in range(c.NUM_TASKS)
            ]

            cond_a = o.And(is_et_trigger_for_p, o.Or(*latest_ready_task_on_p))
            o.add(Implies(
                cond_a, 
                PbEq([(And(latest_ready_task_on_p[t], schedule_next(trigger, t, p)), 1) for t in range(c.NUM_TASKS)], 1)
            ))

            # Condition b
            other_procs = [u for u in range(c.NUM_PROC) if u != p]
            tasks_not_originating_on_p = [
                o.And(trigger.available_tasks[t], o.Not(v.origin[t][p])) for t in range(c.NUM_TASKS)
            ]

            def available_task_count_ge(proc, num):
                return PbGe([(And(tasks_not_originating_on_p[t], v.origin[t][proc]), 1) for t in range(c.NUM_TASKS)], num)

            stealing_allowed = [
                o.Or(
                    o.And(trigger.free_procs[u], available_task_count_ge(u, 2)),
                    o.And(o.Not(trigger.free_procs[u]), available_task_count_ge(u, 1))
                ) for i, u in enumerate(other_procs)
            ]

            oldest_task_to_steal = [
                Or(*[o.And(
                    tasks_not_originating_on_p[t],
                    v.origin[t][u],
                    *[o.Implies(And(tasks_not_originating_on_p[t2], v.origin[t2][u]), v.ready_t[t] <= v.ready_t[t2]) for t2 in range(c.NUM_TASKS) if t2 != t]
                ) for u in other_procs]) for t in range(c.NUM_TASKS)
            ]

            cond_b = And(is_et_trigger_for_p, Not(cond_a), Or(*stealing_allowed), Or(*oldest_task_to_steal))

            # Add constraints for conditions a, b, and c
            o.add(o.Implies(cond_b, PbEq([(And(oldest_task_to_steal[t], schedule_next(trigger, t, p)), 1) for t in range(c.NUM_TASKS)], 1)))

            
            # Condition c
            cond_c = And(is_et_trigger_for_p, o.Not(o.Or(cond_a, cond_b)))

            o.add(o.Implies(cond_c, And(*[Not(trigger.next_task[t]) for t in range(c.NUM_TASKS)], 
                                        *[Not(trigger.next_proc[p]) for p in range(c.NUM_PROC)])))

        print("Work Stealing", o.check())


if __name__ == '__main__':
    c = Config()
    o = MySolver()
    dag = Workload(c, o)
    dag.add_constraints()

    ## Work Stealing
    ws = Schedule(dag, "ws")
    ws.add_constraints()
    work_stealing(ws, get_triggers(ws))


    ## Optimal
    opt = Schedule(dag, "opt")
    opt.add_constraints()

    o.add(ws.time_taken >= 1.7 * opt.time_taken)
    print(o.s.sexpr())
    # print(o.check())
    # m = o.model()
    # ws.visualize(m, "ws_model")
    # opt.visualize(m, "opt_model")

    # print("Added all constraints")


