import os,json,datetime,urllib.request,urllib.parse,math
from pathlib import Path
ROOT=Path(__file__).parent
KEY=os.environ.get('FOOTBALL_DATA_TOKEN','')
if not KEY: raise SystemExit('Missing FOOTBALL_DATA_TOKEN secret')
now=datetime.datetime.now(datetime.timezone.utc)
start=(now-datetime.timedelta(days=1)).date().isoformat(); end=(now+datetime.timedelta(days=7)).date().isoformat()
comps={'PL':'Premier League','PD':'La Liga','BL1':'Bundesliga','SA':'Serie A','FL1':'Ligue 1','DED':'Eredivisie','PPL':'Primeira Liga','CL':'Liga Mistrzów','ELC':'Championship'}
allmatches=[]; errors=[]
for code,league in comps.items():
 try:
  url=f'https://api.football-data.org/v4/competitions/{code}/matches?'+urllib.parse.urlencode({'dateFrom':start,'dateTo':end})
  req=urllib.request.Request(url,headers={'X-Auth-Token':KEY})
  with urllib.request.urlopen(req,timeout=22) as resp: data=json.load(resp)
  for m in data.get('matches',[]):
   allmatches.append({'id':m['id'],'league':league,'utc':m.get('utcDate'),'home':m.get('homeTeam',{}).get('name') or 'Do ustalenia','away':m.get('awayTeam',{}).get('name') or 'Do ustalenia','status':m.get('status'),'score':m.get('score',{}).get('fullTime',{})})
 except Exception as e: errors.append(f'{code}: {type(e).__name__} {e}')
# No synthetic predictions or fake expert tips: unavailable means unavailable.
if not allmatches: raise SystemExit('No match data received; preserving previous snapshot. '+ '; '.join(errors))
allmatches.sort(key=lambda m:m.get('utc') or '')
result={'updatedAt':now.isoformat(),'source':'football-data.org','matches':allmatches,'errors':errors,'predictions':[]}
(ROOT/'data.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Updated {len(allmatches)} matches; errors: {len(errors)}')
