# Work Stealing Verification

Models the work-stealing algorithms for multithreaded multiprocessor scheduling.

## Config

See [config.py](./config.py) to configure the following options:

| Option | Description |
|--------|-------------|
| `NUM_PROC` | # of processors |
| `NUM_THREADS` | # of threads (or the # of disjoint graphs in the computation) |
| `MIN_INST_PER_THREAD` | minimum length of each disjoint computation graph | 
| `MAX_INST_PER_THREAD` | maximum length of each disjoint computation graph |
| `MAX_TOT_INST` | maximum total number of nodes in the computation graph |
| `MAX_EXECUTION_TIME_PER_INST` | max ratio by which the execution time of two instructions (nodes) can vary |
| `CONTEXT_SHIFT_DELAY_RANGE` | max ratio of context shift delay with execution time of any instruction (node) |


## Run

```bash
python3 multithreaded_computation_simple.py
```

The output performs a binary search over the worst-case ratio of the time taken by work stealing over the optimal scheduling algorithm.
An example computation graph along with work stealing schedule and the optimal schedule is visualized in the folder `./graphs`.



