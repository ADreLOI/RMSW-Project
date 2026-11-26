# Run the webapp and simulation engine

## Try it on Windows

Open Docker Desktop in Linux container mode, then double-click `Manage-Lab.cmd` in the repository root. Choose **3**. The first start builds two images and downloads Python dependencies inside Docker. Once the engine connects, the menu opens [the lab](http://127.0.0.1:8768). Choose **7** to stop both. You can close and reopen the menu at any time.

| What to run | Docker start / stop | Native start / stop |
| --- | --- | --- |
| Engine only | 1 / 5 | 2 / 6 |
| Engine and local webapp | 3 / 7 | 4 / 8 |

Native mode requires Windows Python 3.10+ with pip and venv. The menu prepares `code/simulator/.venv` on first use. Set `LAB_PYTHON` to a particular Python executable if required. The scientific workflow script `code/simulator/scripts/Run-Study.ps1` also works as a standalone dashboard. Stop it before starting the split stack on the same port or using the same job directory.

An engine started alone waits for its webapp and reconnects automatically. By default it waits for the local webapp of the same runtime. Selecting **3** after **1**, or **4** after **2**, adds the local webapp. To switch between native and Docker, stop the current pair first. Stopping only the engine leaves the webapp open. The engine finishes queued experiments during a normal stop. Leave Docker Desktop running until the stop command returns.

The menu can also run without prompts, for example:

```powershell
.\Manage-Lab.cmd -Action start -Mode docker -Services both -NoBrowser
.\Manage-Lab.cmd -Action stop -Mode docker -Services both
```

### Existing checkouts

On a PC updating from the older layout, stop the old lab before switching revisions. Git moves tracked summaries, but raw traces and local jobs belong to each operator. If present under the old code/simulation/results/ directory, copy missing core/raw/, extension/raw/ and lab/ contents to the matching code/simulator/results/ directories. Keep existing job IDs and files. Start the new menu after copying so Docker mounts the new paths.

## Test the dashboard

1. Open **Live map** and choose **Run selected policy**. A second browser on the same webapp receives the same live samples. The small map beside the setup form shows observed cells and boat positions. The caption shows the simulation time and radio reading. The engine samples at radio exchanges and the interface sends the latest available sample up to ten times per second. Fast runs may show just their last sample.
2. When verification finishes, the submitting browser opens the usual recorded replay. Use pause, seek, speed, policy comparison and the event log there. Each viewer controls their own replay clock.
3. In **Runs & jobs**, inspect the completed job and download its ZIP. Stop and restart the stack to see the same job. Both runtimes store new evidence in `code/simulator/results/lab`. Docker mounts the existing core and extension evidence read-only, including any raw logs present on that PC. A fresh checkout contains the bundled S4-T example. The interactive checkpoint slides that use other policies also need their original core traces.
4. For native logs, open `.lab-launcher/engine.err.log` or `web.err.log`. For Docker logs, leave the menu running, open PowerShell in the repository root, and run the following. The local key is generated automatically on first use.

```powershell
$env:LAB_ENGINE_KEY = Get-Content -Raw .lab-launcher/engine.key
docker compose logs --tail 50 web engine
```

## GitHub Pages + Render (agreed publication path)

GitHub Pages serves the interface, guide, presentations, historical core/extension
summaries and five verified demonstration replays (seed 1000, slowdown, L=5).
The Pages build regenerates these five logs in CI and compares their scientific
values with the frozen core. They are identified by their own raw hashes; they
do not replace the original logs or change the 900-run study.

Render runs only the relay. The engine on the operator's PC supplies live samples,
new jobs, other raw logs and downloads. A disconnected public page remains usable
with its published data; experiment buttons are disabled. Results produced on a
PC are not automatically published on Pages.

### Prepare Render

For a new service, first push and validate the implementation branch and use it
for the initial Render deployment. Configure the hook and Pages before merging
to main, then change Render's branch to main. The existing service is
https://rmsw-relay.onrender.com and the Pages site is
https://adreloi.github.io/RMSW-Project/#map.

| Render field | Value |
| --- | --- |
| Source | Public Git Repository: https://github.com/ADreLOI/RMSW-Project |
| Name | rmsw-relay |
| Language | Python 3 |
| Branch | main |
| Region | Frankfurt |
| Root Directory | code |
| Build Command | `python -m pip install "aiohttp>=3.12,<4"` |
| Start Command | `python -m webapp.relay` |
| Compute | Free |
| Health Check Path (Advanced) | /health |

Add these environment variables in Render:

| Name | Value |
| --- | --- |
| LAB_WEB_BIND | 0.0.0.0 |
| LAB_ENGINE_KEY | Generated private key, also used by the PC engine |
| LAB_PUBLIC_ACCESS | 1 (public browser access, explicitly approved by the project owner) |
| LAB_BROWSER_ORIGIN | https://adreloi.github.io |

The browser origin has no `/RMSW-Project` path or trailing slash. For a custom
Pages domain replace it with that exact HTTPS origin. The relay uses Render's
`RENDER_EXTERNAL_URL` and `PORT` automatically. An explicit
`LAB_PUBLIC_ORIGIN` overrides the detected URL; normally leave it unset.
Never put the engine key in the public configuration, repository variables or commits.
With `LAB_PUBLIC_ACCESS=1`, an existing `LAB_WEB_PASSWORD` is ignored. Anyone can
request the allowed experiments and download engine-served evidence while the
PC engine is connected. The private engine key, exact browser-origin checks,
session tokens, input validation and four-job queue bound remain active.
Origin checks are not visitor authentication. No new jobs are accepted while
the engine is disconnected, and the relay does not queue jobs for later delivery.
Jobs already accepted by the PC may finish even after disconnection.

To retain password-protected hosting instead, omit `LAB_PUBLIC_ACCESS`, set
`LAB_WEB_PASSWORD` and build Pages without `--public-access`.

Click **Deploy web service** after the code is on main. A successful build and an
HTTP 200 response from `https://<actual-render-host>/health` confirm the relay is
running; `engine_connected: false` is expected until a PC connects.

### Enable automatic publication

1. GitHub repository **Settings → Pages → Source: GitHub Actions**.
2. Render service **Settings → Deploy Hook**: copy the secret URL into GitHub
   **Settings → Secrets and variables → Actions → New repository secret** named
   `RENDER_DEPLOY_HOOK_URL`. Do not share the URL in chat or documentation.
3. Add the **repository variable** `LAB_RELAY_URL` with the actual HTTPS Render
   origin. This address is public and is included in the Pages build. If omitted,
   visitors must enter it manually in the connection panel. Set it to
   `https://rmsw-relay.onrender.com` to enable automatic connection.
4. Keep native Render auto-deploy disabled if offered: GitHub Actions requests
   deployment after its checks, specifying the tested commit SHA.

`simulator.yaml` runs on push/PR to main, dev and dev-code**. It tests the
scientific implementation and remote transport, executes five reference missions,
verifies their evidence, builds the static site and uploads its artifact.
Only a successful **push to main** publishes Pages and requests a Render deploy.
PRs and development branches never publish. The Render job confirms that Render
accepted the request, not that its asynchronous build is already live. The
initial manual deployment creates the service and makes its hook available.

This path does not require the failing GitHub OAuth popup. It follows
[Render's deploy-hook integration](https://render.com/docs/deploy-hooks) and
[GitHub's Pages workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

### Connect the PC and browser

Once per Windows user/PC, open `Manage-Lab.cmd` and choose **9**. Accept the
default relay URL and enter the value of `LAB_ENGINE_KEY` configured on Render
at the hidden prompt. The ignored `.lab-launcher/remote.xml` stores the key
encrypted with Windows DPAPI; it can only be decrypted by that Windows user on
that PC. Configure Andrea's launcher separately instead of copying this file.
Alternatively run `Manage-Lab.cmd -Action configure-remote`.

For subsequent use, start Docker Desktop and choose **1** to start only the
engine, or **2** for native Python. Stop an existing engine before changing its
destination or key. Choose **5** to stop the Docker engine or **6** for native.
Options **3/4** still start the local webapp and engine; **7/8** stop that pair.
Explicit `LAB_RELAY_URL` and `LAB_ENGINE_KEY` environment variables override
the saved profile, as in the alternative instructions below.

Open the Pages site: it loads published data first and automatically connects to
the configured relay, without a browser password. The panel **Collegamento al
motore / Engine connection** shows waiting/connected status. Mission controls
become available when the engine connects and are disabled when it disconnects.
Reloading starts the connection again. Live sockets still use short-lived,
one-use origin-bound tickets; the browser never receives the engine key.

After a relay restart the engine and browser retry their connections. New
experiments and their files remain on the PC. A new run is never automatically
resubmitted after a network failure. For large archive downloads the browser
buffers the authenticated response before saving it.

### Verify before calling the deployment complete

- Local: menu **3**, replay and comparison, timeline/charts, history, slides,
  job submission and ZIP/raw/figure downloads; then menu **7**.
- Public with PC off: guide/slides, historical summaries and five demo replays.
- Public with PC on: verify automatic connection, submit a short job, observe live samples, open
  the verified replay and download its ZIP. Disconnect and reconnect.
- Publication: a main push passes CI; Pages and Render show the tested revision.

Programmatic relay tests and headless replay tests do not replace this browser
and Docker checklist.

## Alternative: serve the frontend and relay together

Deploy one **web** instance. The engine and result files stay on the operator's PC. The web service needs a long-running process, WebSocket upgrades, streaming HTTP uploads/downloads and HTTPS. Its connection state is in memory. In this combined mode evidence, new runs and downloads require the engine connection.

On a server with Docker Compose, use a checkout of the same revision. Set these environment variables in the hosting environment or a private `.env` at the repository root:

| Variable | Value on the server |
| --- | --- |
| `LAB_PUBLIC_ORIGIN` | The exact public HTTPS origin, e.g. `https://lab.example.org` |
| `LAB_ENGINE_KEY` | A private random engine key. Generate one with `openssl rand -hex 32` |
| `LAB_WEB_PASSWORD` | A separate password for the browser login `lab`. Anyone given this login can run experiments and download evidence |

```sh
docker compose up -d --build web
```

Put an HTTPS reverse proxy on that host in front of `127.0.0.1:8768`. For example, this Caddy site uses the configured DNS name and forwards both HTTP and WebSocket requests. Replace the example hostname with yours.

```caddyfile
lab.example.org {
    reverse_proxy 127.0.0.1:8768
}
```

For a container hosting platform, select build context `code`, Dockerfile `Dockerfile`, target `web`. The image listens on `PORT` (8768 by default). Forward the original Host header, allow upgrade and long-running transfers, and run a single replica. Host access to the app uses the browser login. The engine authenticates separately.

On the operator's PC, run the following from PowerShell with the real hostname and the same engine key as the server. The prompt keeps the key out of shell history.

```powershell
$env:LAB_RELAY_URL = 'https://lab.example.org'
$secret = Read-Host 'Engine key' -AsSecureString
$env:LAB_ENGINE_KEY = [Net.NetworkCredential]::new('', $secret).Password
.\Manage-Lab.cmd
```

Choose **1** for Docker or **2** for native. The engine connects outbound. Open the public HTTPS address in the browser and sign in as `lab`. Options **3** and **4** are reserved for a local webapp and direct the engine to that local instance. Stop an existing engine before changing its destination or credentials.

To stop the hosted webapp, run `docker compose stop web` on the server. There is no database migration or copy of the research results on the server.
