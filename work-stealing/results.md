----------------
Proc = 2
Threads = 3
Inst Per Thread = 2 (exactly 2)
Exec Cost per Inst = 1-10

Context Switch Cost -- Ratio
0. 0 - 1.5
1. 1 - 1.708
2. 10 - 2.291
3. 100 - 2.473 (2.473 w/ no bound on exec cost)
4. 1000 - 2.491 (2.491 w/ no bound on exec cost)
5. (0-1) - 2
4. (0-10) - 2.7265625
5. (0-100) - 2.9609375
6. (0-1000) - 2.9921875

<!-- 1. 10 - 3.99
2. 20 - 6.49
3. 30 - 8.99
4. 40 - 11.49
3. 100  26.49 -->

Linear relationship!

-----------------------
P = 3
T = 3
I = 2

0. 0 - 1
1. 1 - 1.4921875
2. 10 - 1.8299
3. 100 - 1.976
4. 1000 - 1.994
5. (0-1) - 1.4921875
5. (0-10) - 2.578125
6. (1-100) - 2.578125
7. (0-1000) - 2.578125
-----------------------

P = 2
T = 3
I = 3

1. 10 - 
4. 40 - 14.49   