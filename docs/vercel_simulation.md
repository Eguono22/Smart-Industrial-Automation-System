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

Recent history and ML training live in function memory and may reset on cold
starts, instance changes, an hour of inactivity, or eviction from the bounded
32-session cache. Small JSON-only sensor/control snapshots travel in the signed
browser session so stop, emergency-stop and fault state survive worker changes.
Configure a stable secret SECRET_KEY in Vercel production; the value is stored in
Vercel's sensitive environment settings, never in the repository. These snapshots
are not durable production records and contain no executable model data. The backend samples at
most once every two seconds per active session; control actions trigger an
immediate scan. The ML engine trains as enough session samples accumulate.

## Operations modules

The Operations dropdown leaves the original four screens in place and adds an
overview at `/operations`. Customers/sites/assets, work orders, telemetry,
notifications and user access have searchable sample tables at
`/operations/<module>`. These are explicitly labeled example previews: there is no
record creation, account management or notification delivery in the public demo.
The industry catalog and browser-local solution planner are available at
`/industry-hub`, including capability selection and JSON export.

The full account-based operations application remains in `server.py` and runs via
`python app.py` or Docker on a host with durable database storage. Its Operations
menu opens the existing persistent modules with the same account/customer scopes;
only administrators can open user administration. Set `SIAS_OPERATIONS_URL` on the
Vercel simulator to that workspace's HTTPS URL to show links to its modules. Leave
it empty when no full workspace is connected. URLs with credentials, queries or
fragments are rejected.

## Release validation

Use Python 3.12 and run `python -m pytest tests/ -q`. Check all four screens and
exercise start, stop, emergency stop, fault injection and alarm acknowledgement.
Confirm separate browser sessions do not share controls. Use GitHub-verified
commits for deployment; keep Vercel's required signature verification enabled.
After the deployment is Ready, check `/ready` for `mode: simulation` and verify
that chart values and the PLC scan tick update in the browser. Check the Operations
dropdown on desktop and mobile, sample-table search, and industry-plan export.
