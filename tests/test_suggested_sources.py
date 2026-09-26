import json
from pathlib import Path
import unittest
from scripts import update_playlists as u

ROOT = Path(__file__).resolve().parents[1]


class SuggestedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.sources = json.loads((ROOT / 'config/sources.json').read_text())['sources'][-2:]
        self.policy = json.loads((ROOT / 'config/policy.json').read_text())

    def test_exact_aliases_pass_existing_policy(self):
        for source in self.sources:
            for alias in source['entry_aliases']:
                with self.subTest(name=alias['from_name']):
                    c, reason = u.channel_from_entry(
                        {'tvg-id': alias['from_id']}, alias['from_name'],
                        alias['url'], source, self.policy, False)
                    self.assertEqual(reason, 'accepted')
                    self.assertEqual(c['id'], alias['id'])
                    self.assertEqual(c['name'], alias['name'])

    def test_alias_is_source_name_id_and_url_scoped(self):
        source = self.sources[0]
        alias = source['entry_aliases'][0]
        attrs = {'tvg-id': alias['from_id']}
        for a, name, url, src in [
            (attrs, 'Different', alias['url'], source),
            (attrs, alias['from_name'], alias['url'] + '?different=1', source),
            ({'tvg-id': 'unmapped'}, alias['from_name'], alias['url'], source),
            (attrs, alias['from_name'], alias['url'], {'name': 'other', 'url': source['url']}),
        ]:
            self.assertIsNone(u.channel_from_entry(a, name, url, src, self.policy, False)[0])

    def test_alias_cannot_bypass_headers_country_or_exclusion(self):
        source = self.sources[0]
        alias = source['entry_aliases'][0]
        args = ({'tvg-id': alias['from_id']}, alias['from_name'], alias['url'], source)
        self.assertEqual(u.channel_from_entry(*args, self.policy, True)[1], 'custom_headers')
        policy = {**self.policy, 'excluded_ids': [alias['id']]}
        self.assertEqual(u.channel_from_entry(*args, policy, False)[1], 'excluded_pay_tv')
        attrs = {**args[0], 'tvg-country': 'GB'}
        self.assertEqual(u.channel_from_entry(attrs, *args[1:], self.policy, False)[1], 'not_us_or_no_id')
