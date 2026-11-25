# A spec in pyproject.toml

For a fixed-step ODE solver, the spec can be a table in `pyproject.toml` instead of a Python file. Write the equations from the physics, not from the solver's code: a copied mistake passes every check.

```toml
[[tool.physverify.ode]]
solver = "damped_oscillator:integrate"          # module:function
args = ["source", "y0", "t_end", "n_steps"]     # what to pass, in the solver's order (this is the default)
order = 2                                       # the claimed order
t_end = 1.0
y0 = { x = 1.0, v = 0.0 }
parameters = { omega = 3.0, gamma = 0.4 }
equations = { x = "v", v = "-omega**2 * x - 2*gamma*v" }
patch = true                                    # explicit Runge-Kutta methods only
```

```bash
physverify run pyproject.toml
pytest pyproject.toml
```

`path = "src"` says where the module is, inside the project folder. Add one table per solver.

## What is passed to the solver

| Name in `args` | Value |
|---|---|
| `source` | a function `source(t)`: what to add to the right-hand side (an array, or 0.0 for none) |
| `f` | a function `f(t, y)`, the whole right-hand side from the table, source included |
| `y0` | the starting state, in the order of `equations` |
| `t0`, `t_end` | 0 and the end time |
| `n_steps`, `h`, `times` | the number of steps, the step size, the array of n_steps + 1 times |

`returns = "final"` (default) means an array with the state at `t_end`; `returns = "trajectory"` means an array of shape (n_steps + 1, variables) starting with `y0`. Any other shape is an ERROR.

## Which checks run

| `args` contains | Checks | What they say about the equations in the solver |
|---|---|---|
| `source` | manufactured solution, reference solution | tested |
| `f` | the same | **not tested**: the solver is given the equations from the table, so only the integrator is checked; the label says so |
| neither | reference solution only | tested from this one starting state |

`conserved = "v**2/2 + omega**2*x**2/2"` adds a drift check, `returns = "trajectory"` adds the error over the whole run where `source` or `f` is passed, and `patch = true` adds the [patch test](checks/patch.md), which needs `source` or `f`.

## What the equations may contain

Numbers, the variables, the parameters, `t`, `pi`, `+ - * / **`, and `sin cos tan arcsin arccos arctan arctan2 sinh cosh tanh exp log sqrt abs`. Anything else is refused: the text is read by a small parser, never with `eval`. Importing and calling the solver does run code, so use this only on projects you trust.

The manufactured solution stays within 0.1 of `y0` in each variable, so choose a `y0` with typical sizes, away from singular points. For anything else (stiff problems, PDEs, a solver that needs an adapter), write a [Python spec](getting-started.md).
