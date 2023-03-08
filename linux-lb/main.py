from z3 import *
from config import Config

set_param(proof=True)

class Timestep:
    def __init__(self, t, s):
        self.t = t      # the large timestep
        self.s = s      # the stage within

    # next Timestep
    def next(self):
        if self.s == cfg.STAGES[self.t] - 1:
            return Timestep(self.t + 1, 0)
        return Timestep(self.t, self.s + 1)



## Data Structures

class Task:
    '''
    Per task variables and constraints. For the time being, all tasks exist (constant number of tasks)
    '''
    def __init__(self, index : int):
        self.constraints = []
        self.index = index
        ## variables

        # cpu[T.t][0] is the distribution at timestep t before any load balancing happens at the first level
        # cpu[T.t][STAGES[T.t] - 1] is the distribution at timestep t before balancing happens at the final level
        # cpu[NUM_TIMESTEPS][0] is the FINAL distribution
        self.cpu = [[Int(f'task[{index}].cpu[{i}][{s}]') for s in range(cfg.STAGES[i])] for i in range(cfg.NUM_TIMESTEPS + 1)]

        self.weight = Real(f'task[{index}].weight')

        # In each of *_avg:
        # 1. Variable[T.t] is the value it has at the END of the timestep
        # 2. I add *_avg[NUM_TIMESTEPS] to serve as *_avg[-1] and give z3 more control
        # over initial conditions. Note: there is no need to introduce load_avg for tasks because it's
        # the same as runnable_avg
        self.__runnable_avg = [Real(f'tasks[{index}].runnable_avg[{i}]') for i in range(cfg.NUM_TIMESTEPS)]
        self.__runnable_avg.append(Real(f'tasks[{index}].runnable_avg[-1]'))
        self.__util_avg = [Real(f'tasks[{index}].util_avg[{i}]') for i in range(cfg.NUM_TIMESTEPS)]
        self.__util_avg.append(Real(f'tasks[{index}].util_avg[-1]'))
        # portion of CPU time this task took in the past interval
        self.runtime = [Real(f'tasks[{index}].runtime[{i}]') for i in range(cfg.NUM_TIMESTEPS)]
        # portion of time this task was runnable in the past interval
        self.runnable = [Real(f'tasks[{index}].runnable[{i}]') for i in range(cfg.NUM_TIMESTEPS)]
        # a variable defined just because I'm too lazy to sum runtime myself
        self.total_runtime = Real(f'tasks[{index}].total_runtime')

        ## constraints

        self.constraints.append(self.total_runtime == Sum(self.runtime))
        # cpu of task t at every stage of timestep T is any of the existing CPUs
        for stage in self.cpu:
            self.constraints.extend(And(cpu >= 0, cpu < cfg.NUM_CPUS) for cpu in stage)

        '''
        In the real linux kernel, pelt.c has code to estimate load_avg, runnable_avg and util_avg
        per second for each entity. Here, I assume that load balancing intervals are integral multiples
        of pelt intervals, so a single timestep (which represents the smallest load balancing interval
        in the system) is exactly 1 sec. So there is no need to model partial periods or pelt divisors
        or all of that.
        '''
        for i in range(cfg.NUM_TIMESTEPS):
            # all stats are positive and a task can only ever consume a 100% of CPU time
            self.constraints.extend([
                self.__runnable_avg[i] >= 0.0,
                self.__runnable_avg[i] <= 1.0,
                self.__util_avg[i] >= 0.0,
                self.__util_avg[i] <= 1.0,
                self.runtime[i] >= 0.0,
                self.runtime[i] <= 1.0,

                ## Q. so runnable = 1?
                self.runnable[i] >= 1.0, # add constraint to say that tasks should be runnable at least *some* times
                self.runnable[i] <= 1.0
            ])

            # util_avg <= runnable_avg
            self.constraints.append(self.__util_avg[i] <= self.__runnable_avg[i])
            
            # runnable >= runtime
            self.constraints.append(self.runnable[i] >= self.runtime[i])

            # util_avg is ewma(runtime) and runnable_avg is ewma(runnable)
            self.constraints.extend([
                self.__util_avg[i] == 0.5 * self.runtime[i] + 0.5 * self.__util_avg[i - 1],
                self.__runnable_avg[i] == 0.5 * self.runnable[i] + 0.5 * self.__runnable_avg[i - 1]
            ])


        ## initial conditions

        # all stats are positive and a task can only ever consume a 100% of CPU time
        self.constraints.extend([
            self.__runnable_avg[-1] >= 0.0,
            self.__runnable_avg[-1] <= 1.0,
            self.__util_avg[-1] >= 0.0,
            self.__util_avg[-1] <= 1.0,
            self.weight >= 1.0,
            self.weight <= 1.0
        ])

        # util_avg <= runnable_avg
        self.constraints.append(self.__util_avg[-1] <= self.__runnable_avg[-1])



    def on_cpu(self, T: Timestep, cpu: "CPU"):
        return self.cpu[T.t][T.s] == cpu.index

    def in_domain(self, T: Timestep, domain: "Domain"):
        return Or(*[self.on_cpu(T, cpu) for cpu in domain.cpus])

    ## migrations

    def migrates_to(self, T: Timestep, cpu: "CPU"):
        return self.on_cpu(T.next(), cpu)

    # migrates at all in T
    def migrates(self, T: Timestep):
        next_T = T.next()
        return self.cpu[T.t][T.s] != self.cpu[next_T.t][next_T.s]


    # The following functions return the stats that should be used for balancing,
    # which happens at the beginning of the timestep. In other words, they return
    # the stats the END of the PREVIOUS timestep.
    def load_avg(self, T: Timestep):
        return self.__runnable_avg[T.t - 1]

    def runnable_avg(self, T: Timestep):
        return self.__runnable_avg[T.t - 1]

    def util_avg(self, T: Timestep):
        return self.__util_avg[T.t - 1]

    '''
    If the groups have a load/utilization/number imbalance, return the load/util/1 of the task
    '''
    def metric(self, T: Timestep, m_util: BoolRef, m_task: BoolRef, m_load: BoolRef):
        return If(
            m_util,
            self.util_avg(T),
            If(
                m_task,
                1,
                self.load_avg(T)
            )
        )

# TODO: add constraint for whether or not tasks block
# constrain runnable and runtime per cpu

class CPU:
    def __init__(self, index):
        self.index = index
        # list of ancestors of CPU.
        self.domains = []

        ## variables

        # a variable to define how runtimes for tasks running on this cpu
        # should get incremented without multiplication
        self.min_runtime = [Real(f'cpu[{index}].min_runtime[{i}]') for i in range(cfg.NUM_TIMESTEPS)]

        # load_avg and co are sums of the corresponding stats in tasks.
        # task.on_cpu varies depending on which stage we are at, but
        # task.*_avg is constant throughout the timestep at the value before any
        # balancing happens
        self.load_avg = None
        self.runnable_avg = None
        self.util_avg = None
        self.nr_running = None

    def __repr__(self):
        return str(self.index)

    def update_stats(self, T):
        constraints = []
        # Because I assume that all tasks are always runnable, this way of counting runnable tasks on CPU is valid.
        self.nr_running = sum(If(task.on_cpu(T, self), 1, 0) for task in tasks)

        ## Constraints concerned with task stat update AFTER load balancing has been done at T{t, STAGES[t]} for all t

        # only update running stats after timestep 0
        # and right before load balancing happens at each timestep
        if T.t > 0 and T.s == 0:
            # sum of runtimes of tasks on this cpu for this timestep
            runtimes = 0.0
            # sum of min_runtimes
            min_runtimes = 0.0
            # the index of task.stats *before* load balancing happens at T{t + 1, 0}
            i = T.t - 1

            for task in tasks:
                # if task on cpu, then its runtime >= cpu.min_runtime
                constraints.append(Implies(task.on_cpu(T, self), task.runtime[i] >= self.min_runtime[i]))
                runtimes += If(task.on_cpu(T, self), task.runtime[i], 0.0)
                min_runtimes += If(task.on_cpu(T, self), self.min_runtime[i], 0.0)

            # sum of runtimes on this cpu at timestep i is less than or equal to 1
            constraints.append(runtimes <= 1)

            # it's a fair scheduler, so cpu time is evenly divided TODO modify for the blocking case
            # min_runtime[i] = x
            # x * nr_running = x * [task[1].on_cpu] + ... + x * [task[NUM_TASKS].on_cpu] == 1
            constraints.append(Implies(self.nr_running > 0, min_runtimes == 1))
            constraints.append(Implies(self.nr_running == 0, And(min_runtimes == 0, self.min_runtime[i] == -1))) # otherwise, self.min_runtime will be unconstrained

        ## lb constraints
        self.load_avg = sum(If(task.on_cpu(T, self), task.load_avg(T), 0.0) for task in tasks)
        self.runnable_avg = sum(If(task.on_cpu(T, self), task.runnable_avg(T), 0.0) for task in tasks)
        self.util_avg = sum(If(task.on_cpu(T, self), task.util_avg(T), 0.0) for task in tasks)
        return constraints




class Group:
    def __init__(self, mask):
        ## properties
        self.capacity = sum(mask)
        self.weight = self.capacity  # because homogeneous system
        self.cpus = []
        for i in range(cfg.NUM_CPUS):
            if mask[i] == 1:
                self.cpus.append(cpus[i])

        # for debugging
        self.group_type = [String(f'group{self.cpus}.group_type[{i}]') for i in range(cfg.NUM_TIMESTEPS)]

        ## stats
        # group_load
        self.load = None
        # load / capacity
        self.avg_load = None
        # group_runnable
        self.runnable = None
        # group_util
        self.util = None
        # sum_nr_running
        self.nr_running = None
        # number of idle cpus in group
        self.idle_cpus = None

        ## group type
        self.is_overloaded = None
        self.is_fully_busy = None
        self.has_spare = None


    def update_stats(self, T):
        constraints = []

        self.load = sum(cpu.load_avg for cpu in self.cpus)
        self.avg_load = self.load / self.capacity
        self.runnable = sum(cpu.runnable_avg for cpu in self.cpus)
        self.util = sum(cpu.util_avg for cpu in self.cpus)
        self.nr_running = sum(cpu.nr_running for cpu in self.cpus)
        self.idle_cpus = sum(If(cpu.nr_running == 0, 1, 0) for cpu in self.cpus)

        self.is_overloaded = And(
            self.nr_running > self.weight,
            Or(
                self.capacity < self.util * cfg.IMBALANCE_PCT,
                self.capacity * cfg.IMBALANCE_PCT < self.runnable
            )
        )
        self.has_spare = And(
            Not(self.is_overloaded),
            Or(
                self.nr_running < self.weight,
                And(
                    self.capacity * cfg.IMBALANCE_PCT >= self.runnable,
                    self.capacity > self.util * cfg.IMBALANCE_PCT
                )
            )
        )
        self.is_fully_busy = And(
            Not(self.is_overloaded),
            Not(self.has_spare)
        )

        # for debugging
        constraints.append(And(
            # T.s doesn't matter because a group is used only once per timestep
            self.is_overloaded == (self.group_type[T.t] == "overloaded"),
            self.has_spare == (self.group_type[T.t] == "has_spare"),
            self.is_fully_busy == (self.group_type[T.t] == "fully_busy")
        ))

        return constraints


    def busier_or_equal(self, other: "Group"):
        # Cases: (No pinning)
        # overloaded    | overloaded --> compare avg_load
        # overloaded    | Not(overloaded) --> true
        # x             | overloaded --> false
        # fully busy    | fully busy --> compare avg_load
        # fully busy    | has spare  --> true
        # x             | fully busy --> false
        # has spare     | has spare  --> compare
        return Or(
            And(
                self.is_overloaded,
                other.is_overloaded,
                self.avg_load >= other.avg_load
            ),
            And(
                self.is_overloaded,
                Not(other.is_overloaded)
            ),
            And(
                self.is_fully_busy,
                other.is_fully_busy,
                self.avg_load >= other.avg_load
            ),
            And(
                self.is_fully_busy,
                other.has_spare
            ),
            And(
                self.has_spare,
                other.has_spare,
                Or(
                    self.idle_cpus < other.idle_cpus,
                    And(
                        self.idle_cpus == other.idle_cpus,
                        self.nr_running >= other.nr_running
                    )
                )
            )
        )


'''
The group formation algorithm should be overridden for different kernel versions.
See the Scheduling Group Construction bug, 
fixed with this patch https://lore.kernel.org/all/20170428132502.501420079@infradead.org/.
'''
class Domain:

    def __init__(self, level, mask):
        ## properties
        self.capacity = sum(mask)
        self.weight = self.capacity     # because homogeneous system
        self.groups = []
        self.level = level              # the level of the domain disregarding the single-CPU domain level,
                                        # or in other words the level of the groups of this domain
        self.cpus = []
        for i in range(cfg.NUM_CPUS):
            if mask[i] == 1:
                self.cpus.append(cpus[i])

        name = f'domain{self.cpus}'

        ## for debugging
        '''
        A domain has many possible imbalances depending on which group is chosen as a source.
        This variable is to trace the imbalance between the first group and the group actually chosen.
        '''
        self.__imbalance = [Real(name + f'.imbalance[{i}]') for i in range(cfg.NUM_TIMESTEPS)]
        self.migration_type = [String(name + f'.migration_type[{i}]') for i in range(cfg.NUM_TIMESTEPS)]

        ## stats
        # total_load
        self.load = None
        # load / capacity
        self.avg_load = None

    def __repr__(self):
        return f'domain{self.cpus}'

    def update_stats(self, T):
        constraints = []
        for cpu in self.cpus:
            constraints.extend(cpu.update_stats(T))
        for g in self.groups:
            constraints.extend(g.update_stats(T))
        self.load = sum(g.load for g in self.groups)
        self.avg_load = self.load / self.capacity
        return constraints

    # returns the imbalance in this domain at timestep T.t
    # we need not pay attention to T.s since a domain is only
    # balanced once per timestep.
    def imbalance(self, T):
        return self.__imbalance[T.t]


    ## load balancing

    def group_of(self, cpu):
        for g in self.groups:
            if cpu in g.cpus:
                return g
        assert False

    def strictly_busiest_group(self, g):
        return And(*[Not(other.busier_or_equal(g)) if other != g else True for other in self.groups])

    def among_busiest_groups(self, g):
        return And(*[g.busier_or_equal(other) if other != g else True for other in self.groups])

    '''
    Older algorithm, has the bug.
    '''
    def build_groups_nonoverlapping(self):
        covered = [False for _ in range(cfg.NUM_CPUS)]
        for cpu in self.cpus:
            if not covered[cpu.index]:
                group_mask = cfg.TOP_LEVELS[self.level][cpu.index]
                new_group = Group(group_mask)
                for j in new_group.cpus:
                    covered[j.index] = True
                self.groups.append(new_group)


## Group Construction. Almost 1 to 1 translation from the kernel code.

def build_domains(s: Solver):
    for cpu in cpus:
        for level in range(cfg.NUM_TOP_LEVELS):
            domain_mask = cfg.TOP_LEVELS[level + 1][cpu.index]
            # the CPU responsible for active load balancing in this domain
            # this isn't exactly how it should be defined (at least not for
            # overlapping NUMA domains), but for the time being: TODO
            first_cpu = -1
            for i in range(cfg.NUM_CPUS):
                if domain_mask[i] == 1:
                    first_cpu = i
                    break
            assert first_cpu > -1

            if first_cpu == cpu.index:
                domain = Domain(level, domain_mask)
                hierarchy[level].append(domain)
                cpu.domains.append(domain)
            else:
                cpu.domains.append(cpus[first_cpu].domains[level])


def build_groups(s: Solver):
    for level in hierarchy:
        for domain in level:
            domain.build_groups_nonoverlapping()



## Load Balancing

# migration types
def migrate_util(busiest: Group, local: Group, idle: BoolRef):
    return And(
        local.has_spare,
        busiest.is_overloaded,
        Or(
            Not(idle),
            local.capacity > local.util
        )
    )

def migrate_task(busiest: Group, local: Group, idle: BoolRef):
    return And(
        local.has_spare,
        Not(migrate_util(busiest, local, idle))
    )

def migrate_load(busiest: Group, local: Group, idle: BoolRef):
    return And(
        Not(migrate_util(busiest, local, idle)),
        Not(migrate_task(busiest, local, idle))
    )

def busiest_cpu(cpu, src_grp, m_util, m_task, m_load):
    return And(
        Implies(
            m_load,
            And(*[cpu.load_avg >= other.load_avg for other in src_grp.cpus])
            # ignore cpu capacity since system is homogeneous and no other SCHED_CLASS
        ),
        Implies(
            m_util,
            And(cpu.nr_running > 1 ,*[Implies(other.nr_running > 1, cpu.util_avg >= other.util_avg) for other in src_grp.cpus])
        ),
        Implies(
            m_task,
            And(*[cpu.nr_running >= other.nr_running for other in src_grp.cpus])
        )
    )

'''
AND(
    for cpu in group.cpus:
        if cpu is busiest, then:
            only one task on cpu
            OR
            AND(
                for task in cpu.tasks:
                    metric too large
            )
)

The fact that "only one task on cpu" prevents migration is enforced in multiple places in code, for instance see
https://elixir.bootlin.com/linux/v5.19.4/source/kernel/sched/fair.c#L10031,
https://elixir.bootlin.com/linux/v5.19.4/source/kernel/sched/fair.c#L7828 (Task running implies it's the only one on cpu)
'''
def none_suitable(T:Timestep, domain: Domain, src_grp: Group, dst_grp: Group, idle: BoolRef):
    m_util = migrate_util(src_grp, dst_grp, idle)
    m_task = migrate_task(src_grp, dst_grp, idle)
    m_load = migrate_load(src_grp, dst_grp, idle)
    imb = imbalance(domain, src_grp, dst_grp, m_util, m_task, m_load)
    return And(
        *[Implies(
            busiest_cpu(cpu, src_grp, m_util, m_task, m_load),
            Or(
                And( # Each task's metric is greater than the imbalance
                    *[Implies(
                        task.on_cpu(T, cpu),
                        task.metric(T, m_util, m_task, m_load) > imb
                    ) for task in tasks]
                ),
                cpu.nr_running <= 1 # this CPU has either 1 or no task
            )
        ) for cpu in src_grp.cpus])

def clamp(val):
    return If(val > 0, val, 0)

def imbalance(domain: Domain, src_grp: Group, dst_grp: Group, m_util, m_task, m_load):
    return If(
            m_util,
            clamp(dst_grp.capacity - dst_grp.util),
            If(
                m_task,
                If(
                    src_grp.is_overloaded,
                    1,
                    clamp(src_grp.nr_running - dst_grp.nr_running) / 2 if src_grp.weight == 1 else clamp(
                        dst_grp.idle_cpus - src_grp.idle_cpus)
                ),
                If(
                    src_grp.avg_load - domain.avg_load < domain.avg_load - dst_grp.avg_load,
                    src_grp.avg_load - domain.avg_load,
                    domain.avg_load - dst_grp.avg_load
                )
            )
        )

# @param T: Timestep
## Q. When timestep anyway has the level, why take it as a sep arg

class LoadBalance:
    def __init__(self, T, level, s : Solver):
        pass
        

def load_balance(T, level, s : Solver):
    constraints = []

    for domain in level:
        constraints.extend(domain.update_stats(T))
        for b in domain.cpus:
            '''
            For each cpu in this domain:
            
            Either 1) it's not responsible for balancing
            2) local group is the busiest 
             https://elixir.bootlin.com/linux/v5.19.4/source/kernel/sched/fair.c#L9657 and https://elixir.bootlin.com/linux/v5.19.4/source/kernel/sched/fair.c#L9669
            Or 3) NOT(idle) AND the local group is overloaded AND more loaded than average
            Or 4) None of the busiest groups is considerably busier
            Or 5) NOT(idle) AND None of the busiest groups is overloaded (delegate the balancing to the idle balancer) 
             https://elixir.bootlin.com/linux/v5.19.4/source/kernel/sched/fair.c#L9697
            Or 6) None of the cpus in the busiest groups has a suitable task 
            Or 7) some task actually migrates to b, subject to migration_constraints,
            where migration_constraints have the form "if a task migrates, then so and so is true"

            8) if the cpu is responsible for balancing, any migration to it comes from this domain
            
            Note: we cannot merge 5 and 6 into "enforce migration_constraints" because then z3 might choose not
            to migrate any tasks at all.
            '''
            first_idle = And(
                b.nr_running == 0,
                *[cpu.nr_running > 0 for cpu in domain.cpus if cpu.index < b.index]
            )
            first_cpu = And(
                b == domain.cpus[0],
                *[cpu.nr_running > 0 for cpu in domain.cpus]
            )
            ## 1)
            should_we_balance = Or(first_idle, first_cpu)

            groups = domain.groups # TODO, change how this is obtained for overlapping NUMA
            idle = b.nr_running == 0
            local = domain.group_of(b) # TODO, change for overlapping NUMA
            # the terminology is confusing, the group of dst_cpu is called both local
            # and destination in different parts of the code. I use both names here to avoid
            # confusion
            dst_grp = local

            ## 2)
            local_the_busiest = domain.strictly_busiest_group(local) # TODO, change for NUMA

            ## 3)
            local_above_average = And(
                # Not(idle) I could put this, but (TODO) I want to test whether the model allows a group to be overloaded when a cpu in it is idle
                local.is_overloaded,
                local.avg_load >= domain.avg_load
            )

            ## 5)
            none_overloaded = And(Not(idle), *[Not(g.is_overloaded) for g in groups])

            ## 4)
            '''
            Idle:
            AND(
            For g in groups: 
                if g is among busiest, then:
                    g is NOT overloaded
                    AND(
                        only one task or less running on g
                        OR
                        g has more idle cpus than local
                    )
            )
            Periodic:
            AND(
            For g in groups: 
                if g is among busiest, then:
                    g is overloaded AND NOT considerably more loaded
            )
            
            Note that this assumes that the Linux load balancer is smarter than it really is. That is, that if there are
            multiple groups with the same busyness level, it will pick the one which has migratable tasks if any.
            '''
            no_considerable_imbalance = And(
                    *[Implies(
                        domain.among_busiest_groups(g),  # busiest group
                        Or(
                            And(
                                idle,
                                Not(g.is_overloaded),
                                Or(
                                    g.nr_running <= 1,  # don't want livelocks
                                    And(g.weight > 1, local.idle_cpus <= g.idle_cpus + 1)  # no considerable imbalance
                                )
                            ),
                            And(
                                Not(idle), ## Q. seems redundant?
                                local.is_overloaded,
                                g.avg_load <= cfg.IMBALANCE_PCT * local.avg_load # not considerably more loaded
                            )
                        )
                    ) for g in groups]
                )

            ## 6)
            no_suitable_task = And(
                *[Implies(
                    domain.among_busiest_groups(g),  # busiest group
                    none_suitable(T, domain, g, local, idle)
                ) for g in groups]
            )

            ## 7)
            migration_happens = Or(
                *[And(task.migrates(T), task.migrates_to(T, b)) for task in tasks]
            )

            ## 8) if a task migrates in this domain, it goes to b. (Also eliminates interdomain balancing)
            no_interdomain_balancing = And(
                *[Implies(
                    And(task.in_domain(T, domain), task.migrates(T)),
                    task.migrates_to(T, b)
                ) for task in tasks]
            )

            # migration constraints
            migration_constraints = []

            for a in domain.cpus:
                if a == b:
                    continue

                src_grp = domain.group_of(a) # TODO, change for NUMA
                # A) only intergroup balancing
                if src_grp == local:
                    constraints.extend(
                        [Not(
                            And(task.on_cpu(T, a), task.migrates_to(T, b))
                        ) for task in tasks]
                    )
                    continue

                migration_a = Or(*[And(task.on_cpu(T, a), task.migrates(T)) for task in tasks])

                # B) all tasks migrating within this domain migrate from a
                all_migrations_a = And(
                    *[Implies(
                        And(task.in_domain(T, domain), task.migrates(T)),
                        task.on_cpu(T, a)
                    ) for task in tasks]
                )

                # C) group of src_cpu is among the busiest in domain
                src_busiest = domain.among_busiest_groups(src_grp)

                m_util = migrate_util(src_grp, dst_grp, idle)
                s.add(Bool(f'm_util[{a}->{b}][({T.t}, {T.s}])[domain{domain.cpus}]') == m_util)
                m_task = migrate_task(src_grp, dst_grp, idle)
                s.add(Bool(f'm_task[{a}->{b}][({T.t}, {T.s}])[domain{domain.cpus}]') == m_task)
                m_load = migrate_load(src_grp, dst_grp, idle)
                s.add(Bool(f'm_load[{a}->{b}][({T.t}, {T.s}])[domain{domain.cpus}]') == m_load)

                # D) cpu_a is busiest cpu in src_grp
                cpu_a_busiest = busiest_cpu(a, src_grp, m_util, m_task, m_load)

                # compute imbalance only once
                imb = imbalance(domain, src_grp, dst_grp, m_util, m_task, m_load)

                # E) sum of tasks migrating <= imbalance
                sum_migrating = sum(
                    If(
                        And(task.on_cpu(T, a), task.migrates(T)),
                        task.metric(T, m_util, m_task, m_load),
                        0
                    ) for task in tasks
                )
                not_more_than_imbalance = sum_migrating <= imb

                # F) any other task still in a would exceed imbalance if migrated or will leave a empty
                '''
                For all tasks: if task is in a and stays in a, 
                then task.metric + sum(task.metric for tasks migrating from a to b) > domain.imbalance,
                OR it will be the only task in a
                '''
                nr_migrating = sum(
                    If(And(task.on_cpu(T, a), task.migrates(T)), 1, 0) for task in tasks
                )
                next_T = T.next()
                as_much_as_possible = And(
                    *[Implies(
                        And(task.on_cpu(T, a), Not(task.migrates(T))),
                        Or(
                            task.metric(T, m_util, m_task, m_load) + sum_migrating > imb,
                            a.nr_running == 1 + nr_migrating
                            #And(*[Not(other.on_cpu(next_T, a)) for other in tasks if other != task]) which is more efficient?
                        )
                    ) for task in tasks]
                )

                # G) if cpu_b is idle, number of tasks migrating < number of tasks on CPU
                # not_leave_empty = Implies(idle, nr_migrating < a.nr_running) -- fixed temporarily
                not_leave_empty = nr_migrating < a.nr_running

                # for debugging
                # calculate_imbalance = And(
                #     domain.imbalance(T) == imb,
                #     Implies(m_load, (domain.migration_type[T.t] == "migrate_load")),
                #     Implies(m_task, (domain.migration_type[T.t] == "migrate_task")),
                #     Implies(m_util, (domain.migration_type[T.t] == "migrate_util")),
                #     Implies(Not(Or(m_util, m_load, m_task)), (domain.migration_type[T.t] == "no_migration"))
                # )
                calculate_imbalance = True

                migration_constraints.append(migration_a == all_migrations_a)
                migration_constraints.append(Implies(
                    migration_a,
                    And(
                        src_busiest,
                        cpu_a_busiest,
                        as_much_as_possible,
                        not_more_than_imbalance,
                        not_leave_empty
                    )
                ))
                migration_constraints.append(Implies(migration_a, calculate_imbalance))

            # working constraints
            constraints.append(Xor(
                Or(
                    Not(should_we_balance),
                    local_the_busiest,
                    local_above_average,
                    none_overloaded,
                    no_considerable_imbalance,
                    no_suitable_task
                ),
                migration_happens
            ))
            constraints.append(Implies(migration_happens, And(*migration_constraints)))
            constraints.append(Implies(should_we_balance, no_interdomain_balancing))

            # for debugging
            s.add(Bool(f'migration_happens[{b}]({T.t}, {T.s})[domain{domain.cpus}]') == migration_happens)
            s.add(Bool(f'local_the_busiest[{b}]({T.t}, {T.s})[domain{domain.cpus}]') == local_the_busiest)
            s.add(Bool(f'local_above_average[{b}]({T.t}, {T.s})[domain{domain.cpus}]') == local_above_average)
            s.add(Bool(f'none_overloaded[{b}]({T.t}, {T.s})[domain{domain.cpus}]') == none_overloaded)
            s.add(Bool(f'no_considerable_imbalance[{b}]({T.t}, {T.s})[domain{domain.cpus}]') == no_considerable_imbalance)
            s.add(Bool(f'no_suitable_task[{b}]({T.t}, {T.s})[domain{domain.cpus}]') == no_suitable_task)

            # constraints.append(Implies(
            #     And(should_we_balance, local_the_busiest),
            #     domain.migration_type[T.t] == "no_migration - local_the_busiest")
            # )
            # constraints.append(Implies(
            #     And(should_we_balance, Not(local_the_busiest), local_above_average),
            #     domain.migration_type[T.t] == "no_migration - local_above_average")
            # )
            # constraints.append(Implies(
            #     And(should_we_balance, Not(local_the_busiest), Not(local_above_average), none_overloaded),
            #     domain.migration_type[T.t] == "no_migration - none_overloaded")
            # )
            # constraints.append(Implies(
            #     And(should_we_balance, Not(local_the_busiest), Not(local_above_average), Not(none_overloaded), no_considerable_imbalance),
            #     domain.migration_type[T.t] == "no_migration - no_considerable_imbalance")
            # )
            # constraints.append(Implies(
            #     And(should_we_balance, Not(local_the_busiest), Not(local_above_average), Not(none_overloaded), Not(no_considerable_imbalance), no_suitable_task),
            #     domain.migration_type[T.t] == "no_migration - no_suitable_task")
            # )

    return constraints


def rebalance_domains(s : Solver):
    constraints = []
    T = Timestep(0, 0)
    while(T.t < cfg.NUM_TIMESTEPS):
        constraints.extend(load_balance(T, hierarchy[T.s], s))
        T = T.next()
    # update stats after all load balancing done.
    for cpu in cpus:
        constraints.extend(cpu.update_stats(T))
    return constraints



## Utilities

'''
A hacky way to allow main.py to read values from example.py. 
'''
def set_cfg(_cfg):
    global cfg
    cfg = _cfg

def set_tasks(_tasks):
    global tasks
    tasks = _tasks

def set_cpus(_cpus):
    global cpus
    cpus = _cpus

def set_hierarchy(_hierarchy):
    global hierarchy
    hierarchy = _hierarchy

def print_constraints(con):
    for c in con:
        print(c, end='\n-----------------------------\n')

def test_sat_tasks(s, debug = False):
    if debug:
        print("==================================")
    for task in tasks:
        s.add(*task.constraints)
        if debug:
            print_constraints(task.constraints)


def test_sat_domains(s, debug = False):
    build_domains(s)
    build_groups(s)
    constraints = rebalance_domains(s)
    s.add(*constraints)
    if debug:
        print("==================================")
        print_constraints(constraints)


def test_sat(s, debug = False):
    test_sat_tasks(s, False)
    print("checking tasks")
    res = s.check()
    print(f'tasks {res}')

    test_sat_domains(s, False)
    print("checking domains")
    res = s.check()
    print(f'domains {res}')

    if res == sat:
        m = s.model()
        l = sorted ([f'{d} = {m[d]}' for d in m])
        with open("result.txt", 'w') as f:
            for e in l:
                # print(e)
                f.write(str(e) + '\n')
    else:
        pass #print(s.proof())


def print_model(m: ModelRef):
    print("Task\tCPU\trunnable_avg\tutil_avg")
    for t in range(cfg.NUM_TIMESTEPS):
        ts = Timestep(t, 0)
        print(f"\nTS {t} ====================================")
        for task in tasks:
            print(f'T{task.index}\t{[m[task.cpu[t][i]] for i in range(cfg.STAGES[t])] + [m[task.cpu[t+1][0]]]}\t{m[task.runnable_avg(ts)]}\t{m[task.util_avg(ts)]}')

    print('\n\n')
        # for domain in domains:
        #     # print("domain")
        #     pass
# Run-specific constraints

def work_conserving(s: Solver):
    s.push()
    t = cfg.NUM_TIMESTEPS
    constraints = []
    while t < cfg.NUM_TIMESTEPS+1:
        T = Timestep(t, 0)

        for cpu in cpus:
            nr_running = sum([If(task.on_cpu(T, cpu), 1, 0) for task in tasks])
            constraints.append(nr_running > 0)
        t += 1

    s.add(Not(And(*constraints)))

    res = s.check()
    print(f'work conserving {res}')

    if res == sat:
        with open('tmp.out', 'w') as f:
            m = s.model()
            for d in sorted([k for k in m], key=lambda x : str(x)):
                print(f'{d}={m[d]}', file=f)
        print_model(s.model())
    
    s.pop()

def unfairness(s: Solver, val = 0.915):
    s.push()
    constraints = []

    m1 = 0
    m2 = 0

    for task in tasks:
        total_runtime = sum(task.runtime)
        m1 += total_runtime
        m2 += total_runtime * total_runtime
    

    
    s.add((m1 * m1) <= (m2 * val * len(tasks)))

    res = s.check()
    print(f'unfairness {res}')

    if res == sat:
        with open('tmp.out', 'w') as f:
            m = s.model()
            for d in sorted([k for k in m], key=lambda x : str(x)):
                print(f'{d}={m[d]}', file=f)
        print_model(s.model())
    
    s.pop()
    

if __name__ == "__main__":
    cfg = Config()
    tasks = [Task(i) for i in range(cfg.NUM_TASKS)]
    cpus = [CPU(i) for i in range(cfg.NUM_CPUS)]
    # Holds the domains for each topology level. Used for balancing constraints.
    hierarchy = [[] for _ in range(cfg.NUM_TOP_LEVELS)]  # list[list[Domain]]

    s = Solver()

    test_sat(s, True)
    work_conserving(s)
    # unfairness(s)
