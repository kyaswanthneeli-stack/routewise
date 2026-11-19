"""Run with python -m unittest test_public_demo."""
import unittest
import httpx
from fastapi.testclient import TestClient
from app import create_app, Provider

class PublicDemoTests(unittest.TestCase):
    def client(self, handler):
        return TestClient(create_app({'fast': Provider('fast','https://example.test/v1','private-test-key','model')}, httpx.MockTransport(handler),'gateway-key'))

    def test_generation_cache_and_private_auth(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(200,json={'choices':[{'message':{'content':'Test answer'}}]})
        client=self.client(handler)
        first=client.post('/public/demo',json={'example':'rag'})
        self.assertEqual(first.status_code,200)
        self.assertFalse(first.json()['cached'])
        self.assertNotIn('private-test-key',first.text)
        self.assertTrue(client.post('/public/demo',json={'example':'rag'}).json()['cached'])
        self.assertEqual(len(calls),1)
        self.assertEqual(client.post('/public/demo',json={'example':'arbitrary'}).status_code,422)
        self.assertEqual(client.post('/v1/chat/completions',json={'messages':[{'role':'user','content':'hello'}]}).status_code,401)

    def test_failed_calls_count_toward_limit(self):
        client=self.client(lambda request: httpx.Response(429))
        for _ in range(6):
            self.assertEqual(client.post('/public/demo',json={'example':'rag'}).status_code,503)
        self.assertEqual(client.post('/public/demo',json={'example':'rag'}).status_code,429)

    def test_no_fixture_when_unconfigured(self):
        client=TestClient(create_app({},api_key='test'))
        self.assertEqual(client.post('/public/demo',json={'example':'rag'}).status_code,503)

if __name__=='__main__':
    unittest.main()
