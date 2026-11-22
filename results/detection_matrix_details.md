### projectile / (baseline)
- mms [vacuum/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- mms [vacuum/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- invariant [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- patch [vacuum/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [vacuum/euler] PASS: observed order 1.00 (expected 1)
- reference [vacuum/euler] PASS: observed order 1.00 (expected 1)
- invariant [vacuum/euler] PASS: observed order 1.00 (expected 1)
- patch [vacuum/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [linear/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [linear/rk4] PASS: observed order 4.00 (expected 4)
- mms [linear/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [linear/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [linear/euler] PASS: observed order 1.00 (expected 1)
- reference [linear/euler] PASS: observed order 1.00 (expected 1)
- patch [linear/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [quadratic/rk4] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [quadratic/rk4] PASS: observed order 4.03 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- mms [quadratic/rk4 (whole trajectory)] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [quadratic/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [quadratic/euler] PASS: observed order 1.00 (expected 1)
- reference [quadratic/euler] PASS: observed order 1.00 (expected 1)
- patch [quadratic/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- limit [vacuum/rk4 range] PASS: observed order 2.00 (expected 2)

### projectile / gravity_sign
- mms [vacuum/rk4] FAIL: error does not decrease with resolution (about 19.6 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [vacuum/rk4] FAIL: error does not decrease with resolution (about 19.6 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [vacuum/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 19.6 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [vacuum/rk4] FAIL: error does not decrease with resolution (about 2.72 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [vacuum/rk4] FAIL: expected an exact solution to round-off, but the error reaches 19.6 and shrinks at about order -0.00
- mms [vacuum/euler] FAIL: error does not decrease with resolution (about 19.6 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [vacuum/euler] FAIL: error does not decrease with resolution (about 19.6 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [vacuum/euler] FAIL: error does not decrease with resolution (about 2.72 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [vacuum/euler] FAIL: expected an exact solution to round-off, but the error reaches 19.6 and shrinks at about order -0.00
- mms [linear/rk4] FAIL: error does not decrease with resolution (about 19.4 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [linear/rk4] FAIL: error does not decrease with resolution (about 19.4 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [linear/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 19.4 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [linear/rk4] FAIL: expected an exact solution to round-off, but the error reaches 19.4 and shrinks at about order -0.00
- mms [linear/euler] FAIL: error does not decrease with resolution (about 19.4 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [linear/euler] FAIL: error does not decrease with resolution (about 19.4 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [linear/euler] FAIL: expected an exact solution to round-off, but the error reaches 19.4 and shrinks at about order 0.00
- mms [quadratic/rk4] FAIL: error does not decrease with resolution (about 16.5 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [quadratic/rk4] FAIL: error does not decrease with resolution (about 15.6 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [quadratic/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 16.5 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [quadratic/rk4] FAIL: expected an exact solution to round-off, but the error reaches 16.5 and shrinks at about order -0.00
- mms [quadratic/euler] FAIL: error does not decrease with resolution (about 16.5 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [quadratic/euler] FAIL: error does not decrease with resolution (about 15.6 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [quadratic/euler] FAIL: expected an exact solution to round-off, but the error reaches 16.6 and shrinks at about order 0.00
- limit [vacuum/rk4 range] ERROR: RuntimeError: projectile never landed within 100 s

### projectile / linear_drag_missing_mass
- mms [vacuum/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- mms [vacuum/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- invariant [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- patch [vacuum/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [vacuum/euler] PASS: observed order 1.00 (expected 1)
- reference [vacuum/euler] PASS: observed order 1.00 (expected 1)
- invariant [vacuum/euler] PASS: observed order 1.00 (expected 1)
- patch [vacuum/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [linear/rk4] FAIL: error does not decrease with resolution (about 0.0389 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [linear/rk4] FAIL: error does not decrease with resolution (about 0.12 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [linear/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.0404 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [linear/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0182 and shrinks at about order -0.00
- mms [linear/euler] FAIL: error does not decrease with resolution (about 0.0412 at the finest level)
- reference [linear/euler] FAIL: error does not decrease with resolution (about 0.12 at the finest level)
- patch [linear/euler] FAIL: expected an exact solution to round-off, but the error reaches 0.0184 and shrinks at about order 0.00
- mms [quadratic/rk4] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [quadratic/rk4] PASS: observed order 4.03 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- mms [quadratic/rk4 (whole trajectory)] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [quadratic/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [quadratic/euler] PASS: observed order 1.00 (expected 1)
- reference [quadratic/euler] PASS: observed order 1.00 (expected 1)
- patch [quadratic/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- limit [vacuum/rk4 range] PASS: observed order 2.00 (expected 2)

### projectile / quad_drag_factor_half
- mms [vacuum/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- mms [vacuum/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- invariant [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- patch [vacuum/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [vacuum/euler] PASS: observed order 1.00 (expected 1)
- reference [vacuum/euler] PASS: observed order 1.00 (expected 1)
- invariant [vacuum/euler] PASS: observed order 1.00 (expected 1)
- patch [vacuum/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [linear/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [linear/rk4] PASS: observed order 4.00 (expected 4)
- mms [linear/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [linear/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [linear/euler] PASS: observed order 1.00 (expected 1)
- reference [linear/euler] PASS: observed order 1.00 (expected 1)
- patch [linear/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [quadratic/rk4] FAIL: error does not decrease with resolution (about 0.339 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [quadratic/rk4] FAIL: error does not decrease with resolution (about 1.41 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [quadratic/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.347 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [quadratic/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0581 and shrinks at about order -0.00
- mms [quadratic/euler] FAIL: error does not decrease with resolution (about 0.338 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [quadratic/euler] FAIL: error does not decrease with resolution (about 1.41 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [quadratic/euler] FAIL: expected an exact solution to round-off, but the error reaches 0.0591 and shrinks at about order 0.01
- limit [vacuum/rk4 range] PASS: observed order 2.00 (expected 2)

### projectile / quad_drag_speed_from_vx
- mms [vacuum/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- mms [vacuum/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- invariant [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- patch [vacuum/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [vacuum/euler] PASS: observed order 1.00 (expected 1)
- reference [vacuum/euler] PASS: observed order 1.00 (expected 1)
- invariant [vacuum/euler] PASS: observed order 1.00 (expected 1)
- patch [vacuum/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [linear/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [linear/rk4] PASS: observed order 4.00 (expected 4)
- mms [linear/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [linear/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [linear/euler] PASS: observed order 1.00 (expected 1)
- reference [linear/euler] PASS: observed order 1.00 (expected 1)
- patch [linear/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [quadratic/rk4] FAIL: error does not decrease with resolution (about 0.354 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [quadratic/rk4] FAIL: error does not decrease with resolution (about 0.343 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [quadratic/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.357 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [quadratic/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0344 and shrinks at about order -0.00
- mms [quadratic/euler] FAIL: error does not decrease with resolution (about 0.357 at the finest level)
- reference [quadratic/euler] FAIL: error does not decrease with resolution (about 0.343 at the finest level)
- patch [quadratic/euler] FAIL: expected an exact solution to round-off, but the error reaches 0.0349 and shrinks at about order 0.01
- limit [vacuum/rk4 range] PASS: observed order 2.00 (expected 2)

### projectile / quad_drag_abs_vx
- mms [vacuum/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- mms [vacuum/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- invariant [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- patch [vacuum/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [vacuum/euler] PASS: observed order 1.00 (expected 1)
- reference [vacuum/euler] PASS: observed order 1.00 (expected 1)
- invariant [vacuum/euler] PASS: observed order 1.00 (expected 1)
- patch [vacuum/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [linear/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [linear/rk4] PASS: observed order 4.00 (expected 4)
- mms [linear/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [linear/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [linear/euler] PASS: observed order 1.00 (expected 1)
- reference [linear/euler] PASS: observed order 1.00 (expected 1)
- patch [linear/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [quadratic/rk4] FAIL: error does not decrease with resolution (about 0.000503 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [quadratic/rk4] PASS: observed order 4.03 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- mms [quadratic/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.000503 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [quadratic/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0652 and shrinks at about order 0.00
- mms [quadratic/euler] PASS: observed order 1.00 (expected 1)
- reference [quadratic/euler] PASS: observed order 1.00 (expected 1)
- patch [quadratic/euler] FAIL: expected an exact solution to round-off, but the error reaches 0.0662 and shrinks at about order 0.01
- limit [vacuum/rk4 range] PASS: observed order 2.00 (expected 2)

### projectile / landing_no_interp
- mms [vacuum/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- mms [vacuum/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- invariant [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- patch [vacuum/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [vacuum/euler] PASS: observed order 1.00 (expected 1)
- reference [vacuum/euler] PASS: observed order 1.00 (expected 1)
- invariant [vacuum/euler] PASS: observed order 1.00 (expected 1)
- patch [vacuum/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [linear/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [linear/rk4] PASS: observed order 4.00 (expected 4)
- mms [linear/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [linear/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [linear/euler] PASS: observed order 1.00 (expected 1)
- reference [linear/euler] PASS: observed order 1.00 (expected 1)
- patch [linear/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [quadratic/rk4] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [quadratic/rk4] PASS: observed order 4.03 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- mms [quadratic/rk4 (whole trajectory)] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [quadratic/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [quadratic/euler] PASS: observed order 1.00 (expected 1)
- reference [quadratic/euler] PASS: observed order 1.00 (expected 1)
- patch [quadratic/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- limit [vacuum/rk4 range] FAIL: observed order 1.00 is below the expected 2

### projectile / angle_not_converted
- mms [vacuum/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- mms [vacuum/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- invariant [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- patch [vacuum/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [vacuum/euler] PASS: observed order 1.00 (expected 1)
- reference [vacuum/euler] PASS: observed order 1.00 (expected 1)
- invariant [vacuum/euler] PASS: observed order 1.00 (expected 1)
- patch [vacuum/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [linear/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [linear/rk4] PASS: observed order 4.00 (expected 4)
- mms [linear/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [linear/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [linear/euler] PASS: observed order 1.00 (expected 1)
- reference [linear/euler] PASS: observed order 1.00 (expected 1)
- patch [linear/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- mms [quadratic/rk4] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [quadratic/rk4] PASS: observed order 4.03 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- mms [quadratic/rk4 (whole trajectory)] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [quadratic/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [quadratic/euler] PASS: observed order 1.00 (expected 1)
- reference [quadratic/euler] PASS: observed order 1.00 (expected 1)
- patch [quadratic/euler] EXACT: reproduced to round-off (largest error 5.7e-14), as designed
- limit [vacuum/rk4 range] FAIL: error does not decrease with resolution (about 182 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator

### projectile / euler_extra_step
- mms [vacuum/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- mms [vacuum/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- invariant [vacuum/rk4] EXACT: error below 1e-12 at every resolution; order not measurable
- patch [vacuum/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [vacuum/euler] PASS: observed order 1.00 (expected 1)
- reference [vacuum/euler] PASS: observed order 1.00 (expected 1)
- invariant [vacuum/euler] PASS: observed order 1.01 (expected 1)
- patch [vacuum/euler] FAIL: expected an exact solution to round-off, but the error reaches 0.075 and shrinks at about order 1.00
- mms [linear/rk4] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [linear/rk4] PASS: observed order 4.00 (expected 4)
- mms [linear/rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [linear/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [linear/euler] PASS: observed order 1.00 (expected 1)
- reference [linear/euler] PASS: observed order 1.00 (expected 1)
- patch [linear/euler] FAIL: expected an exact solution to round-off, but the error reaches 0.075 and shrinks at about order 1.00
- mms [quadratic/rk4] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- reference [quadratic/rk4] PASS: observed order 4.03 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- mms [quadratic/rk4 (whole trajectory)] PASS: observed order 4.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [quadratic/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [quadratic/euler] PASS: observed order 1.00 (expected 1)
- reference [quadratic/euler] PASS: observed order 1.00 (expected 1)
- patch [quadratic/euler] FAIL: expected an exact solution to round-off, but the error reaches 0.075 and shrinks at about order 1.00
- limit [vacuum/rk4 range] PASS: observed order 2.00 (expected 2)

### projectile / euler_instead_of_rk4
- mms [vacuum/rk4] FAIL: observed order 1.00 is below the expected 4
- reference [vacuum/rk4] FAIL: observed order 1.00 is below the expected 4
- mms [vacuum/rk4 (whole trajectory)] FAIL: observed order 1.00 is below the expected 4
- invariant [vacuum/rk4] FAIL: observed order 1.00 is below the expected 4
- patch [vacuum/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [linear/rk4] FAIL: observed order 1.00 is below the expected 4
- reference [linear/rk4] FAIL: observed order 1.00 is below the expected 4
- mms [linear/rk4 (whole trajectory)] FAIL: observed order 1.00 is below the expected 4
- patch [linear/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- mms [quadratic/rk4] FAIL: observed order 1.00 is below the expected 4
- reference [quadratic/rk4] FAIL: observed order 1.00 is below the expected 4
- mms [quadratic/rk4 (whole trajectory)] FAIL: observed order 1.00 is below the expected 4
- patch [quadratic/rk4] EXACT: reproduced to round-off (largest error 1.4e-14), as designed
- limit [vacuum/rk4 range] FAIL: observed order 1.00 is below the expected 2

### projectile / rk4_weights
- mms [vacuum/rk4] FAIL: error does not decrease with resolution (about 3.03 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [vacuum/rk4] FAIL: error does not decrease with resolution (about 3.33 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [vacuum/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 3.03 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [vacuum/rk4] FAIL: observed order 1.00 is below the expected 4
- patch [vacuum/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.9 and shrinks at about order 0.00
- mms [linear/rk4] FAIL: error does not decrease with resolution (about 3.01 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [linear/rk4] FAIL: error does not decrease with resolution (about 3.3 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [linear/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 3.01 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [linear/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.901 and shrinks at about order 0.00
- mms [quadratic/rk4] FAIL: error does not decrease with resolution (about 2.91 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [quadratic/rk4] FAIL: error does not decrease with resolution (about 3.42 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [quadratic/rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 2.91 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [quadratic/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.902 and shrinks at about order 0.00
- limit [vacuum/rk4 range] FAIL: observed order 1.01 is below the expected 2

### projectile / rk4_full_step_stage2
- mms [vacuum/rk4] FAIL: observed order 1.00 is below the expected 4
- reference [vacuum/rk4] FAIL: observed order 1.00 is below the expected 4
- mms [vacuum/rk4 (whole trajectory)] FAIL: observed order 1.00 is below the expected 4
- invariant [vacuum/rk4] FAIL: observed order 1.00 is below the expected 4
- patch [vacuum/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0167 and shrinks at about order 1.00
- mms [linear/rk4] FAIL: observed order 1.00 is below the expected 4
- reference [linear/rk4] FAIL: observed order 1.00 is below the expected 4
- mms [linear/rk4 (whole trajectory)] FAIL: observed order 1.00 is below the expected 4
- patch [linear/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0165 and shrinks at about order 1.00
- mms [quadratic/rk4] FAIL: observed order 1.00 is below the expected 4
- reference [quadratic/rk4] FAIL: observed order 1.01 is below the expected 4
- mms [quadratic/rk4 (whole trajectory)] FAIL: observed order 1.00 is below the expected 4
- patch [quadratic/rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0159 and shrinks at about order 1.00
- limit [vacuum/rk4 range] FAIL: observed order 1.01 is below the expected 2

### pendulum / (baseline)
- mms [rk4] PASS: observed order 3.98 (expected 4)
- reference [rk4] PASS: observed order 3.95 (expected 4)
- mms [rk4 (whole trajectory)] PASS: observed order 4.05 (expected 4)
- invariant [rk4] PASS: observed order 5.10 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [rk4] EXACT: reproduced to round-off (largest error 8.1e-15), as designed
- limit [small-oscillation frequencies] PASS: frequencies match the closed form (relative error 5.8e-13)

### pendulum / coupling_sign
- mms [rk4] FAIL: error does not decrease with resolution (about 0.02 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 0.247 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.02 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: error does not decrease with resolution (about 0.00248 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0273 and shrinks at about order -0.00
- limit [small-oscillation frequencies] PASS: frequencies match the closed form (relative error 5.8e-13)

### pendulum / mass_matrix_missing_cos
- mms [rk4] FAIL: error does not decrease with resolution (about 0.46 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 0.0603 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.46 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: error does not decrease with resolution (about 0.00065 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.883 and shrinks at about order 0.00
- limit [small-oscillation frequencies] PASS: frequencies match the closed form (relative error 3.3e-13)

### pendulum / gravity_mass_missing
- mms [rk4] FAIL: error does not decrease with resolution (about 1.73 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 0.422 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 1.73 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: error does not decrease with resolution (about 0.0203 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 3.34 and shrinks at about order -0.00
- limit [small-oscillation frequencies] FAIL: frequencies [np.float64(2.1219488542025706), np.float64(5.525671664678316)] differ from [2.621396023017722, 6.0009996814048545] (relative error 0.19)

### pendulum / rk4_stage4_time
- mms [rk4] FAIL: observed order 0.98 is below the expected 4
- reference [rk4] PASS: observed order 3.95 (expected 4)
- mms [rk4 (whole trajectory)] FAIL: observed order 0.97 is below the expected 4
- invariant [rk4] PASS: observed order 5.10 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0147 and shrinks at about order 1.00
- limit [small-oscillation frequencies] PASS: frequencies match the closed form (relative error 5.8e-13)

### pendulum / swapped_lengths
- mms [rk4] FAIL: error does not decrease with resolution (about 0.0884 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 0.0381 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.0884 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: error does not decrease with resolution (about 0.000296 at the finest level)
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.165 and shrinks at about order -0.00
- limit [small-oscillation frequencies] PASS: frequencies match the closed form (relative error 5.8e-13)

### pendulum / small_angle_gravity
- mms [rk4] FAIL: error does not decrease with resolution (about 0.0129 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 0.074 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.0129 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: error does not decrease with resolution (about 0.000762 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.165 and shrinks at about order -0.00
- limit [small-oscillation frequencies] PASS: frequencies match the closed form (relative error 5.3e-13)

### pendulum / euler_instead_of_rk4
- mms [rk4] FAIL: observed order 1.01 is below the expected 4
- reference [rk4] FAIL: observed order 1.39 is below the expected 4
- mms [rk4 (whole trajectory)] FAIL: observed order 1.01 is below the expected 4
- invariant [rk4] FAIL: observed order 1.17 is below the expected 4
- patch [rk4] EXACT: reproduced to round-off (largest error 7.4e-15), as designed
- limit [small-oscillation frequencies] PASS: frequencies match the closed form (relative error 5.8e-13)

### pendulum / rk4_weights
- mms [rk4] FAIL: error does not decrease with resolution (about 0.49 at the finest level)
- reference [rk4] FAIL: error does not decrease with resolution (about 1.1 at the finest level)
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.49 at the finest level)
- invariant [rk4] FAIL: observed order 0.97 is below the expected 4
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.154 and shrinks at about order 0.01
- limit [small-oscillation frequencies] PASS: frequencies match the closed form (relative error 5.8e-13)

### pendulum / rk4_full_step_stage2
- mms [rk4] FAIL: observed order 0.93 is below the expected 4
- reference [rk4] FAIL: observed order 1.06 is below the expected 4
- mms [rk4 (whole trajectory)] FAIL: observed order 0.96 is below the expected 4
- invariant [rk4] FAIL: observed order 0.95 is below the expected 4
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.0258 and shrinks at about order 0.96
- limit [small-oscillation frequencies] PASS: frequencies match the closed form (relative error 5.8e-13)

### kepler / (baseline)
- mms [rk4] PASS: observed order 4.00 (expected 4); 2 finest resolution(s) within a factor 100 of the noise floor (8.2e-13) were left out of the fit as round-off
- reference [rk4] PASS: observed order 4.04 (expected 4)
- mms [rk4 (whole trajectory)] PASS: observed order 4.00 (expected 4); 2 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- invariant [rk4] PASS: observed order 4.12 (expected 4)
- patch [rk4] EXACT: reproduced to round-off (largest error 1.1e-14), as designed
- invariant [rk4 angular momentum] PASS: observed order 5.03 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- limit [orbit closes after one period] PASS: observed order 4.14 (expected 4)

### kepler / inverse_r_force
- mms [rk4] FAIL: error does not decrease with resolution (about 0.073 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 0.735 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.073 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: error does not decrease with resolution (about 0.557 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.165 and shrinks at about order -0.00
- invariant [rk4 angular momentum] PASS: observed order 5.01 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- limit [orbit closes after one period] FAIL: error does not decrease with resolution (about 1.78 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator

### kepler / y_force_sign
- mms [rk4] FAIL: error does not decrease with resolution (about 0.612 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 2.6 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.612 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: error does not decrease with resolution (about 8.19 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.577 and shrinks at about order 0.00
- invariant [rk4 angular momentum] FAIL: error does not decrease with resolution (about 0.605 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- limit [orbit closes after one period] FAIL: error does not decrease with resolution (about 16.9 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator

### kepler / gm_one_percent
- mms [rk4] FAIL: error does not decrease with resolution (about 0.00909 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 0.0322 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.00909 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: error does not decrease with resolution (about 0.019 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.00552 and shrinks at about order 0.00
- invariant [rk4 angular momentum] PASS: observed order 5.03 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- limit [orbit closes after one period] FAIL: error does not decrease with resolution (about 0.942 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator

### kepler / softening_left_on
- mms [rk4] FAIL: error does not decrease with resolution (about 1.16e-06 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 1.37e-05 at the finest level)
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 1.16e-06 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: error does not decrease with resolution (about 6.88e-06 at the finest level)
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 4.99e-07 and shrinks at about order 0.00
- invariant [rk4 angular momentum] PASS: observed order 5.03 (expected 4); 1 finest resolution(s) within a factor 100 of the noise floor (1e-12) were left out of the fit as round-off
- limit [orbit closes after one period] FAIL: error does not decrease with resolution (about 0.000331 at the finest level)

### kepler / euler_instead_of_rk4
- mms [rk4] FAIL: observed order 0.99 is below the expected 4
- reference [rk4] FAIL: observed order 0.95 is below the expected 4
- mms [rk4 (whole trajectory)] FAIL: observed order 0.99 is below the expected 4
- invariant [rk4] FAIL: observed order 0.97 is below the expected 4
- patch [rk4] EXACT: reproduced to round-off (largest error 1.1e-14), as designed
- invariant [rk4 angular momentum] FAIL: observed order 0.99 is below the expected 4
- limit [orbit closes after one period] FAIL: observed order 0.49 is below the expected 4

### kepler / rk4_weights
- mms [rk4] FAIL: error does not decrease with resolution (about 0.326 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [rk4] FAIL: error does not decrease with resolution (about 0.418 at the finest level)
- mms [rk4 (whole trajectory)] FAIL: error does not decrease with resolution (about 0.326 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- invariant [rk4] FAIL: observed order 1.00 is below the expected 4
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.147 and shrinks at about order -0.00
- invariant [rk4 angular momentum] FAIL: observed order 1.00 is below the expected 4
- limit [orbit closes after one period] FAIL: error does not decrease with resolution (about 2.19 at the finest level)

### kepler / rk4_full_step_stage2
- mms [rk4] FAIL: observed order 0.99 is below the expected 4
- reference [rk4] FAIL: observed order 0.99 is below the expected 4
- mms [rk4 (whole trajectory)] FAIL: observed order 0.99 is below the expected 4
- invariant [rk4] FAIL: observed order 1.00 is below the expected 4
- patch [rk4] FAIL: expected an exact solution to round-off, but the error reaches 0.00337 and shrinks at about order 1.00
- invariant [rk4 angular momentum] FAIL: observed order 1.00 is below the expected 4
- limit [orbit closes after one period] FAIL: observed order 0.62 is below the expected 4

### heat1d / (baseline)
- mms [FTCS coupled dt ~ dx^2] PASS: observed order 2.00 (expected 2)
- mms [FTCS time-only refinement] PASS: observed order 1.00 (expected 1)
- mms [FTCS space-only refinement] PASS: observed order 2.00 (expected 2)
- reference [FTCS eigenmode decay] PASS: observed order 1.99 (expected 2)
- patch [FTCS cubic in x, linear in t] EXACT: reproduced to round-off (largest error 2.8e-16), as designed

### heat1d / dx_off_by_one
- mms [FTCS coupled dt ~ dx^2] FAIL: observed order 0.91 is below the expected 2
- mms [FTCS time-only refinement] FAIL: error does not decrease with resolution (about 0.0117 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- mms [FTCS space-only refinement] FAIL: observed order 0.91 is below the expected 2
- reference [FTCS eigenmode decay] FAIL: observed order 1.00 is below the expected 2
- patch [FTCS cubic in x, linear in t] FAIL: expected an exact solution to round-off, but the error reaches 0.0515 and shrinks at about order 0.34

### heat1d / alpha_ignored
- mms [FTCS coupled dt ~ dx^2] FAIL: error does not decrease with resolution (about 0.235 at the finest level)
- mms [FTCS time-only refinement] FAIL: error does not decrease with resolution (about 0.0698 at the finest level)
- mms [FTCS space-only refinement] FAIL: error does not decrease with resolution (about 0.272 at the finest level)
- reference [FTCS eigenmode decay] FAIL: error does not decrease with resolution (about 0.128 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- patch [FTCS cubic in x, linear in t] FAIL: expected an exact solution to round-off, but the error reaches 0.0789 and shrinks at about order 0.00

### heat1d / extra_time_step
- mms [FTCS coupled dt ~ dx^2] PASS: observed order 2.00 (expected 2)
- mms [FTCS time-only refinement] PASS: observed order 1.00 (expected 1)
- mms [FTCS space-only refinement] PASS: observed order 2.00 (expected 2)
- reference [FTCS eigenmode decay] PASS: observed order 2.00 (expected 2)
- patch [FTCS cubic in x, linear in t] FAIL: expected an exact solution to round-off, but the error reaches 0.00212 and shrinks at about order 1.00

### heat1d / unstable_dt
- mms [FTCS coupled dt ~ dx^2] FAIL: error does not decrease with resolution (about 4.31e+261 at the finest level)
- mms [FTCS time-only refinement] PASS: observed order 1.00 (expected 1)
- mms [FTCS space-only refinement] FAIL: error does not decrease with resolution (about 3.09e+261 at the finest level)
- reference [FTCS eigenmode decay] FAIL: error does not decrease with resolution (about 2.16e+261 at the finest level)
- patch [FTCS cubic in x, linear in t] FAIL: expected an exact solution to round-off, but the error reaches 0.349

### heat1d / source_time_shift
- mms [FTCS coupled dt ~ dx^2] PASS: observed order 2.00 (expected 2)
- mms [FTCS time-only refinement] PASS: observed order 1.00 (expected 1)
- mms [FTCS space-only refinement] PASS: observed order 2.00 (expected 2)
- reference [FTCS eigenmode decay] PASS: observed order 1.99 (expected 2)
- patch [FTCS cubic in x, linear in t] FAIL: expected an exact solution to round-off, but the error reaches 0.00111 and shrinks at about order 1.00

### sod / (baseline)
- reference [Sod shock tube, density L1] PASS: observed order 0.63 (expected 0.5)
- reference [smooth density wave, periodic] PASS: observed order 0.98 (expected 1)
- reference [acoustic wave about rest, periodic] PASS: observed order 0.99 (expected 1)
- reference [acoustic pulse leaving through an open end] PASS: after the pulse left through the open end, at most 0.00018 of it remained (limit 0.01) on 50 to 200 cells
- invariant [discrete conservation of mass, momentum, energy] EXACT: reproduced to round-off (largest error 4.4e-16), as designed

### sod / gamma_wrong
- reference [Sod shock tube, density L1] FAIL: error does not decrease with resolution (about 0.0605 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [smooth density wave, periodic] PASS: observed order 0.98 (expected 1)
- reference [acoustic wave about rest, periodic] FAIL: error does not decrease with resolution (about 0.425 at the finest level); the error is the same at every resolution, which points to something independent of the step (a jump in the model such as a potential cutoff crossing, a wrong constant, or a reference for a different problem) rather than to the integrator
- reference [acoustic pulse leaving through an open end] FAIL: 0.165 of an outgoing acoustic pulse is still in the domain after it should have left through the open end (limit 0.01): the boundary reflects or the solution is unstable
- invariant [discrete conservation of mass, momentum, energy] FAIL: expected an exact solution to round-off, but the error reaches 0.03 and shrinks at about order -0.00

### sod / nonconservative_momentum
- reference [Sod shock tube, density L1] PASS: observed order 0.43 (expected 0.5)
- reference [smooth density wave, periodic] PASS: observed order 0.98 (expected 1)
- reference [acoustic wave about rest, periodic] PASS: observed order 0.99 (expected 1)
- reference [acoustic pulse leaving through an open end] PASS: after the pulse left through the open end, at most 0.00018 of it remained (limit 0.01) on 50 to 200 cells
- invariant [discrete conservation of mass, momentum, energy] FAIL: expected an exact solution to round-off, but the error reaches 0.0113 and shrinks at about order 0.80

### sod / wave_speed_without_sound
- reference [Sod shock tube, density L1] PASS: observed order 0.59 (expected 0.5)
- reference [smooth density wave, periodic] PASS: observed order 0.99 (expected 1)
- reference [acoustic wave about rest, periodic] FAIL: error does not decrease with resolution (about 1.4e+05 at the finest level)
- reference [acoustic pulse leaving through an open end] FAIL: 58.5 of an outgoing acoustic pulse is still in the domain after it should have left through the open end (limit 0.01): the boundary reflects or the solution is unstable
- invariant [discrete conservation of mass, momentum, energy] EXACT: reproduced to round-off (largest error 4.4e-16), as designed

### sod / last_step_not_clipped
- reference [Sod shock tube, density L1] PASS: observed order 0.63 (expected 0.5)
- reference [smooth density wave, periodic] PASS: observed order 0.98 (expected 1)
- reference [acoustic wave about rest, periodic] PASS: observed order 1.05 (expected 1)
- reference [acoustic pulse leaving through an open end] PASS: after the pulse left through the open end, at most 0.00013 of it remained (limit 0.01) on 50 to 200 cells
- invariant [discrete conservation of mass, momentum, energy] FAIL: expected an exact solution to round-off, but the error reaches 0.00208 and shrinks at about order 1.33

### sod / reflective_boundary
- reference [Sod shock tube, density L1] PASS: observed order 0.63 (expected 0.5)
- reference [smooth density wave, periodic] PASS: observed order 0.98 (expected 1)
- reference [acoustic wave about rest, periodic] PASS: observed order 0.99 (expected 1)
- reference [acoustic pulse leaving through an open end] FAIL: 1 of an outgoing acoustic pulse is still in the domain after it should have left through the open end (limit 0.01): the boundary reflects or the solution is unstable
- invariant [discrete conservation of mass, momentum, energy] EXACT: reproduced to round-off (largest error 4.4e-16), as designed
