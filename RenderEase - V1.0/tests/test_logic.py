"""Pure Python, no Blender imports and no renders."""
from datetime import datetime, timedelta
from types import SimpleNamespace
import tempfile
from pathlib import Path
import unittest

from renderease.validation import validate, validate_output
from renderease.queue_manager import next_job, eligible, Runtime
from renderease.state_machine import transition, TRANSITIONS
from renderease.utils import parse_local

NOW = datetime(2026, 9, 7, 12)


def job(**changes):
    data = dict(id='1', name='Cube', scene_name='Scene', render_type='STILL',
                frame_start=1, frame_end=1, resolution_x=32, resolution_y=24,
                resolution_percentage=100, output_path='/tmp/render.png',
                schedule_enabled=False, scheduled_at='', schedule_held=False, status='PENDING')
    data.update(changes)
    return SimpleNamespace(**data)


class ValidationTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(job(), ['Scene']), ([], []))

    def test_invalid_fields(self):
        for change in [dict(name=' '), dict(scene_name='missing'), dict(render_type='VIDEO'),
                       dict(frame_start=-1), dict(frame_end=1048575), dict(frame_start=4),
                       dict(resolution_x=0), dict(resolution_y=0),
                       dict(resolution_percentage=0), dict(resolution_percentage=101),
                       dict(output_path=' '), dict(schedule_enabled=True, scheduled_at='bad')]:
            with self.subTest(change=change):
                self.assertTrue(validate(job(**change), ['Scene'])[0])

    def test_past_save_warns_execution_allowed(self):
        item = job(schedule_enabled=True, scheduled_at=(NOW-timedelta(seconds=1)).isoformat())
        self.assertTrue(validate(item, ['Scene'], saving=True, now=NOW)[1])
        self.assertEqual(validate(item, ['Scene'], now=NOW), ([], []))

    def test_future_schedule(self):
        self.assertEqual(validate(job(schedule_enabled=True, scheduled_at='2026-09-08 12:00:00'),
                                  ['Scene'], saving=True, now=NOW), ([], []))

    def test_datetime(self):
        self.assertEqual(parse_local('2026-09-07 12:00:00'), NOW)
        for value in ('nonsense', '2026-02-30', '2026-09-07T12:00:00+02:00'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_local(value)

    def test_output_validation_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'missing' / 'render.png'
            self.assertEqual(validate_output(str(output)), [])
            self.assertFalse(output.parent.exists())
            blocker = Path(directory) / 'file'
            blocker.write_text('preserve')
            self.assertTrue(validate_output(str(blocker / 'image.png')))
            self.assertEqual(blocker.read_text(), 'preserve')
        self.assertTrue(validate_output('bad\x00path'))


class QueueTests(unittest.TestCase):
    def test_order_and_terminal_skip(self):
        entries = [job(status=s) for s in ('COMPLETED', 'CANCELLED', 'FAILED', 'RENDERING', 'PENDING')]
        self.assertIs(next_job(entries, NOW), entries[-1])
        self.assertIsNone(next_job(entries[:-1], NOW))

    def test_due_and_not_due(self):
        due = job(status='SCHEDULED', schedule_enabled=True, scheduled_at=NOW.isoformat())
        future = job(status='SCHEDULED', schedule_enabled=True, scheduled_at=(NOW+timedelta(seconds=1)).isoformat())
        self.assertIs(next_job([future, due], NOW), due)
        self.assertIsNone(next_job([future], NOW))
        due.schedule_held = True
        self.assertFalse(eligible(due, NOW))

    def test_schedule_only(self):
        self.assertIsNone(next_job([job()], NOW, scheduled_only=True))

    def test_invalid_schedule_reaches_validation(self):
        item = job(schedule_enabled=True, scheduled_at='bad')
        self.assertIs(next_job([item], NOW), item)
        self.assertTrue(validate(item, ['Scene'])[0])

    def test_failure_stops_all_automatic_execution(self):
        state = Runtime()
        state.running = True
        state.message = 'Failure'
        state.stop(failed=True)
        self.assertFalse(state.running)
        self.assertTrue(state.paused)
        self.assertEqual(state.last_error, 'Failure')

    def test_cancel_does_not_fake_active_render_stop(self):
        state = Runtime()
        state.active_id = 'render'
        state.running = True
        state.stop()
        self.assertFalse(state.running)
        self.assertTrue(state.paused)
        self.assertEqual(state.active_id, 'render')

    def test_twenty_jobs_order_operations(self):
        items = [job(id=str(i)) for i in range(20)]
        items.insert(0, items.pop(19))
        self.assertEqual(next_job(items, NOW).id, '19')
        items[0].status = 'COMPLETED'
        self.assertEqual(next_job(items, NOW).id, '0')
        del items[1]
        self.assertEqual(next_job(items, NOW).id, '1')


class StateTests(unittest.TestCase):
    def test_all_transition_pairs(self):
        for source in TRANSITIONS:
            for target in TRANSITIONS:
                with self.subTest(source=source, target=target):
                    item = job(status=source)
                    if target in TRANSITIONS[source]:
                        transition(item, target)
                        self.assertEqual(item.status, target)
                    else:
                        with self.assertRaises(ValueError):
                            transition(item, target)


if __name__ == '__main__':
    unittest.main()
