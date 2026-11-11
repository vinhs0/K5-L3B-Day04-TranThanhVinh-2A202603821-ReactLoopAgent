import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, tool_call, final

URL = 'https://stspg.io/7pwv28hvkmz8'  # shortlink của h02n9572mx9y trong snapshot


class FollowReferenceTests(unittest.TestCase):
    ARGS = '{"provider":"github","incident_id":"h02n9572mx9y"}'
    LINKED = '{"provider":"github","incident_id":"xr3myzj7ms51"}'

    def test_unread_linked_incident_is_requested_once(self):
        fake = FakeProvider([tool_call('1', 'get_incident_details', self.ARGS),
                             final('Xong ' + URL),
                             tool_call('2', 'get_incident_details', self.LINKED),
                             final('Đã đọc cả hai ' + URL)])
        result = run_agent('Điều tra', fake, StatusTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        events = [x['event'] for x in result['trace']]
        self.assertIn('validation_unfollowed_reference', events)
        self.assertEqual([x['arguments']['incident_id'] for x in result['trace'] if x['event'] == 'tool'],
                         ['h02n9572mx9y', 'xr3myzj7ms51'])

    def test_reference_check_is_not_repeated_and_does_not_block_completion(self):
        fake = FakeProvider([tool_call('1', 'get_incident_details', self.ARGS),
                             final('Xong ' + URL), final('Vẫn không đọc ' + URL)])
        result = run_agent('Điều tra', fake, StatusTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([x['event'] for x in result['trace']].count('validation_unfollowed_reference'), 1)

    def test_no_reference_check_without_links(self):
        fake = FakeProvider([tool_call('1', 'get_status', '{"provider":"github"}'), final('ok')])
        result = run_agent('x', fake, StatusTools())
        self.assertFalse(any(x['event'] == 'validation_unfollowed_reference' for x in result['trace']))


if __name__ == '__main__':
    unittest.main()
