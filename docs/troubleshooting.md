# Troubleshooting

## ModuleNotFoundError: No module named agent

This can happen when Flask is launched with `python web/app.py` because Python uses `web/` as the import root. The dashboard now inserts the project root into `sys.path` automatically.

Recommended commands from the project root:

```powershell
.venv\Scripts\Activate.ps1
python web\app.py
```

Then open:

```text
http://127.0.0.1:8080
```
