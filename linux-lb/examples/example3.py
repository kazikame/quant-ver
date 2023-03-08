from z3 import *
from main import *

'''
Four CPUs, 10 tasks.
Balanced Groups.
migrate_load and migrate_task
'''

cfg = Config()

cfg.NUM_CPUS = 4
cfg.NUM_TASKS = 10
cfg.NUM_TOP_LEVELS = 2
cfg.TOP_LEVELS = [
    [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1]
    ],
    [
        [1, 1, 0, 0],
        [1, 1, 0, 0],
        [0, 0, 1, 1],
        [0, 0, 1, 1]
    ],
    [[1, 1, 1, 1]] * 4
]
cfg.STAGES = [cfg.NUM_TOP_LEVELS] * cfg.NUM_TIMESTEPS + [1]
set_cfg(cfg)

tasks = [Task(i) for i in range(cfg.NUM_TASKS)]
set_tasks(tasks)
cpus = [CPU(i) for i in range(cfg.NUM_CPUS)]
set_cpus(cpus)
# Holds the domains for each topology level. Used for balancing constraints.
hierarchy = [[] for _ in range(cfg.NUM_TOP_LEVELS)]  # list[list[Domain]]
set_hierarchy(hierarchy)

s = Solver()

print("Building system")
build_domains(s)
build_groups(s)

print("Adding Constraints")
for task in tasks:
    s.add(task.constraints)
s.add(rebalance_domains())
s.add(hierarchy[1][0].migration_type[1] == "migrate_load")

print("Checking")
res = s.check()
print(f'example 3 {res}')

if res == sat:
    m = s.model()
    l = sorted([f'{d} = {m[d]}' for d in m])
    with open("example3.txt", 'w') as f:
        for e in l:
            print(e)
            f.write(str(e) + '\n')
else:
    pass  # print(s.proof())