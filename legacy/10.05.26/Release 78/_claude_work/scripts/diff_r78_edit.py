import xml.etree.ElementTree as ET, json, sys
F=30000/1001
def tc(f): s=f/F; return f"{int(s//60)}:{s%60:05.2f}"
def load(fn):
    s=ET.parse(fn).getroot().find('sequence')
    items=[]
    for ti,t in enumerate(s.findall('media/video/track')):
        for c in t:
            if c.tag!='clipitem': continue
            n=c.findtext('name') or ''
            if not n.startswith('ANG '): continue
            items.append(dict(tr=ti+1,name=n,ang=int(n.split()[1]),st=int(c.findtext('start')),en=int(c.findtext('end')),
                              inp=int(c.findtext('in')),out=int(c.findtext('out')),on=c.findtext('enabled')=='TRUE'))
    return s,items
so,O=load('orig.xml'); su,U=load('user.xml')
def chosen(items):
    # active angle per main-time segment: enabled ANG clips
    on=[i for i in items if i['on']]
    on.sort(key=lambda x:(x['st'],x['tr']))
    return on
CO=chosen(O); CU=chosen(U)
print('orig shots',len(CO),'user shots',len(CU))
# overlap check: more than one enabled at same time (top one wins)
import collections
# build source-frame -> angle maps (nest in = source frame of body)
def srcmap(ch):
    m={}
    for c in ch:
        for g in range(c['inp'],c['out']): m[g]=c['ang'] if g not in m else max(m[g],c['ang'])  # placeholder
    return m
def srcmap_top(ch):
    m={}
    for c in sorted(ch,key=lambda x:x['tr']):  # higher track wins
        for g in range(c['inp'],c['out']): m[g]=(c['ang'],c['tr'])
    return m
MO=srcmap_top(CO); MU=srcmap_top(CU)
NB=max(max(MO),max(MU))+1
# removed source ranges (in orig, not in user)
def ranges(pred):
    out=[];g=0
    while g<NB:
        if pred(g):
            h=g
            while h<NB and pred(h): h+=1
            out.append((g,h)); g=h
        else: g+=1
    return out
rem=ranges(lambda g: g in MO and g not in MU)
add=ranges(lambda g: g in MU and g not in MO)
print('removed (source/body time):',[(tc(a),tc(b),round((b-a)/F,2)) for a,b in rem])
print('added back:',[(tc(a),tc(b),round((b-a)/F,2)) for a,b in add])
# angle changes
chg=[];g=0
keys=sorted(set(MO)&set(MU))
cur=None
for g in keys:
    a=MO[g][0]; b=MU[g][0]
    k=(a,b) if a!=b else None
    if k and cur and cur[2]==k and cur[1]==g: cur[1]=g+1
    else:
        if cur: chg.append(cur)
        cur=[g,g+1,k] if k else None
if cur: chg.append(cur)
ANG={1:'NICK',2:'GUESTS',3:'WIDE',4:'SPLIT-NICK',5:'SPLIT-GUESTS',6:'TAT+NICKPIP',7:'TAT+GUESTPIP',8:'TAT ONLY',9:'NICK TIGHT',10:'GUESTS TIGHT'}
print('angle changes',len(chg))
tot=collections.Counter()
for a,b,(x,y) in chg:
    tot[(ANG[x],ANG[y])]+=(b-a)/F
    print(f'  body {tc(a)}-{tc(b)} ({(b-a)/F:4.1f}s)  {ANG[x]:13s} -> {ANG[y]}')
print('summary');[print(f'  {k[0]:13s}->{k[1]:13s} {v:6.1f}s') for k,v in sorted(tot.items(),key=lambda x:-x[1])]
def angtime(M):
    c=collections.Counter()
    for g,(a,t) in M.items(): c[ANG[a]]+=1/F
    return c
ao,au=angtime(MO),angtime(MU)
print('angle time orig -> user')
for k in ANG.values(): print(f'  {k:13s} {ao[k]:6.1f} -> {au[k]:6.1f}')
# user enabled clips sitting on disabled track 11 or overlapping
print('user enabled on V11 (disabled track):',[(tc(c['st']),tc(c['en']),c['name']) for c in CU if c['tr']==11])
print('--- by region (body time) ---')
REG=[('talk 0:00-4:47',0,int(287*F)),('screen 4:47-19:04',int(287*F),int(1144*F)),('outro 19:04-end',int(1144*F),NB)]
for nm,a,b in REG:
    co=collections.Counter(); cu=collections.Counter()
    for g in range(a,b):
        if g in MO: co[ANG[MO[g][0]]]+=1/F
        if g in MU: cu[ANG[MU[g][0]]]+=1/F
    print(nm); [print(f'   {k:13s} {co[k]:6.1f} -> {cu[k]:6.1f}') for k in ANG.values() if co[k] or cu[k]]
# shot lengths
import numpy as np
def shots(ch): 
    L=[(c['en']-c['st'])/F for c in ch]; return len(L),round(float(np.median(L)),1)
print('shots/median orig',shots(CO),'user',shots(CU))
