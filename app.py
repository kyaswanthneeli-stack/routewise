"""RouteWise: explicit heuristic routing with an optional OpenAI-shaped upstream."""
import asyncio
import hmac
import os
import time
import uuid
from dataclasses import dataclass
import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

class Message(BaseModel):
    role: str = Field(pattern=r'^(system|user|assistant)$')
    content: str = Field(max_length=16000)
class Chat(BaseModel):
    model: str = 'auto'
    messages: list[Message] = Field(min_length=1,max_length=30)
    max_tokens: int = Field(default=256,ge=1,le=4096)
    stream: bool = False

def classify(messages):
    text=' '.join(m.content for m in messages if m.role=='user').lower()
    signals=[word for word in ['prove','architecture','tradeoff','debug','multi-step','analyze','analyse'] if word in text]
    complex_request=len(text)>600 or bool(signals)
    return ('reasoning' if complex_request else 'fast'), {'method':'deterministic heuristic','signals':signals,'characters':len(text)}

@dataclass
class Provider:
    name:str
    url:str=''
    key:str=''
    model:str=''
    input_per_million:float=0.0
    output_per_million:float=0.0

class Retryable(Exception): pass

def create_app(providers=None, transport=None, api_key=None):
    api_key=api_key or os.getenv('ROUTEWISE_API_KEY')
    if providers is None:
        providers={}
        for tier in ['fast','reasoning']:
            prefix=tier.upper()
            url=os.getenv(prefix+'_BASE_URL','')
            if url:
                if not url.startswith('https://'): raise ValueError('Upstream URLs must use HTTPS')
                providers[tier]=Provider(tier,url,os.getenv(prefix+'_API_KEY',''),os.getenv(prefix+'_MODEL',''))
    app=FastAPI(title='RouteWise',version='0.2.0'); metrics=[]; lock=asyncio.Lock()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['https://kyaswanthneeli-stack.github.io'],
        allow_methods=['GET', 'POST'],
        allow_headers=['content-type'],
    )
    class PublicRoute(BaseModel):
        text: str = Field(min_length=1, max_length=4000)
        preference: str = Field(default='auto', pattern='^(auto|fast|reasoning)$')
    @app.get('/public/status')
    def public_status():
        return {'status':'ok','routing':'operational','provider_calls_available': bool(providers),
                'model_inference':'configured' if providers else 'not_configured'}
    @app.post('/public/route')
    def public_route(payload:PublicRoute):
        # This public endpoint computes only actual route decisions; never invokes upstream providers.
        tier, reason=classify([Message(role='user',content=payload.text)])
        if payload.preference != 'auto':
            tier=payload.preference
            reason={'method':'explicit override','signals':[],'characters':len(payload.text)}
        other='reasoning' if tier=='fast' else 'fast'
        return {'selected':tier,'alternate':other,'routing':reason,
                'provider_calls_executed':0,'model_response':None,
                'mode':'real_server_side_route_decision',
                'note':'This endpoint computes real routing decisions without calling a model. '
                       'LLM completions require private upstream provider configuration.'}
    async def invoke(provider,request):
        if not provider.url: return {'choices':[{'index':0,'message':{'role':'assistant','content':f'Demo response from {provider.name}; no language model was called.'},'finish_reason':'stop'}],'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}
        async with httpx.AsyncClient(timeout=15,transport=transport,follow_redirects=False) as client:
            try:
                response=await client.post(provider.url.rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+provider.key},json={'model':provider.model,'messages':[m.model_dump() for m in request.messages],'max_tokens':request.max_tokens,'stream':False})
            except (httpx.TimeoutException,httpx.NetworkError) as exc: raise Retryable() from exc
        if response.status_code==429 or response.status_code>=500: raise Retryable()
        if response.status_code>=300: raise HTTPException(502,'Upstream rejected request; credentials and payload not logged')
        try:
            data=response.json()
            if not isinstance(data.get('choices'),list) or not data['choices']: raise ValueError()
            return data
        except (ValueError,AttributeError): raise HTTPException(502,'Invalid upstream response')
    @app.get('/health')
    def health(): return {'status':'ok','mode':'live' if providers else 'demo'}
    def authorize(key):
        if not api_key or not key or not hmac.compare_digest(key,'Bearer '+api_key): raise HTTPException(401,'Valid bearer token required')
    @app.post('/v1/chat/completions')
    async def chat(request:Chat,authorization:str|None=Header(default=None)):
        authorize(authorization)
        if request.stream: raise HTTPException(400,'Streaming is not implemented')
        if request.model not in {'auto','fast','reasoning'}: raise HTTPException(400,'Use model auto, fast or reasoning')
        if sum(len(m.content) for m in request.messages)>64000: raise HTTPException(413,'Conversation too large')
        tier,reason=classify(request.messages)
        if request.model!='auto': tier=request.model;reason={'method':'explicit override'}
        other='reasoning' if tier=='fast' else 'fast'
        pool=providers or {t:Provider(t) for t in ['fast','reasoning']}
        candidates=[pool[t] for t in [tier,other] if t in pool]
        attempts=[];start=time.perf_counter()
        for provider in candidates:
            attempts.append(provider.name)
            try: data=await invoke(provider,request)
            except Retryable: continue
            elapsed=round((time.perf_counter()-start)*1000,3)
            usage=data.get('usage') or {}
            # Prices default to zero / unknown; never imply actual provider prices or savings.
            estimate=None
            if provider.input_per_million or provider.output_per_million:
                estimate=(usage.get('prompt_tokens',0)*provider.input_per_million+usage.get('completion_tokens',0)*provider.output_per_million)/1_000_000
            route={'selected':provider.name,'attempts':attempts,'reason':reason,'latency_ms':elapsed,'demo':not bool(providers),'estimated_cost_usd':estimate}
            async with lock:
                metrics.append(route);del metrics[:-200]
            return {**data,'id':data.get('id','chatcmpl-'+uuid.uuid4().hex),'object':'chat.completion','created':int(time.time()),'model':provider.model or provider.name,'routing':route}
        raise HTTPException(503,'All configured providers unavailable')
    @app.get('/metrics')
    async def stats(authorization:str|None=Header(default=None)):
        authorize(authorization)
        async with lock: return {'requests':list(metrics),'retention':200,'prompt_logging':False}
    return app
app=create_app()
