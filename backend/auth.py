"""Local operator sessions and explicit administrator bearer credentials."""
import base64
import hashlib
import hmac
import json
import time
from fastapi import HTTPException

ORIGINS={'http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:8000','http://localhost:8000'}
HOSTS={'127.0.0.1:8000','localhost:8000','127.0.0.1:5173','localhost:5173'}


class Authorization:
    def __init__(self,settings):
        self.settings=settings
        self.mode=settings.get('auth_mode','disabled')

    def origin(self,request):
        if request.headers.get('origin') not in ORIGINS or request.headers.get('host','').lower() not in HOSTS:
            raise HTTPException(403,'Local sessions require an allowed same-site Origin and Host')

    def sign(self,payload):
        raw=base64.urlsafe_b64encode(json.dumps(payload,separators=(',',':')).encode()).decode().rstrip('=')
        signature=hmac.new(self.settings['session_secret'].encode(),raw.encode(),hashlib.sha256).hexdigest()
        return raw+'.'+signature

    def local_session(self,request):
        if self.mode!='local' or request.client.host not in ('127.0.0.1','::1'):
            raise HTTPException(403,'Local operator session is unavailable')
        self.origin(request)
        actor={'id':'local-operator','role':'operator','expires':int(time.time())+8*3600}
        return actor,self.sign(actor)

    def actor(self,request):
        if self.mode=='disabled':return {'id':'embedded-test','role':'admin'}
        header=request.headers.get('authorization','')
        if header.startswith('Bearer '):
            supplied=header[7:]
            for role in ('admin','operator'):
                expected=self.settings.get(role+'_token')
                if expected and hmac.compare_digest(supplied,expected):return {'id':role+'-token','role':role}
            raise HTTPException(401,'Invalid bearer credential')
        token=request.cookies.get('farm_session')
        if token and self.mode=='local':
            try:
                raw,sig=token.rsplit('.',1)
                actual=hmac.new(self.settings['session_secret'].encode(),raw.encode(),hashlib.sha256).hexdigest()
                if not hmac.compare_digest(sig,actual):raise ValueError()
                actor=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
                if actor['expires']<time.time() or actor['role']!='operator':raise ValueError()
                if request.method not in ('GET','HEAD'):self.origin(request)
                return actor
            except (ValueError,KeyError,TypeError):
                raise HTTPException(401,'Expired or invalid local session')
        return {'id':'anonymous','role':'viewer'}

    def require(self,request,role):
        if self.mode=='readonly':raise HTTPException(403,'Server is in read-only mode')
        actor=self.actor(request)
        ranks={'viewer':0,'operator':1,'admin':2}
        if ranks.get(actor['role'],0)<ranks[role]:
            raise HTTPException(401 if actor['role']=='viewer' else 403,'Required role: '+role)
        return actor
