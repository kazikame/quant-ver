#group util = sum of util_avg of each cpu
def find_migration_type(busiest, local, idle):
    if local.has_spare():
        if busiest.is_overloaded() and (not idle or local.capacity > local.util):
            return MIGRATE_UTIL
        else:
            return MIGRATE_TASK
    # else: ...

def find_busiest_cpu(group, m_type):
    cpu_list = group.get_cpus()
    match m_type:
        case MIGRATE_UTIL:
            cpu_with_more = filter(lambda cpu: cpu.nr_running > 1, cpu_list)
            return argmax(cpu_with_more, key=cpu.util_avg)
        case MIGRATE_TASK:
            return argmax(cpu_list, key=cpu.nr_running)
        # case ...

def calculate_imbalance(busiest, local, m_type):
    match m_type:
        case MIGRATE_UTIL:
            return local.capacity - local.util
        case MIGRATE_TASK:
            if busiest.is_overloaded():
                return 1
            else:
                return (busiest.nr_idle_cpus - local.nr_idle_cpus) / 2
        # case ...

def detach_tasks(src_c, dst_c, m_type, imb):
    for task in src_c.rq.tasks:
        val = task.metric(m_type)
        if val <= imb:
            migrate(task, src_c, dst_c)
            imb -= val

# Assuming all statistics are updated
def load_balance(c, sd):
    if not is_responsible(c, sd):
        return
    
    if not considerable_imbalance(c.idle, sd):
        return
    
    dst_g = sd.find_group(c)

    if sd.group_above_average(dst_g):
        return

    src_g = sd.find_busiest_group()
    
    m_type = find_migration_type(src_g, dst_g, c.idle)
    src_c = src_g.find_busiest_cpu(m_type)
    imb = calculate_imbalance(src_g, dst_g, m_type)

    detach_tasks(src_c, c, m_type, imb)