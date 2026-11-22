| Problem | Bug | mms | reference | invariant | limit | patch | Predicted by design |
|---|---|---|---|---|---|---|---|
| projectile | (none) | ok | ok | ok | ok | ok | baseline (all should pass) |
| projectile | gravity_sign | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | invariant, limit, mms, patch, reference |
| projectile | linear_drag_missing_mass | FLAGGED | FLAGGED | no | no | FLAGGED | mms, patch, reference |
| projectile | quad_drag_factor_half | FLAGGED | FLAGGED | no | no | FLAGGED | mms, patch, reference |
| projectile | quad_drag_speed_from_vx | FLAGGED | FLAGGED | no | no | FLAGGED | mms, patch, reference |
| projectile | quad_drag_abs_vx | FLAGGED | no | no | no | FLAGGED | mms, patch |
| projectile | landing_no_interp | no | no | no | FLAGGED | no | limit |
| projectile | angle_not_converted | no | no | no | FLAGGED | no | limit |
| projectile | euler_extra_step | no | no | no | no | FLAGGED | patch |
| projectile | euler_instead_of_rk4 | FLAGGED | FLAGGED | FLAGGED | FLAGGED | no | invariant, mms, reference |
| projectile | rk4_weights | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | invariant, mms, patch, reference |
| projectile | rk4_full_step_stage2 | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | mms, patch, reference |
| pendulum | (none) | ok | ok | ok | ok | ok | baseline (all should pass) |
| pendulum | coupling_sign | FLAGGED | FLAGGED | FLAGGED | no | FLAGGED | invariant, mms, patch, reference |
| pendulum | mass_matrix_missing_cos | FLAGGED | FLAGGED | FLAGGED | no | FLAGGED | invariant, mms, patch, reference |
| pendulum | gravity_mass_missing | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | invariant, limit, mms, patch, reference |
| pendulum | rk4_stage4_time | FLAGGED | no | no | no | FLAGGED | mms, patch |
| pendulum | swapped_lengths | FLAGGED | FLAGGED | FLAGGED | no | FLAGGED | invariant, mms, patch, reference |
| pendulum | small_angle_gravity | FLAGGED | FLAGGED | FLAGGED | no | FLAGGED | invariant, mms, patch, reference |
| pendulum | euler_instead_of_rk4 | FLAGGED | FLAGGED | FLAGGED | no | no | invariant, mms, reference |
| pendulum | rk4_weights | FLAGGED | FLAGGED | FLAGGED | no | FLAGGED | invariant, mms, patch, reference |
| pendulum | rk4_full_step_stage2 | FLAGGED | FLAGGED | FLAGGED | no | FLAGGED | mms, patch, reference |
| kepler | (none) | ok | ok | ok | ok | ok | baseline (all should pass) |
| kepler | inverse_r_force | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | invariant, limit, mms, patch, reference |
| kepler | y_force_sign | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | invariant, limit, mms, patch, reference |
| kepler | gm_one_percent | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | invariant, limit, mms, patch, reference |
| kepler | softening_left_on | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | mms, patch, reference |
| kepler | euler_instead_of_rk4 | FLAGGED | FLAGGED | FLAGGED | FLAGGED | no | invariant, mms, reference |
| kepler | rk4_weights | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | invariant, mms, patch, reference |
| kepler | rk4_full_step_stage2 | FLAGGED | FLAGGED | FLAGGED | FLAGGED | FLAGGED | mms, patch, reference |
| heat1d | (none) | ok | ok | n/a | n/a | ok | baseline (all should pass) |
| heat1d | dx_off_by_one | FLAGGED | FLAGGED | n/a | n/a | FLAGGED | mms, patch, reference |
| heat1d | alpha_ignored | FLAGGED | FLAGGED | n/a | n/a | FLAGGED | mms, patch, reference |
| heat1d | extra_time_step | no | no | n/a | n/a | FLAGGED | patch |
| heat1d | unstable_dt | FLAGGED | FLAGGED | n/a | n/a | FLAGGED | mms, patch, reference |
| heat1d | source_time_shift | no | no | n/a | n/a | FLAGGED | patch |
| sod | (none) | n/a | ok | ok | n/a | n/a | baseline (all should pass) |
| sod | gamma_wrong | n/a | FLAGGED | FLAGGED | n/a | n/a | reference |
| sod | nonconservative_momentum | n/a | no | FLAGGED | n/a | n/a | invariant |
| sod | wave_speed_without_sound | n/a | FLAGGED | no | n/a | n/a | reference |
| sod | last_step_not_clipped | n/a | no | FLAGGED | n/a | n/a | invariant |
| sod | reflective_boundary | n/a | FLAGGED | no | n/a | n/a | reference |

Bugs seeded: 37. Flagged by at least one check: 37. Missed by all: 0.
Of the 37 flagged: 37 by at least one FAIL, 0 only by INCONCLUSIVE or ERROR.
Bug-free baselines with a false alarm: 0 of 5.
Bugs flagged per family: mms 27, reference 28, invariant 22, limit 14, patch 27.
Bugs flagged by that family alone: mms 0, reference 2, invariant 2, limit 2, patch 3.
