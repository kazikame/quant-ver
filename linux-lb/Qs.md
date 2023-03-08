# Questions

1. ~~where is the cpu after final level balancing at each ts stored?~~
    - in next ts[0]
2. why is runnable set to 1?
    - every task is always runnable, most likely
    - (L207): every task is run evenly at every ts?????
        - every task's runtime is min_runtime????
        - what exactly is Z3 deciding?
            - ts are after 1s
            - runnable hardcoded to 1
            - runtime is set
                - =min_runtime
            - *_avg are also set, as a result
            - min_runtime is also set (depending on if there are any tasks)
                - `min_runtime[i]*num_tasks = 1`, `i` is the ts
3. EWMA weight set to 0.5?
    - should this be in config?
    - can the results change because of this?

4. what is cpu.min_runtime?
    - why is every task on that CPU run for a minimum time?

5. **Why is cpu util_avg = sum of task util avg?**
    - In current setup, running = min_running = 1/nr_running
    - therefore CPU's util avg depends on 

5. What is "String()" in z3?
    - using strings as enums -- is this advisable?

6. L211: task.runnable_avg?
    - runnable_avg == sum of EWMA(runnable) of each task
    - util_avg == sum of EWMA(runtime) of each task
    - load_avg????
        - most likely accounts for task priorities

7. Why not save vars at every ts?
    - diff var for every ts

8. L600 -- looks p important for bug

9. L606: why Not(idle)?

10. L631: so either:
    - each group is not maximally busy
    - or if:
        - curr cpu is idle AND g is not overloaded,
    - why does CPU's idleness affect this?


## Higher-order questions
1. what's the max TS this can scale to?

2. Can we allow Z3 to pick the NUMA nodes config as well? (Pick cfg.TOP_LEVELS)


## TODO
~~1. Work conservation constraint: works!~~
~~2. Reduce the example size?~~

~~3. Fix constraint when # tasks < # CPUs~~

4. Why is there unfairness when # tasks < # CPUs

5. allow runnable to be <1.


### Group Imbalance Bug
3. add weight to tasks
    - set runnable_avg to 1 -- makes program linear again!
4. remove constraints to have the group imbalance bug
    - migrate_task is not a thing:
        - remove from `none_suitable()`
        - remove from `busiest_cpu()`
        - remove from `imbalance()`
        - remove from `Task.metric()`

### Unfairness?

- core pinning?
- model timesteps that aren't fixed
- after a timestep, do things always get better?

3. class Domain may need to be overriden?


## Notes
1. Domain has a capacity == no. of CPU in it?
    - Weight = capacity
2. Domain.level == Root level is -1, above is 0, ...
3. Each group is kinda like a domain lol


4. Timesteps are closed interval
    - runnable, runtime, util_avg, etc. are noted at END of ts
    - 

5. update_stats: set constraints on runtime, etc. vars at the end of this timestep
    - CPU sets constraints on task
    - group does nothing