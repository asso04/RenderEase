# RenderEase

Queue and schedule Blender renders without babysitting your machine.

A small local-only Blender add-on: ordered still/animation jobs, local scheduling,
manual execution, failure recovery and the last 50 history entries. No dependencies,
accounts, network calls, telemetry or external services.

Implementation and usage documentation: [renderease/README.md](renderease/README.md).
Validation evidence and hardware report: [VALIDATION.md](VALIDATION.md).
Installable artifact: `dist/renderease.zip`.

From this directory:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/package.py
```
