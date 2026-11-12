# Run the webapp and simulation engine

## Try it on Windows

Open Docker Desktop in Linux container mode, then double-click `Run-Lab.cmd` in the repository root. Choose **3**. The first start builds two images and downloads Python dependencies inside Docker. Once the engine connects, the menu opens [the lab](http://127.0.0.1:8768). Choose **7** to stop both. You can close and reopen the menu at any time.

| What to run | Docker start / stop | Native start / stop |
| --- | --- | --- |
| Engine only | 1 / 5 | 2 / 6 |
| Engine and local webapp | 3 / 7 | 4 / 8 |

Native mode requires Windows Python 3.10+ with pip and venv. The menu prepares `code/simulation/.venv` on first use. Set `LAB_PYTHON` to a particular Python executable if required. The original `Run-Lab.ps1` also works as a standalone dashboard. Stop it before starting the split stack on the same port or using the same job directory.

An engine started alone waits for its webapp and reconnects automatically. By default it waits for the local webapp of the same runtime. Selecting **3** after **1**, or **4** after **2**, adds the local webapp. To switch between native and Docker, stop the current pair first. Stopping only the engine leaves the webapp open. The engine finishes queued experiments during a normal stop. Leave Docker Desktop running until the stop command returns.

The menu can also run without prompts, for example:

```powershell
.\Run-Lab.cmd -Action start -Mode docker -Services both -NoBrowser
.\Run-Lab.cmd -Action stop -Mode docker -Services both
```

## Test the dashboard

1. Open **Live map** and choose **Run selected policy**. A second browser on the same webapp receives the same live samples. The small map beside the setup form shows observed cells and boat positions. The caption shows the simulation time and radio reading. The engine samples at radio exchanges and the interface sends the latest available sample up to ten times per second. Fast runs may show just their last sample.
2. When verification finishes, the submitting browser opens the usual recorded replay. Use pause, seek, speed, policy comparison and the event log there. Each viewer controls their own replay clock.
3. In **Runs & jobs**, inspect the completed job and download its ZIP. Stop and restart the stack to see the same job. Both runtimes store new evidence in `code/simulation/results/lab`. Docker mounts the existing core and extension evidence read-only, including any raw logs present on that PC. A fresh checkout contains the bundled S4-T example. The interactive checkpoint slides that use other policies also need their original core traces.
4. For native logs, open `.lab-launcher/engine.err.log` or `web.err.log`. For Docker logs, leave the menu running, open PowerShell in the repository root, and run the following. The local key is generated automatically on first use.

```powershell
$env:LAB_ENGINE_KEY = Get-Content -Raw .lab-launcher/engine.key
docker compose logs --tail 50 web engine
```

## Host the webapp after the local test

Deploy one **web** instance. The engine and result files stay on the operator's PC. The web service needs a long-running process, WebSocket upgrades, streaming HTTP uploads/downloads and HTTPS. Its connection state is in memory. The page can open while the engine is offline and connects when the engine comes online. Evidence, new runs and downloads require that connection.

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

For a container hosting platform, select build context `code/simulation`, Dockerfile `Dockerfile`, target `web`. The image listens on `PORT` (8768 by default). Forward the original Host header, allow upgrade and long-running transfers, and run a single replica. Host access to the app uses the browser login. The engine authenticates separately.

On the operator's PC, run the following from PowerShell with the real hostname and the same engine key as the server. The prompt keeps the key out of shell history.

```powershell
$env:LAB_RELAY_URL = 'https://lab.example.org'
$secret = Read-Host 'Engine key' -AsSecureString
$env:LAB_ENGINE_KEY = [Net.NetworkCredential]::new('', $secret).Password
.\Run-Lab.cmd
```

Choose **1** for Docker or **2** for native. The engine connects outbound. Open the public HTTPS address in the browser and sign in as `lab`. Options **3** and **4** are reserved for a local webapp and direct the engine to that local instance. Stop an existing engine before changing its destination or credentials.

To stop the hosted webapp, run `docker compose stop web` on the server. There is no database migration or copy of the research results on the server.
