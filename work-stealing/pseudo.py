def task_ready_trigger(task : Task, ready_tasks : [Task], free_procs : [Proc]):
    if task.origin_proc in free_procs:
        schedule(task, task.origin_proc)
        break

    for proc in free_procs:        
        # if len(proc.ready_queue) == 0:
        if any(map(ready_tasks, lambda t: t.origin_proc == proc)):
            continue
        steal(task, proc)
        schedule(task, proc)
        break
    
    return

def task_end_trigger(task : Task, ready_tasks : [Task], free_procs : [Proc]):
    curr_proc = task.exec_proc

    for ready_task in ready_tasks:
        if ready_task.origin == curr_proc:
            schedule_now(ready_task, curr_proc)
            break
    
    for ready_task in ready_task:
        if (ready_task.origin not in free_procs) or \
            # len(ready_task.origin.ready_queue) > 1
            len(map(ready_tasks, 
                    lambda t: t.origin == ready_task.origin
                            and t.ready_time > ready_task.ready_time)) > 0:
                steal(ready_task, curr_proc)
                schedule_now(ready_task, curr_proc)
                break
    
    return
    

    '''
    simulating queues is hard.
    Instead, to check if the ready_queue of a processor is empty,
    we can check if any ready task originated on that proc
    '''