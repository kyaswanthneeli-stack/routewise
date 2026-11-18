import unittest
import httpx
from fastapi.testclient import TestClient
from app import create_app,Provider
class Tests(unittest.TestCase):
 def setUp(self):self.c=TestClient(create_app({},api_key='test'));self.h={'Authorization':'Bearer test'};self.req={'messages':[{'role':'user','content':'hello'}]}
 def post(self,c=None):return (c or self.c).post('/v1/chat/completions',json=self.req,headers=self.h)
 def test_auth(self):self.assertEqual(self.c.post('/v1/chat/completions',json=self.req).status_code,401)
 def test_simple(self):self.assertEqual(self.post().json()['routing']['selected'],'fast')
 def test_complex(self):self.req['messages'][0]['content']='Analyze tradeoffs';self.assertEqual(self.post().json()['routing']['selected'],'reasoning')
 def test_override(self):self.req['model']='reasoning';self.assertEqual(self.post().json()['routing']['selected'],'reasoning')
 def test_stream_rejected(self):self.req['stream']=True;self.assertEqual(self.post().status_code,400)
 def test_unknown_model(self):self.req['model']='fake';self.assertEqual(self.post().status_code,400)
 def test_demo_label(self):self.assertTrue(self.post().json()['routing']['demo'])
 def test_unknown_cost(self):self.assertIsNone(self.post().json()['routing']['estimated_cost_usd'])
 def client(self,handler):return TestClient(create_app({'fast':Provider('fast','https://fast.test/v1','k','small'),'reasoning':Provider('reasoning','https://reason.test/v1','k','large')},httpx.MockTransport(handler),api_key='test'))
 def test_fallback(self):
  def handler(req):return httpx.Response(429) if req.url.host=='fast.test' else httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'ok'}}]})
  result=self.post(self.client(handler));self.assertEqual(result.status_code,200);self.assertEqual(result.json()['routing']['attempts'],['fast','reasoning'])
 def test_timeout_fallback(self):
  def handler(req):
   if req.url.host=='fast.test':raise httpx.ReadTimeout('timeout')
   return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'ok'}}]})
  self.assertEqual(self.post(self.client(handler)).json()['routing']['selected'],'reasoning')
 def test_all_down(self):self.assertEqual(self.post(self.client(lambda req:httpx.Response(503))).status_code,503)
 def test_auth_failure_not_retried(self):
  seen=[]
  def handler(req):seen.append(req.url.host);return httpx.Response(401)
  self.assertEqual(self.post(self.client(handler)).status_code,502);self.assertEqual(len(seen),1)
 def test_bad_response(self):self.assertEqual(self.post(self.client(lambda req:httpx.Response(200,json={'bad':1}))).status_code,502)
 def test_no_prompt_metrics(self):self.post();self.assertNotIn('hello',self.c.get('/metrics',headers=self.h).text)

 def test_public_route_is_real_server_classification(self):
  response=self.c.post('/public/route',json={'text':'Analyze architecture tradeoffs'})
  self.assertEqual(response.status_code,200)
  body=response.json()
  self.assertEqual(body['selected'],'reasoning')
  self.assertEqual(body['routing']['method'],'deterministic heuristic')
  self.assertEqual(body['provider_calls_executed'],0)
  self.assertIsNone(body['model_response'])
 def test_public_route_uses_override_and_validates(self):
  result=self.c.post('/public/route',json={'text':'hello','preference':'reasoning'})
  self.assertEqual(result.json()['selected'],'reasoning')
  self.assertEqual(self.c.post('/public/route',json={'text':'hello','preference':'bad'}).status_code,422)
  self.assertEqual(self.c.post('/public/route',json={'text':'x'*4001}).status_code,422)
 def test_public_status_distinguishes_model_config(self):
  self.assertEqual(self.c.get('/public/status').json()['provider_calls_available'],False)
 def test_public_cors_allows_portfolio_only(self):
  r=self.c.options('/public/route',headers={'origin':'https://kyaswanthneeli-stack.github.io','access-control-request-method':'POST'})
  self.assertEqual(r.headers.get('access-control-allow-origin'),'https://kyaswanthneeli-stack.github.io')

if __name__=='__main__':unittest.main()
