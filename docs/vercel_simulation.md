# Interactive SIAS application on Vercel

The Vercel entrypoint (`public_site.py`) runs the original Smart Industrial
Automation System interface through `demo_app.py`:

- `/`: original application home with Dashboard, PLC Monitor and Maintenance links.
- `/dashboard`: six sensor gauges, health and anomaly charts, machine controls,
  fault injection and the deterministic scenario.
- `/plc-monitor`: live input contacts, output coils, ladder logic and alarm handling.
- `/maintenance`: health, remaining-life estimates, sensor status and alarm history.

The screens use the existing page JavaScript. A two-second HTTP update loop feeds
its `data_update` handlers, allowing gauges and charts to work without persistent
Socket.IO connections on Vercel. Machine actions refresh the PLC immediately.
The navbar identifies the session as a simulation; Live indicates that updates
are being received, rather than a physical machine connection.

## Runtime and data

Each browser session receives its own software-only sensor simulator, simulated
PLC and predictive engine. CSRF tokens protect state-changing requests. The public
simulator always constructs `SimulatedPLCAdapter` directly and ignores Modbus
configuration; it cannot connect to or operate real equipment. It does not expose
account, customer, asset or gateway-write endpoints and never opens SQLite.
Predictive-model persistence is disabled for simulation sessions.

Session state and recent history live only in function memory. They may reset on
cold starts, instance changes, an hour of inactivity, or eviction from the bounded
32-session cache. They are not durable production records. The backend samples at
most once every two seconds per active session; control actions trigger an
immediate scan. The ML engine trains as enough session samples accumulate.

The full account-based operations application remains in `server.py` and runs via
`python app.py` or Docker on a host with durable database storage. The former
industry catalog and solution planner are retained in `industry_hub.html`, exposed
at `/industry-hub` in that authenticated application, away from the simulator's
primary navigation.

## Release validation

Use Python 3.12 and run `python -m pytest tests/ -q`. Check all four screens and
exercise start, stop, emergency stop, fault injection and alarm acknowledgement.
Confirm separate browser sessions do not share controls. Use GitHub-verified
commits for deployment; keep Vercel's required signature verification enabled.
After the deployment is Ready, check `/ready` for `mode: simulation` and verify
that chart values and the PLC scan tick update in the browser.
