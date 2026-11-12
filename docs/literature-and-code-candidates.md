# Literature and code candidates

Working note, 14 September 2026. These are candidate sources and reusable software projects to inspect before deciding the final simulator scope. Do not cite or reuse any item before reading the source and checking its license.

## Most relevant candidates

### Coordination of marine multi-robot systems with communication constraints

- Paper: Antoni Martorell-Torres, Jose Guerrero-Sastre, Gabriel Oliver-Codina, "Coordination of marine multi robot systems with communication constraints", Applied Ocean Research, 2024.
- DOI: https://doi.org/10.1016/j.apor.2023.103848
- Code: https://github.com/martorelltorres/MMRS_stack
- License: GPL-3.0.
- Why it matters: very close to our topic. It uses AUVs exploring the seafloor and an ASV as relay/coordinator, with decisions based on acoustic communication quality.
- Reuse risk: ROS Noetic, COLA2, Ubuntu 20.04, and several robotics dependencies. Strong as a reference and possible architecture inspiration, but probably heavy as the main course simulator.

### Atlas and CARA

- Paper: Razanne Abu-Aisheh, Francesco Bronzino, Lou Salaun, Thomas Watteyne, "CARA: Connectivity-Aware Relay Algorithm for Multi-Robot Expeditions", Sensors, 2022.
- DOI: https://doi.org/10.3390/s22239042
- Code: https://github.com/openwsn-berkeley/Atlas
- Why it matters: 2D exploration and mapping with networked robots, packet delivery ratio, relay placement, and completion-time evaluation. Not marine-specific, but close to the communication-aware exploration mechanism.
- Reuse risk: may need adaptation from indoor/floorplan exploration to seabed coverage. Useful as a simple simulator reference.

### AoI-inspired collaborative information collection for AUV-assisted IoUT

- Paper/code repository: https://github.com/fangzr/AoI-Inspired-Collaborative-Information-Collection
- License: Apache-2.0.
- Language: MATLAB.
- Why it matters: multi-AUV underwater information collection with acoustic-channel calculations, energy consumption, 2D movement over seabed for one AUV type, and vertical motion for another.
- Reuse risk: focuses on Age of Information and queueing rather than cooperative coverage mapping. Good for communication/channel and MATLAB modelling ideas.

## Higher-fidelity simulator candidates

### UUV Simulator

- Paper: Musa Morena Marcusso Manhaes, Sebastian A. Scherer, Martin Voss, Luiz Ricardo Douat, Thomas Rauschenbach, "UUV Simulator: A Gazebo-based package for underwater intervention and multi-robot simulation", OCEANS 2016.
- DOI: https://doi.org/10.1109/OCEANS.2016.7761080
- Code: https://github.com/uuvsimulator/uuv_simulator
- License: Apache-2.0.
- Why it matters: Gazebo/ROS underwater simulator with vehicle dynamics, thrusters, current models, sensors, and multi-robot support.
- Reuse risk: archived/read-only since 2023 and tied to older ROS distributions. Better as a realism reference or optional extension than as the first implementation.

### DAVE Aquatic Virtual Environment

- Paper: Mabel M. Zhang et al., "DAVE Aquatic Virtual Environment: Toward a General Underwater Robotics Simulator", IEEE/OES AUV Symposium, 2022.
- DOI: https://doi.org/10.1109/AUV53081.2022.9965808
- Documentation: https://field-robotics-lab.github.io/dave.doc/
- Why it matters: underwater robotics simulator with bathymetry models, underwater vehicle models, sonar, DVL, currents, and Gazebo support.
- Reuse risk: likely too heavy for the core project unless the mentor explicitly expects a robotics-simulator stack.

### Stonefish

- Paper/code: Patryk Cieslak, "Stonefish: An Advanced Open-Source Simulation Tool Designed for Marine Robotics, With a ROS Interface", OCEANS 2019.
- DOI: https://doi.org/10.1109/OCEANSE.2019.8867434
- Code: https://github.com/patrykcieslak/stonefish
- License: GPL-3.0.
- Why it matters: actively relevant marine robotics simulator with hydrodynamics, underwater rendering, sonar-oriented ecosystem, and ROS integration.
- Reuse risk: C++/ROS/Linux/GPU requirements. Probably too much for the main project, but useful if a realistic AUV extension becomes necessary.

## Initial conclusion

For the course proposal, the strongest position is to cite the close marine multi-robot and AUV planning literature, then start with a controlled Python or MATLAB simulator. We can say that heavier open-source stacks exist and will be inspected, but the first implementation should isolate coordination under intermittent connectivity.

The most promising reuse paths are:

1. Use MMRS_stack as the closest conceptual reference.
2. Use Atlas as inspiration for a lightweight 2D exploration and communication simulator.
3. Use the AoI MATLAB repository for acoustic-channel and underwater information-transfer ideas.
4. Keep UUV Simulator, DAVE, and Stonefish as optional realism extensions.
