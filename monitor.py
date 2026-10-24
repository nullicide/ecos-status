#!/usr/bin/env python3
"""ECOS public status checks and publishing state. Python standard library only.
External GET monitoring represents endpoint reachability, not backend functionality.
"""
from __future__ import annotations
import datetime as dt
import email.utils
import html
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'site' / 'data' / 'status.json'
FEED = ROOT / 'site' / 'feed.xml'
URL = (os.getenv('ECOS_STATUS_PUBLIC_URL') or 'https://nullicide.github.io/ecos-status/').rstrip('/') + '/'
TARGETS = {
    'website': ('https://www.energycontrolos.com/', ('ENERGY CONTROL OS',)),
    'access': ('https://app.energycontrolos.com/login/', ('Welcome back', 'ENERGY CONTROL OS')),
    'requests': ('https://www.energycontrolos.com/request-access/', ('Request enterprise access', 'ACCESS & EVALUATION', 'Request access')),
}
TITLES = {'website': 'Public website', 'access': 'Enterprise access page', 'requests': 'Request Access page'}
UTC = dt.timezone.utc

def now() -> dt.datetime:
    return dt.datetime.now(UTC)

def iso(value:dt.datetime)->str:
    return value.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00','Z')

def parse(value:str)->dt.datetime:
    if not value: raise ValueError('Missing ISO datetime')
    item=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if item.tzinfo is None: raise ValueError('Include timezone e.g. 2026-11-10T02:00:00Z')
    return item.astimezone(UTC)

def read()->dict:
    # A newly created repository may not contain its initial status file.
    # Initialize only when absent; never overwrite an existing history.
    if not STATE.is_file():
        print('Status history not found; initializing a new, unverified monitoring record.')
        return {
            'schema': 1,
            'checked_at': None,
            'first_checked_at': None,
            'components': {name: {
                'state': 'unknown', 'fail_streak': 0, 'success_streak': 0
            } for name in TARGETS},
            'daily': {},
            'incidents': [],
            'maintenance': [],
        }
    # Invalid existing JSON is a real error; do not silently discard history.
    return json.loads(STATE.read_text(encoding='utf-8'))

def write(data:dict)->None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=False)+'\n',encoding='utf-8')
    rss(data)

def check_http(url:str,fragments:tuple[str,...])->bool:
    """Two GET attempts; a challenge page/soft error cannot count as success."""
    for attempt in range(2):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'ECOS-External-Availability/1.0','Accept':'text/html'})
            with urllib.request.urlopen(req,timeout=12) as response:
                if not 200<=response.status<300: raise ValueError('Non-success status')
                if 'text/html' not in response.headers.get('content-type','').lower(): raise ValueError('Non-HTML response')
                body=response.read(220_000).decode('utf-8',errors='replace')
                if not any(frag.lower() in body.lower() for frag in fragments): raise ValueError('Expected page marker absent')
                if 'http error 403' in body.lower() or 'access to ' in body.lower() and 'was denied' in body.lower():
                    raise ValueError('Intermediary denial body')
                return True
        except (urllib.error.URLError,TimeoutError,ValueError,OSError):
            if attempt==0: time.sleep(1)
    return False

def new_incident(data,component,tstamp):
    if any(not it.get('ended_at') and it.get('component')==component and it.get('origin')=='monitor' for it in data['incidents']):return
    data['incidents'].append({'id':str(uuid.uuid4())[:12],'origin':'monitor','component':component,
       'title':TITLES[component]+' — availability disruption',
       'detail':'Repeated external requests did not return the expected page. Investigation is in progress.',
       'status':'investigating','started_at':tstamp,'ended_at':None,
       'updates':[{'at':tstamp,'status':'investigating','detail':'Repeated external availability checks failed.'}]})

def resolve_auto(data,component,tstamp):
    for i in data['incidents']:
        if i.get('origin')=='monitor' and i.get('component')==component and not i.get('ended_at'):
            i['ended_at']=tstamp;i['status']='resolved'
            i['detail']='External endpoint checks have returned to normal. This does not validate application functions.'
            i.setdefault('updates',[]).append({'at':tstamp,'status':'resolved','detail':i['detail']})

def monitor(data:dict,results:dict[str,bool],instant:dt.datetime)->dict:
    stamp=iso(instant)
    if not data.get('first_checked_at'):data['first_checked_at']=stamp
    data['checked_at']=stamp
    day=instant.date().isoformat();daily=data.setdefault('daily',{}).setdefault(day,{})
    for name in TARGETS:
        passed=bool(results[name]);obj=data['components'].setdefault(name,{})
        prior=obj.get('state','unknown')
        if passed:
            obj['success_streak']=obj.get('success_streak',0)+1
            obj['fail_streak']=0
            obj['state']='operational' if obj['success_streak']>=2 or prior in ('unknown','operational') else 'degraded'
            if obj['state']=='operational':resolve_auto(data,name,stamp)
        else:
            obj['fail_streak']=obj.get('fail_streak',0)+1
            obj['success_streak']=0
            obj['state']='outage' if obj['fail_streak']>=2 else 'degraded'
            if obj['state']=='outage':new_incident(data,name,stamp)
        stats=daily.setdefault(name,{'ok':0,'fail':0})
        stats['ok' if passed else 'fail']+=1
    cutoff=(instant-dt.timedelta(days=90)).date().isoformat()
    data['daily']={d:v for d,v in data['daily'].items() if d>=cutoff}
    data['incidents']=data['incidents'][-180:]
    return data

def manual(data:dict,action:str,component:str,title:str,detail:str,start:str,end:str,instant:dt.datetime)->dict:
    stamp=iso(instant)
    title=title.strip()[:160];detail=detail.strip()[:1800]
    if component not in TARGETS:raise ValueError('Unrecognized component')
    if action in ('incident_open','incident_update','maintenance_schedule') and not title and action!='incident_update':raise ValueError('Title required')
    if action=='incident_open':
        data['incidents'].append({'id':str(uuid.uuid4())[:12],'origin':'manual','component':component,'title':title,'detail':detail,'status':'investigating','started_at':stamp,'ended_at':None,
           'updates':[{'at':stamp,'status':'investigating','detail':detail}]})
    elif action in ('incident_update','incident_resolve'):
        open_items=[i for i in data['incidents'] if i['component']==component and not i.get('ended_at')]
        if not open_items:raise ValueError('No open incident for the selected component')
        obj=open_items[-1]
        if title:obj['title']=title
        if detail:obj['detail']=detail
        if action=='incident_resolve':obj['ended_at']=stamp;obj['status']='resolved'
        else:obj['status']='identified'
        obj.setdefault('updates',[]).append({'at':stamp,'status':obj['status'],'detail':detail or ('Incident resolved.' if obj['status']=='resolved' else 'Incident update published.')})
    elif action=='maintenance_schedule':
        begins=parse(start);ends=parse(end)
        if ends<=begins:raise ValueError('Maintenance end must be after start')
        data['maintenance'].append({'id':str(uuid.uuid4())[:12],'component':component,'title':title,'detail':detail,'starts_at':iso(begins),'ends_at':iso(ends),'completed_at':None})
    elif action=='maintenance_complete':
        items=[m for m in data['maintenance'] if m['component']==component and not m.get('completed_at')]
        if not items:raise ValueError('No active/scheduled maintenance record')
        items[-1]['completed_at']=stamp
    else:raise ValueError('Unknown action')
    return data

def rss(data:dict)->None:
    channel=ET.Element('rss',version='2.0');ch=ET.SubElement(channel,'channel')
    for k,v in [('title','Energy Control OS — Status Updates'),('link',URL),('description','Public incidents and maintenance notices for Energy Control OS.'),('language','en-us')]:ET.SubElement(ch,k).text=v
    entries=[]
    for i in data.get('incidents',[]):
        updated=(i.get('updates') or [{}])[-1]
        entries.append((updated.get('at') or i.get('started_at',''),i.get('id','')+'-'+str(len(i.get('updates',[]))),i.get('title',''),updated.get('detail') or i.get('detail',''),i.get('status',''),i.get('ended_at')))
    for m in data.get('maintenance',[]):entries.append((m.get('starts_at',''),m.get('id',''),m.get('title',''),m.get('detail',''),'scheduled',m.get('completed_at')))
    for stamp,ident,title,detail,status,ended in sorted(entries,key=lambda x:x[0],reverse=True)[:25]:
        if not stamp:continue
        item=ET.SubElement(ch,'item')
        ET.SubElement(item,'title').text=title+' — '+('Resolved' if ended else status.title())
        ET.SubElement(item,'description').text=detail
        ET.SubElement(item,'link').text=URL+'#incidents'
        ET.SubElement(item,'guid',isPermaLink='false').text='ecos-'+ident
        ET.SubElement(item,'pubDate').text=email.utils.format_datetime(parse(stamp))
    ET.indent(channel,'  ')
    FEED.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(channel,encoding='utf-8')+b'\n')

def alert_operator(message:str)->None:
    endpoint=os.getenv('ECOS_STATUS_ALERT_WEBHOOK','').strip()
    if not endpoint:return
    if not endpoint.startswith('https://'):
        print('Warning: alert webhook must use HTTPS; notification skipped')
        return
    packet=json.dumps({'text':message,'content':message}).encode('utf-8')
    req=urllib.request.Request(endpoint,data=packet,headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=10) as response:
            print('Alert notification attempted; response HTTP',response.status)
    except (urllib.error.URLError,TimeoutError,OSError) as error:
        print('Warning: alert delivery failed:',type(error).__name__)

def main():
    data=read();action=os.getenv('ACTION','check').strip() or 'check';instant=now()
    previous={name:obj.get('state','unknown') for name,obj in data['components'].items()}
    if action=='check':
        results={name:check_http(*target) for name,target in TARGETS.items()}
        print('External checks:',', '.join(f'{name}={"reachable" if passed else "unreachable"}' for name,passed in results.items()))
        monitor(data,results,instant)
        changes=[f'{TITLES[name]}: {previous[name]} -> {data["components"][name]["state"]}'
                 for name in TARGETS if previous[name]!=data['components'][name]['state'] and (previous[name] not in ('unknown','operational') or data['components'][name]['state'] in ('degraded','outage'))]
        if changes:alert_operator('ECOS external status check: '+ '; '.join(changes)+' · '+URL)
    else:
        manual(data,action,os.getenv('COMPONENT','website'),os.getenv('TITLE',''),os.getenv('MESSAGE',''),os.getenv('START_UTC',''),os.getenv('END_UTC',''),instant)
        alert_operator('ECOS status publication: '+action+' / '+os.getenv('COMPONENT','website')+' · '+URL)
    write(data)
    print('Wrote public status data at',iso(instant))

if __name__=='__main__': main()
