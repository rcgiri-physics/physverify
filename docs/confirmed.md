# Confirmed by maintainers

While physverify was tested on public physics code, each suspected defect was checked by a run against a reference from the physics and reported to the project. These are reports where the project's maintainers confirmed the defect or merged a fix (checked 2026-11-14). The link in each row is the source; the one-line summaries are ours.

| Project | What was found | Outcome |
|---|---|---|
| [SymPy](https://github.com/sympy/sympy/issues/30810) | `units`: the astronomical unit, nautical mile and torr differ from their exact definitions | confirmed by a core developer against primary sources |
| [Astropy](https://github.com/astropy/astropy/issues/20681) | the "surface tension" physical type is registered as J m² instead of J/m² | confirmed by a maintainer; fix in progress |
| [PyGMT](https://github.com/GenericMappingTools/pygmt/issues/4960) | `sequence_join` treats any string containing a space as a datetime | fixed ([PR #4961](https://github.com/GenericMappingTools/pygmt/pull/4961)) |
| [Pynite](https://github.com/JWock82/Pynite/issues/353) | `BeamSegY.max_moment` ignores `P_delta` | confirmed by the author; fix planned |
| [EinsteinPy](https://github.com/einsteinpy/einsteinpy/issues/705) | `DeSitter()` puts the scale factor on a spatial coordinate | fixed ([PR #707](https://github.com/einsteinpy/einsteinpy/pull/707)) |
| [findiff](https://github.com/maroba/findiff/issues/119) | `set_accuracy` is ignored after the first call; `3 - Diff(0)` has the wrong sign ([#120](https://github.com/maroba/findiff/issues/120)) | both fixed |
| [TESPy](https://github.com/oemof/tespy/issues/1127) | the pressure term of the incompressible-fluid entropy has the wrong units | fixed |
| [openmmtools](https://github.com/choderalab/openmmtools/issues/822) | the harmonic-oscillator test system reports the wrong standard deviation of its potential | confirmed by a developer |
| [moltemplate](https://github.com/jewettaij/moltemplate/issues/120) | `msifrc2lt.py`: an undefined name in the out-of-plane branch | confirmed by the author |
| [PyAstronomy](https://github.com/sczesla/PyAstronomy/issues/71) | `pyasl.planck` used CGS constants where SI were expected | confirmed and fixed |
| [qmat](https://github.com/Parallel-in-Time/qmat/issues/23) | three Runge-Kutta schemes labelled with a higher order than they have | fixed; qmat now checks its tables with `physverify.butcher` in CI |

Smaller projects whose authors fixed a reported defect include [freepaths](https://github.com/anufrievroman/freepaths/issues/31), [ugropy](https://github.com/ipqa-research/ugropy/issues/46), [phlower](https://github.com/ricosjp/phlower/issues/2), [spin-model-transformers](https://github.com/mcbal/spin-model-transformers/issues/2), [finitevolume2-python](https://github.com/pmocz/finitevolume2-python/issues/3), [mhd-boris](https://github.com/pmocz/mhd-boris/issues/2) and [StatMech_IsingModel](https://github.com/PHYS3934/StatMech_IsingModel/issues/4).

This list shows that the defects were real; it is not a measure of how often physverify finds bugs. Most were found by a test script written for each repository, with physverify running the checks and the sandbox (see [Results on real code](results.md)).
