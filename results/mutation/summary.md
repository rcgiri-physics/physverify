# Mutation score of the benchmark specs

Made by `python -m pvbench.mutation`. Each change is one program-made edit inside the listed functions; NOT RUN changes are on lines that run only when a seeded bug is switched on and are left out of the score.

| Problem | Functions | Changes | Not run | Caught | Survived | Score |
|---|---|---|---|---|---|---|
| projectile | rhs_seeded, range_seeded | 38 | 1 | 31 | 6 | 31/37 |
| pendulum | rhs_seeded | 24 | 0 | 21 | 3 | 21/24 |
| kepler | rhs_seeded | 17 | 0 | 11 | 6 | 11/17 |
| heat1d | solve | 31 | 1 | 22 | 8 | 22/30 |
| sod | solve | 73 | 27 | 37 | 9 | 37/46 |

## Survivors

- projectile.py:94:15: operator / -> *
- projectile.py:94:15: operator * -> /
- projectile.py:94:15: operator * -> /
- projectile.py:158:11: comparison < -> <=
- projectile.py:158:15: constant 100.0 -> 110.00000000000001
- projectile.py:161:12: comparison < -> <=
- pendulum.py:96:13: constant 1.0 -> 1.1
- pendulum.py:97:27: operator * -> /
- pendulum.py:98:16: constant 1.0 -> 1.1
- kepler.py:65:15: operator * -> /
- kepler.py:65:20: constant 1.01 -> 1.1110000000000002
- kepler.py:66:23: constant 2 -> 2.2
- kepler.py:70:23: operator + -> -
- kepler.py:71:21: operator / -> *
- kepler.py:73:14: operator * -> /
- heat1d.py:131:18: constant 0.6 -> 0.66
- heat1d.py:132:38: operator / -> *
- heat1d.py:136:10: operator / -> *
- heat1d.py:136:10: constant 1.0 -> 1.1
- heat1d.py:137:18: constant 1.0 -> 1.1
- heat1d.py:146:28: operator * -> /
- heat1d.py:146:29: operator + -> -
- heat1d.py:146:33: constant 1 -> 1.1
- sod.py:189:18: operator / -> *
- sod.py:189:18: constant 5.0 -> 5.5
- sod.py:189:24: constant 3.0 -> 3.3000000000000003
- sod.py:191:10: operator + -> -
- sod.py:191:31: constant 0.5 -> 0.55
- sod.py:205:25: operator / -> *
- sod.py:207:42: comparison <= -> <
- sod.py:210:16: comparison > -> >=
- sod.py:215:51: constant 0.5 -> 0.55
