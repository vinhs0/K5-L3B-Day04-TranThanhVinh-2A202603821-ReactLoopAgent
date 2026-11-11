"""Kiểm tra retry 429 có giới hạn và ghi chú pagination (offline)."""
import sys
import unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'bonus'))
import agent
from agent import run_agent
from bonus.tools import BonusTools
from test_agent import call, final, ScriptedProvider


class RetryTests(unittest.TestCase):
    def test_always_429_stops_after_limit(self):
        t = BonusTools(scenario='rate_limit_always')
        calls = [call(str(i), 'get_vercel_status', {}) for i in range(5)]
        p = ScriptedProvider(calls + [final('Không kiểm tra được Vercel (429)')])
        r = run_agent('Kiểm tra', p, t, max_steps=8)
        self.assertEqual(r['status'], 'completed')
        executed = [e for e in r['trace'] if e['event'] == 'tool']
        self.assertEqual(len(executed), 3)
        events = [e['event'] for e in r['trace']]
        self.assertIn('rate_limit_exhausted', events)
        self.assertEqual(events.count('rate_limit_blocked'), 2)
        self.assertEqual(events.count('rate_limit_retry'), 2)
        self.assertIn('RETRY_LIMIT_REACHED', p.histories[-1][-1]['content'])
        self.assertIn('dừng retry', p.histories[3][-1]['content'])

    def test_nudge_when_model_gives_up_early(self):
        t = BonusTools(scenario='rate_limit_once')
        p = ScriptedProvider([call('a', 'get_vercel_status', {}), final('Vercel bị 429, không rõ'),
                              call('b', 'get_vercel_status', {}), final('Vercel none')])
        r = run_agent('Kiểm tra', p, t, max_steps=6)
        self.assertEqual(r['status'], 'completed')
        events = [e['event'] for e in r['trace']]
        self.assertEqual(events.count('validation_rate_limit_retry'), 1)
        self.assertEqual(len([e for e in r['trace'] if e['event'] == 'tool']), 2)

    def test_always_429_nudge_is_bounded(self):
        t = BonusTools(scenario='rate_limit_always')
        p = ScriptedProvider([final('bỏ cuộc')] * 0 + [call('a', 'get_vercel_status', {}), final('x'),
                              call('b', 'get_vercel_status', {}), final('x'),
                              call('c', 'get_vercel_status', {}), final('Không kiểm tra được Vercel')])
        r = run_agent('Kiểm tra', p, t, max_steps=10)
        self.assertEqual(r['status'], 'completed')
        self.assertEqual(len([e for e in r['trace'] if e['event'] == 'tool']), 3)
        self.assertEqual(r['answer'], 'Không kiểm tra được Vercel')

    def test_retry_after_sleep_is_bounded(self):
        t = BonusTools(scenario='rate_limit_once')
        orig = t.execute

        def execute(name, args):
            res = orig(name, args)
            if res.get('error') == 'RATE_LIMITED':
                res['retry_after_seconds'] = 100
            return res
        t.execute = execute
        p = ScriptedProvider([call('a', 'get_vercel_status', {}), call('b', 'get_vercel_status', {}), final()])
        with mock.patch('agent.time.sleep') as sl:
            r = run_agent('Kiểm tra', p, t, max_steps=5)
        sl.assert_called_once_with(agent.MAX_SLEEP_PER_RETRY)
        self.assertEqual(r['status'], 'completed')
        self.assertTrue(all(isinstance(e, dict) and 'event' in e for e in r['trace']))

    def test_next_offset_note_and_prompt(self):
        t = BonusTools()
        args = {'provider': 'vercel', 'incident_id': 'sps6n39gm4sg', 'limit': 1}
        p = ScriptedProvider([call('a', 'get_incident_details', args), final('x')])
        r = run_agent('Kiểm tra', p, t, max_steps=4)
        self.assertIn('agent_note', p.histories[1][-1]['content'])
        self.assertIn('429', p.histories[0][0]['content'])
        tool = [e for e in r['trace'] if e['event'] == 'tool'][0]
        self.assertNotIn('agent_note', tool['result'])


if __name__ == '__main__':
    unittest.main()
