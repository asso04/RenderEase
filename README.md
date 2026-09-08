# RenderEase

Schedule Blender renders and let them run automatically at the right time.

RenderEase is a lightweight, local-only Blender add-on designed to make rendering easier when you don't want to manually start or monitor the process.

## Features

* Schedule renders for a specific time
* Support for still images and animations
* Local-only operation
* Manual render execution
* Failure recovery
* Recent render history
* No accounts or external services
* No telemetry
* No network connection required

Everything runs locally inside Blender.

## Installation

Download the installable ZIP:

`dist/renderease.zip`

Then in Blender:

**Edit → Preferences → Add-ons → Install from Disk**

Select `renderease.zip` and enable the add-on.

Validation and hardware testing:

[RenderEase - V1.0/VALIDATION.md](VALIDATION.md)

## Development

Run tests:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

Build the installable package:

```powershell
python tools/package.py
```

## Early Release & Feedback

This GitHub version is an early free release intended for testing and feedback.

If you try RenderEase, feedback about bugs, workflow improvements, missing features, or real-world use cases is highly appreciated.

Once enough feedback has been collected and the add-on has been refined, a more complete version with additional features will be released.

The link to the full version will be added here when it becomes available.
