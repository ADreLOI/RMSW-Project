# Proposal review and implementation shortlist

Reviewed 30 September 2026. This is a working review for Andrea and Ettore, not a submitted research result.

## Bottom line

Keep the original direction: **does a short-horizon outage warning, used for advance task reservation, improve online two-USV survey coordination relative to reacting after disconnection?** The study is about the usefulness and cost of a coordination intervention, not inventing a better predictor, optimizing every layer of a maritime system, or demonstrating a realistic ship simulator.

The proposal is coherent enough to develop, but its claims and implementation contract need the clarifications below. There is no verified basis for saying that nobody has studied prediction-aware multi-robot coordination. A course project can still contribute a carefully bounded, reproducible comparison. Do not claim novelty beyond what the literature actually establishes.

The [Research Plan assignment](https://canvas.kth.se/courses/63857/assignments/393684) explicitly allows relevant proposal text to be reused without rephrasing. The modular plan therefore retains the title, author block, original introduction, background paragraphs, main question, design paragraphs, source descriptions, procedure paragraphs, and analysis paragraphs wherever compatible with the 2026 headings.

## Evidence and limits of this review

- Current Overleaf proposal: [II2202 - Proposal](https://www.overleaf.com/project/6a92bdbdf9d3e9e6f2331706), downloaded unchanged before review.
- Current Research Plan brief and [Canvas proposal feedback](https://canvas.kth.se/courses/63857/assignments/393680), including the mentor comments supplied in this conversation.
- Available local meeting-review notes from the earlier mentor recording, including basic-case-first and accessible-code advice. The newer uploaded meeting MP4 has **not been independently transcribed/replayed in this pass**; do not attribute the new implementation defaults to that recording.
- Publisher/author/maintainer pages linked below. Abstracts and repository documentation establish existence and scope, not a full reproduction or an exhaustive systematic review.
- Local simulator source and its actual unit-test/sanity-check output.

## Full section-by-section review

| Proposal location | Keep | Clarify in the research plan | Why / status |
| --- | --- | --- | --- |
| Title and opening | Two-USV seabed-survey coverage; direct boat-to-boat radio; 2D scope | Explain that “seabed survey” motivates the coverage task, not a validated seabed/sea-state simulation | Mentor 1.1 and 2.1; no topic change needed |
| 1.1 Background | Existing CPP and communication-aware coordination sources | Add concrete cross-usecase perspectives, offshore wind-farm survey application, and task-level marine difficulties | Explicit mentor request |
| 1.1 Related work | Yang, Bramblett/Bezzo, Gordon and other existing references | Distinguish coverage planning, predicting other robots, radio-map planning, and predicting an outage | Necessary to avoid an unsupported gap claim |
| 1.2 Problem/aim/question | Original main question and predictive-versus-reactive comparison | Split action effect, forecast usefulness, and cost/trade-off questions; retain the main question as the umbrella | Explicit mentor request; not a new forecasting project |
| 1.2 Hypothesis | Conditional expectation of benefit | Do not promise less redundant coverage merely because links fail; robust disjoint assignments may make redundancy zero | Methodological correction |
| 1.2 Preallocation | Fixed partition as a zero-online-message reference | Explain when equal progress makes it sufficient, and why slowdown may motivate dynamic rebalancing | Explicit mentor request; preallocation is not intrinsically wrong |
| 2.1 Design | Controlled, quantitative, paired 2D study; fade persistence; motion/channel scope | Separate implementation correctness from physical realism; first demonstrate the simplest useful case | Mentor basic-case-first advice |
| 2.2 Sources/materials | Synthetic configurations/logs, no participants, true versus local state, code provenance | Put procedural forecast definitions and metric definitions in 2.3/2.4; add numerical settings with provenance | Explicit mentor 2.2 comment and implementability requirement |
| 2.3 Procedure | Basic coverage → common allocator/reactive → predictor → pilot → paired runs | Specify tasks, allocator, successful exchange, failed exchange, reservation size, event order, and permitted observations | Needed to implement the proposed comparison |
| 2.4 Analysis | Restricted mean completion time, common administrative timeout, paired bootstrap, costs, null outcomes | Define the estimand and event matching; add host computation and conditional energy/lifetime reasoning | Explicit mentor 2.4 request |
| Plan section 3 | Existing Andrea/Ettore ownership split | Dependencies, milestones, scope fallback, risks and who reproduces tests | Required by the new assignment |

## Changes required by the mentor versus choices proposed here

The mentor requested better references/application framing, clearer questions, benchmark provenance, justification of prediction versus preallocation, an explicit model/source rationale, a sources-focused 2.2, and resource trade-offs. The written feedback did **not** prescribe a particular grid size, signal threshold, predictor, number of seeds, Python library, queue length, or consensus protocol.

The following additions are proposed author choices and are labelled that way in the plan:

1. A concrete synthetic starting configuration, to avoid “parameters will be chosen later”.
2. A safe atomic exchange abstraction, so one failed message cannot silently give a task two owners.
3. A common greedy projected-finish-time allocator inspired by auction allocation.
4. A longer-backlog-without-prediction ablation. Its purpose is to ask whether forecast timing helps beyond having more reserved work.
5. An explicit residual-plus-relative-motion trend rule, consistent with the original signal/relative-motion idea but **not mandated by the professor**.
6. A persistence warning reference and an optional oracle diagnostic.
7. Ten pilot seeds and initially thirty evaluation seeds per condition.

Review these together before implementation. If you prefer the simplest raw-RSS trend rather than the residual formulation, change its definition consistently in the procedure, configuration and code. Do not add distance-loss change twice to a raw RSS slope, since it can already contain the effect of separation.

## The three most important validity checks

### 1. Outage persistence is not onset predictability

A two-state Markov fade can produce longer outages without any observable precursor before an onset. Do not let the predictor see the hidden fade state or future positions. A negative result under abrupt fades is meaningful; do not alter the generator until prediction “wins”. Separate distance-driven warnings from fade-driven outages in diagnostics.

### 2. Reservation is not automatically forecasting benefit

If prediction-aware coordination uses a longer queue than the reactive strategy, a gain might be caused by backlog size alone. Keep the same allocator for every online policy and compare the predictive switch against an always-long queue. Account for extra bytes/compute and for the cost of work locked to a slow robot.

### 3. Define the stale-state mechanism before claiming duplicated work

With disjoint ownership and no unilateral stealing, outages mainly cause idle time and missed rebalancing opportunities, not necessarily duplicate task execution. Sensing overlap can still occur while travelling. Log both and be willing to report zero redundant observations. A deliberately unsafe reactive policy would not be a credible benchmark.

## Verified public code and algorithms

None of the external repositories below has been installed or reproduced during this review. “Verified” means the repository/paper and stated capability are inspectable at the linked primary source. Before actual reuse, pin a commit, preserve licence notices, reproduce a small example, and document the modification. Do not describe a repository as your own algorithm.

| Priority | Candidate and provenance | What can be reused | Licence/environment verified | Fit and limitation |
| --- | --- | --- | --- | --- |
| Core coverage lead | [PythonRobotics](https://github.com/AtsushiSakai/PythonRobotics), [grid-sweep module](https://github.com/AtsushiSakai/PythonRobotics/blob/master/PathPlanning/GridBasedSweepCPP/grid_based_sweep_coverage_path_planner.py), [author paper](https://arxiv.org/abs/1808.10703) | Grid-sweep path generation and comparison tests | [MIT licence](https://github.com/AtsushiSakai/PythonRobotics/blob/master/LICENSE); Python, NumPy/Matplotlib and local helpers for this component | Closest lightweight coverage component. No multi-USV allocation, packet protocol, or marine dynamics. The existing rectangular sweep may already be sufficient; reuse need not mean replacing working code. |
| Published allocation reference | [MIT ACL CBBA page](https://acl.mit.edu/projects/consensus-based-bundle-algorithm), Choi/Brunet/How, *IEEE TRO* 25(4), 912–926 (2009), DOI [10.1109/TRO.2009.2022423](https://doi.org/10.1109/TRO.2009.2022423) | Auction/bundle building and conflict-resolution ideas; original MATLAB software is linked from the lab page | Original downloadable package/licence not independently inspected here | Strong provenance for allocation. CBBA's repeated communication and guarantees are not an atomic-session greedy assignment. Cite the original paper, document simplification, do not inherit its guarantees. |
| Python implementation candidate | [zehuilu/CBBA-Python](https://github.com/zehuilu/CBBA-Python) | Task-agent scoring, ordered bundles, example use of CBBA.solve | [MIT licence](https://raw.githubusercontent.com/zehuilu/CBBA-Python/main/LICENSE); README lists Python >=3.7, NumPy, Matplotlib | Third-party implementation, not the original authors' code. Time-window/task reward choices and network consensus need adaptation to cell surveys. If selected, use the same adapted allocator for every online policy. |
| Motion-fidelity extension | [Fossen's PythonVehicleSimulator](https://github.com/cybergalactic/PythonVehicleSimulator) | Otter twin-propeller USV motion/control model for a targeted sensitivity check | Maintainer page lists MIT; NumPy, Matplotlib, tests | Marine dynamics are genuinely relevant here, but it does not provide the coverage/networking experiment. Add only after the basic allocation experiment works. |
| Closest existing marine architecture | [Martorell-Torres' MMRS_stack](https://github.com/martorelltorres/MMRS_stack) and the [2024 paper](https://www.sciencedirect.com/science/article/pii/S0141118723003899) | Communication-quality-aware coordination and task-allocation architecture | GPL-3.0; Ubuntu20.04, ROS Noetic, COLA2, multiple submodules | AUV explorers plus an ASV coordinator using acoustic links and data latency. Not a drop-in two-surface-boat radio survey. Useful reading; heavy core dependency. Check each submodule's licence before reuse. |
| Networking/exploration reference | [openwsn-berkeley/Atlas](https://github.com/openwsn-berkeley/Atlas), connected to the CARA research line | Inspectable Python exploration/wireless simulation modules, RunSim.py and tests | No repository-level licence was visible in the checked root; do not assume copying permission | Strong mechanism lead, terrestrial/floorplan setting. Inspect/read for understanding; clarify licensing before copying code. Do not confuse it with a ready-made maritime simulator. |
| Not currently an executable lead | [mit-acl/CACBBA](https://github.com/mit-acl/CACBBA) | Communication-aware CBBA research pointer | Checked root contains only README.md, one commit; no executable implementation/licence visible | Despite its README calling it an official implementation, it is not currently a usable code dependency. Do not build the workplan around it. |

### Recommended minimum reuse path

Keep the local grid-sweep sanity baseline. Use PythonRobotics as a coverage cross-check or adapt only the relevant module if it adds value. Read the original CBAA/CBBA description, then implement and test a clearly labelled simplified allocator; time-box reproducing CBBA-Python before making it a dependency. Keep Fossen's Otter model as one later motion-fidelity check, not a requirement for tomorrow's plan.

This gives traceable algorithms without making ROS/Gazebo setup the project. The choice is based on the scoped coordination question and integration burden, not on a claim that high-fidelity simulation is unimportant.

## Verified paper reading shortlist

| Order | Paper/source | What to extract for this study | Do not claim |
| --- | --- | --- | --- |
| 1 | Yang et al. (2023), [Cooperative survey of seabed ROIs using multiple USVs with coverage path planning](https://www.sciencedirect.com/science/article/pii/S0029801822025914), DOI10.1016/j.oceaneng.2022.113308 | Offshore wind-farm motivation; coverage geometry, decomposition, turns, travel between subregions | Their coverage optimizer evaluates our radio-outage reservation policy |
| 2 | Bramblett & Bezzo (2023), [Epistemic planning](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2023.1149439/full), DOI10.3389/frobt.2023.1149439 | What disconnected robots know; coverage/task allocation and communication restrictions | Prediction-aware coordination is an unexplored field |
| 3 | Gong et al. (2022), [Resource-aware synchronized path following](https://www.sciencedirect.com/science/article/pii/S0967066122000752), DOI10.1016/j.conengprac.2022.105184 | Event/self-triggered communication and predicted path variables; resource metrics | Path-variable prediction is a predictor of radio outages, or power is calibrated for our boats |
| 4 | Sousa et al. (2018), [An Aquatic Mobile Sensing USV Swarm](https://pmc.ncbi.nlm.nih.gov/articles/PMC6210362/), DOI10.3390/s18103440 | Practical USV sensing/networking, RSSI-based link-quality estimation, routing overhead | Their routing evaluation establishes our coverage-reservation benefit |
| 5 | Gordon et al. (2026), [author publication record](https://www.tkn.tu-berlin.de/bib/gordon2026communication-aware/), DOI10.1109/INFOCOM59046.2026.11571354 | Current radio-map-to-planning approach and risk/cost reasoning | Radio-map motion planning is the same task allocation benchmark |
| 6 | Sinay et al. (2017), [Maintaining Communication in Multi-Robot Tree Coverage](https://www.ijcai.org/proceedings/2017/630), DOI10.24963/ijcai.2017/630 | A contrasting nonmarine coverage/connectivity use case | A continuously connected tree algorithm directly matches rectangular intermittent survey |

For each full paper, record information available to each robot, assumptions, comparator, model parameters/provenance, repeated runs, metrics, limitations and released code. The newer paper is not automatically the best benchmark; comparability matters.

## Current local implementation: actual verification

The existing code in RMSW-Project/RMSW-Project/simulation currently enumerates disjoint column-wise boustrophedon paths and counts coverage. It does **not** simulate physical seconds, temporary slowdowns, a radio channel, messages, ownership transfer, forecasts, energy or experiments.

Checked in this review:

- All **5 unit tests passed**.
- A 12x8 grid with **2 robots** covered 96 cells, with 48 steps per robot, zero redundant observations and zero messages.
- Always-up and always-down link arguments gave identical results, as intended for the communication-independent control.

This is an implementation sanity check, not evidence supporting a research hypothesis. Preserve it as a regression test while adding finite-speed execution and logging. The README's example with 3 robots is a generic test example; the research core remains 2 robots.

## Minimum implementation gates

1. Reproduce existing fixed-partition tests; define units and cell-entry sensing.
2. Implement finite-speed motion/turning and policy-independent slowdown; verify deterministic completion by hand.
3. Implement the common allocator and versioned exchange semantics. Test failed sessions, budget exhaustion and ownership invariants.
4. Show one hand-checked trace where a queue empties or rebalancing is delayed during an outage. If the action changes nothing, diagnose that before running a large experiment.
5. Add non-predictive long-backlog and predictive switch with exactly the same allocator.
6. Test the predictor on fixed traces with permitted observations only; preserve pilot/test separation.
7. Freeze settings; run paired core seeds; retain timeouts and errors; regenerate all figures from raw logs.
8. Add one optional motion or distance-loss sensitivity only if the core is complete.

## Author decisions before approving the plan

- Agree whether the basic atomic allocation session is an acceptable abstraction. More realistic partial message delivery needs a recovery protocol and is an extension, not a silent assumption.
- Agree on the provisional grid, time scale, queue sizes and forecast rule. The defaults are synthetic and not maritime measurements.
- Confirm with the mentor whether measured host computation plus conditional energy/break-even reasoning satisfies the lifetime discussion, or whether a particular hardware power model is expected.
- Check later official report/presentation deadlines; only the Research Plan deadline (1 October2026, 19:00) is verified here. Later workplan dates are internal targets.
- Finish the required earlier quizzes and author the final submitted wording.

The [course AI guideline](https://canvas.kth.se/courses/63857/pages/guideline-for-using-generative-ai-tools), checked live, explicitly prohibits autogenerated submission text while allowing feedback and verified programming/data help and requiring disclosure. This assisted document and the drafted plan are working materials; disclosure alone does not turn autogenerated paragraphs into permitted submission text.

## Project organization and boundaries

Root II2202-research-plan.tex is now only the input graph. Research_Plan contains preamble, frontmatter, numbered sections, references and the same customized IEEE bibliography style used in the proposal. The article uses sections/subsections rather than book chapters; separate files do not force new pages because input is used instead of include.

The existing proposal project was not edited. Original template files were retained, and both source projects were backed up locally before changes. No GitHub commit, push, remote branch change, Overleaf/GitHub sync, or Canvas submission was performed.
