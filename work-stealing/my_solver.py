from typing import Any, List, Dict
from z3 import ArithRef, Bool, BoolRef, Function, FuncDeclRef, Int, Real,\
    EnumSort, Const, Solver, Optimize
from z3.z3 import And, Not, Or, BoolSort, Datatype, ForAll, Implies, IntSort, RealSort, Reals, sat, set_param
from z3 import PbEq

def extract_vars(e: BoolRef) -> List[str]:
    if e.children() == []:
        if str(e)[:4] == "Var(" or str(e) in ["True", "False"]:
            return []
        elif type(e) == ArithRef or type(e) == BoolRef\
                or type(e) == FuncDeclRef:
            return [str(e)]
        else:
            return []
    else:
        return sum(map(extract_vars, e.children()), start=[])


class MySolver:
    '''A thin wrapper over z3.Solver'''
    s: Solver
    num_constraints: int
    variables: Dict[str, Any]
    track_unsat: bool
    # If we are tracking only a subset
    track_unsat_subset: bool

    # No idea what the type is :(
    types: Dict[str, Any] = {}

    def __init__(self):
        self.s = Solver()
        # set_param('parallel.enable', True)
        self.num_constraints = 0
        self.variables = {}
        self.track_unsat = False

    def add(self, expr):
        # for var in extract_vars(expr):
        #     if var not in self.variables:
        #         print(f"Warning: {var} in {str(expr)} not previously declared")
        #         assert(False)
        if self.track_unsat:
            self.s.assert_and_track(expr,
                                    str(expr) + f"  :{self.num_constraints}")
        else:
            self.s.add(expr)
        self.num_constraints += 1

    def assert_and_track(self, expr):
        self.s.assert_and_track(expr,
                                str(expr) + f"  :{self.num_constraints}")
        self.s.set(unsat_core=True)
        self.num_constraints += 1
        self.track_unsat_subset = True

    def to_smt2(self):
        return self.s.to_smt2()

    def statistics(self):
        return self.s.statistics()

    def all_smt(self, vars):
        def block_term(s, m, t):
            s.add(t != m.eval(t))
        def fix_term(s, m, t):
            s.add(t == m.eval(t))
        def all_smt_rec(terms):
            if sat == self.s.check():
                m = self.s.model()
                yield m
                for i in range(len(terms)):
                    if terms[i].sort() != RealSort():
                        self.s.push()
                        block_term(self.s, m, terms[i])
                        for j in range(i):
                            if terms[j].sort() != RealSort():
                                fix_term(self.s, m, terms[j])
                        for m in all_smt_rec(terms[i:]):
                            yield m
                        self.s.pop()
        for m in all_smt_rec(vars):
            yield m

    def set(self, **kwds):
        if "unsat_core" in kwds and kwds["unsat_core"]:
            self.track_unsat = True
        return self.s.set(**kwds)

    def check(self):
        return self.s.check()

    def model(self):
        return self.s.model()

    def unsat_core(self):
        assert(self.track_unsat or self.track_unsat_subset)
        return self.s.unsat_core()

    # def to_smt2(self):
    #     return self.s.to_smt2()

    def assertions(self):
        return self.s.assertions()

    def Real(self, name: str):
        self.variables[name] = Real(name)
        return self.variables[name]

    def Function(self, name: str, *signature):
        self.variables[name] = Function(name, *signature)
        return self.variables[name]

    def Int(self, name: str, temp: bool = False):
        self.variables[name] = Int(name)
        return self.variables[name]

    def Bool(self, name: str):
        self.variables[name] = Bool(name)
        return self.variables[name]

    def DefineEnumType(self, name: str, li: List[str]):
        Type = Datatype(name)
        for val in li:
            Type.declare(val)
        self.types[name] = Type.create()

        return self.types[name]

    def Enum(self, type_name: str, name: str, temp : bool = False):
        if not temp:
            self.variables[name] = Const(name, self.types[type_name])

        return self.variables[name]

    def IntSort(self):
        return IntSort()

    def RealSort(self):
        return RealSort()

    def BoolSort(self):
        return BoolSort()

    def ForAll(self, var: list, expr):
        return ForAll(var, expr)

    def Implies(self, expr1, expr2) -> BoolRef:
        return Implies(expr1, expr2)

    def And(self, *exprs) -> BoolRef:
        return And(*exprs)

    def Or(self, *exprs) -> BoolRef:
        return Or(*exprs)

    def Not(self, expr) -> BoolRef:
        return Not(expr)
    
    def ExactlyK(self, l, k) -> BoolRef:
        return PbEq([(entry, 1) for entry in l], k)

    def maximize(self, expr):
        return self.s.maximize(expr)

    def push(self):
        self.s.push()
    def pop(self):
        self.s.pop()
