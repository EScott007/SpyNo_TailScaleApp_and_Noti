# **<ins>SpyNo-SAARUS</ins>**
<img src="https://github.com/cobra-X71/SpyNo-SAARUS/blob/main/Media.jpg" width=350>

This GitHub Contains all of the model code and supporting .py files. 

## <ins>Code Links</ins>
This space will be for code links on the ReadMe
This link will be for the GitHub Programming Syntax [GitHub Programming](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)

## <ins>Dashboard Integration Modes</ins>

The dashboard in `app.py` supports two run modes:

1. Production integration mode (with real `main.py` producer)
2. Mock integration mode (without Hailo/cameras/sensors)

### Production Integration Mode

Run `main.py` in one terminal and the dashboard in another terminal:

```bash
APP_HOST=100.116.184.23 APP_PORT=5000 MOCK_MODE=0 python3 app.py
```

Dashboard URL:

```text
http://100.116.184.23:5000
```

### Mock Integration Mode (Pi-only testing)

Use app-only synthetic telemetry:

```bash
APP_HOST=100.116.184.23 APP_PORT=5000 MOCK_MODE=1 python3 app.py
```

Or use a two-process simulation similar to production:

Terminal 1:

```bash
python3 mock_main.py
```

Terminal 2:

```bash
APP_HOST=100.116.184.23 APP_PORT=5000 MOCK_MODE=0 python3 app.py
```

### Integration Health Checks

Check data feed health:

```text
GET /api/health
```

Check merged telemetry payload:

```text
GET /api/data
```

`/api/health` reports:

- `bridge_state`: `live`, `stale`, or `offline`
- `bridge_age_sec`: age of latest producer update
- `mock_mode`: whether synthetic producer is enabled inside `app.py`

Optional staleness tuning (default is 3 seconds):

```bash
BRIDGE_STALE_SECONDS=5 APP_HOST=100.116.184.23 APP_PORT=5000 python3 app.py
```
