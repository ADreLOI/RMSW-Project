# Coordination work counts

Counts describe algorithmic binary64 arithmetic, not Python/processor instructions or energy. Exclude motion, logging, JSON encoding, plotting, profiling, and offline integer geometry construction. Counts stop at completion/timeout and include initial online allocation. GOP = arithmetic / 1e9, not GOP/s.

Each floating add/subtract/multiply/divide counts one; squaring is one multiply. No fused multiply-add. Logarithms and square roots are separate. Integer bookkeeping is excluded. Logical counts are pseudocode ordering tests or membership visits, not machine-level instruction counts.

Allocation: one seconds-per-cell division per boat; executing remaining edge time uses division plus addition; each remaining step division plus addition; required turns one addition. Each eligible score `elapsed + steps * seconds_per_cell + turns * turn_s` costs four arithmetic operations. NumPy uses elementwise binary64, without BLAS. Argmin over N candidates counts N-1 ordering tests; each subsequent best tuple adds one lexicographic test. The four-cell hand-worked test evaluates 2+2+1 candidate scores plus two divisions: 22 operations.

Persistence copies signal values, with one threshold addition and the executed short-circuit warning comparisons. A full trend with N samples and K projected values costs: 6N for relative times/residuals; 2N+2 for sums/means; 7N for centered least-squares sums; 3 for slope/intercept; 4 for relative velocity; 14K for projections; one threshold addition. Total `15N+9+14K+1`, or 141 at N=5,K=4. There are N+K logarithms, K square roots, and N+K clamp comparisons plus executed warning comparisons. Warmup uses persistence.

Resynchronization's set union has zero floating arithmetic; |C0|+|C1| membership visits are reported as logical work. Python hashing internals are not claimed as known instruction counts. Communication work is represented by bytes, rather than invented floating arithmetic.

Component CPU counters exclude writing/plotting but may be below Windows timer resolution. Separate saved-input repeated benchmarks run batches above 150 ms CPU time, with seven batches, and include wrapper/loop overhead. Peak process RAM includes the interpreter, NumPy, geometry, and simulator; separate tracemalloc profiles describe incremental Python allocations and exclude some native allocations.
