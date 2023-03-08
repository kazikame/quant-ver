# Results

1. 2 threads, no cts, factor = 1.5, 3/3
    - instant

2. 2 threads, no cts, factor > 1.5, 2/2
    - instant unsat

2. 2 threads, no cts, factor > 1.5, 3/3
    - still running

3. 3 threads, factor > 1.66, no cts, 5/5
    - still running

4. 

## Optimizations

1. Don't have to run for 0 to 5 instructions, 5 instructions is enough (especially w/o cts)
2. Remove spawn edges -- done
3. Remove context shift cost constraints -- done
3. Remove work stealing constraints -- only test for work conserving -- done
4. Try maximize (non-linear!) -- done
5. Add extraneous constraints -- for > num_instructions, set to fixed value.
3. Try with some other solver?
    - yices
    - cvc4

### What's done:

1. Found an example where adding context switch cost makes work stealing worse
2. Still, we have good reason to believe that even with context switch cost, TimeTaken(WorkStealing) / (T_1 / P) is bounded
    - and so work stealing can only do so bad
3. Tried finding this ratio while varying the context switch costs w.r.t. the duration of a single instruction
    - Still trying to interpret the results:
        - 

## Table

### 2P, 3I
R = 0.1 -> 1.5234375
R = 0.2 -> 1.54296875
R = 0.3 -> 1.5625
R = 0.4 -> 1.58203125
R = 0.5 -> 1.59765625
R = 0.6 -> 1.61328125
R = 0.7 -> 1.62890625
R = 0.8 -> 1.640625
R = 0.9 -> 1.65234375
R = 1.0 -> 1.6640625
R = 1.1 -> 1.67578125
R = 1.2 -> 1.68359375
R = 1.3 -> 1.6953125
R = 1.4 -> 1.703125
R = 1.5 -> 1.7109375
R = 1.6 -> 1.71875
R = 1.7 -> 1.7265625
R = 1.8 -> 1.734375
R = 1.9 -> 1.7421875
R = 2.0 -> 1.74609375
R = 4.0 -> 1.83203125
R = 6.0 -> 1.87109375
R = 8.0 -> 1.8984375
R = 10.0 -> 1.9140625
R = 20.0 -> 1.953125
R = 30.0 -> 1.9609375
R = 40.0 -> 1.96875
R = 50.0 -> 1.9765625
R = 60.0 -> 1.9765625
R = 70.0 -> 1.984375
R = 80.0 -> 1.984375
R = 90.0 -> 1.984375
R = 100.0 -> 1.984375

### 2P, 4I
R = 0.1 -> 1.5390625
R = 0.2 -> 1.578125
R = 0.3 -> 1.609375
R = 0.4 -> 1.640625
R = 0.5 -> 1.6640625
R = 0.6 -> 1.6796875
R = 0.7 -> 1.703125
R = 0.8 -> 1.71875
R = 0.9 -> 1.734375
R = 1.0 -> 1.7421875
R = 1.1 -> 1.765625
R = 1.2 -> 1.78125
R = 1.3 -> 1.796875
R = 1.4 -> 1.8125
R = 1.5 -> 1.828125
R = 1.6 -> 1.84375
R = 1.7 -> 1.859375
R = 1.8 -> 1.8671875
R = 1.9 -> 1.8828125
R = 2.0 -> 1.8984375
R = 4.0 -> 2.078125
R = 6.0 -> 2.1796875
R = 8.0 -> 2.2421875
R = 10.0 -> 2.2890625
R = 20.0 -> 2.3828125
R = 30.0 -> 2.4140625
R = 40.0 -> 2.4375
R = 50.0 -> 2.4453125
R = 60.0 -> 2.453125
R = 70.0 -> 2.4609375
R = 80.0 -> 2.46875
R = 90.0 -> 2.46875
R = 100.0 -> 2.46875

### 2P, 5I
R = 0.1 -> 1.546875
R = 0.2 -> 1.59375
R = 0.3 -> 3.3359375
R = 0.4 -> 4.9609375
R = 0.5 -> 4.5859375
R = 0.6 -> 1.4921875
R = 0.7 -> 3.9609375
R = 0.8 -> 4.921875
R = 0.9 -> 3.53125
R = 1.0 -> 2.9609375
R = 1.1 -> 4.703125
R = 1.2 -> 4.2109375
R = 1.3 -> 4.9921875
R = 1.4 -> 2.8828125
R = 1.5 -> 4.9609375
R = 1.6 -> 1.0546875
R = 1.7 -> 4.5546875
R = 1.8 -> 3.1171875
R = 1.9 -> 4.9375
R = 2.0 -> 1.4375
R = 4.0 -> 4.9921875
R = 6.0 -> 2.109375
R = 8.0 -> 1.8046875
R = 10.0 -> 4.9921875
R = 20.0 -> 4.8125
R = 30.0 -> 3.2421875
R = 40.0 -> 4.9921875
R = 50.0 -> 4.9921875
R = 60.0 -> 4.9921875
R = 70.0 -> 4.9921875
R = 80.0 -> 4.9921875
R = 90.0 -> 4.9921875
R = 100.0 -> 4.9921875

### 2P, 6I
R = 0.1 -> 1.8671875
R = 0.2 -> 4.0078125
R = 0.3 -> 4.1796875
R = 0.4 -> 4.7421875
R = 0.5 -> 4.9921875
R = 0.6 -> 4.9921875
R = 0.7 -> 4.9921875
R = 0.8 -> 4.9921875
R = 0.9 -> 4.9921875
R = 1.0 -> 4.9921875
R = 1.1 -> 4.9765625
R = 1.2 -> 3.1328125
R = 1.3 -> 4.9921875
R = 1.4 -> 4.9921875
R = 1.5 -> 4.9921875
R = 1.6 -> 3.9921875
R = 1.7 -> 4.8984375
R = 1.8 -> 4.46875
R = 1.9 -> 4.1640625
R = 2.0 -> 4.8828125
R = 4.0 -> 3.0625
R = 6.0 -> 1.1171875
R = 8.0 -> 4.75
R = 10.0 -> 1.234375
R = 20.0 -> 3.484375
R = 30.0 -> 3.5234375
R = 40.0 -> 4.8984375
R = 50.0 -> 4.9921875
R = 60.0 -> 4.546875
R = 70.0 -> 4.4375
R = 80.0 -> 4.9921875
R = 90.0 -> 4.9921875
R = 100.0 -> 4.9921875

## 01/18

1. Bug Fixing:
    - comparing smt constraints w/ different ratios: no diff
    - running commandline z3: works fine!
    - start binary search from there: works fine!
    - esoteric bug in binary search?
        - bug in z3?!

2. Linear Search:
    - sat examples are found wayyy faster than unsat
    - increment by 0.01 until found, still doesn't work
        - HUGE variance in running time :(
            - most will take <0.1s, and then suddenly one will take >10mins
            - use the same graph?! TODO: Check graphs, can't z3 scale them up directly?

3. Interpreting Results:
    - All examples generated are valid DAGs
    - WS bottoms out at a small finite ratio

3. Next:
    - Find real examples
    - Topological Sort
    - Modelling Disk: Special processor, some instructions can only be executed by this
    - try line fitting on graphs (worst case ratio wrt processors/instructions for a particular context switch cost?)

4. 
    - Multiple linear graphs whose execution time is a non-increasing function dependent on resources -- memory, cpu, ...
    - Add stealing cost: arbitrarily worse
        - 