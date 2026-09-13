# Simulation workspace

Reserved for future implementation. No simulator, parameters or experimental results are provided yet.

Suggested layout once a method is selected:

- `src/`: model and policy implementation.
- `configs/`: small, versioned scenario configurations.
- `tests/`: deterministic model checks and regression tests.
- `scripts/`: repeatable experiment and analysis entry points.

Agree on the causal mechanism and baselines before choosing a framework. A full robotics stack is not required merely because the application is maritime robotics.

## Candidates to evaluate, not installed dependencies

- [PythonVehicleSimulator](https://github.com/cybergalactic/PythonVehicleSimulator): vessel models and guidance/navigation/control, including an Otter USV model. Potential source for a targeted motion-model check. It does not by itself establish a multi-boat coverage/networking experiment.
- [VRX](https://github.com/osrf/vrx/wiki): a Gazebo-based USV autonomy environment. Potential higher-fidelity option; installation, integration and runtime must be tested before committing to it. Vehicle realism does not automatically validate a wireless channel model.

Descriptions checked against the maintainers' documentation on 11 September 2026. Neither repository has been installed, benchmarked or selected for this project. Check licenses and pin revisions before reuse.

For each candidate, record: original paper, repository/version, license, required environment, time to reproduce one example, parameters exposed, tests, missing components and adaptation effort. Prefer a small reproducible pilot over a long feature comparison.
