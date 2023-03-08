
class Config:

    # Number of processors
    NUM_PROC: int = 2

    # Number of threads
    NUM_THREADS: int = 3

    # Minimum number of instructions per thread
    # THIS CAN BE THE SAME AS MAX, and it likely wouldn't affect the power of the model.
    MIN_INST_PER_THREAD: int = 1
    # Total number of instructions per thread
    MAX_INST_PER_THREAD: int = 6

    MAX_TOTAL_INST: int = 6

    # Maximum time an instruction can take to execute
    MAX_EXECUTION_TIME_PER_INST: int = 10

    # Minimum time an instruction can take to execute
    MIN_EXECUTION_TIME_PER_INST: int = 1

    CONTEXT_SHIFT_DELAY_MIN: float = 0
    CONTEXT_SHIFT_DELAY_MAX: float = 10
    CONTEXT_SHIFT_DELAY_RANGE: float = 0

    unsat_core: bool = False

    def __init__(self):
        pass