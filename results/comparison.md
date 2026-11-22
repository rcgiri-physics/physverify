| Strategy | Bugs caught | Missed | False alarms on baselines | Runtime (s) |
|---|---|---|---|---|
| plain tests | 27 of 37 | 10 | 0 of 5 | 7.3 |
| reference only | 28 of 37 | 9 | 0 of 5 | 13.5 |
| convergence only | 27 of 37 | 10 | 0 of 5 | 16.4 |
| full suite | 37 of 37 | 0 | 0 of 5 | 33.1 |

| Problem | Bug | plain tests | reference only | convergence only | full suite |
|---|---|---|---|---|---|
| projectile | gravity_sign | caught | caught | caught | caught |
| projectile | linear_drag_missing_mass | caught | caught | caught | caught |
| projectile | quad_drag_factor_half | caught | caught | caught | caught |
| projectile | quad_drag_speed_from_vx | caught | caught | caught | caught |
| projectile | quad_drag_abs_vx | **missed** | **missed** | caught | caught |
| projectile | landing_no_interp | **missed** | **missed** | **missed** | caught |
| projectile | angle_not_converted | caught | **missed** | **missed** | caught |
| projectile | euler_extra_step | caught | **missed** | **missed** | caught |
| projectile | euler_instead_of_rk4 | caught | caught | caught | caught |
| projectile | rk4_weights | caught | caught | caught | caught |
| projectile | rk4_full_step_stage2 | caught | caught | caught | caught |
| pendulum | coupling_sign | caught | caught | caught | caught |
| pendulum | mass_matrix_missing_cos | caught | caught | caught | caught |
| pendulum | gravity_mass_missing | caught | caught | caught | caught |
| pendulum | rk4_stage4_time | **missed** | **missed** | caught | caught |
| pendulum | swapped_lengths | caught | caught | caught | caught |
| pendulum | small_angle_gravity | caught | caught | caught | caught |
| pendulum | euler_instead_of_rk4 | caught | caught | caught | caught |
| pendulum | rk4_weights | caught | caught | caught | caught |
| pendulum | rk4_full_step_stage2 | caught | caught | caught | caught |
| kepler | inverse_r_force | caught | caught | caught | caught |
| kepler | y_force_sign | caught | caught | caught | caught |
| kepler | gm_one_percent | caught | caught | caught | caught |
| kepler | softening_left_on | **missed** | caught | caught | caught |
| kepler | euler_instead_of_rk4 | caught | caught | caught | caught |
| kepler | rk4_weights | caught | caught | caught | caught |
| kepler | rk4_full_step_stage2 | caught | caught | caught | caught |
| heat1d | dx_off_by_one | caught | caught | caught | caught |
| heat1d | alpha_ignored | caught | caught | caught | caught |
| heat1d | extra_time_step | **missed** | **missed** | **missed** | caught |
| heat1d | unstable_dt | caught | caught | caught | caught |
| heat1d | source_time_shift | **missed** | **missed** | **missed** | caught |
| sod | gamma_wrong | caught | caught | **missed** | caught |
| sod | nonconservative_momentum | **missed** | **missed** | **missed** | caught |
| sod | wave_speed_without_sound | **missed** | caught | **missed** | caught |
| sod | last_step_not_clipped | **missed** | **missed** | **missed** | caught |
| sod | reflective_boundary | **missed** | caught | **missed** | caught |

Runtimes depend on the machine; the other columns do not (the checks are deterministic).
