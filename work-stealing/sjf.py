def sjf(ready_tasks):
    min_len = None
    min_task = ready_task[0]
    for task in ready_tasks:
        if task.length < min_len:
            min_len = task.length
            min_task = task
    
    return min_task

def sys(event, output, w, current_task):
    new_event = Event()
    last_scheduled_task_end_time = current_task.time

    ready_time = min(w.task.ready_time)

