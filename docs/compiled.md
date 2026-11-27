# Compiled solvers (C, C++, Fortran, Julia)

`physverify.bridge` runs a program as a command and reads the numbers it prints, so the order studies can
check code that is not written in Python. It runs the program: trusted code or the sandbox only.

```python
import numpy as np
from physverify.bridge import command_integrate
from physverify.studies import reference_study

# ./oscillator Y0_1 Y0_2 T_END N_STEPS prints the final state
integrate = command_integrate(["./oscillator", "{y0}", "{t_end}", "{n_steps}"])
rhs = lambda t, y: np.array([y[1], -y[0]])          # written from the physics, not from the program
print(reference_study(integrate, rhs, np.array([1.0, 0.0]), 1.0, (8, 16, 32, 64), 4.0))
```

- An item that is exactly `{name}` with an array value becomes one argument per element; numbers are
  written with `repr`, so no digits are lost. No shell is used.
- Every number on stdout is read, Fortran exponents (`1.0D+00`) included. `last=d` keeps the last d numbers,
  for a program that prints a header or the whole trajectory.
- `command(template)` is the general form: `command(["./heat", "{n}"])(n=32)` returns the numbers printed.
  Use it with `trajectory_order_study`, `check_order` on errors you compute, or the heat checks.
- A compiled program cannot call a Python source term, so `command_integrate` refuses a non-zero one. For the
  manufactured-solution checks, build the source into the program. Julia: `["julia", "solver.jl", ...]`.
- `ctypes` is the other route for a shared library with a C interface; physverify has no wrapper for it,
  since the call signature is the program's own.
