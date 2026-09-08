# Validation report — 2026-09-07

Environment: Windows, Python 3.10, Blender **4.3.2** (32f5fdce0a0a).
Target API baseline: 4.2 LTS; no Blender 4.2 executable was tested.

## Results

- Installation regression fixed: enabling through Blender's add-on installer
  originally raised `'_RestrictData' object has no attribute 'texts'` because
  registration read file data inside Blender's restricted context. Recovery now
  runs after registration, on the first timer tick or explicit job operation.
- `python tests/blender_install_zip.py`: **passed** on Blender 4.3.2. Installs the
  actual distribution ZIP in a temporary isolated user profile, enables it via
  Blender's preferences operator, checks deferred initialization, and disables it.
  No user preferences changed and no renders performed. Both the 14 pure tests
  and Blender adapter suite were rerun successfully after this correction.

- `python -m unittest discover -s tests -p 'test_*.py' -v`: **14 tests passed**.
  Pure logic only: validation, date parsing, invalid dates, past schedule warnings,
  due/held/future selection, terminal skipping, all state transition pairs,
  failure/cancellation session state, non-writing path checks and 20-job ordering.
- `blender_integration.py`: **passed** on Blender 4.3.2. Registration, unique
  handlers/timer, actual save/load, operator add/duplicate/move/remove/reset,
  missing-scene failure, mocked schedule dispatch, actual rendering/completion,
  two-job continuation, setting/scene restoration, bounded history, disable/enable,
  teardown and loading a file without add-on data.
- The real-render pass preceded a persistence improvement from Scene storage to
  native Text datablock properties and extraction of an invocation adapter.
  The final persistence and execution path were subsequently covered by
  `blender_adapters.py` **with render invocation mocked**, without repeating real renders.
- `blender_adapters.py`: **passed** on the final storage design. Actual native Text
  save/load, scene duplication/removal, callbacks/timer across load, mocked still
  and animation invocations, completion and queue continuation, cancelled and
  failed outcomes, setting restoration, due/held schedule dispatch, active-render
  edit lock, 50-entry history, repeat registration cycles and new-file recovery.

## Hardware-safe accounting

| Test | Invoked Blender | Actual render | Resolution / frames | Engine / device |
|---|---|---|---|---|
| Pure logic suite | No | No | None | None |
| Successful real integration | Yes, background | 2 completed stills | 32×24, 100%, 1 frame each | Cycles CPU, 1 sample, 2 threads; no GPU rendering |
| Final adapter suite | Yes, background | No; explicit adapter mocked | Definitions only | No renderer used |
| Earlier adapter development attempt | Yes, background | 1 unintended render invocation, interrupted | 32×24, 100%, frame 1 | Factory EEVEE; GPU initialization/use not measured |

The earlier adapter attempt patched Blender's dynamic `bpy.ops.render` proxy,
which did not intercept the invocation. It was interrupted after detection,
before any completion/output was reported. It is not counted as a passed test.
The boundary was replaced by an explicit RenderEase invocation function and
the corrected suite completed with zero real renders. No claim is made that
this interrupted invocation used no GPU resources.

The two completed renders used only the factory cube/camera/light, no modifiers,
volumes, denoising, compositor, simulations or external assets. Safe settings were
asserted before execution. PNGs and temporary .blend files from successful tests
were removed by TemporaryDirectory cleanup. No benchmark, stress test or hardware,
driver, thermal or power-setting changes were performed.

## Not validated

- Interactive sidebar drawing, dialogs, actual modal INVOKE_DEFAULT execution,
  Esc keyboard behavior and multi-window context restoration: no GUI session run.
- Actual animation rendering: invocation and frame settings tested with mocks.
- Actual scheduled render waiting: due/not-due dispatch exercised with controlled
  timestamps and mocks, avoiding extra render workloads and long waits.
- Visual UI responsiveness: 20-job queue operations covered without rendering;
  manual sidebar scrolling/drawing acceptance remains pending.
- Blender 4.2/other releases, macOS/Linux, other engines, complex scenes, video
  encoding, out-of-space conditions and renderer hangs.

Exact commands and manual acceptance steps are in `renderease/README.md`.
Nothing was published or deployed.
