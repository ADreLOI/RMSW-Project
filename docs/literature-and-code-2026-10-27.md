# Literature and public code: verified matrix (27 October 2026)

This note supersedes the 14 September candidate list for planning purposes; the earlier file is kept unchanged. It answers the question from the 27 October meeting: which published papers and public repositories can anchor the simulator, provide comparable data or algorithms, and justify why the model is credible.

**How items were checked.** Bibliographic metadata and citation counts come from the Crossref API (`is-referenced-by-count`, queried 2026-10-27). Crossref counts are lower than Google Scholar, but they are reproducible. Repository licences and contents were checked on the GitHub page. "Read" means only that the abstract or README was inspected. Before citing a claim, both authors still have to read the relevant section of the full paper.

## 1. What public code exists, and what we can honestly do with it

| Source | Code / data | Licence | Closeness to our question | Use in this project |
|---|---|---|---|---|
| Tan et al., *IR²: Implicit Rendezvous for Robotic Exploration Teams under Sparse Intermittent Connectivity*, IROS 2024, doi:10.1109/IROS58592.2024.10801761 (15 cites) | [marmotlab/IR2-Multi-Robot-RL-Exploration](https://github.com/marmotlab/IR2-Multi-Robot-RL-Exploration), Python/PyTorch, trained model | Apache-2.0 | Robots learn when to disconnect and reconnect under line-of-sight signal limits; ground robots, not boats | Related work for E1 recovery. Our fixed meeting point is the simplest non-learned version of the rendezvous behaviour they learn. Not reproduced. |
| da Silva, Chaimowicz, Silva, Hsieh, *Communication-Constrained Multi-Robot Exploration with Intermittent Rendezvous*, IROS 2024, doi:10.1109/IROS58592.2024.10802343 (11); da Silva & Chaimowicz, ICAR 2025, doi:10.1109/ICAR65334.2025.11338679 | [ROS-Noetic-Multi-robot-Sandbox](https://github.com/multirobotplayground/ROS-Noetic-Multi-robot-Sandbox) | GPL-3.0 | Planned rendezvous schedules (job-shop / MILP) for exploration with intermittent communication | Main literature anchor for the E1 design choice. ROS Noetic + Gazebo stack is too heavy to port. |
| Martorell-Torres et al., Applied Ocean Research 2024, doi:10.1016/j.apor.2023.103848 (already cited) | [MMRS_stack](https://github.com/martorelltorres/MMRS_stack) | GPL-3.0 | Marine team, acoustic link quality drives coordination | Closest marine reference. Not adopted: ROS/COLA2 dependencies. |
| Abu-Aisheh et al., CARA, Sensors 2022 (already cited) | [openwsn-berkeley/Atlas](https://github.com/openwsn-berkeley/Atlas) | see repo | 2D exploration with packet delivery and relays | Reference for lightweight 2D comms-aware simulation. |
| Sakai et al., PythonRobotics, arXiv:1808.10703 (already cited) | [GridBasedSweepCPP](https://github.com/AtsushiSakai/PythonRobotics/tree/master/PathPlanning/GridBasedSweepCPP) | MIT | Grid boustrophedon coverage | Our S1 sweep has a closed-form check instead (Section 3); optional cross-check. |
| Mier, Valente, de Bruin, *Fields2Cover*, IEEE RA-L 8(4) 2023, doi:10.1109/LRA.2023.3248439 | [Fields2Cover](https://github.com/Fields2Cover/Fields2Cover), C++17 + `pip install fields2cover` | BSD-3-Clause | Benchmarking framework for coverage path planning (agricultural) | Candidate for a coverage-planner cross-check. Its build dependencies (GDAL, OR-tools) are heavy. |
| Torroba, Sprague, Folkesson, IEEE RA-L 2022, doi:10.1109/LRA.2022.3182807 (16); Kiessling et al., arXiv:2410.15720 (2024), KTH | No public repository found; the survey dataset is described in the paper (Hugin AUV, Kongsberg EM2040, ~4 M beams) | – | Probabilistic bathymetric maps; informative planning with hardware-in-the-loop on an embedded platform | KTH-local anchor for map accuracy and for hardware-constrained planning. Contacting the SMaRC group for data is a possible follow-up. |
| Binney, Krause, Sukhatme, ICRA 2010 | Code released online according to the paper (Python/NumPy) | not checked | GP informative path planning for ocean gliders | Background on map uncertainty versus path choice. Not used. |

**Conclusion for the report.** No public repository combines (a) multi-USV seabed coverage, (b) an intermittent boat-to-boat radio link and (c) online task reallocation. Each component has a published, inspectable reference: rendezvous under intermittent connectivity (IR², da Silva et al.), marine coordination (MMRS_stack), coverage (PythonRobotics, Fields2Cover) and bathymetric mapping (Torroba et al.). The simulator's credibility should therefore rest on four things:

1. model forms taken from these sources (log-distance path loss, Gilbert burst channel, boustrophedon coverage, IHO S-44 uncertainty);
2. closed-form and hand-worked checks;
3. independent reconstruction of every log;
4. explicitly bounded claims.

Do not claim we "reproduced" any of these systems.

## 2. Recent, well-cited papers by theme

### Multi-USV bathymetric / seabed survey planning
- L. Zhao, Y. Bai, J. K. Paik, "Optimal coverage path planning for USV-assisted coastal bathymetric survey: Models, solutions, and lake trials," *Ocean Engineering*, 2024, doi:10.1016/j.oceaneng.2024.116921 (53 cites). Field-validated CPP for survey USVs.
- L. Zhao, Y. Bai, "Energy efficient coverage path planning for USV-assisted inland bathymetry under current effects," *Ocean Engineering*, 2024, doi:10.1016/j.oceaneng.2024.117910 (29). Directly relevant to the cost/efficiency trade-off.
- L. Zhao, Y. Bai, "Joint-optimized coverage path planning framework for USV-assisted offshore bathymetric mapping," *Knowledge-Based Systems*, 2024, doi:10.1016/j.knosys.2024.112449 (23).
- T. Wilson, S. B. Williams, "Adaptive path planning for depth-constrained bathymetric mapping with an autonomous surface vessel," *J. Field Robotics*, 2017, doi:10.1002/rob.21718 (35).
- I. Torroba, N. Bore, J. Folkesson, "Towards autonomous industrial-scale bathymetric surveying," IROS 2019, doi:10.1109/IROS40897.2019.8968241 (26). KTH.
- Z. Liu et al., "Unmanned surface vehicles: An overview of developments and challenges," *Annual Reviews in Control*, 2016, doi:10.1016/j.arcontrol.2016.04.018 (1178). General USV background.

### Communication-restricted multi-robot coordination
- J. Gielis, A. Shankar, A. Prorok, "A critical review of communications in multi-robot systems," *Current Robotics Reports*, 2022, doi:10.1007/s43154-022-00090-9 (159).
- F. Amigoni, J. Banfi, N. Basilico, "Multirobot exploration of communication-restricted environments: A survey," *IEEE Intelligent Systems*, 2017, doi:10.1109/MIS.2017.4531226 (129).
- G. Hollinger, S. Singh, "Multi-robot coordination with periodic connectivity," ICRA 2010, doi:10.1109/ROBOT.2010.5509175 (69). Classic basis for periodic regrouping.
- S. Raja, G. Habibi, J. P. How, "Communication-aware consensus-based decentralized task allocation in communication constrained environments," *IEEE Access*, 2022, doi:10.1109/ACCESS.2021.3138857 (37). Extends CBBA (already cited) to limited links.
- Y. Mostofi, "Communication-aware motion planning in fading environments," ICRA 2008, doi:10.1109/ROBOT.2008.4543693 (29).

### Link-quality prediction: classical versus learned (predictor comparison, E2)
- G. Cerar et al., "Machine learning for wireless link quality estimation: A survey," *IEEE Communications Surveys & Tutorials*, 2021, doi:10.1109/COMST.2021.3053615 (84). The main reference for comparing statistical and ML estimators.
- R. Parasuraman, B.-C. Min, P. Ögren, "Rapid prediction of network quality in mobile robots," *Ad Hoc Networks*, 2023, doi:10.1016/j.adhoc.2022.103014 (8). Path-loss model + variogram + Kalman filter, compared with GP regression; KTH co-author. Directly motivates our Kalman comparator.
- Y. Kanto, K. Watabe, "Wireless link quality estimation using LSTM model," NOMS 2024, doi:10.1109/NOMS59830.2024.10575638 (12). The learned end of the spectrum. We did not implement an LSTM: it needs a deep-learning runtime and does not fit an MCU budget without quantisation. Our MLP stands in as the small learned model.
- S. Sinha et al., "Native AI-based hybrid deep learning for wireless link quality prediction in NTN waterside scenarios," *ICT Express*, 2026, doi:10.1016/j.icte.2025.10.001 (5). Maritime/riverside Wi-Fi and LoRa RSSI.

### Maritime radio channel (justifies the log-distance + burst abstraction)
- B. Yamamoto et al., "Received signal strength indication (RSSI) of 2.4 GHz and 5 GHz WLAN systems projected over land and sea for near-shore maritime robot operations," *J. Mar. Sci. Eng.* 7(9):290, 2019, doi:10.3390/jmse7090290 (24). The closest measured setting to ours: two-ray fits line-of-sight large-scale loss, and there is a mean change of about 10 dB going from land to sea. Use it to discuss our 0/−10 dB offsets qualitatively. It does not calibrate them.
- F. Li et al., "Ship-to-ship maritime wireless channel modeling under various sea state conditions based on REL model," *Frontiers in Marine Science*, 2023, doi:10.3389/fmars.2023.1134286 (21). Sea-state-dependent shadow fading.
- Y.-M. Le Roux et al., "Experimental measurements of propagation characteristics for maritime radio links," ITST 2009, doi:10.1109/ITST.2009.5399326 (16).

### Map accuracy and survey standards (E3)
- International Hydrographic Organization, *S-44 Standards for Hydrographic Surveys*, Edition 6.0.0, 2020. Supplies the TVU form √(a²+(b·d)²). Order 1a uses a = 0.5 m, b = 0.013. Verify these against the published table before quoting.

### Hardware and compute cost (hardware projection)
- C. Niu, D. Tarapore, K.-P. Zauner, "Depth estimation on embedded computers for robot swarms in forest," arXiv:2012.02907, 2020. Reports about 3.4 W for a Raspberry Pi 4 and 10 W for a Jetson Nano; used only for the board-power assumption.
- MCU clocks and RAM come from the ST STM32F407 and STM32H743 datasheets. Cycle-per-operation ranges are our stated assumptions (see `hardware.py`).

## 3. Model-to-literature checks that strengthen credibility

- **Coverage (S1).** Closed form: each boat sweeps 10 columns × 12 rows, which is 119 edges of 20 m (10 s each) plus 9 column switches with 2 turns × 5 s each. That gives 1190 + 90 = 1280 s and 2 × 2380 = 4760 m. Both match every frozen S1 run without slowdown (`condition-summary.csv`).
- **Radio range.** With P0 = −40 dBm at 1 m, n = 2 and threshold −90 dBm, clear-state range is 10^(50/20) ≈ 316 m. The −10 dB fade state reduces it to 100 m. The grid diagonal is 466 m. Yamamoto et al. report a similar order of magnitude for near-shore 2.4 GHz WLAN, and the faded/clear gap matches their reported land-to-sea delta. These are design choices made plausible by measurements, not a calibration.
- **Burst channel.** The Gilbert two-state process is the textbook burst model (Gilbert 1960, already cited). The pilot fade sequences give pooled transition estimates (p_CF ≈ 0.06, p_FC ≈ 0.29), consistent with the configured q = 0.2 and L ∈ {2, 5, 10}.
