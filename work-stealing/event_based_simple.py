from typing import List
from z3.z3 import ArithRef, BoolRef, ModelRef, is_algebraic_value, is_int_value, is_rational_value, is_true, sat, PbEq, PbLe, And, Or, Implies, Not
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
        for t in range(c.NUM_TASKS):
            o.add(v.exec_t[t] >= 0)
        
        '''
        Edge Validity: there can be atmost one edge between two tasks
        '''
        for t1 in range(c.NUM_TASKS):
            for t2 in range(c.NUM_TASKS):
                o.add(Implies(v.seq[t1][t2], o.Not(v.join[t1][t2])))
                o.add(Implies(v.join[t1][t2], o.Not(v.seq[t1][t2])))
        
        '''
        Seq Edge Validity: there can be atmost one outgoing seq edge from every task
        '''
        for t in range(c.NUM_TASKS):
            o.add(PbLe([(v.seq[t][t2], 1) for t2 in range(c.NUM_TASKS)], 1))

        '''
        parent
        '''
        for t1 in range(c.NUM_TASKS):
            for t2 in range(c.NUM_TASKS):
                o.add(v.parent[t1][t2] == o.Or(v.seq[t1][t2], v.join[t1][t2]))


class SchedulingAlgorithm:
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
        self.origin = [[o.Bool(f"OriginProcessor(t={t}, p={p})") for p in range(c.NUM_PROC)] for t in range(c.NUM_TASKS)]
        self.stolen = [o.Bool(f"Stolen(t={t})") for t in range(c.NUM_TASKS)]


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
            o.add(v.ready_t[t] <= v.ready_t[t])
            expr = []
            has_parent = []
            for t2 in range(c.NUM_TASKS):
                o.add(o.Implies(o.And(dag.parent[t2][t]),
                                        self.end_t[t2] <= self.ready_t[t]))
                expr.append(o.And(dag.parent[t2][t],
                                    self.ready_t[t] == self.end_t[t2]))

                has_parent.append(dag.parent[t2][t])

            o.add(o.Implies(o.Or(*has_parent), o.Or(*expr)))
            o.add(o.Implies(o.Not(o.Or(*has_parent)), self.ready_t[t] == 0))
        
        print(o.check())

        '''
        StartTime >= 0
        EndTime = StartTime + ExecutionTime + ContextShiftTime
        '''
        for t in range(c.NUM_TASKS):
            o.add(v.start_t[t] >= 0)
            o.add(v.end_t[t] == (v.start_t[t] + dag.exec_t[t]))
        
        print(o.check())
        
        '''
        Total time taken
        '''
        o.add(o.And(*[v.time_taken >= v.end_t[t] for t in range(c.NUM_TASKS)]))
        o.add(o.Or(*[v.time_taken == v.end_t[t] for t in range(c.NUM_TASKS)]))

        print(o.check())

        '''
        Schedule: every task must be scheduled on EXACTLY one processor
        '''
        for t in range(c.NUM_TASKS):
            o.add(PbEq([(v.sched[t][p], 1) for p in range(c.NUM_PROC)], 1))
        
        print(o.check())

        '''
        Premption is not allowed
        '''
        for t1 in range(c.NUM_TASKS):
            for t2 in range(c.NUM_TASKS):
                for p in range(c.NUM_PROC):
                    o.add(o.Implies(o.And(v.sched[t1][p], v.sched[t2][p], v.start_t[t1] <= v.start_t[t2]),
                                    v.end_t[t1] <= v.start_t[t2]))
        

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
    def __init__(self, v : SchedulingAlgorithm, pre):
        self.c = v.c
        self.o = v.o
        c = self.c
        o = self.o

        self.time = o.Real(f"{pre}_trigger_time")
        self.ready_t = o.Real(f"{pre}_trigger_task_ready_time")
        self.tasks = [o.Bool(f"{pre}_trigger_task{t}") for t in range(c.NUM_TASKS)] # which task
        self.procs = [o.Bool(f"{pre}_trigger_proc{p}") for p in range(c.NUM_PROC)]
        self.seq = [o.Bool(f"{pre}_seq(t={t})") for t in range(c.NUM_TASKS)]
        self.join = [o.Bool(f"{pre}_join(t={t})") for t in range(c.NUM_TASKS)]
        self.stolen = o.Bool(f"{pre}_trigger_stolen_task")

        '''
        exactly one task is true
        '''
        o.add(PbEq([(self.tasks[t], 1) for t in range(c.NUM_TASKS)], 1))

        '''
        time is end_t of that task
        '''
        for t in range(c.NUM_TASKS):
            o.add(o.Implies(self.tasks[t], self.time == v.end_t[t]))
            o.add(o.Implies(self.tasks[t], self.ready_t == v.ready_t[t]))
            o.add(o.Implies(self.tasks[t], self.stolen == v.stolen[t]))
        
        

        '''
        processor executed the task
        '''
        for t in range(c.NUM_TASKS):
            o.add(o.Implies(self.tasks[t],
                            o.And(*[(self.procs[p] == v.sched[t][p]) for p in range(c.NUM_PROC)])))

        print("Trigger done", o.check())

    
    @classmethod
    def get_triggers(cls, v : SchedulingAlgorithm):
        c = v.c
        o = v.o

        triggers = [Trigger(v, num) for num in range(c.NUM_TASKS)]

        '''
        every task must have a corresponding trigger
        '''
        for t in range(c.NUM_TASKS):
            o.add(Or(*[trigger.tasks[t] for trigger in triggers]))
        '''
        triggers are ordered in time
        '''
        for t in range(c.NUM_TASKS-1):
            o.add(triggers[t].time <= triggers[t+1].time)
        
        return triggers

def work_stealing(v : SchedulingAlgorithm, triggers : [Trigger]) -> None:
    o = v.o
    c = v.c

    # schedule this `task` next for the current processor
    def schedule_next(trigger, task, nt_end_t):
        # TODO: start_time of this next task must be max(end_time of current task, ready_time of next_task)
        return And(*[v.sched[task][p] == trigger.procs[p] for p in range(c.NUM_PROC)], nt_end_t == v.end_t[task])
    
    # schedule `task`` AFTER the next trigger for the current processor
    def schedule_next_or_later(trigger, task, nt_end_t):
        return And(*[v.sched[task][p] == trigger.procs[p] for p in range(c.NUM_PROC)], nt_end_t <= v.end_t[task])
        # constraints = []
        # constraints.append(And(*[v.sched[task][p] == trigger.procs[p] for p in range(c.NUM_PROC)]))

        # for j in range(i+1, c.NUM_TASKS):
        #     trigger2 = triggers[j]
        #     constraints.append(Implies(o.And(*[trigger2.procs[p] == trigger.procs[p] for p in range(c.NUM_PROC)]),
        #                   v.end_t[task] <= trigger2.start_t))

        # return And(*constraints)

    # For each trigger
    for t in range(c.NUM_TASKS):
        trigger = triggers[t]

        # End time of the task that is exected by current proc AFTER this trigger
        nt_end_t = o.Real(f't={t} next et')
        nt_ready_t = o.Real(f't={t} next ready time')
        nt_stolen = o.Bool(f't={t} next stolen')
        
        less_than = []
        equal_to = []
        same_proc_next_trigger = []
        for t2 in range(t+1, c.NUM_TASKS):
            trigger2 = triggers[t2]
            expr = And(*[(trigger2.procs[p] == trigger.procs[p]) for p in range(c.NUM_PROC)])
            same_proc_next_trigger.append(expr)
            less_than.append(Implies(expr,
                                     nt_end_t <= trigger2.time))
            equal_to.append(And(expr,
                                nt_end_t == trigger2.time, 
                                nt_ready_t == trigger2.ready_t,
                                nt_stolen == trigger2.stolen))
        o.add(And(*less_than))
        o.add(Implies(Or(*same_proc_next_trigger), Or(*equal_to)))
        print("trigger next vars", o.check())

        '''
        Work Stealing Algorithm
        1. A processor can only steal when its queue is empty
        2. A processor can only steal the oldest instruction in another processor’s queue.
        3. A processor only executes the youngest instruction in its own queue.
        4. Minimize Context Switches -- consecutive instructions must run on same proc if they are ready
        '''
        # 1. If there is a sequential task that is ready, run that next
        for task in range(c.NUM_TASKS):
            o.add(o.Implies(o.And(trigger.seq[task], v.ready_t[task] <= trigger.time),
                            schedule_next(trigger, task, nt_end_t)))


        # 2. if runqueue is not empty, run the task that was ready last (youngest task)
        any_in_queue = []
        potential_next = []
        last_ready = []
        for task in range(c.NUM_TASKS):
            in_queue = And(*[v.origin[task][p] == trigger.procs[p] for p in range(c.NUM_PROC)],
                            v.start_t[task] >= trigger.time,
                            Not(v.stolen[task]))
            any_in_queue.append(in_queue)
            potential_next.append(And(in_queue, schedule_next(trigger, task, nt_end_t)))
            last_ready.append(Implies(in_queue, nt_ready_t >= v.ready_t[task]))

        o.add(o.And(*last_ready))
        o.add(Implies(Or(*any_in_queue), o.Or(*potential_next)))

        # 3. if runqueue is empty, next task must be stolen
        o.add(Implies(Not(Or(*any_in_queue)), nt_stolen))

        # TODO: 4. if next task is stolen, it must be the oldest ready task on the originating runqueue 


        # for T1 in range(c.NUM_THREADS):
        #     for i in range(c.MAX_INST_PER_THREAD):
        #         expr1 = []
        #         expr2 = []
        #         expr3 = []
        #         # 4.
        #         # if i < c.MAX_INST_PER_THREAD-1:
        #         #     for P in range(c.NUM_PROC):
        #         #         o.add(o.Implies(
        #         #             o.And(
        #         #                 v.ready_time[T1][i+1] <= v.end_time[T1][i],
        #         #                 v.schedule[T1][i][P],
        #         #                 i+1 < dag.num_instructions[T]
        #         #                 ),
        #         #             v.schedule[T1][i+1][P]
        #         #         ))
        #         for T2 in range(c.NUM_THREADS):
        #             for j in range(c.MAX_INST_PER_THREAD):
        #                 expr1.append(o.Or(o.Implies(o.And(i < dag.num_instructions[T1], j < dag.num_instructions[T2],
        #                                                 o.Not(v.stolen[T2][j]),
        #                                                 origin_same_as_execution(T2, j, T1, i)),
        #                                             o.Or(v.end_time[T2][j] <= v.start_time[T1][i],
        #                                                 v.ready_time[T2][j] > v.start_time[T1][i])),
        #                                 o.Implies(o.And(i < dag.num_instructions[T1], j < dag.num_instructions[T2],
        #                                                 v.stolen[T2][j],
        #                                                 origin_same_as_execution(T2, j, T1, i),
        #                                                 v.ready_time[T2][j] < v.start_time[T1][i]),
        #                                             v.start_time[T2][j] < v.start_time[T1][i])))

        #                 expr2.append(o.Implies(o.And(i < dag.num_instructions[T1], j < dag.num_instructions[T2],
        #                                         same_origin_instructions(T1, i, T2, j)),
        #                                         o.Or(v.ready_time[T1][i] <= v.ready_time[T2][j],
        #                                             v.start_time[T2][j] <= v.start_time[T1][i])))

        #                 expr3.append(o.Implies(o.And(i < dag.num_instructions[T1], j < dag.num_instructions[T2],
        #                                             o.Not(v.stolen[T2][j]),
        #                                             same_origin_instructions(T1, i, T2, j)),
        #                                         o.Or(v.ready_time[T1][i] <= v.ready_time[T2][j],
        #                                             v.end_time[T2][j] <= v.ready_time[T1][i])))

        #         o.add(o.Implies(o.And(v.stolen[T1][i]),
        #                         o.And(*expr1)))

        #         o.add(o.Implies(o.And(v.stolen[T1][i]),
        #                         o.And(*expr2)))

        #         o.add(o.Implies(o.And(o.Not(v.stolen[T1][i])),
        #                         o.And(*expr3)))
        
        print("Work Stealing", o.check())

        # '''
        # Work Conserving: \forall P, i !FreeProcessor(P, [ReadyTime(i), StartTime(i)])
        # '''
        # for P in range(c.NUM_PROC):
        #     for T in range(c.NUM_THREADS):
        #         for i in range(c.MAX_INST_PER_THREAD):
        #             var = o.Bool(f"BusyBW_{T}_{i}")
        #             o.add(var == self.is_proc_busy(P, v.ready_time[T][i], v.start_time[T][i]))
        #             o.add(o.Implies(o.And(i < dag.num_instructions[T], 
        #                             v.start_time[T][i] != v.ready_time[T][i]),
        #                             var))

        # print("Work Conserving", o.check())



if __name__ == '__main__':
    c = Config()
    o = MySolver()
    dag = Workload(c, o)
    dag.add_constraints()

    ## Work Stealing
    ws = SchedulingAlgorithm(dag, "ws")
    ws.add_constraints()
    work_stealing(ws, Trigger.get_triggers(ws))

    ws.visualize(o.model(), "ws_model")

    ## Optimal
    opt = SchedulingAlgorithm(dag, "opt")
    opt.add_constraints()

    print("Added all constraints")


