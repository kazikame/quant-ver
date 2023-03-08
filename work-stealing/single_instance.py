from fractions import Fraction
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from timeit import default_timer as timer
from my_solver import MySolver
import sys
from typing import Any, Dict, List, Tuple, Union
import z3
from z3 import And, If, Implies, Not, Or,\
    is_algebraic_value, is_int_value, is_rational_value
import sys
import graphviz

ModelDict = Dict[str, Union[Fraction, bool]]


def model_to_dict(model: z3.ModelRef) -> ModelDict:
    ''' Utility function that takes a z3 model and extracts its variables to a
    dict'''
    decls = model.decls()
    res: Dict[str, Union[Fraction, bool]] = {}
    for d in decls:
        val = model[d]
        if type(val) == z3.BoolRef:
            res[d.name()] = bool(val)
        elif type(val) == z3.IntNumRef:
            res[d.name()] = Fraction(val.as_long())
        else:
            # Assume it is numeric
            res[d.name()] = val.as_fraction()
    return res


class Config:
    # number of processors
    P: int = 2
    # Number of instructions per processor
    I: int = 3

    # Ratio of Context Switch Cost to instruction duration
    R: float = 0
    def __init__(self, proc=2, inst=3) -> None:
        self.P = proc
        self.I = inst
        self.R = 0



class Variables:
    def __init__(self, c: Config, s: MySolver):
        # Convenience variable with a list of all instructions
        self.instrs = []
        for p in range(c.P):
            self.instrs.extend([(p, i) for i in range(c.I)])

        # Execution time for each instruction
        self.instr_dur = [[s.Real(f"instr_dur_{p},{i}") for i in range(c.I)]
                          for p in range(c.P)]

        # Start and end times for each instruction
        self.start = [[s.Real(f"start_{p},{i}") for i in range(c.I)]
                      for p in range(c.P)]
        self.end = [[s.Real(f"end_{p},{i}") for i in range(c.I)]
                    for p in range(c.P)]

        # When all of the instructions parents stopped executing
        self.ready = [[s.Real(f"ready_{p},{i}") for i in range(c.I)]
                      for p in range(c.P)]

        # Whether or not there is an join/seq edge from instruction 1 to 2
        self.join_edge = [[[[s.Bool(f"join_edge_{p1},{i1},{p2},{i2}")
                        for i2 in range(c.I)] for p2 in range(c.P)]
                      for i1 in range(c.I)] for p1 in range(c.P)]
        self.seq_edge = [[[[s.Bool(f"seq_edge_{p1},{i1},{p2},{i2}")
                        for i2 in range(c.I)] for p2 in range(c.P)]
                      for i1 in range(c.I)] for p1 in range(c.P)]

        # If there were infinitely many processors, this would be
        # the earliest time at which it can be scheduled
        self.t_inf = [[s.Real(f"t_inf_{p},{i}") for i in range(c.I)]
                      for p in range(c.P)]

        # If there was just one processor, this is how long it would
        # take to execute all instructions
        self.t_1 = s.Real("t_1")


        self.switch_cost = s.Real("switch_cost")
        self.min_execution_cost = s.Real("min_execution_cost")


class VariableNames:
    ''' Class with the same structure as Variables, but with just the names '''
    instrs: List[Tuple[int, int]]
    instr_dur: List[List[str]]
    start: List[List[str]]
    end: List[List[str]]
    
    join_edge: List[List[List[str]]]
    seq_edge:  List[List[List[str]]]
    t_inf: List[List[str]]
    t_1: str

    def __init__(self, v: Variables):
        for x in v.__dict__:
            if type(v.__dict__[x]) == list:
                self.__dict__[x] = self.to_names(v.__dict__[x])
            else:
                self.__dict__[x] = str(x)

    @classmethod
    def to_names(cls, x: List[Any]):
        res = []
        for y in x:
            if type(y) == list:
                res.append(cls.to_names(y))
            else:
                if type(y) in [bool, int, float, tuple]:
                    if type(y) == tuple:
                        assert(len(y) == 2 and type(y[0]) == int)
                    res.append(y)
                else:
                    res.append(str(y))
        return res


def valid_schedule(c: Config, s: MySolver, v: Variables):
    ''' Ensure that the schedule is a valid one '''

    # Simple bounds
    for (p, i) in v.instrs:
        # Execution times are positive (disallowing zero disallows cycles)
        s.add(v.instr_dur[p][i] > v.min_execution_cost)
        # Start times are non-negative
        s.add(v.start[p][i] >= 0)


    # Sequential Edges: atmost one outgoing and one incoming
    for (p1, i1) in v.instrs:
        for (p2, i2) in v.instrs:
            s.add(Implies(v.seq_edge[p1][i1][p2][i2], Not(Or(*[v.seq_edge[p1][i1][p3][i3] for (p3, i3) in v.instrs if (p3, i3) != (p2, i2)]))))
            s.add(Implies(v.seq_edge[p2][i2][p1][i1], Not(Or(*[v.seq_edge[p3][i3][p1][i1] for (p3, i3) in v.instrs if (p3, i3) != (p2, i2)]))))

    # If one instruction depends on another, it should start after it
    for (p1, i1) in v.instrs:
        for (p2, i2) in v.instrs:
            s.add(Implies(Or(v.join_edge[p1][i1][p2][i2], v.seq_edge[p1][i1][p2][i2]),
                          v.start[p2][i2] >= v.end[p1][i1]))

    # One processor cannot execute multiple instructions at the same time
    for (p, i) in v.instrs:
        if i < c.I - 1:
            s.add(v.start[p][i+1] >= v.end[p][i])

    # Instructions take time to execute
    for (p1, i1) in v.instrs:
        # If we depend on an instruction in a different processor, add
        # communication cost
        if i1 > 0:
            # switched = Not(v.edge[p1][i1-1][p1][i1])
            # switched = Or(*[v.edge[p2][i2][p1][i1]
            #                 for (p2, i2) in v.instrs if p1 != p2])
            switched = Not(v.seq_edge[p1][i1-1][p1][i1])
        else:
            switched = True

        s.add(Implies(Not(switched), v.end[p1][i1] ==
                      v.start[p1][i1] + v.instr_dur[p1][i1]))
        s.add(Implies(switched, v.end[p1][i1] ==
                      v.start[p1][i1] + v.instr_dur[p1][i1] + v.switch_cost))

    # Compute ready time
    for (p1, i1) in v.instrs:
        equals = [v.ready[p1][i1] == 0]
        for (p2, i2) in v.instrs:
            # Ready time is greater than end time of parents
            s.add(Implies(Or(v.join_edge[p2][i2][p1][i1], v.seq_edge[p2][i2][p1][i1]),
                          v.ready[p1][i1] >= v.end[p2][i2]))

            # Ready time is equal to at least one of the parents or to 0
            equals.append(And(Or(v.join_edge[p2][i2][p1][i1], v.seq_edge[p2][i2][p1][i1]),
                              v.ready[p1][i1] == v.end[p2][i2]))
        s.add(Or(*equals))

        # Redundant constraint: start time >= ready time
        s.add(v.start[p1][i1] >= v.ready[p1][i1])


def work_conserving(c: Config, s: MySolver, v: Variables):
    ''' Ensure that work is conserved '''
    
    # If start time > ready time, no processors were free in that period
    for (p1, i1) in v.instrs:
        # Start and end times of our period of interest
        period = (v.ready[p1][i1], v.start[p1][i1])

        # Was processsor p2 available? That is, one of the gaps must overlap
        # with our period of interest
        for p2 in range(c.P):
            available = [v.start[p2][0] > period[0]]
            for i2 in range(c.I-1):
                available.append(And(
                    v.start[p2][i2+1] > period[0],
                    v.end[p2][i2] < period[1],
                    v.start[p2][i2+1] > v.end[p2][i2]))
            available.append(v.end[p2][-1] < period[1])

            s.add(Implies(v.start[p1][i1] > v.ready[p1][i1],
                          Not(Or(*available))))


def work_stealing(c: Config, s: MySolver, v: Variables):
    ''' Ensure that work stealing is respected '''

    for (p1, i1) in v.instrs:
        stolen = Or(*[Or(v.join_edge[p2][i2][p1][i1], v.seq_edge[p2][i2][p1][i1])
                      for (p2, i2) in v.instrs if p2 != p1])

        # If an instruction is stolen, we were done with all other tasks
        # spawned from p1
        local_fin = []
        for i_prev in range(i1):
            local_fin.append(And(*[Implies(Or(v.join_edge[p1][i_prev][p2][i2], v.seq_edge[p1][i_prev][p2][i2]),
                                           v.end[p2][i2] <= v.start[p1][i1])
                                   for (p2, i2) in v.instrs if p2 != p1]))
        s.add(Implies(stolen, And(*local_fin)))

        # If an instruction was stolen, the source processor was busy
        for p2 in range(c.P):
            busy = Or(*[And(v.start[p2][i2] <= v.start[p1][i1],
                            v.end[p2][i2] >= v.start[p1][i1])
                        for i2 in range(c.I)])
            for i2 in range(c.I):
                if p1 == p2:
                    continue
                s.add(Implies(Or(v.join_edge[p2][i2][p1][i1], v.seq_edge[p2][i2][p1][i1]), busy))

    # Execute an instruction that is the child of the latest instruction if
    # possible
    for (p1, i1) in v.instrs:
        if i1 == c.I - 1:
            # The last instruction is not allowed to have children since there
            # is no scope of executing in this processor
            for (p2, i2) in v.instrs:
                s.add(Not(Or(v.join_edge[p1][i1][p2][i2], v.seq_edge[p1][i1][p2][i2])))
            continue

        # Is a child available to be executed?
        seq_child = []
        join_child = []
        for (p2, i2) in v.instrs:
            seq_child.append(And(v.seq_edge[p1][i1][p2][i2],
                             v.ready[p2][i2] == v.end[p1][i1]))
            join_child.append(And(v.join_edge[p1][i1][p2][i2],
                             v.ready[p2][i2] == v.end[p1][i1]))

        seq_child = Or(*seq_child)
        join_child = Or(*join_child)
        
        s.add(Implies(Not(v.seq_edge[p1][i1][p1][i1+1]),
                      Not(seq_child)))
        
        s.add(Implies(Not(Or(v.join_edge[p1][i1][p1][i1+1], v.seq_edge[p1][i1][p1][i1+1])),
                      Not(Or(seq_child, join_child))))

    # TODO: execute instructions in the correct order
    # TODO: steal the oldest instruction first


def theoretical_execution_times(c: Config, s: MySolver, v: Variables):
    ''' Compute the theoretical execution times '''

    # If an instruction has no parents, switching is inevitable
    switching = [[Not(Or(*[v.seq_edge[p2][i2][p1][i1] for (p2, i2) in v.instrs]))
                  for i1 in range(c.I)] for p1 in range(c.P)]

    # If there is just one processor, the execution time is the sum
    # of the execution times
    s.add(v.t_1 == sum([v.instr_dur[p][i]
                        + If(switching[p][i], v.switch_cost, 0)
                       for (p, i) in v.instrs]))
    # s.add(v.t_1 == sum([v.instr_dur[p][i]
    #                     + v.switch_cost
    #                    for (p, i) in v.instrs]))
    # If there are infinitely many processors, the t_inf is the
    # maximum of the t_inf of all its parents
    for (p1, i1) in v.instrs:
        equals = [v.t_inf[p1][i1] == v.switch_cost + v.instr_dur[p1][i1]]
        for (p2, i2) in v.instrs:
            # Greater than any of the parents
            s.add(Implies(v.seq_edge[p2][i2][p1][i1],
                          v.t_inf[p1][i1] >=
                          v.t_inf[p2][i2] + v.instr_dur[p1][i1]))
            s.add(Implies(And(v.join_edge[p2][i2][p1][i1], Not(v.seq_edge[p2][i2][p1][i1])),
                          v.t_inf[p1][i1] >=
                          v.t_inf[p2][i2] + v.instr_dur[p1][i1] + v.switch_cost))
            # Equal to (switch cost + dur) or equal to at least one of its
            # parents + dur
            equals.append(And(v.seq_edge[p2][i2][p1][i1],
                              v.t_inf[p1][i1] ==
                              v.t_inf[p2][i2] + v.instr_dur[p1][i1]))

            equals.append(And(v.join_edge[p2][i2][p1][i1], Not(v.seq_edge[p2][i2][p1][i1]),
                              v.t_inf[p1][i1] ==
                              v.t_inf[p2][i2] + v.instr_dur[p1][i1] + v.switch_cost))
        s.add(Or(*equals))

def get_num(num):
    if is_int_value(num):
        return float(num.as_long())
    elif is_rational_value(num):
        return float(num.as_fraction())
    elif is_algebraic_value(num):
        return float(num.approx(2))
    # print(f"Error: number {num} is invalid")
    return num

def plot_dag(m: ModelDict, c: Config, v: VariableNames, name : str = "graph"):
    '''Plot the DAG'''
    dot = graphviz.Digraph(comment="Scheduling Algorithm", format='jpg')
    dot.graph_attr['rankdir'] = 'LR'
    # print(m, v.start[0][0])
    for (p, i) in v.instrs:
        start_time = float(get_num(m[v.start[p][i]]))
        end_time = float(get_num(m[v.end[p][i]]))
        exec_time = float(get_num(m[v.instr_dur[p][i]]))

        dot.node(name=f"(P{p}, {i})", label=f"(P{p}, {i}, {exec_time})\\n{start_time:.2f}-{end_time:.2f}")

        for (p1, i1) in v.instrs:
            if m.get(v.seq_edge[p][i][p1][i1], False):
                dot.edge(f"(P{p}, {i})", f"(P{p1}, {i1})")
            elif m.get(v.join_edge[p][i][p1][i1], False):
                dot.edge(f"(P{p}, {i})", f"(P{p1}, {i1})", color='green')
    
    dot.render(f"graphs/{name}", view=False)
                

    

def plot_schedule(m: ModelDict, c: Config, v: VariableNames):
    ''' Plot the schedule '''
    print(f"t_1: {m[v.t_1]}, t_inf: {[str(p) + ',' + str(i) + ':' + str(m[v.t_inf[p][i]]) for (p, i) in v.instrs]}")
    fig, ax = plt.subplots()
    max_time = Fraction(0)
    for (p, i) in v.instrs:
        # Did this switch processors?
        switched = m[v.end[p][i]] > m[v.start[p][i]] + m[v.instr_dur[p][i]]

        # If switched, plot the switch cost
        switch_cost = 0.0
        if switched:
            ax.add_patch(mpatches.Rectangle((m[v.start[p][i]], p),
                                            v.switch_cost, 0.5,
                                            facecolor='red', alpha=0.5,
                                            edgecolor="black"))
            switch_cost = v.switch_cost

        ax.add_patch(mpatches.Rectangle((m[v.start[p][i]] + switch_cost, p),
                                        m[v.instr_dur[p][i]], 0.5,
                                        facecolor='b', alpha=0.5,
                                        edgecolor="black"))
        print(f"P{p} I{i} {m[v.ready[p][i]]} → {m[v.start[p][i]]} ↔ {m[v.end[p][i]]} ({m[v.instr_dur[p][i]]})")
        max_time = max(max_time, Fraction(m[v.end[p][i]]))

    for (p1, i1) in v.instrs:
        for (p2, i2) in v.instrs:
            if m.get(v.seq_edge[p1][i1][p2][i2], False) or m.get(v.join_edge[p1][i1][p2][i2], False):
                ax.arrow(m[v.end[p1][i1]], p1+0.25,
                         dx=float(m[v.start[p2][i2]] - m[v.end[p1][i1]]),
                         dy=(p2 - p1 - 0.1),
                         head_width=0.02, head_length=0.02, fc=('k' if m[v.seq_edge[p1][i1][p2][i2]] else 'g'), ec=('k' if m[v.seq_edge[p1][i1][p2][i2]] else 'g'))
    ax.set_ylim(0, c.P)
    ax.set_xlim(0, float(max_time))
    plt.savefig('pic.png')


def query(o : MySolver, v : Variables, alpha : float):
    query = [v.end[0][-1] >= alpha * (v.t_1 / c.P)]
    for (p, i) in v.instrs:
        # Max of all the t_infs
        query.append(v.end[0][-1] >= alpha * v.t_inf[p][i])

    o.add(o.And(*query))

def query2(o : MySolver, v : Variables, num : int, den : int):
    query = [den * v.end[0][-1] >= num * (v.t_1 / c.P)]
    for (p, i) in v.instrs:
        # Max of all the t_infs
        query.append(den * v.end[0][-1] >= num * v.t_inf[p][i])

    o.add(o.And(*query))

def binary_search(o : MySolver, v : Variables, c : Config, low = 1, high = 10, eps = 0.01):
    ans = 1
    m = None
    while high - low > eps:
        mid = (high + low) / 2
        o.push()
        query(o, v, mid)
        with open(f"P{c.P}I{c.I}R{c.R}M{mid:2f}.smt", 'w') as f:
            print(o.to_smt2(), file=f)
        
        start = timer()
        sol = o.check()
        end = timer()
        print(f"Checking for {mid} ({end-start}s)")
        if sol != z3.sat:
            if sol == z3.unknown:
                print("Unknown")
                o.pop()
                return ans, None
            high = mid
            # print("Doesn't work for", mid)
        
        else:
            print(f"Works for {mid} ({sol})")
            ans = mid
            low = mid
            m = o.model()
        o.pop()
    
    return ans, m

def linear_search(o : MySolver, v : Variables, c : Config, low = 1, high = 10, eps = 0.01):
    sol = z3.sat
    ans = -1
    mid = 100
    den = 100
    m = None
    while sol == z3.sat:
        mid += 1
        o.push()
        query2(o, v, mid, den)
        with open(f"P{c.P}I{c.I}R{c.R}M{mid/den:2f}.smt", 'w') as f:
            print(o.to_smt2(), file=f)
        
        start = timer()
        sol = o.check()
        end = timer()
        print(f"Checking for {mid} ({end-start}s)")

        if sol == z3.sat:
            print(f"Works for {mid} ({sol})")
            ans = mid/den
            m = o.model()
    
    return ans, m

if __name__ == "__main__":
    # z3.set_param("parallel.enable", True)


    c = Config()
    switch_to_instr_ratios = [x/10 for x in range(1, 20)]
    
    if (len(sys.argv) > 1):
        if (len(sys.argv) < 3):
            print("Usage: python single_instance.py <num-proc> <num-instr> [ratio]")
            exit(0)
        c.P = int(sys.argv[1])
        c.I = int(sys.argv[2])
        if (len(sys.argv) > 3):
            switch_to_instr_ratios = [float(sys.argv[3])]

    print(f"{c.P} proc, {c.I} instr")
    s = MySolver()
    v = Variables(c, s)

    valid_schedule(c, s, v)
    work_conserving(c, s, v)
    work_stealing(c, s, v)
    theoretical_execution_times(c, s, v)
    
    s.add(v.min_execution_cost == 1)
    s.add(v.switch_cost >= 0)

    # switch_to_instr_ratios.extend([float(x) for x in range(2, 10, 2)])
    # switch_to_instr_ratios.extend([float(x) for x in range(10, 110, 10)])
    switch_to_instr_ratios.reverse()
    print(switch_to_instr_ratios)
    ans_li = []
    ans = 10
    for r in switch_to_instr_ratios:
        s.push()
        # s.add(v.switch_cost <= r)
        c.R = r
        ans, m = binary_search(s, v, c)
        m = model_to_dict(m)
        print("R =", r, "->", ans)
        ans_li.append(ans)
        plot_dag(m, c, VariableNames(v), f"P{c.P}I{c.I}R{c.R}M{r:2f}")
        s.pop()

    plt.plot(switch_to_instr_ratios, ans_li)
    plt.title(f"P = {c.P}, I = {c.I}")
    plt.xlabel("Switch Cost Ratio")
    plt.ylabel("Worst Case Ratio")
    plt.savefig(f"graphs/P{c.P}I{c.I}.png")
