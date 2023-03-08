# SRPT verification model

## Requirements
* Z3 solver and bindings for Python: ``pip install z3-solver``
* Python image library (only necessary if generating task visualizations): ``pip install pillow``
* Python argument parsing library: ``pip install argparse``


``test.py`` contains a full model with terminal flags to specify concrete values for minimum and maximum running and blocking times, deadlines, and other details. An example query:

``python3 ./test.py -d 1000 -t 4 -s 2 -g 10 -l 10 -e 0.1 -f 10 -m 0.1 -n 10 -c 1 -u 7 -w -r res.csv -i res.png``

In this query, we set 4 tasks and 2 steps, wich values for minimum and maximum running time (e, f) and minimum and maximum blocking time (m, n). c is the number of tasks which must be finished by SRPT while u is the number of tasks which must be finished by the unconstrained model. A full listing of command line options can be obtained with ``python3 ./test.py -h``.

``test-ratio.py`` and ``test-ratio-smt.py`` contain queries for testing the ratio question: can an oracle schedule finish alpha times more tasks than SRPT. An example query:

``python3 ./test-ratio.py -d 100000 -t 4 -s 2 -e 1 -b 6 -c 1 -u 4 -r res.csv -i res.png``

In this query, e is the minimum running time of a task (essentially, unit time) and b is the ratio between e and the maximum running time of a task. As in ``test.py``, c is the number of tasks which must be finished by SRPT and u is the number which must be finished by the unconstrained (oracle) scheduler. Use ``python3 ./test-ratio.py -h`` to obtain a list of all flags.

``test-time.py`` and ``test-time-smt.py`` contain queries for testing average running time: can SRPT have average running time q times worse than an oracle scheduler. An example query:
  
``python3 test-time.py -d 100000 -t 3 -s 2 -e 1 -q 2.9 -r res.csv -i res.png``

In this query, we have 3 tasks (t) and two steps (s). e again represents the minimum running time of any task (unit time). q is the ratio between average completion time of tasks under SRPT and the oracle schedule.

The ``-smt.py`` variants for ratio and time queries output SMT Lib files containing the generated constraints instead of invoking the solver directly. This allows direct command line invocation of solvers on the output constraints, and allows for testing with solvers other than Z3. Note that variable names in this model are pre-pended with `a` because the Python bindings for Z3 do not correctly handle the translation to SMT constraints when a variable name starts with a non-letter.

Running the solver directly requires Z3 to be installed seperately:

``apt install z3``

For example, to run constraints directly with a solver terminal utitlity, do the following:

``python3 test-time-smt.py -d 100000 -t 3 -s 2 -e 1 -q 2.9 -r constraint.smt2``

``z3 -st -T:10 --model constraint.smt2``

The above Z3 options output the satisfying model and solver statistics with a time limit of 10 seconds.