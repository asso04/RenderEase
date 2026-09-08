# RenderEase 0.1.0

**Queue and schedule Blender renders without babysitting your machine.**

RenderEase queues local stills and animations in a Blender-native sidebar. It has
no backend, network code, accounts, telemetry, paid services or third-party Python
dependencies. This MVP covers job management, scheduling, render execution and
bounded local history only.

## Compatibility

API target: Blender 4.2 LTS and later Blender 4.x, using the legacy add-on ZIP
workflow. Integration tested with **Blender 4.3.2 on Windows**, in background mode.
Blender 4.2 itself and other versions/platforms have not been validated. Interactive
sidebar drawing, modal rendering and keyboard cancellation still need manual QA;
background integration success is not a claim that all interactive behavior has
been validated.

## Installation

1. Use `dist/renderease.zip`, or build it with `python tools/package.py` from the
   repository root. The ZIP contains the `renderease/` package, not an extra project folder.
2. In Blender 4.3, open **Edit > Preferences > Add-ons**.
3. Open the top-right dropdown and choose **Install from Disk…**.
4. Select `renderease.zip`, then install and enable **RenderEase**.
5. In the 3D View, press **N**, then open the **RenderEase** tab.

The exact installation menu wording may vary in other 4.x versions. No Python
packages, extension repositories or service configuration are needed.

## Create and execute a job

1. Configure the scene's camera, engine, samples and output format in Blender.
2. Click **Add Job**, name it, and choose a scene.
3. Choose **Still** or **Animation**, frame(s), resolution, scale and output.
4. Confirm the dialog to add the definition to the queue.
5. Select a job and use **Edit**, **Duplicate**, arrows, **Remove** or **Reset**.
6. Use **Run Now** for the selected pending/scheduled job, **Run Next** for the
   first eligible job, or **Run Queue** to process eligible jobs in list order.

Still uses the start frame; animation renders the inclusive start/end range with
step 1. Resolution is 4–65536 pixels per dimension; MVP scale is 1–100%.
Scene render engine, samples, image/video format, layers and other options are
inherited at execution time. Jobs do not snapshot geometry or all scene settings.
An image format is required for stills. Scene references are stored by name; if
you rename a scene, update pending job definitions through Edit.

The selected job's details are read-only outside the Edit dialog. This prevents
partially entered dates and invalid settings from being dispatched by the timer.
Finished jobs require Reset before editing/rerunning. Duplicate and Reset disable
scheduling, so an old definition cannot accidentally launch a second scheduled job.

## Scheduling

**Scheduled jobs only start while Blender is open.**

Enable Schedule in the job dialog and enter a local date/time such as
`2026-09-08 23:30:00`. No timezone offset or OS scheduler is used. Due jobs are
checked approximately every 10 seconds while idle, in queue order. Jobs becoming
due during a render wait for the renderer to become idle.

A past time saved in the dialog produces a warning and a visible held state. Use
**Run Now** explicitly, or edit it to a future time. Schedules already overdue
when a file is loaded or the add-on is enabled are also held, with an explanation.
Jobs becoming due during an uninterrupted session remain eligible. Times use the
computer's local wall clock: timezone/DST changes are not normalized; review dates
after a clock change. Only one occurrence is scheduled, with no recurrence.

## Queue, failure and cancellation behavior

- Only one RenderEase job can render at a time. Blender's active render-job flag
  also prevents starting while an unrelated Blender render is active.
- Run Queue skips finished/cancelled/failed jobs and future or held schedules. It
  stops once no jobs are currently eligible; future schedules remain armed.
- A validation or execution failure records FAILED, stores a readable message and
  stops queue continuation **and** independent automatic scheduling for the session.
  Fix/reset the job, then explicitly Run Queue or Resume Scheduling.
- Cancel Queue stops future dispatch and pauses automatic scheduling. It does not
  pretend to abort Blender's current render. Use **Esc in Blender's render window**
  to cancel that render. A render-cancel callback records CANCELLED.
- Run Now bypasses the selected job's future/held time, but still validates its
  definition. It does not implicitly resume other jobs after cancellation/failure.
- A cancelled queue leaves waiting job statuses intact. Cancelled *renders* have
  CANCELLED status and cannot automatically restart.
- Definitions cannot be modified through RenderEase during a render or active queue.

The panel shows start/completion/failure messages, active job, scheduling state and
errors. Persistent completion status and timestamps remain in the job and history
even when the live message advances to the next job. Operator reports provide
additional feedback for explicit actions. Console logs include job IDs, transitions,
scheduler dispatch and errors; stack traces appear only in the console.

## Output and temporary settings

Output follows Blender's filename/prefix semantics. Use a distinct filename for a
still and a distinct prefix/folder for an animation. Blender's own file format,
extension and overwrite settings apply; this MVP does not detect output collisions.
`//` paths require a saved .blend file. Existing ancestors are inspected without
writing probe files. Missing output directories are created **only at render start**.
Permission, invalid path and creation errors fail the job and stop automatic work.

Resolution, path, frame range/step/current frame and the initiating window's scene
are restored after rendering, before queue continuation. Completion handlers only
signal an outcome; the timer waits until Blender releases its render job before
restoring settings or dispatching more work. UI rendering uses INVOKE_DEFAULT;
background tests use synchronous EXEC_DEFAULT.

## Persistence and assumptions

One queue per .blend file is stored in native PropertyGroups on the dedicated Text
datablock `.RenderEase Queue`, retained with a fake user. This is a Blender datablock,
not a JSON database or external text file. Scene duplication/deletion does not copy
or delete the queue. Do not delete/duplicate this dedicated datablock manually or
append multiple queue datablocks from other files; merging queues is outside this MVP.

Save the .blend file to persist job definitions, ordering, statuses, timestamps and
history. There is no autosave or external recovery database. The history contains
the last 50 outcomes, including failures and cancelled renders. Deleting/resetting
a job does not delete its history.

Running/paused state is session-only; file load/enable never resumes a saved active
queue. Persisted RENDERING jobs become FAILED with recovery guidance. Future valid
schedules re-arm; overdue ones are held. Undo/redo invalidates runtime tracking and
recovers definitions. Avoid editing scenes, undoing, loading files, saving temporary
render settings or disabling the add-on during a render. If disabled mid-render,
tracking is stopped, the job is marked failed and Blender's active render is left
alone; temporary render settings cannot safely be restored until it ends, so they
may remain applied in this exceptional case. Save before starting work.

## State machine

| Source | Allowed destinations |
|---|---|
| PENDING | SCHEDULED, RENDERING, CANCELLED, FAILED |
| SCHEDULED | PENDING, RENDERING, CANCELLED, FAILED |
| RENDERING | COMPLETED, FAILED, CANCELLED |
| COMPLETED | PENDING |
| FAILED | PENDING |
| CANCELLED | PENDING |

FAILED is allowed directly from waiting states for execution-time validation errors.
No terminal job reruns automatically. Unexpected API errors are logged and stop the
queue; no known failure intentionally leaves a job RENDERING.

## Architecture and repository structure

```text
renderease/
    __init__.py          deterministic registration and rollback
    properties.py        native job/queue/history definitions
    utils.py             local datetime parsing and logging
    validation.py        deterministic, non-writing validation
    state_machine.py     explicit transitions
    queue_manager.py     pure eligibility/order/session state
    scheduler.py         one persistent timer and deferred dispatch
    handlers.py          centralized render/load/undo callbacks
    render_executor.py   settings, native rendering, outcomes and recovery
    operators.py         validated draft editing and queue commands
    panels.py            sidebar, UIList, status and bounded history
    README.md            installation and product documentation
tests/
    test_logic.py        pure Python tests
    blender_adapters.py  Blender tests with render invocation mocked
    blender_integration.py  two tiny real CPU stills
tools/package.py         standard-library ZIP builder
README.md
VALIDATION.md
dist/renderease.zip
```

Queue selection has no Blender/UI dependency. The scheduler calls the execution
adapter; UI calls operators. Registration installs classes, data properties,
centralized callbacks and one timer, with rollback on failure. Unregister removes
callbacks/timer and classes deterministically, with repeat calls supported.

## Automated tests

Run from the repository root. Pure logic:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

Blender integration without rendering (including failure/cancel and animation invocation):

```powershell
& 'C:\Program Files\Blender Foundation\Blender 4.3\blender.exe' --background --factory-startup --threads 2 --python-exit-code 1 --python tests/blender_adapters.py
```

Optional minimal real-render integration (exactly two stills):

```powershell
& 'C:\Program Files\Blender Foundation\Blender 4.3\blender.exe' --background --factory-startup --threads 2 --python-exit-code 1 --python tests/blender_integration.py
```

Adjust the executable path for your installation. The real-render script uses the
factory cube, 32×24 PNGs, one frame per job, Cycles CPU, one sample, two CPU threads,
no denoising/compositing and a temporary directory removed after successful checks.
It preflights scene complexity, settings and frames before rendering. Cycles CPU
is used for predictable headless testing without a GPU graphics context. Tests
never benchmark, stress-test, tune hardware or change power/driver settings.
The no-render adapter suite patches RenderEase's explicit invocation function,
not Blender's dynamic `bpy.ops` proxy.

## Manual acceptance checks still required

1. Install/enable the ZIP in Blender 4.3.2. In a new factory cube file verify the
   empty sidebar, Add dialog, validation messages and selected details.
2. Use one still job, 320×240 at 100%, frame 1, one CPU sample, two threads, no
   denoising/compositor, and a unique temporary PNG output. Validate the scene is
   just the cube/camera/light before running. Confirm completed status, timestamp
   and output. The automated smoke test already exercises this at 32×24.
3. For interactive continuation, use at most two trivial one-frame jobs and verify
   the second starts and the queue stops. Do not rerun this solely to benchmark.
4. Prefer a mocked schedule test. If interactive timer acceptance is needed, set
   one tiny job a few seconds ahead; expect dispatch within about 10 seconds. Verify
   past dates are visibly held and Run Now is explicit.
5. Check Cancel Queue prevents the next job, then Esc reports CANCELLED for the
   active job. Use mocked tests for repeated cancellation/failure scenarios.
6. Make 10–20 definitions without rendering. Check scrolling, Edit, Duplicate,
   movement limits, Remove, Reset and status/history readability at normal sidebar
   widths. Confirm queue edit controls lock during rendering.
7. Save/reopen; disable/enable twice; load a new file. Verify no duplicate callbacks
   or automatic restart of old completed/failed/cancelled jobs. Delete temporary
   test outputs afterward, keeping user files untouched.

No render-speed, thermal, power or component-lifespan benefits are claimed.

## Troubleshooting and limits

- **Nothing starts:** Blender must be open, no render may already be running, and
  scheduling must not be paused or held. Check the local clock and status area.
- **Scene missing:** choose an existing scene in Edit; Reset a failed job first.
- **Output fails:** use a writable directory; save the .blend before using `//`.
  Validation cannot guarantee future disk space or permissions.
- **No camera / movie format for still:** fix the scene's camera/output properties.
- **Job says failed after reopening:** the saved file contained RENDERING; reset
  explicitly. Unsaved results cannot be recovered from disk automatically.
- **Blender crashes or renderer hangs:** an in-process add-on cannot supervise a
  crashed process or safely kill a hung render. Use Blender's cancellation controls.
- **Completion errors from render engines:** exceptions, CANCELLED return values and
  missing completion signals are handled. Blender may not expose a detailed cause
  for every renderer failure; a native cancel callback is recorded as cancelled.
- Other render engines, plugins, video encoders, multi-window interactive behavior,
  complex scene setups and actual animation rendering have not been validated.
- Full visual and modal UI acceptance is pending; see the repository validation report.
