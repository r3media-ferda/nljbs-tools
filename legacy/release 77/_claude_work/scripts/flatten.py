import sys, copy, xml.etree.ElementTree as ET
src,dst=sys.argv[1],sys.argv[2]
r=ET.parse(src).getroot(); main=r.find('sequence')
seqs={}
for s in r.iter('sequence'):
    if s.find('media') is not None: seqs[s.get('id')]=s
files={f.get('id'):f for f in r.iter('file') if len(f)}
out=ET.Element('xmeml',version='4'); ms=ET.SubElement(out,'sequence',id='flat'); ET.SubElement(ms,'name').text='flat'; ET.SubElement(ms,'duration').text=main.findtext('duration')
vid=ET.SubElement(ET.SubElement(ms,'media'),'video')
layers={}
for ti,tr in enumerate(main.findall('media/video/track')):
    if tr.findtext('enabled')!='TRUE': continue
    for c in tr.findall('clipitem'):
        sq=c.find('sequence')
        if sq is None or c.findtext('enabled')!='TRUE': continue
        ang=seqs[sq.get('id')]; s0=int(c.findtext('start')); e0=int(c.findtext('end')); i0=int(c.findtext('in'))
        for aj,atr in enumerate(ang.findall('media/video/track')):
            for ac in atr.findall('clipitem'):
                a_s=int(ac.findtext('start')); a_e=int(ac.findtext('end'))
                lo=max(a_s,i0); hi=min(a_e,i0+(e0-s0))
                if hi<=lo: continue
                cc=copy.deepcopy(ac); fe=cc.find('file')
                cc.remove(fe); cc.append(copy.deepcopy(files[fe.get('id')]))
                cc.find('in').text=str(int(ac.findtext('in'))+(lo-a_s)); cc.find('start').text=str(s0+lo-i0); cc.find('end').text=str(s0+hi-i0)
                layers.setdefault(ti*10+aj,[]).append(cc)
for k in sorted(layers):
    t=ET.SubElement(vid,'track'); [t.append(c) for c in layers[k]]; ET.SubElement(t,'enabled').text='TRUE'
ET.ElementTree(out).write(dst)
