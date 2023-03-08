# Notes

## Variables

### Free

1. Datatype Thread: Algebraic, up to MAX_NUM_THREADS
2. Function StartTime(Thread, Int) -> Real
3. Function ExecutionTime(Thread, Int) -> Real
4. Function NumInstructions(Thread) -> Int
5. Function Join(Thread, Int, Thread, Int) -> Bool
6. Function Spawn(Thread, Int, Thread) -> Bool
7. Datatype Processor: Algebraic, up to MAX_PROC
8. Function Schedule(Thread, Int) -> Processor
9. Function ContextShiftDelay(Processor, Processor) -> Real

### Bounded

1. EndTime(Thread, Int) -> Real: EndTime(T, i) := StartTime(T, i) + ExecutionTime(T, i)
2. ValidIndex(Thread, Int) -> Bool: ValidIndex(T, i) := i >= 0 && i < NumInstructions(T)




## Domain Bounds

1. StartTime is non-negative: StartTime(T, i) >= 0
2. Duration is bounded: Duration(T, i) > 0 && Duration(T, i) <= MAX_DURATION
3. Number of instructions per thread is bounded. NumInstructions(T) >= 0 && NumInstructions(T) <= MAX_INSTRUCTIONS_PER_THREAD
4. Total Number of instructions is also bounded. Sum_{T}(NumInstructions(T)) <= MAX_INSTRUCTIONS_TOTAL

5. Constant context shift delay: P1 != P2 => ContextShiftDelay(P1, P2) = K
                                 P1 == P2 => ContextShiftDelay(P1, P2) = 0
**TODO:** Add more bounds on ContextShiftDelay

## Graph Edges

1. Sequential Edges: ValidIndex(T, i) => EndTime(T, i) <= StartTime(T, i+1)
2. Join Edges: ValidIndex(T1, i) && ValidIndex(T2, j) && T1 != T2 && Join(T1, i, T2, j) => EndTime(T1, i) <= StartTime(T2, j)
3. (Optional) Graph is strict or fully strict.
4. Spawn Edges: ValidIndex(T, i) && T1 != T2 && Spawn(T1, i, T2) => EndTime(T1, i) <= StartTime(T2, 0)

## Scheduling Correctness

1. Processor cannot preempt in the middle of instructions: ValidIndex(T1, i) && ValidIndex(T2, j) && Schedule(T1, i) = P && Schedule(T2, j) = P && (T1 != T2) => (EndTime(T1, i) + C <= StartTime(T2, j)) || (EndTime(T2, j) + C <= StartTime(T1, i))  

## Real World Delays

1. If a thread is juggled between proc, then next instruction takes more time  


## Work Stealing

Born: Instruction -> Processor
Executed: Instruction -> Processor

Stolen: Instruction -> Bool

1. 2 processors for every instruction: where its 'born', and where it is executed
    - the 'born' processor == parent's execution processor

2. Stolen(instruction) == (Born(inst) != Executed(inst))

3. Stolen(i) => And_{j}(Executed(j) == Executed(i) AND EndTime(j) <= StartTime(i) => EndTime(j) + Cost <= StartTime(i))

3. Stealing a thread: 