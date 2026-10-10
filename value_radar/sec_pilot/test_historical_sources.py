import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from historical_sources import probe

class SourceTests(unittest.TestCase):
    def test_missing_secret_makes_no_request(self):
        with patch('historical_sources.urllib.request.build_opener') as opener:
            r=probe('');opener.assert_not_called()
        self.assertTrue(all(x['status']=='missing_secret' for x in r['endpoints'].values()))
    def test_access_denied_never_serializes_secret_or_error_body(self):
        key='synthetic-sensitive-test-key'
        with patch('historical_sources.urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=HTTPError('https://example.org/?apikey='+key,402,key,{},None)
            r=probe(key)
        self.assertNotIn(key,json.dumps(r));self.assertTrue(all(x['http']==402 for x in r['endpoints'].values()))
        self.assertFalse(r['complete_historical_universe_verified'])

if __name__=='__main__':unittest.main()

