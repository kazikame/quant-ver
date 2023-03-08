class Config:
    # NUM_CPUS = 8
    NUM_CPUS = 4
    # NUM_TASKS = 10  # By default: 2 * NUM_CPUS, but a single CPU might get assigned all tasks if z3 so wills
    NUM_TASKS = 5
    NUM_TIMESTEPS = 2
    '''
    number of topology levels *without the level with individual CPUs*.
    '''
    NUM_TOP_LEVELS = 2
    '''
    A graph for each level. Related CPUs (e.g. same node) form connected components.
    Default: binary tree
    '''
    # TOP_LEVELS = [
    #     [
    #         [1, 0, 0, 0, 0, 0, 0, 0],
    #         [0, 1, 0, 0, 0, 0, 0, 0],
    #         [0, 0, 1, 0, 0, 0, 0, 0],
    #         [0, 0, 0, 1, 0, 0, 0, 0],
    #         [0, 0, 0, 0, 1, 0, 0, 0],
    #         [0, 0, 0, 0, 0, 1, 0, 0],
    #         [0, 0, 0, 0, 0, 0, 1, 0],
    #         [0, 0, 0, 0, 0, 0, 0, 1]
    #     ],
    #     [
    #         [1, 1, 0, 0, 0, 0, 0, 0],
    #         [1, 1, 0, 0, 0, 0, 0, 0],
    #         [0, 0, 1, 1, 0, 0, 0, 0],
    #         [0, 0, 1, 1, 0, 0, 0, 0],
    #         [0, 0, 0, 0, 1, 1, 0, 0],
    #         [0, 0, 0, 0, 1, 1, 0, 0],
    #         [0, 0, 0, 0, 0, 0, 1, 1],
    #         [0, 0, 0, 0, 0, 0, 1, 1]
    #     ],
    #     [
    #         [1, 1, 1, 1, 0, 0, 0, 0],
    #         [1, 1, 1, 1, 0, 0, 0, 0],
    #         [1, 1, 1, 1, 0, 0, 0, 0],
    #         [1, 1, 1, 1, 0, 0, 0, 0],
    #         [0, 0, 0, 0, 1, 1, 1, 1],
    #         [0, 0, 0, 0, 1, 1, 1, 1],
    #         [0, 0, 0, 0, 1, 1, 1, 1],
    #         [0, 0, 0, 0, 1, 1, 1, 1]
    #     ],
    #     [[1, 1, 1, 1, 1, 1, 1, 1]] * 8
    # ]
    TOP_LEVELS = [
        [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ],
        [
            [1, 1, 0, 0],
            [1, 1, 0, 0],
            [0, 0, 1, 1],
            [0, 0, 1, 1],
        ],
        [
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
        ]
    ]
    '''
    Number of levels to balance at each timestep. 1 stage <-> no balancing, NUM_TOP_LEVELS stages <-> all levels 
    '''
    STAGES = [NUM_TOP_LEVELS] * NUM_TIMESTEPS + [1]
    IMBALANCE_PCT = 1.17