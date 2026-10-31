# Identities, round trips and sibling code

**Question:** does the code agree with itself and with textbook identities, where no exact solution is needed?

Most of the bugs found in widely used libraries during the corpus study were of three kinds, and none of them needed an order study:

- **Two code paths that must agree, but do not.** In one acoustics library, Eyring's reverberation formula had the air-absorption term with the wrong sign, while Sabine's formula right next to it was correct. Two related functions differed in the same way elsewhere: a `max_moment` that ignored a flag its `min_moment` sibling passed on, and a zone plate that ignored its design wavelength while the binary version used it.
- **An operation that its inverse does not undo.** A solar-image rotation by zero time moved the map by half a pixel, because the reference pixel was written as `1 + n/2` instead of `(n + 1)/2`.
- **A textbook identity that fails.** Poisson's equation for a potential and its density, unitarity of a lossless scattering matrix, `E² = p² + m²`, a sliding average that returns to the mean on stationary noise.

`physverify.identities` has a small check for each. All of them return a `Result`; wrap one in `Check("limit", label, lambda: ...)` to run it with the other checks.

```python
--8<-- "docs/examples/identities.py"
```

Output:

```text
--8<-- "docs/examples/output/identities.txt"
```

| Function | What it checks |
|---|---|
| `check_agree(a, b, inputs, rtol, atol)` | `a(*x) == b(*x)` for each input: sibling paths, two formulas that coincide in a limit |
| `check_roundtrip(forward, inverse, inputs)` | `inverse(forward(x)) == x` |
| `check_derivative(f, df, points, order=1)` | an analytic first or second derivative against finite differences of `f` |
| `check_identity([(label, lhs, rhs), ...])` | identities you compute from the physics |
| `check_unitary(M)` | `M^H M = I`, for one matrix or a stack |
| `fd_derivative`, `laplacian_fd` | the finite-difference helpers, for building your own identities |

Values may be real or complex, scalars or arrays; a non-finite value is a FAIL.

For a test that passes only at symmetric example values, for output of the right shape but the wrong size, and for stencils and numerical fluxes, see [Hidden defaults, scale, stencils and fluxes](defaults-scale-stencils.md).

## What these checks cannot tell you

A round trip or a sibling comparison uses two pieces of the code under test, so it passes when both share the same mistake. Use them to find inconsistencies, and keep at least one check against a reference written from the physics. A derivative check settles whether a derivative matches its function, not whether the function is right.

A derivative check also works the other way: it can show that a suspected bug is not one. A code reader claimed that an activity-coefficient derivative in a thermodynamics library dropped a term; comparing it with finite differences of the activity coefficients agreed to 1e-10, so no issue was filed.
