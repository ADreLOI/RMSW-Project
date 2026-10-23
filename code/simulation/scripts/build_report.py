"""Assemble a reviewable report draft using the assigned 2026 LaTeX template."""
from pathlib import Path
import csv
import json
import shutil

ROOT=Path(__file__).resolve().parents[3]
PAPER=ROOT/'paper'/'Final_Report'
RESULTS=ROOT/'code'/'simulation'/'results'/'core'
sections=PAPER/'sections'; sections.mkdir(parents=True,exist_ok=True)

def write(name,text): (PAPER/name).write_text(text.strip()+'\n',encoding='utf-8')

template=(ROOT/'paper'/'professor-template-2026'/'II2202-report.tex').read_text(encoding='utf-8')
preamble=template.split('\\begin{document}')[0]
preamble=preamble.replace(r'\documentclass[11pt,a4paper]{article}','')
preamble=preamble.replace('{sourcesanspro}','{sourcesans}') # Current name, same template font family.
preamble=preamble.replace(r'\selectfont\bfseries}w',r'\selectfont\bfseries}')
preamble=preamble.replace('Period X','Periods 1--2').replace('Final report template','Final report').replace('Insert date','October 23, 2026')
preamble += r'''
\usepackage{fontawesome5,amsmath,booktabs,tabularx,array,enumitem,graphicx,needspace}
\newcolumntype{Y}{>{\raggedright\arraybackslash}X}
\setlist[enumerate]{leftmargin=1.8em,itemsep=3pt,topsep=3pt}
\emergencystretch=3em
'''
write('preamble.tex',preamble)
write('main.tex',r'''
\documentclass[11pt,a4paper]{article}
\input{preamble}
\begin{document}
\input{frontmatter}
\clearpage
\input{sections/01_introduction}
\input{sections/02_method}
\input{sections/03_results}
\input{sections/04_discussion}
\input{sections/05_conclusion}
\clearpage
\bibliographystyle{myIEEEtran}
\bibliography{references}
\clearpage
\appendix
\input{sections/appendix}
\end{document}
''')
shutil.copy2(ROOT/'paper'/'research-plan'/'references'/'references.bib',PAPER/'references.bib')
shutil.copy2(ROOT/'paper'/'professor-template-2026'/'myIEEEtran.bst',PAPER/'myIEEEtran.bst')
write('frontmatter.tex',r'''
\reporttitle{Prediction-Aware Coordination for Two-USV Seabed Survey Coverage under Intermittent Connectivity}
\unnumberedheading{Authors}
\noindent\begin{minipage}[t]{0.48\linewidth}\centering
\textbf{Andrea Lo Iacono}\\\texttt{andli2@kth.se}\\
\href{https://github.com/ADreLOI}{\faGithubSquare\hspace{0.13cm}ADreLOI}
\end{minipage}\hfill
\begin{minipage}[t]{0.48\linewidth}\centering
\textbf{Ettore Mugisha Cirillo}\\\texttt{emcir@kth.se}\\
\href{https://github.com/EccirilloM}{\faGithubSquare\hspace{0.13cm}EccirilloM}
\end{minipage}
\begin{mdframed}[linecolor=guidancetext,linewidth=0.5pt,roundcorner=3pt]
\centering\href{https://github.com/ADreLOI/RMSW-Project}{\faGithubSquare\hspace{0.15cm}Project code, paper, configurations, and reproducibility instructions}
\end{mdframed}
\unnumberedheading{Abstract}
We implemented a controlled two-dimensional simulation of two unmanned surface vehicles surveying a known grid while coordinating over a synthetic intermittent radio link. The study compares fixed partitioning, reactive short queues, an always-long queue, and trend- or persistence-triggered task reservation. Ten pilot seeds selected warning margins using fixed-route replay; 30 separate evaluation seeds per condition produced 900 paired mission runs. All evaluation logs were checked against reconstructed coverage, travel, communication, and information-gap metrics. Fixed partitioning completed every run. Reactive short queues completed none because the modeled boats could exhaust work outside communication range. The predictive variants completed most runs, but the trend variant showed no consistent advantage over an always-long queue or persistence. Held-out warning F1 was approximately 0.175 for both predictors. Thus, these settings support a queue-reservation and reconnection explanation rather than a claim that the trend forecast improves surveying. Conclusions concern this synthetic model; they do not establish maritime map accuracy, energy savings, or vessel safety.
\begin{guidancebox}
Working draft with generated experiment results. Both authors must independently review the implementation, sources, analysis, and interpretation before submission. Main-body limit: ten pages, excluding this cover, references, and appendices.
\end{guidancebox}
''')
write('sections/01_introduction.tex',r'''
\section{Introduction}
\subsection{Background and Rationale}
Cooperative survey coverage divides an area among vehicles so they can observe it in parallel. Coverage path planning includes marine applications, but coverage of an ideal grid does not by itself establish bathymetric reconstruction quality \cite{galceran2013coverage,yang2023cooperative}. Marine coordination also connects communication quality with task allocation \cite{martorell2024coordination}. A fixed partition is a useful reference when workloads and progress are balanced. Online reassignment may become useful after an unexpected slowdown, provided the vehicles can exchange current coverage and task state.

Our motivating problem is whether reserving more work before a predicted outage improves a two-vehicle survey. Prediction may help a vehicle avoid exhausting its committed work, but an always-long queue could provide the same benefit. Moreover, route changes can alter connectivity, and abrupt synthetic fades may have no observable precursor. The experiment therefore retains both a communication-independent reference and a non-predictive long-queue control.

\subsection{Theory and Related Work}
Yang et al. address cooperative USV coverage planning \cite{yang2023cooperative}; Bramblett and Bezzo study multi-robot planning with restricted communication \cite{bramblett2023epistemic}. These motivate a bounded coordination experiment rather than a new vessel model. Published consensus-based auctions provide an allocation reference \cite{choi2009auction}, but our deterministic greedy rule does not implement CBBA's distributed consensus or inherit its guarantees.

The model combines a log-distance signal form \cite{goldsmith2005pathloss} with a two-state burst process motivated by Gilbert \cite{gilbert1960burst}. Persistence and ordinary least squares are standard forecasting components \cite{hyndman2021forecasting,nistLeastSquares}. The combined residual-signal and relative-motion warning is a study-specific construction. We compare reservation policies under one common allocator, without claiming superiority to published coverage or allocation systems.

\subsection{Research Problem, Aim, and Research Questions}
The aim is to evaluate whether short-horizon outage warnings improve online task reservation between two USVs. The main question is: how does prediction-triggered reservation affect mission completion time and redundant coverage relative to reactive resynchronization under intermittent boat-to-boat connectivity?
\begin{enumerate}[label=\textbf{RQ\arabic*.}]
\item Across fade-persistence and balanced/unequal-progress conditions, what is the effect of trend-triggered reservation relative to reactive coordination?
\item Does any benefit remain relative to an always-long queue, and what communication and computation costs accompany it?
\item How useful are trend and persistence warnings in terms of false alarms, missed outages, and lead time under the same reservation action?
\end{enumerate}
The expectation that anticipation might help requires both a useful warning and an action that improves the mission. Null and adverse effects are valid outcomes. Fixed partitioning is a reference, not an assumed defective baseline.
''')
write('sections/02_method.tex',r'''
\section{Research Method}
\subsection{Research Design and Methodological Rationale}
We implemented a controlled quantitative simulation with five configurations: S1 fixed partition, S2 reactive short queue, S3 always-long queue, S4-T trend-triggered reservation, and S4-P persistence-triggered reservation. Motion, sensing, allocator, disturbance generation, exchange budget, and stopping rules are shared. Each condition has 30 paired evaluation seeds; seed, fade-persistence level, and slowdown condition identify a matched scenario. Realized radio histories can differ because routes depend on policy.

This design isolates queue reservation under a simple, inspectable model. It omits hydrodynamics, currents, collision avoidance, sonar reconstruction, and measured sea-channel calibration. No external robotics code was adopted. Implementation tests establish software properties, not maritime realism.

\subsection{Data, Materials, Participants, or Other Sources}
The data are synthetic trajectories, observations, task assignments, and communication events. There are no human participants. Table~\ref{tab:settings} gives author-selected controls retained from the revised research plan. The full plan, assigned template, source snapshots, frozen configuration, seeds, and analysis scripts are preserved separately from the active paper.
\begin{table}[htbp]\centering
\caption{Core synthetic settings. Model forms are source-informed; numerical values are author-selected controls, not sea-trial measurements.}\label{tab:settings}
\begin{tabularx}{\linewidth}{@{}p{3.2cm}Y@{}}\toprule
Quantity & Value\\\midrule
Grid and starts & $20\times12$ cells, side $20$ m; starts $(10,10)$ and $(210,10)$ m.\\
Motion and sensing & $2$ m/s; one-second ticks; $5$ s per heading change; observations on arrival at cell centres, including transit.\\
Slowdown & None, or boat 1 at half speed for $300$ s; integer onset uniform on $[600,900]$ s.\\
Communication & Every $10$ s; atomic batch, at most four datagrams and $8192$ UTF-8 JSON bytes.\\
Signal & $P_0=-40$ dBm, $d_0=1$ m, $n=2$, threshold $-90$ dBm; fade offsets $0/-10$ dB.\\
Fade process & Stationary faded fraction $q=0.2$; target mean faded duration $L=2,5,10$ exchanges.\\
Reservation & Short/long unstarted queues $3/12$ tasks per boat, excluding the executing task.\\
Forecast & Five successful samples; onset horizon three exchanges, four projected samples; margins $0,2,4$ dB in pilot.\\
Stopping and seeds & Full coverage or $\tau=7200$ s; pilot seeds $0$--$9$, evaluation seeds $1000$--$1029$.\\\bottomrule
\end{tabularx}\end{table}
The signal is
\begin{equation}
r_k=P_0-10n\log_{10}\left(\max(d_k,d_0)/d_0\right)+z_k.
\end{equation}
The stationary two-state fade uses $\Pr(F\to C)=1/L$ and $\Pr(C\to F)=q/[L(1-q)]$. Fade draws and slowdown draws use independent, policy-independent random streams. A fade is not automatically a failed exchange; delivery also depends on distance. At $n=2$, the clear-state threshold distance is approximately $316$ m. There is no rendezvous controller, so disconnected idle boats may never reconnect.

\subsection{Work Procedure and Data Collection}
S1 divides adjacent columns equally and follows a boustrophedon sweep without online messages. At a successful online session, the two boats merge delivered coverage, retain executing tasks, release unstarted queues, and jointly refill them. For each eligible unobserved task and boat with capacity, the allocator minimizes projected finish time, including committed remaining work, shortest grid travel, and turns. Ties use task ID then boat ID. Shortest paths minimize turns and prefer the horizontal-first path if still tied. The speed currently reported by each boat is held constant for allocation estimates; future slowdown states are unavailable to the allocator.

S2 refills to three tasks, S3 to twelve, and S4 normally to three but to twelve when its warning is positive. Initialization uses a jointly agreed allocation. During disconnection, ownership remains committed; a boat never steals tasks and idles after exhausting its queue. A successful budget-conforming batch contains two state datagrams, one proposal, and one acknowledgement. A failed radio opportunity attempts the two state datagrams without delivery. An oversized offered batch is rejected before transmission and recorded separately. This is an ideal atomic protocol, not real lossy consensus.

At each tick the simulator applies the slowdown, advances both boats, records cell-centre observations, evaluates any scheduled radio opportunity, and then forecasts and allocates only after a successful exchange. Completion is checked from true observed coverage and ends the mission without a final coordination batch. Return travel and data upload are excluded.

The trend warning estimates relative velocity from the last two successful position exchanges and fits an ordinary least-squares trend to the last five signal residuals after removing known distance loss. Actual timestamps include gaps. Forecasts combine extrapolated separation with the residual trend; persistence holds the latest received signal. Trend falls back to persistence before five samples. Both project four samples and warn if two adjacent samples beginning within the next three exchanges fall below the threshold plus margin. They cannot access future fade or slowdown draws.

Sixty fixed-route pilot replays selected a separate margin for each predictor using pooled event-level F1, with ties favouring smaller margins. Both selected $4$ dB. An additional 240 online pilot runs checked feasibility. Short-queue stalls were retained as a model outcome, without adding a recovery controller or changing parameters. The frozen design then generated $2\times3\times5\times30=900$ evaluation runs. The optional distance-loss sensitivity and oracle were not part of this core evaluation.

\subsection{Data Analysis and Quality Assurance}
The primary contrast is S4-T minus S2 within each of six conditions. Secondary contrasts are S4-T minus S3 and S4-T minus S4-P. A timed-out mission contributes time at risk to the restricted mean,
\begin{equation}
\widehat\mu_\tau=N^{-1}\sum_s\min(T_s,\tau),
\end{equation}
without being called a completion. We used 2000 paired-seed bootstrap resamples and percentile 95\% intervals. These are marginal intervals; no simultaneous family-wise claim is made. Completion proportions and coverage accompany time estimates, since low travel or communication in stalled runs is not efficiency.

A radio outage is a maximal run of at least two missed opportunities. Consecutive positive warnings collapse into one alert episode until a negative warning or outage/reconnection. Alerts match the first eligible onset one to three exchanges later, once per onset. The first three opportunities are excluded from onset recall; the last four from alert matching. Undefined precision/recall remain undefined. Both warnings are also replayed on the same 180 held-out fixed-route traces, so route changes cannot explain replay scores.

Raw logs retain one-second positions and idle counters, cell observations, pre-synchronization information gaps, task versions, encoded messages, warnings, and component work counters. We reconstructed all 900 evaluation logs and checked observation counts, coverage, travel, idle time, transmitted bytes, reservations, and information-gap summaries. Unique-owner and budget assertions run throughout. Deterministic tests include hand-calculated finite-speed coverage, turning, disconnection, reconnection, prediction inputs, event boundaries, and serialization budgets.

We count floating-point arithmetic separately from logical ordering/membership checks and logarithm/square-root calls. A billion counted arithmetic operations is one GOP, not GOP/s or processor instructions. Component CPU counters exclude file writing and plotting; small Windows CPU timings require separate repeated saved-input benchmarks. Isolated process high-water RAM and separate incremental Python allocation profiles describe this host implementation. The local information gap is $D_i(t)=|C(t)\setminus C_i(t)|/240$, measured before synchronization and at stopping. It is not bathymetric error.

\subsection{Use of AI Tools}
Codex generated the initial simulator, tests, analysis scripts, report structure, and this draft text from the revised plan. Verification included deterministic tests and independent reconstruction of logged metrics. Automated checks do not replace author review of modeling choices, references, code, statistical interpretation, or writing. Both authors' independent reproduction and review remain pending. The repository records assistance, provenance, and these limits explicitly.
''')
write('sections/03_results.tex',r'''
\section{Results}
\subsection{Mission outcomes and the primary comparison}
All 900 planned runs produced retained logs and reconstructed metrics. S1 completed $180/180$ missions with no redundant observations. S2 completed $0/180$ and reached approximately $23.5$--$23.7\%$ coverage. S3, S4-T, and S4-P completed $158/180$, $156/180$, and $162/180$ respectively. These pooled counts describe the matrix; paired inference remains within each condition.

\begin{figure}[htbp]\centering\includegraphics[width=\linewidth]{generated/mission-time.png}
\caption{Restricted mean time to coverage with 95\% bootstrap intervals. Unfinished missions contribute $7200$ s without being counted as completed. Each point uses 30 seeds.}\label{fig:time}\end{figure}
\begin{table}[htbp]\centering\caption{Restricted mean time in seconds, rounded for display.}\label{tab:times}
\input{generated/mission-table}
\end{table}
For balanced progress, S4-T minus S2 was $-5386$ s at $L=2$ (95\% interval $[-5773,-4810]$), $-4422$ s at $L=5$ ($[-5194,-3464]$), and $-5150$ s at $L=10$ ($[-5718,-4400]$). Under slowdown, the corresponding differences were $-5322$, $-4370$, and $-5047$ s. These restricted-time differences include S2's persistent non-completion. S1 remained faster than every online configuration in these settings, with means $1280$ s without slowdown and $1423$ s with slowdown.

\subsection{Reservation control and warning quality}
S4-T showed no consistent improvement over S3. Its mean restricted-time difference from S3 was positive in all six conditions, ranging from $2.8$ to $196.3$ s. At $L=5$ without slowdown it was $+196.3$ s ($[0.7,583.0]$); with slowdown it was $+194.2$ s ($[-0.2,577.5]$). The trend/persistence comparison was also mixed: at $L=5$ S4-T was about $575$ s slower without slowdown and $570$ s slower with slowdown, while several other conditions differed only slightly. The complete paired contrasts, including uncertainty, are provided with the generated data.

On held-out fixed-route replay, the trend predictor matched 197 of 757 eligible outages, with 1299 false alerts: precision $0.132$, recall $0.260$, F1 $0.175$. Persistence matched 196 outages with 1280 false alerts: precision $0.133$, recall $0.259$, F1 $0.176$. Forty early-boundary outages per predictor and 25 late-boundary alerts per predictor were excluded and counted. These scores do not indicate a substantial trend-predictor advantage.

\subsection{Coverage and resource trade-offs}
The online long-queue and predictive methods produced redundant observations, including travel through already observed cells; S2's zero redundancy accompanies severe incomplete coverage. No duplicate task ownership or session-budget violation was detected in the reconstructed evaluation logs. Communication attempts, bytes, component operation counts, idle time, and missing-information fractions are retained per run and summarized by condition. Counts stop at completion or timeout.
\begin{figure}[htbp]\centering\includegraphics[width=\linewidth]{generated/resource-tradeoff.png}
\caption{Communication volume and restricted time, interpreted alongside completion and achieved coverage. Points represent conditions, not an imposed weighted score.}\end{figure}
\begin{table}[htbp]\centering
\caption{Descriptive resource means over the balanced 180-run matrix per policy, measured until completion or timeout. Low resource use in an incomplete mission is not efficiency. Missing-information gaps are averaged before synchronization.}
\input{generated/resource-table}
\end{table}
\input{generated/host-summary}
''')
write('sections/04_discussion.tex',r'''
\section{Discussion}
\subsection{Interpretation and Answers to the Research Questions}
For RQ1, prediction-triggered reservation improved restricted mission time relative to the reactive short queue, but the contrast is dominated by an identified failure mode: boats can become idle beyond radio range. It does not isolate forecast skill. For RQ2, the always-long queue performed at least as well in mean restricted time in every condition, and fixed partitioning completed reliably with less coordination cost. Thus these experiments do not establish that the predictive policy is preferable. For RQ3, held-out replay showed similar, low event-level F1 for trend and persistence. Abrupt Markov fade onsets are not necessarily predictable from received history.

The revised plan anticipated both null effects and stalled reconnection. Retaining those outcomes exposes a limitation of the chosen coordination model. Increasing queue size can prevent some queue exhaustion even without a useful forecast. The present results support that mechanism more directly than a prediction benefit. Redundant observations arise from transit and do not imply inconsistent ownership.

\subsection{Validity, Limitations, and Generalizability}
The evidence concerns one grid, two start locations, one common greedy allocator, and synthetic numerical controls. S2's complete censoring makes its restricted mean well-defined but leaves its uncensored completion-time distribution unidentified. Percentile bootstrap intervals with 30 seeds can be discrete and sensitive to a few stalled missions; the six conditions should not be pooled into a universal effect. Reusing the same fade trace across policies controls exogenous randomness but cannot equalize route-dependent delivery.

Atomic batch commitment simplifies agreement and omits partial delivery, retransmission timing, contention, and real distributed consensus. Ideal cell-centre sensing omits sonar, localization error, and bathymetric uncertainty. The simulator has no rendezvous or collision avoidance, so it is unsuitable as an operational controller. All results require independent author reproduction and review. Software verification does not calibrate a marine environment.

\subsection{Ethics, Societal Aspects, and Sustainability}
Synthetic data avoid human-participant privacy issues. The main responsibility is to prevent a small verified model from being presented as evidence of safe autonomous vessel deployment, accurate seabed maps, or measured energy savings. A stalled policy can appear cheap in movement or communication because it accomplishes less work; coverage and censoring must accompany resource indicators. Bytes, operation counts, laptop CPU time, and process RAM do not determine radio or propulsion energy, battery endurance, or device lifetime.

\subsection{Implications and Future Work}
A separate, explicitly revised study could add one common recovery/rendezvous rule and repeat all controls, or test a channel with independently justified observable precursors. These changes should be specified before a new evaluation rather than tuned to reverse the current ranking. Measured radio traces and vessel/sensor models would then be needed to assess external validity. The existing long-queue ablation should remain, because it reveals when reservation capacity accounts for the apparent benefit of prediction.
''')
write('sections/05_conclusion.tex',r'''
\section{Conclusion}
The implemented simulator provides reproducible comparisons, retained raw evidence, and metrics for the five configurations in the revised plan. In the tested settings, fixed partitioning completed every mission. Predictive reservation reduced restricted mission time relative to a reactive policy that stalled, but trend warnings did not provide a consistent advantage over always reserving a long queue or using persistence. The defensible conclusion is a bounded finding about task reservation and reconnection in this synthetic model, with no demonstrated maritime, map-accuracy, or energy benefit.
''')
write('sections/appendix.tex',r'''
\section{Reproduction and implementation details}
The GitHub repository separates \texttt{paper/} and \texttt{code/}. The historical research-plan source is preserved under \texttt{paper/research-plan/}; the professor's original template is under \texttt{paper/professor-template-2026/}. Compile this report from \texttt{paper/Final\_Report/} using LuaLaTeX and BibTeX, with \texttt{main.tex} as the entry point.

From \texttt{code/simulation/}, install the project and run the documented test, pilot, evaluation, analysis, benchmark, and replay commands. The frozen design records margins, seed ranges, conditions, and analysis rules. The evaluation manifest records source hashes; raw-log SHA-256 hashes and reconstruction checks accompany the summaries. Bulk raw logs remain local and can be regenerated from the frozen design; a representative raw trace and an offline five-policy replay are supplied for inspection.

The implementation resolves plan details explicitly: observations occur at target/transit cell centres, shortest paths minimize turns with horizontal-first ties, initial heading has no turning cost, slowdown onset is integer-uniform and applies before the tick's movement, and task execution continues within the remaining tick after a waypoint. Failed sessions retain committed ownership; no recovery or theft is introduced. Component operation-count formulas and message encoding are documented beside the code.

The original template contains a stray \texttt{w} in its section-format command. Removing this typographical error preserves the intended formatting. The report retains the template's font family, 11-point body, one-inch margins, spacing, and required headings, and adds GitHub icons and a boxed repository link from the research-plan styling. The KTH logo is omitted in accordance with the course formatting page.
''')
bench=json.loads((RESULTS/'host-benchmark.json').read_text()) if (RESULTS/'host-benchmark.json').exists() else None
if bench:
    t=bench['timings']; ram=bench['process_memory']
    text=(r'\par Separate repeated saved-input benchmarks on the recorded host measured median CPU time per decision of '+
          f"{t['trend']['median_cpu_ns']/1000:.1f}"+r' $\mu$s for trend, '+f"{t['persistence']['median_cpu_ns']/1000:.1f}"+r' $\mu$s for persistence, and '+
          f"{t['allocation']['median_cpu_ns']/1000:.1f}"+r' $\mu$s for the representative allocation. Isolated full-process peak RAM ranged from '+
          f"{min(r['peak_process_rss_bytes'] for r in ram)/2**20:.1f}"+' to '+f"{max(r['peak_process_rss_bytes'] for r in ram)/2**20:.1f}"+
          r' MiB across the five configurations. These are implementation- and host-specific measurements. Incremental Python allocation profiles and all batch timings are retained separately; small per-session CPU counters may be below the Windows timer resolution.')
else: text=r'\par Host timing and memory benchmarking remain pending and are not claimed as measured results.'
write('generated/host-summary.tex',text)
print(PAPER/'main.tex')
