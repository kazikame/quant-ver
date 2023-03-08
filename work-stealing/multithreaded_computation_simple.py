from typing import List
from z3.z3 import ArithRef, BoolRef, ModelRef, is_algebraic_value, is_int_value, is_rational_value, is_true, sat
from config import Config
from my_solver import MySolver
import graphviz

'''
Z3 constraints to generate every valid multithreaded computation's directed acyclic graph
'''
class DAG:
    c : Config
    o : MySolver
    def __init__(self, c : Config, o : MySolver) -> None:
        self.c = c
        self.o = o

        self.num_instructions = [o.Int(f"NumInstructions(T{thread})") for thread in range(c.NUM_THREADS)]
        self.execution_time = [[o.Real(f"ExecutionTime(T{thread}, {inst})") for inst in range(c.MAX_INST_PER_THREAD)] 
                                                                           for thread in range(c.NUM_THREADS)]
        self.join_edge = [[[[o.Bool(f"JoinEdge(T{t1}, {i1}, T{t2}, {i2})") for i2 in range(c.MAX_INST_PER_THREAD)]
                                                                          for t2 in range(c.NUM_THREADS)]
                                                                          for i1 in range(c.MAX_INST_PER_THREAD)]
                                                                          for t1 in range(c.NUM_THREADS)]

        # self.spawn_edge = [[[o.Bool(f"SpawnEdge(T{t1}, {i}, T{t2})") for t2 in range(c.NUM_THREADS)]
        #                                                              for i in range(c.MAX_INST_PER_THREAD)]
        #                                                              for t1 in range(c.NUM_THREADS)]

        # self.context_shift_delay = o.Real("ContextShiftDelay")

        self.cs_delay_per_thread = [[o.Real(f"ContextShiftDelay(T{t}I{i})") for i in range(c.MAX_INST_PER_THREAD)] for t in range(c.NUM_THREADS)]
        # self.context_shift_delay = [[o.Real(f"ContextShiftDelay(P{p1}, P{p2})") for p1 in range(c.NUM_PROC)]
        #                                                                        for p2 in range(c.NUM_PROC)]

        self.parent = [[[[o.Bool(f"Parent({T1}, {i}, {T2}, {j})") for j in range(c.MAX_INST_PER_THREAD)]
                                                                 for T2 in range(c.NUM_THREADS)]
                                                                 for i in range(c.MAX_INST_PER_THREAD)]
                                                                 for T1 in range(c.NUM_THREADS)]
        # O(T^2)
        for T1 in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                for T2 in range(c.NUM_THREADS):
                    for j in range(c.MAX_INST_PER_THREAD):
                        edge_set = [self.join_edge[T1][i][T2][j]]
                        # if (j == 0): # Spawn Edge
                        #     edge_set.append(self.spawn_edge[T1][i][T2])
                            # edge_set = o.Or(edge_set, self.spawn_edge[T1][i][T2])
                        if T1 == T2 and i+1 == j: # Sequential Edge
                            edge_set = [True]
                        
                        o.add(o.Implies(o.And(i < self.num_instructions[T1], j < self.num_instructions[T2]), self.parent[T1][i][T2][j] == o.Or(*edge_set)))
                        o.add(o.Implies(o.Or(i >= self.num_instructions[T1], j >= self.num_instructions[T2]), self.parent[T1][i][T2][j] == False))
                        
                        ## Redundant Constraint
                        # o.add(o.Implies(o.Or(i >= self.num_instructions[T1],
                        #                      j >= self.num_instructions[T2]),
                        #                 o.Not(self.parent[T1][i][T2][j])))
    
    def cs_delay_constraints(self, cs_range):
        o = self.o
        v = self
        c = self.c
        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                o.add(cs_range == v.cs_delay_per_thread[T][i])

        # for T in range(c.NUM_THREADS):
        #     for i in range(c.MAX_INST_PER_THREAD):
        #         for T2 in range(c.NUM_THREADS):
        #             for i2 in range(c.MAX_INST_PER_THREAD):
        #                 o.add(v.cs_delay_per_thread[T][i] <= cs_range * v.execution_time[T2][i2])

                # o.add((v.cs_delay_per_thread[T][i] - v.cs_delay_per_thread[0][0]) <= cs_range)
                # o.add((v.cs_delay_per_thread[0][0] - v.cs_delay_per_thread[T][i]) <= cs_range)
                
    '''
    Adds constraints for a valid multithreaded computation DAG
    '''
    def add_constraints(self, cs_delay=True):
        c = self.c
        o = self.o
        v = self

        '''
        ExecutionTime is bounded
        '''
        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                pass
                # o.add(o.And(v.execution_time[T][i] > 0))
                # o.add(o.And(o.Implies(i < v.num_instructions[T], v.execution_time[T][i] >= c.MIN_EXECUTION_TIME_PER_INST)))
                # o.add(o.And(o.Implies(i < v.num_instructions[T], v.execution_time[T][i] <= c.MAX_EXECUTION_TIME_PER_INST)))
                o.add(o.And(v.execution_time[T][i] <= c.MAX_EXECUTION_TIME_PER_INST * v.execution_time[0][0]))
                o.add(o.Implies(i >= v.num_instructions[T], v.execution_time[T][i] == 0))

        '''
        ContextShiftDelay is fixed and bounded
        '''
        # o.add(v.context_shift_delay >= c.CONTEXT_SHIFT_DELAY_MIN)
        # o.add(v.context_shift_delay <= c.CONTEXT_SHIFT_DELAY_MAX)


        '''
        Alternate: CS_Delay_per_thread
        Cost of switching into a thread depends per thread
        Ideally, this should depend on the last executed thread and the next thread,
        but this is easier (and slightly more restrictive) to model.
        '''
        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                o.add(v.cs_delay_per_thread[T][i] >= c.CONTEXT_SHIFT_DELAY_MIN)
                # o.add(v.cs_delay_per_thread[T][i] <= c.CONTEXT_SHIFT_DELAY_MAX)
        
        '''
        Switch on/off: cs_delay is same
        '''
        if cs_delay:
            self.cs_delay_constraints(c.CONTEXT_SHIFT_DELAY_RANGE)
        
        print("DAG:", o.check())
        '''
        Number of Instructions per thread is bounded
        '''
        tot = 0
        for num_inst in v.num_instructions:
            o.add(num_inst >= c.MIN_INST_PER_THREAD)
            o.add(num_inst <= c.MAX_INST_PER_THREAD)
            tot += num_inst
        # print(c.MAX_TOTAL_INST)
        # print(c.NUM_THREADS)
        # print(c.MIN_INST_PER_THREAD)
        # print(c.MAX_INST_PER_THREAD)
        # print("DAG:", o.check())
        o.add(tot <= c.MAX_TOTAL_INST)
        # print("DAG:", o.check())

        # '''
        # Context Shift Delay per processor
        # '''
        # for i, row in enumerate(v.context_shift_delay):
        #     for j, delay in enumerate(row):
        #         if i == j:
        #             o.add(delay == 0)
        #         else:
        #             o.add(delay == c.CONTEXT_SHIFT_DELAY)


        '''
        Edge Validity Constraints: 
        1. Join edges cannot be between same thread
        2. Spawn edges cannot be between the same thread
        '''
        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                for j in range(c.MAX_INST_PER_THREAD):
                    o.add(o.Not(v.join_edge[T][i][T][j]))
        
        # print("DAG:", o.check())
        
        ## Redundant Constraint
        # '''
        # join edge is false between i > num_instr or j > num_instr
        # '''
        # for T1 in range(c.NUM_THREADS):
        #     for i1 in range(c.MAX_INST_PER_THREAD):
        #         for T2 in range(c.NUM_THREADS):
        #             for i2 in range(c.MAX_INST_PER_THREAD):
        #                 o.add(o.Implies(o.Or(i1 >= dag.num_instructions[T1],
        #                                      i2 >= dag.num_instructions[T2]),
        #                                 o.Not(v.join_edge[T1][i1][T2][i2])))

        # for T in range(c.NUM_THREADS):
        #     for i in range(c.MAX_INST_PER_THREAD):
        #         o.add(o.Not(v.spawn_edge[T][i][T]))


'''
Z3 constraints for any valid scheduling algorithm
'''
class SchedulingAlgorithm:
    c : Config
    o : MySolver
    dag : DAG
    def __init__(self, dag : DAG, pre : str) -> None:
        self.dag = dag
        self.c = dag.c
        self.o = dag.o
        c = dag.c
        o = dag.o

        self.ready_time = [[o.Real(f"{pre}_ReadyTime(T{thread}, {inst})") for inst in range(c.MAX_INST_PER_THREAD)]
                                                                   for thread in range(c.NUM_THREADS)]

        self.start_time = [[o.Real(f"{pre}_StartTime(T{thread}, {inst})") for inst in range(c.MAX_INST_PER_THREAD)] 
                                                                   for thread in range(c.NUM_THREADS)]

        self.schedule = [[[o.Bool(f"{pre}_Schedule(T{thread}, {inst}, P{proc})") for proc in range(c.NUM_PROC)]
                                                                          for inst in range(c.MAX_INST_PER_THREAD)]
                                                                          for thread in range(c.NUM_THREADS)]

        self.end_time = [[o.Real(f"{pre}_EndTime(T{thread}, {inst})") for inst in range(c.MAX_INST_PER_THREAD)]
                                                               for thread in range(c.NUM_THREADS)]

        '''
        ReadyTime: The earliest time an instruction can be executed
        1. Children are Ready after Parents are done: Parent(T1, i, T2, j) => StartTime(T1, i) + ExecTime(T1, i) <= ReadyTime(T2, j)  
        2. Children are ready immediately after the last parent completes
        3. If no parent, the node is ready at t = 0
        '''
        for T1 in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                o.add(self.ready_time[T1][i] <= self.start_time[T1][i])
                expr = []
                has_parent = []
                for T2 in range(c.NUM_THREADS):
                    for j in range(c.MAX_INST_PER_THREAD):
                        o.add(o.Implies(o.And(dag.parent[T2][j][T1][i]),
                                              self.end_time[T2][j] <= self.ready_time[T1][i]))
                        expr.append(o.And(dag.parent[T2][j][T1][i],
                                          self.ready_time[T1][i] == self.end_time[T2][j]))
                                        #   *[origin_proc == exec_proc for origin_proc, exec_proc in zip(v.origin[T1][i], v.schedule[T2][j])]))

                        has_parent.append(dag.parent[T2][j][T1][i])

                o.add(o.Implies(o.Or(*has_parent), o.Or(*expr)))
                o.add(o.Implies(o.Not(o.Or(*has_parent)), self.ready_time[T1][i] == 0))

        # EndTime = StartTime + ExecutionTime + ContextShiftTime
        # s.t. ContextShiftTime = 0 if (StartTime[T, i+1] == StartTime[T, i] + ExecutionTime[T, i], and ExecutedProc[T][i] == ExecutedProc[T][i+1])
        # else ContextShiftTime = c

        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                o.add(o.Implies(i >= dag.num_instructions[T], self.end_time[T][i] == 0))
                if i > 0:
                    last_inst_exec_on_same_proc = o.And(
                        *[self.schedule[T][i-1][P] == self.schedule[T][i][P] for P in range(c.NUM_PROC)],
                        self.ready_time[T][i] == self.end_time[T][i-1]
                    )
                    o.add(o.Implies(
                        i < dag.num_instructions[T],
                        o.Or(
                            o.And(
                                last_inst_exec_on_same_proc,
                                self.end_time[T][i] == (self.start_time[T][i] + dag.execution_time[T][i])
                            ),
                            o.And(
                                o.Not(last_inst_exec_on_same_proc),
                                self.end_time[T][i] == (self.start_time[T][i] + dag.execution_time[T][i] + dag.cs_delay_per_thread[T][i])
                            )
                        )))
                else:
                    # first instruction of each thread have context switch cost
                    o.add(o.Implies(i < dag.num_instructions[T], self.end_time[T][i] == (self.start_time[T][i] + dag.execution_time[T][i] + dag.cs_delay_per_thread[T][i])))
                
        # for row1, row2, row3 in zip(self.end_time, self.start_time, dag.execution_time):
        #     for end_time, start_time, exec_time in zip(row1, row2, row3):
        #         for P1 in range(c.NUM_PROC):
        #             for P2 in range(c.NUM_PROC):
        #                 o.add(end_time == (start_time + exec_time))

        self.time_taken = o.Real(f"{pre}_TimeTaken")

        expr1 = []
        expr2 = []
        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                expr1.append(o.Implies(i < dag.num_instructions[T], self.time_taken >= self.end_time[T][i]))
                # expr1 = o.And(expr1, o.Implies(i < dag.num_instructions[T], self.time_taken >= self.end_time[T][i]))
                expr2.append(o.And(i < dag.num_instructions[T], self.time_taken == self.end_time[T][i]))
                # expr2 = o.Or(expr2, o.And(i < dag.num_instructions[T], self.time_taken == self.end_time[T][i]))
        o.add(o.And(*expr1))
        o.add(o.Or(*expr2))


    def add_constraints(self):
        c = self.c
        o = self.o
        v = self
        dag = self.dag

        '''
        StartTime is non-negative
        '''

        for row in v.start_time:
            for start_time in row:
                o.add(start_time >= 0)
        '''
        Basic Bounds:

        1. Atleast one is true
        2. If one is true, then all others are false
        '''
        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                o.add(o.Implies(i < dag.num_instructions[T], o.Or(*(v.schedule[T][i]))))
                o.add(o.Implies(i >= dag.num_instructions[T], o.Not(o.Or(*(v.schedule[T][i])))))

                for P in range(c.NUM_PROC):
                    li = [v.schedule[T][i][x] for x in range(c.NUM_PROC) if x != P]
                    if len(li) > 0:
                        o.add(o.Implies(v.schedule[T][i][P], o.Not(o.Or(*li))))
        

        '''
        Processor cannot preempt in the middle of instructions
        '''
        for T1 in range(c.NUM_THREADS):
            for i1 in range(c.MAX_INST_PER_THREAD):
                for T2 in range(c.NUM_THREADS):
                    for i2 in range(c.MAX_INST_PER_THREAD):
                        for P in range(c.NUM_PROC):
                            if T1 != T2:
                                o.add(o.Implies(o.And(v.schedule[T1][i1][P],
                                                    v.schedule[T2][i2][P],
                                                    v.start_time[T1][i1] <= v.start_time[T2][i2]),
                                                v.end_time[T1][i1] <= v.start_time[T2][i2]))


        '''
        Sequential Edges: \forall T, i  ValidIndex(T, i) => EndTime(T, i) <= StartTime(T, i+1)
        '''
        for T in range(len(v.start_time)):
            for i in range(len(v.start_time[T])-1):
                o.add(v.end_time[T][i] <= v.start_time[T][i+1])
        
        '''
        Join Edges: \forall T1, T2, i, j
                    ValidIndex(T1, i) && ValidIndex(T2, j) && T1 != T2 && Join(T1, i, T2, j) 
                        => EndTime(T1, i) <= StartTime(T2, j)
        TODO: Add optional strict and fully strict constraints
        '''
        for T1 in range(c.NUM_THREADS):
            for i1 in range(c.MAX_INST_PER_THREAD):
                for T2 in range(c.NUM_THREADS):
                    for i2 in range(c.MAX_INST_PER_THREAD):
                        # o.add(o.Not(dag.join_edge[T1][i1][T2][i2]))
                        o.add(o.Implies(o.And(i1  < dag.num_instructions[T1], i2 < dag.num_instructions[T2], dag.join_edge[T1][i1][T2][i2]),
                                        v.end_time[T1][i1] <= v.start_time[T2][i2]))
        

        '''
        Spawn Edges: \forall T1, T2, i 
                    ValidIndex(T1, i) && T1 != T2 && Spawn(T1, i, T2) 
                        => EndTime(T1, i) <= StartTime(T2, 0)
        '''
        # for T1 in range(c.NUM_THREADS):
        #     for i in range(c.MAX_INST_PER_THREAD):
        #         for T2 in range(c.NUM_THREADS):
        #             o.add(o.Implies(o.And(i  < dag.num_instructions[T1], dag.spawn_edge[T1][i][T2]),
        #                     v.end_time[T1][i] <= v.start_time[T2][0]))

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
        for T in range(c.NUM_THREADS):
            for i in range(m[dag.num_instructions[T]].as_long()):
                P = -1
                for proc in range(c.NUM_PROC):
                    if is_true(m[v.schedule[T][i][proc]]):
                        P = proc
                        break
                start_time = self.get_num(m[v.start_time[T][i]])
                end_time = self.get_num(m[v.end_time[T][i]])
                exec_time = self.get_num(m[dag.execution_time[T][i]])
                cs_delay = self.get_num(m[dag.cs_delay_per_thread[T][i]])

                dot.node(name=f"(T{T}, {i})", label=f"(T{T}, {i}, {exec_time}, {cs_delay:.2f})\\n{start_time:.2f}-{end_time:.2f}, P{P}")
                if i < m[dag.num_instructions[T]].as_long() - 1:
                    dot.edge(f"(T{T}, {i})", f"(T{T}, {i+1})")

        # Add Join edges
        for T1 in range(c.NUM_THREADS):
            for i1 in range(m[dag.num_instructions[T1]].as_long()):
                for T2 in range(c.NUM_THREADS):
                    for i2 in range(m[dag.num_instructions[T2]].as_long()):
                        if is_true(m[dag.join_edge[T1][i1][T2][i2]]):
                            dot.edge(f"(T{T1}, {i1})", f"(T{T2}, {i2})", color='green')

        # Add Spawn edges
        # for T1 in range(c.NUM_THREADS):
        #     for i in range(m[dag.num_instructions[T1]].as_long()):
        #         for T2 in range(c.NUM_THREADS):
        #             if is_true(m[dag.spawn_edge[T1][i][T2]]):
        #                 dot.edge(f"(T{T1}, {i})", f"(T{T2}, {0})", color='red')

        dot.render(f"graphs/{name}", view=False)
        return dot

class WorkStealingAlgorithm(SchedulingAlgorithm):
    def __init__(self, dag: DAG) -> None:
        super().__init__(dag, 'WS')
        c = self.c
        o = self.o
        '''
        Work Stealing Variables
        '''
        self.origin = [[[o.Bool(f"OriginProcessor(T{thread}, {inst}, P{proc})") for proc in range(c.NUM_PROC)]
                                                                          for inst in range(c.MAX_INST_PER_THREAD)]
                                                                          for thread in range(c.NUM_THREADS)]

        self.stolen = [[o.Bool(f"Stolen(T{thread}, {inst})") for inst in range(c.MAX_INST_PER_THREAD)]
                                                                   for thread in range(c.NUM_THREADS)]

        '''
        Number of instructions executed by each processor
        '''
        # self.num_instructions_exec = [o.Int(f"NumInstructionsExec({proc})") for proc in range(c.NUM_PROC)]

        # '''
        # Ordered list of instructions as executed by each processor
        # (T, i, StartTime, EndTime, ReadyTime)
        # '''
        # self.ordered_instructions = [[(o.Int(f"OrderedInstThread({proc}, {i})"), o.Int(f"OrderedInstNum({proc}, {i})"), 
        #                                o.Real(f"StartTime({proc}, {i})"), o.Real(f"EndTime({proc}, {i})"), o.Real(f"ReadyTime({proc}, {i})")) for i in range(c.MAX_INST_PER_THREAD * c.NUM_THREADS)]
        #                                                                                                                 for proc in range(c.NUM_PROC)]

    def ordered_executed_inst(self):
        pass
    
    '''
    Returns a Z3 Boolean expression.
    True if no instruction was executed by `P` between (T1, i1) and (T2, i2)
    '''
    def are_instructions_sequential(self, T1: int, i1: int, T2: int, i2: int, P: int) -> BoolRef:
        error
        return True
        c = self.c
        o = self.o
        v = self

        expr = []
        dag = self.dag
        for T in range(c.NUM_THREADS):
            for j in range(c.MAX_INST_PER_THREAD):
                expr.append(o.Implies(o.And(v.schedule[T][j][P]),
                                            o.Or(v.end_time[T][j] <= v.start_time[T1][i1],
                                                 v.start_time[T][j] >= v.end_time[T2][i2])))
                # expr = o.And(expr, o.Implies(o.And(j < dag.num_instructions[T],
                #                                    v.schedule[T][j][P]),
                #                             o.Or(v.end_time[T][j] <= v.start_time[T1][i1],
                #                                  v.start_time[T][j] >= v.end_time[T2][i2])))

        return o.And(*expr)

    '''
    Returns a Z3 boolean expression.
    True if processor `P` is free during any time in the interval [t1, t2]
    '''
    def is_processor_free(self, P : int, t1, t2) -> BoolRef:
        error
        return True
        c = self.c
        o = self.o
        v = self
        dag = self.dag

        expr = False
        for T1 in range(c.NUM_THREADS):
            for i1 in range(c.MAX_INST_PER_THREAD):
                for T2 in range(c.NUM_THREADS):
                    for i2 in range(c.MAX_INST_PER_THREAD):
                        expr = o.Or(expr, o.And(i1 < dag.num_instructions[T1],
                                                i2 < dag.num_instructions[T2],
                                                v.schedule[T1][i1][P],
                                                v.schedule[T2][i2][P],
                                                v.start_time[T1][i1] < v.start_time[T2][i2],
                                                self.are_instructions_sequential(T1, i1, T2, i2, P),
                                                o.Not(o.Or(v.start_time[T2][i2] <= t1,
                                                           v.end_time[T1][i1] >= t2))))


        return expr
        # # Case 1: at time `t`, no instruction is executing on P 
        # # [2, 3]: Is this processor free at t = 3
        # expr1 = True
        # for T in range(c.NUM_THREADS):
        #     for i in range(c.MAX_INST_PER_THREAD):
        #         expr1 = o.And(expr1, 
        #                     o.Implies(o.And(i < dag.num_instructions[T],
        #                                     v.schedule[T][i][P]),
        #                             o.Or(v.start_time[T][i] > t, v.end_time[T][i] <= t)))
        
        # # Case 2: at time `t`, an instruction just ended, but no new instruction started on P
        # # expr2 = False
        # # for T1 in range(c.NUM_THREADS):
        # #     for i in range(c.MAX_INST_PER_THREAD):
        # #         start_time_does_not_match_same_thread = True
        # #         start_time_does_not_match_diff_thread = True
        # #         for T2 in range(c.NUM_THREADS):
        # #             for j in range(c.MAX_INST_PER_THREAD):
        # #                 if T1 == T2:
        # #                     start_time_does_not_match_same_thread = o.And(start_time_does_not_match_same_thread, 
        # #                                                     o.Implies(o.And(j < dag.num_instructions[T2],
        # #                                                                     v.schedule[T2][j][P]),
        # #                                                                 o.Not(v.start_time[T2][j] == v.end_time[T1][i])))
        # #                 else:
        # #                     start_time_does_not_match_diff_thread = o.And(start_time_does_not_match_diff_thread, 
        # #                                                     o.Implies(o.And(j < dag.num_instructions[T2],
        # #                                                                     v.schedule[T2][j][P]),
        # #                                                                 o.Not(v.start_time[T2][j] == v.end_time[T1][i] + c.CONTEXT_SHIFT_DELAYx)))
            
        #         # expr2 = o.Or(expr2, o.And(i < dag.num_instructions[T1],
        #         #                           v.schedule[T1][i][P],
        #         #                           t == v.end_time[T1][i],
        #         #                           start_time_does_not_match))

    '''
    Returns a Z3 boolean expression.
    True if processor `P` is busy during the entire interval [t1, t2]
    '''
    def is_proc_busy(self, P : int, t1, t2) -> BoolRef:
        c = self.c
        o = self.o
        v = self
        dag = self.dag
        
        # There exists a job encompassing the entire interval [t1, t2]
        expr1 = []
        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                expr1.append(o.And(v.schedule[T][i][P],
                                   v.start_time[T][i] <= t1,
                                   v.end_time[T][i] >= t2))
                # expr1 = o.Or(expr1, o.And(i < dag.num_instructions[T],
                #                           v.schedule[T][i][P],
                #                           v.start_time[T][i] <= t1,
                #                           v.end_time[T][i] >= t2))

        # There exists atleast one job starting before t1 and ending between [t1, t2], and
        # for all jobs ending in [t1, t2], there exists a job starting at the same time
        expr2 = []
        job_ends_in_interval = []
        for T1 in range(c.NUM_THREADS):
            for i1 in range(c.MAX_INST_PER_THREAD):
                job_ends_in_interval.append(o.And(v.schedule[T1][i1][P],
                                                  v.start_time[T1][i1] <= t1,
                                                  v.end_time[T1][i1] >= t1,
                                                  v.end_time[T1][i1] < t2))
                # job_ends_in_interval = o.Or(job_ends_in_interval,
                #                             o.And(i1 < dag.num_instructions[T1],
                #                                   v.schedule[T1][i1][P],
                #                                   v.start_time[T1][i1] <= t1,
                #                                   v.end_time[T1][i1] >= t1,
                #                                   v.end_time[T1][i1] < t2))
                inst_begins_right_after = []
                for T2 in range(c.NUM_THREADS):
                    for i2 in range(c.MAX_INST_PER_THREAD):
                        inst_begins_right_after.append(o.And(v.schedule[T2][i2][P],
                                                             v.start_time[T2][i2] == v.end_time[T1][i1]))
                        # inst_begins_right_after = o.Or(inst_begins_right_after, o.And(i2 < dag.num_instructions[T2],
                        #                           v.schedule[T2][i2][P],
                        #                           v.start_time[T2][i2] == v.end_time[T1][i1]))
                
                expr2.append(o.Implies(o.And(v.schedule[T1][i1][P],
                                                     v.end_time[T1][i1] >= t1,
                                                     v.end_time[T1][i1] < t2),
                                               o.Or(*inst_begins_right_after)))
                # expr2 = o.And(expr2, o.Implies(o.And(i1 < dag.num_instructions[T1],
                #                                      v.schedule[T1][i1][P],
                #                                      v.end_time[T1][i1] >= t1,
                #                                      v.end_time[T1][i1] < t2),
                #                                inst_begins_right_after))
        

        return o.Or(o.Or(*expr1), o.And(o.Or(*job_ends_in_interval), o.And(*expr2)))


    def add_constraints(self):
        super().add_constraints()
        c = self.c
        o = self.o
        v = self
        dag = self.dag
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
        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                # 1.
                o.add(o.Implies(i < dag.num_instructions[T], o.Or(*(v.origin[T][i]))))

                for P in range(c.NUM_PROC):
                    li = [v.origin[T][i][x] for x in range(c.NUM_PROC) if x != P]
                    if len(li) > 0:
                        o.add(o.Implies(v.origin[T][i][P], o.Not(o.Or(*li))))

        print("Origin Processor 1", o.check())

        for T1 in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                has_parent = []
                expr = []
                # For every inst (T1, i), if (T2, j) is its parent, then Schedule(T2, j) can be Origin(T1, i)
                for T2 in range(c.NUM_THREADS):
                    for j in range(c.MAX_INST_PER_THREAD):
                        has_parent.append(dag.parent[T2][j][T1][i])
                        # has_parent = o.Or(has_parent, o.And(i < dag.num_instructions[T1],
                        #                                     j < dag.num_instructions[T2],
                        #                                     dag.parent[T2][j][T1][i]))
                        
                        expr.append(o.And(dag.parent[T2][j][T1][i],
                                                *[orig_proc == sched_proc for orig_proc, sched_proc in zip(v.origin[T1][i], v.schedule[T2][j])]))
                        # expr = o.Or(expr, o.And(i < dag.num_instructions[T1],
                        #                         j < dag.num_instructions[T2],
                        #                         dag.parent[T2][j][T1][i],
                        #                         *[orig_proc == sched_proc for orig_proc, sched_proc in zip(v.origin[T1][i], v.schedule[T2][j])]))

                o.add(o.Implies(o.Or(*has_parent), o.Or(*expr)))

        print("Origin Processor 2", o.check())

        # for T in range(c.NUM_THREADS):
        #     for i in range(c.MAX_INST_PER_THREAD-1):
        #         for P in range(c.NUM_PROC):
        #             o.add(o.Implies(o.And(i + 1 < dag.num_instructions[T],
        #                                 v.schedule[T][i][P], v.origin[T][i+1][P]))
        # print(o.check())

        # for T1 in range(c.NUM_THREADS):
        #     for i in range(c.MAX_INST_PER_THREAD):
        #         for T2 in range(c.NUM_THREADS):
        #             for P in range(c.NUM_PROC):
        #                 o.add(o.Implies(o.And(i < dag.num_instructions[T1],
        #                                     dag.spawn_edge[T1][i][T2],
        #                                     v.schedule[T1][i][P]),
        #                                 v.origin[T2][0][P]))

        # print(o.check())

        # Helper expression: True if origin proc is the same as executed proc
        def origin_same_as_execution(T1, i1, T2, i2):
            return o.Or(*[o.And(v.origin[T1][i1][P], v.schedule[T2][i2][P]) for P in range(c.NUM_PROC)])

        def same_origin_instructions(T1, i1, T2, i2):
            return o.Or(*[o.And(v.origin[T1][i1][P], v.origin[T2][i2][P]) for P in range(c.NUM_PROC)])

        '''
        Stolen(T, i):
        '''
        for T in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                o.add(v.stolen[T][i] == o.Not(origin_same_as_execution(T, i, T, i)))

        print("Stolen", o.check())

        '''
        Work Stealing Algorithm
        1. A processor can only steal when its queue is empty
        2. A processor can only steal the oldest instruction in another processor’s queue.
        3. A processor only executes the youngest instruction in its own queue.
        4. Minimize Context Switches -- consecutive instructions must run on same proc if possible
        '''
        for T1 in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                expr1 = []
                expr2 = []
                expr3 = []
                # 4.
                if i < c.MAX_INST_PER_THREAD-1:
                    for P in range(c.NUM_PROC):
                        o.add(o.Implies(
                            o.And(
                                v.ready_time[T1][i+1] <= v.end_time[T1][i],
                                v.schedule[T1][i][P],
                                i+1 < dag.num_instructions[T]
                                ),
                            v.schedule[T1][i+1][P]
                        ))
                for T2 in range(c.NUM_THREADS):
                    for j in range(c.MAX_INST_PER_THREAD):
                        expr1.append(o.Or(o.Implies(o.And(i < dag.num_instructions[T1], j < dag.num_instructions[T2],
                                                        o.Not(v.stolen[T2][j]),
                                                        origin_same_as_execution(T2, j, T1, i)),
                                                    o.Or(v.end_time[T2][j] <= v.start_time[T1][i],
                                                        v.ready_time[T2][j] > v.start_time[T1][i])),
                                        o.Implies(o.And(i < dag.num_instructions[T1], j < dag.num_instructions[T2],
                                                        v.stolen[T2][j],
                                                        origin_same_as_execution(T2, j, T1, i),
                                                        v.ready_time[T2][j] < v.start_time[T1][i]),
                                                    v.start_time[T2][j] < v.start_time[T1][i])))

                        expr2.append(o.Implies(o.And(i < dag.num_instructions[T1], j < dag.num_instructions[T2],
                                                same_origin_instructions(T1, i, T2, j)),
                                                o.Or(v.ready_time[T1][i] <= v.ready_time[T2][j],
                                                    v.start_time[T2][j] <= v.start_time[T1][i])))

                        expr3.append(o.Implies(o.And(i < dag.num_instructions[T1], j < dag.num_instructions[T2],
                                                    o.Not(v.stolen[T2][j]),
                                                    same_origin_instructions(T1, i, T2, j)),
                                                o.Or(v.ready_time[T1][i] <= v.ready_time[T2][j],
                                                    v.end_time[T2][j] <= v.ready_time[T1][i])))

                o.add(o.Implies(o.And(v.stolen[T1][i]),
                                o.And(*expr1)))

                o.add(o.Implies(o.And(v.stolen[T1][i]),
                                o.And(*expr2)))

                o.add(o.Implies(o.And(o.Not(v.stolen[T1][i])),
                                o.And(*expr3)))
        
        print("Work Stealing", o.check())


        # '''
        # List of instructions executed by a processor ordered by start time
        # 1. Every Instruction must be a part of list[P]
        # 2. Every instruction of list[P] for ind < num_instructions_exec[P] should be unique, and executed by P
        # 3. Start time of instruction i+1 >= start time of instruction i
        # 4. (Work Conserving) StartTime of ind == EndTime of ind-1 OR ReadyTime of ind
        # 5. (Work Conserving) StartTime of list[P][0] == ReadyTime[P][0]
        # 6. (Work Conserving) For every instruction i which was started between EndTime(P)(j) and StartTime(P)(j+1)
        #                      StartTime(i) == ReadyTime(i)
        # '''
        # for P in range(c.NUM_PROC):
        #     o.add(v.num_instructions_exec[P] >= 0)
        
        # for T in range(c.NUM_THREADS):
        #     for i in range(c.MAX_INST_PER_THREAD):
        #         for P in range(c.NUM_PROC):
        #             # 1.
        #             o.add(o.Implies(o.And(i < dag.num_instructions[T],
        #                                   v.schedule[T][i][P]),
        #                             o.Or(*[o.And(ind < v.num_instructions_exec[P],
        #                                          T == v.ordered_instructions[P][ind][0],
        #                                          i == v.ordered_instructions[P][ind][1],
        #                                          v.start_time[T][i] == v.ordered_instructions[P][ind][2],
        #                                          v.end_time[T][i] == v.ordered_instructions[P][ind][3],
        #                                          v.ready_time[T][i] == v.ordered_instructions[P][ind][4]) for ind in range(c.MAX_TOTAL_INST)])))

        # for ind in range(c.MAX_TOTAL_INST):
        #     for P in range(c.NUM_PROC):
        #         inst_exec_by_P = []
        #         for T in range(c.NUM_THREADS):
        #             for i in range(c.MAX_INST_PER_THREAD):
        #                 inst_exec_by_P.append(o.And(i < dag.num_instructions[T],
        #                                             T == v.ordered_instructions[P][ind][0],
        #                                             i == v.ordered_instructions[P][ind][1],
        #                                             v.start_time[T][i] == v.ordered_instructions[P][ind][2],
        #                                             v.end_time[T][i] == v.ordered_instructions[P][ind][3],
        #                                             v.ready_time[T][i] == v.ordered_instructions[P][ind][4],
        #                                             v.schedule[T][i][P]))
        #         o.add(o.Implies(ind < v.num_instructions_exec[P], o.Or(*inst_exec_by_P)))
        # print("WC: 1", o.check())

        # for ind in range(1, c.MAX_TOTAL_INST):
        #     for P in range(c.NUM_PROC):
        #         # 2.
        #         o.add(o.Implies(o.And(ind < v.num_instructions_exec[P],
        #                               v.ordered_instructions[P][ind][0] == v.ordered_instructions[P][ind-1][0]),
        #                         o.Not(v.ordered_instructions[P][ind][1] == v.ordered_instructions[P][ind-1][1])))
                
        #         # 3.
        #         o.add(o.Implies(ind < v.num_instructions_exec[P],
        #                         v.ordered_instructions[P][ind][2] > v.ordered_instructions[P][ind-1][2]))

        #         # 4.
        #         o.add(o.Implies(ind < v.num_instructions_exec[P],
        #                         o.Or(v.ordered_instructions[P][ind][2] == v.ordered_instructions[P][ind-1][3],
        #                              v.ordered_instructions[P][ind][2] == v.ordered_instructions[P][ind][4])))
        # print("WC: 4", o.check())

        # # 5.
        # for P in range(c.NUM_PROC):
        #     o.add(o.Implies(0 < v.num_instructions_exec[P],
        #                     v.ordered_instructions[P][0][2] == v.ordered_instructions[P][0][4]))
        # print("WC: 5", o.check())

        # # 6.
        # for P in range(c.NUM_PROC):
        #     # start_match_ready_before_first = []
        #     # for T in range(c.NUM_THREADS):
        #     #     for i in range(c.MAX_INST_PER_THREAD):
        #     #         start_match_ready_before_first.append(o.Implies(o.And(i < dag.num_instructions[T],
        #     #                                                                   v.start_time[T][i] <= v.ordered_instructions[P][0][2]),
        #     #                                                             v.start_time[T][i] == v.ready_time[T][i]))
        #     # o.add(o.Implies(v.num_instructions_exec[P] > 0, o.And(*start_match_ready_before_first)))
        #     for ind in range(c.MAX_TOTAL_INST):
        #         start_match_ready_between = []
        #         start_match_ready_after_last = []
        #         for T in range(c.NUM_THREADS):
        #             for i in range(c.MAX_INST_PER_THREAD):
        #                 if ind > 0:
        #                     # 3 -> EndTime, 2 -> StartTime
        #                     # P -> 0  [1s, 1e]   [2s, 2e]   [3s, 3e]                 
        #                     start_match_ready_between.append(o.Implies(o.And(i < dag.num_instructions[T],
        #                                                                     v.start_time[T][i] >= v.ordered_instructions[P][ind-1][3],
        #                                                                     v.ready_time[T][i] < v.ordered_instructions[P][ind][2]),
        #                                                                     o.Or(v.start_time[T][i] == v.ready_time[T][i],
        #                                                                          v.start_time[T][i] == v.ordered_instructions[P][ind-1][3])))
        #                 else:
        #                     start_match_ready_between.append(o.Implies(o.And(i < dag.num_instructions[T],
        #                                                                     v.start_time[T][i] >= 0,
        #                                                                     v.ready_time[T][i] < v.ordered_instructions[P][ind][2]),
        #                                                                     o.Or(v.start_time[T][i] == v.ready_time[T][i],
        #                                                                          v.start_time[T][i] == 0)))
        #                 start_match_ready_after_last.append(o.Implies(o.And(i < dag.num_instructions[T],
        #                                                                     v.start_time[T][i] >= v.ordered_instructions[P][ind][3]),
        #                                                               o.Or(v.start_time[T][i] == v.ready_time[T][i],
        #                                                                    v.start_time[T][i] == v.ordered_instructions[P][ind][3])))
        #         o.add(o.Implies(ind+1 == v.num_instructions_exec[P],
        #                         o.And(*start_match_ready_after_last)))
                
        #         o.add(o.Implies(ind < v.num_instructions_exec[P],
        #                         o.And(*start_match_ready_between)))

        # print("WC: 6.1", o.check())

        # # 6. (pathological case: if a proc NEVER executes an instruction, then every instruction executes as soon as its ready)
        # start_match_ready = []
        # for T in range(c.NUM_THREADS):
        #     for i in range(c.MAX_INST_PER_THREAD):
        #         start_match_ready.append(o.Implies(i < dag.num_instructions[T],
        #                                            v.start_time[T][i] == v.ready_time[T][i]))
        # print("WC: 6.2", o.check())
        
        # completely_free_proc = [v.num_instructions_exec[P] == 0 for P in range(c.NUM_PROC)]
        # o.add(o.Implies(o.Or(*completely_free_proc), o.And(*start_match_ready)))

        '''
        Work Conserving: \forall P, i !FreeProcessor(P, [ReadyTime(i), StartTime(i)])
        '''
        for P in range(c.NUM_PROC):
            for T in range(c.NUM_THREADS):
                for i in range(c.MAX_INST_PER_THREAD):
                    var = o.Bool(f"BusyBW_{T}_{i}")
                    o.add(var == self.is_proc_busy(P, v.ready_time[T][i], v.start_time[T][i]))
                    o.add(o.Implies(o.And(i < dag.num_instructions[T], 
                                    v.start_time[T][i] != v.ready_time[T][i]),
                                    var))

        print("Work Conserving", o.check())


class OptimalAlgorithm(SchedulingAlgorithm):
    def __init__(self, dag: DAG) -> None:
        super().__init__(dag, 'GO')

class WorkConservingOptimalAlgorithm(SchedulingAlgorithm):
    def __init__(self, dag: DAG) -> None:
        super().__init__(dag, 'WCGO')
        

class Metrics:
    def __init__(self, dag: DAG) -> None:
        self.dag = dag
        self.c = dag.c
        self.o = dag.o
        
        o = self.o
        c = self.c

        self.t_inf = [[o.Real(f"t_inf({T},{i})") for i in range(c.MAX_INST_PER_THREAD)]
                                                 for T in range(c.NUM_THREADS)]
        
        self.t_inf_total = o.Real("t_inf_total")

        self.t_1 = o.Real("t_1")
        pass

    def add_constraints(self):
        dag = self.dag
        o = self.o
        c = self.c

        # t_1 is just sum of all execution times
        o.add(self.t_1 == sum([dag.execution_time[T][i] + dag.cs_delay_per_thread[T][i] for T in range(c.NUM_THREADS) for i in range(c.MAX_INST_PER_THREAD)]))

        # t_inf == execution time for instructions without any parents
        # t_inf_total = max(t_inf)
        for T1 in range(c.NUM_THREADS):
            for i in range(c.MAX_INST_PER_THREAD):
                has_parent = []

                for T2 in range(c.NUM_THREADS):
                    for j in range(c.MAX_INST_PER_THREAD):
                        is_parent = o.And(dag.parent[T2][j][T1][i])
                        has_parent.append(is_parent)

                        o.add(o.Implies(is_parent, self.t_inf[T1][i] >= self.t_inf[T2][j] + dag.execution_time[T1][i]))
                
                o.add(o.Implies(o.Not(o.Or(*has_parent)),
                                self.t_inf[T1][i] == dag.execution_time[T1][i]))
                
                o.add(self.t_inf_total >= self.t_inf[T1][i])
        

def binary_search(o : MySolver, e1, e2, low = 1, high = 2, eps = 0.01):
    ans = 1
    m = None
    while high - low > eps:
        mid = (high + low) / 2
        o.push()
        o.add(e1 >= mid * e2)
        print(f"Checking for {mid}")
        if o.check() != sat:
            high = mid
            print("Doesn't work for", mid)
        else:
            print("Works for", mid)
            ans = mid
            low = mid
            m = o.model()
        o.pop()
    
    return ans, m


if __name__ == '__main__':
    c = Config()
    o = MySolver()

    dag = DAG(c, o)
    dag.add_constraints(cs_delay=True)
    ws = WorkStealingAlgorithm(dag)
    ws.add_constraints()
    opt = OptimalAlgorithm(dag)
    opt.add_constraints()
    # metrics = Metrics(dag)
    # metrics.add_constraints()
    
    print("Added all constraints:", o.check())
    ans, m = binary_search(o, ws.time_taken, opt.time_taken)
    ws.visualize(m, "ws_model")
    opt.visualize(m, "opt_model")
    
    # Query
    # metrics = Metrics(dag)
    # metrics.add_constraints()
    # ans, m = binary_search(o, ws.time_taken * c.NUM_PROC, metrics.t_1)
    # is_sat = o.check()
    # print("Added Query: ", is_sat)

    with open('model.out', 'w') as f:
        for v in o.variables:
            print(v,"=", m[o.variables[v]], file=f)
    print(o.statistics())
    # if is_sat == sat:
    #     m = o.model()
    #     with open("model.out", 'w') as f:
    #         print(m, file=f)
    #     print("Visualizing model")
    #     ws.visualize(m, "ws_model")
    
    # # Test stuff
    # print("Checking!")
    # o.add(o.And(opt.start_time[0][0] <= opt.start_time[1][0],
    #             opt.end_time[0][0] > opt.start_time[1][0],
    #             opt.schedule[0][0][2],
    #             opt.schedule[1][0][2]))

    # print(o.check())

    # m = o.model()
    # print(o.model())

    # o.add(ws.time_taken > 1.5 * opt.time_taken)
    # with open("out2.log", 'w') as f:
    #     print(str(o.to_smt2()), file = f)
    # print(len(o.assertions()))
    # print("Done")
    # # ratio, model = binary_search(o, ws.time_taken, opt.time_taken)
    # # ws.visualize(model, "ws")
    # # opt.visualize(model, "opt")
    # # o.maximize(ws.time_taken / opt.time_taken)
    # print(o.check())
    # # m = o.model()
    # print(o.statistics())
    # # print(m[ws.time_taken].as_decimal(3), m[opt.time_taken].as_decimal(3))
    # # # print(o.statistics())
    # # # Print all models
    # i = 1
    # for m in o.all_smt([dag.num_instructions[T] for T in range(c.NUM_THREADS)]):
    #     ws.visualize(m, f"{i}_ws")
    #     opt.visualize(m, f"{i}_opt")
    #     print(m)
    #     print(m[ws.time_taken].as_decimal(3), m[opt.time_taken].as_decimal(3))
    #     i += 1
    #     if i >= 1:
    #         break
