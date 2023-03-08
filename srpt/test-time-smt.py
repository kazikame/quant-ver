from z3 import *
import time
import csv
import argparse
from PIL import Image, ImageDraw, ImageFont

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--timeout',
                        help='Solver timeout (seconds)',
                        required=True)
    parser.add_argument('-t', '--tasks',
                        help='Number of tasks',
                        required=True)
    parser.add_argument('-s', '--steps',
                        help='Number of steps',
                        required=True)
    parser.add_argument('-e', '--epsilon',
                        help='Smallest possible running time (unit). Default value is 1.',
                        required=False)
    parser.add_argument('-a', '--alpha',
                        help='Minimum blocking time, relative to unit. Default value is 1.',
                        required=False)
    parser.add_argument('-b', '--beta',
                        help='Maximum blocking time, relative to unit. Default value is 1.',
                        required=False)
    parser.add_argument('-q', '--ratio',
                        help='Desired ratio of unconstrained to scheduled average completion times. Default value is 1.',
                        required=False)
    parser.add_argument('-w', '--work_conserving', nargs='?', const=True, default=False,
                        help='Include this flag to require that unconstrainted scheduling is work conserving',
                        required=False)
    parser.add_argument('-o', '--output',
                        help='The output CSV file. If not provided, results are printed to stdout.',
                        required=False)
    parser.add_argument('-i', '--image',
                        help='A file to ouptut an image representation of the resulting schedule, if sat',
                        required=False)
    parser.add_argument('-r', '--results',
                        help='A file to output a .csv representation of the resulting schedule, if sat',
                        required=False)
    args = parser.parse_args()
    return args

args = parse_args()


timeout = float(args.timeout)
tasks = int(args.tasks)
steps = int(args.steps)

epsilon = float(args.epsilon) if args.epsilon else 1.0
alpha = float(args.alpha) if args.alpha else None
beta = float(args.beta) if args.beta else None
ratio = float(args.ratio) if args.ratio else 1.0

min_block = alpha * epsilon if alpha else None
max_block = beta * epsilon if beta else None


work_conserving = args.work_conserving

output_file = args.output
results_file = args.results
image_file = args.image




sol = Solver()

def create_arrs(name):
    return [ [Real('a'+str(i)+'_'+name+'_'+str(j)) for j in range(0,steps)] for i in range(0,tasks)]


#ratio = Real("ratio")
#sol.add(ratio < 3)

L = [Real('a'+str(i)+"_L") for i in range(0,tasks)]
ds1 = create_arrs("ds1")
df1 = create_arrs("df1")
rs1 = create_arrs("rs1")
rf1 = create_arrs("rf1")
bs1 = create_arrs("bs1")
bf1 = create_arrs("bf1")
p1 = create_arrs("p1")

ds2 = create_arrs("ds2")
df2 = create_arrs("df2")
rs2 = create_arrs("rs2")
rf2 = create_arrs("rf2")
bs2 = create_arrs("bs2")
bf2 = create_arrs("bf2")
p2 = create_arrs("p2")

#Comparison constraints:
for i in range(0,tasks):
    for j in range(0,steps):
        sol.add(rf1[i][j] - rs1[i][j] == rf2[i][j] - rs2[i][j])
        sol.add(bf1[i][j] - bs1[i][j] == bf2[i][j] - bs2[i][j])


#Inital values of ds
for i in range(0,tasks):
    sol.add(ds1[i][0] == 0)
    sol.add(ds2[i][0] == ds1[i][0])

#One task must start immediately
sol.add(Or([rs1[i][0] == 0 for i in range(0,tasks)]))

#1
for i in range (0,tasks):
    for j in range(0,steps):
        sol.add(df1[i][j]==rs1[i][j])
        sol.add(rf1[i][j]==bs1[i][j])

        sol.add(df2[i][j]==rs2[i][j])
        sol.add(rf2[i][j]==bs2[i][j])
        if (j < steps - 1):
            sol.add(bf1[i][j]==ds1[i][j+1])

            sol.add(bf2[i][j]==ds2[i][j+1])

#2
sol.add(And([Sum([rf1[i][j] - rs1[i][j] for j in range(0,steps)]) == L[i] for i in range(0,tasks)]))

sol.add(And([Sum([rf2[i][j] - rs2[i][j] for j in range(0,steps)]) == L[i] for i in range(0,tasks)]))

if epsilon <= 0:
    raise Exception("Epsilon must be positive")

sol.add(And([p1[i][j] > 0 for i in range(0,tasks) for j in range(0,steps)]))
sol.add(And([df2[i][j] - ds2[i][j] >= 0 for i in range(0,tasks) for j in range(0,steps)]))
sol.add(And([df1[i][j] - ds1[i][j] >= 0 for i in range(0,tasks) for j in range(0,steps)]))

#3
for i in range(0,tasks):
    for j in range(0,steps):
        sol.add(df1[i][j] - ds1[i][j] >= 0)
        sol.add(df2[i][j] - ds2[i][j] >= 0)

        sol.add(rf1[i][j] - rs1[i][j] >= epsilon)
        sol.add(rf2[i][j] - rs2[i][j] >= epsilon)

        #sol.add(rf1[i][j] - rs1[i][j] <= max_run)
        #sol.add(rf2[i][j] - rs2[i][j] <= max_run)
        
    
    for j in range(0,steps-1):
        if min_block:
            sol.add(bf1[i][j] - bs1[i][j] >= min_block)
            sol.add(bf2[i][j] - bs2[i][j] >= min_block)
        else:
            sol.add(bf1[i][j] - bs1[i][j] > 0)
            sol.add(bf2[i][j] - bs2[i][j] > 0)

        #Only impose bounds on blocking time beta was specified
        if max_block:
            sol.add(bf1[i][j] - bs1[i][j] <= max_block)
            sol.add(bf2[i][j] - bs2[i][j] <= max_block)
            

    #Last blocking period has 0 length
    sol.add(bf1[i][steps-1] == bs1[i][steps-1])
    sol.add(bf2[i][steps-1] == bs2[i][steps-1])


#4
for i in range(0,tasks):
    for j in range(0,steps):
        sol.add(p1[i][j] == Sum([rf1[i][k] - rs1[i][k] for k in range(0,j+1)]))

        sol.add(p2[i][j] == Sum([rf2[i][k] - rs2[i][k] for k in range(0,j+1)]))

for i in range(0,tasks):
    for l in range(0,tasks):
        if i != l:
            for j in range(0,steps):
                for k in range(0,steps):
                    #Constraint 5
                    sol.add(Or(rf1[l][k] <= rs1[i][j],rf1[i][j] <= rs1[l][k]))

                    sol.add(Or(rf2[l][k] <= rs2[i][j],rf2[i][j] <= rs2[l][k]))


                    #Constraint 6                
                    if (j == 0 and k == 0):
                        sol.add((rs1[i][j] < rs1[l][k]) == (L[i] < L[l]))
                    elif (j == 0):
                        sol.add(Implies((rs1[i][j] < rs1[l][k]), Or(Or( \
                            And(L[i] <= L[l] - p1[l][k-1],rf1[l][k-1] <= rs1[i][j]), \
                            And(And(L[l] - p1[l][k-1] <= L[i],rf1[l][k-1] <= rs1[i][j]), \
                                And(bs1[l][k-1] <= rs1[i][j], rs1[i][j] < bf1[l][k-1])), \
                            rf1[l][k-1] > rs1[i][j] \
                        ))))
                    elif (k == 0):
                        True

                    else:
                        sol.add(Implies((rs1[i][j] < rs1[l][k]), Or(Or( \
                            And(L[i] - p1[i][j-1] <= L[l] - p1[l][k-1],rf1[l][k-1] <= rs1[i][j]), \
                            And(And(L[l] - p1[l][k-1] <= L[i] - p1[i][j-1],rf1[l][k-1] <= rs1[i][j]), \
                                And(bs1[l][k-1] <= rs1[i][j], rs1[i][j] < bf1[l][k-1])), \
                            rf1[l][k-1] > rs1[i][j] \
                        ))))
                    
                    sol.add(Implies(And(ds1[l][k] <= bs1[i][j], bs1[i][j] <= df1[l][k]), \
                        Or([bs1[i][j] == rs1[lp][kp] for lp in range(0,tasks) for kp in range(0,steps)])))
                    if work_conserving:
                        sol.add(Implies(And(ds2[l][k] <= bs2[i][j], bs2[i][j] <= df2[l][k]), \
                            Or([bs2[i][j] == rs2[lp][kp] for lp in range(0,tasks) for kp in range(0,steps)])))

#More constriant 7
for i in range(0,tasks):
    for j in range(0,steps):
        sol.add(Or([And(rs1[lp][kp] <= ds1[i][j],ds1[i][j]<=rf1[lp][kp]) for lp in range(0,tasks) for kp in range(0,steps)]))
        if work_conserving:
            sol.add(Or([And(rs2[lp][kp] <= ds2[i][j],ds2[i][j]<=rf2[lp][kp]) for lp in range(0,tasks) for kp in range(0,steps)]))


sol.add(Sum([bf1[i][steps-1] for i in range(0,tasks)]) >= ratio * Sum([bf2[i][steps-1] for i in range(0,tasks)]))

temp_list = [tasks, steps, epsilon, alpha, beta, ratio, work_conserving]
#print("running "+",".join(map(lambda x: str(x),temp_list)))


#Output raw SMT constraints (variable names are also pre-pended with a)
#To avoid Z3 python bindings issues
with open(results_file, mode='w') as f:
    f.write(sol.to_smt2())
exit()