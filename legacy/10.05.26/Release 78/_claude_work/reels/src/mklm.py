import json,re,math,collections,os,pocketsphinx
DICT=set(l.split()[0].split('(')[0] for l in open(os.path.join(os.path.dirname(pocketsphinx.__file__),'model','en-us','cmudict-en-us.dict')))
words=json.load(open('words.json'))
norm=lambda s: re.sub(r"[^a-z0-9']","",s.lower())
# sentences
sents=[];cur=[]
for w in words:
    t=norm(w['w'])
    if t in DICT: cur.append(t)
    if w['p'] and w['p'][-1] in '.?!' and cur: sents.append(['<s>']+cur+['</s>']); cur=[]
if cur: sents.append(['<s>']+cur+['</s>'])
U=collections.Counter(); B=collections.Counter()
for s in sents:
    U.update(s)
    for a,b in zip(s,s[1:]): B[(a,b)]+=1
N=sum(U.values()); V=len(U); D=0.5
uni={w:(c+0.5)/(N+0.5*V) for w,c in U.items()}
uni['<s>']=uni.get('<s>',1e-3)
foll=collections.defaultdict(list)
for (a,b),c in B.items(): foll[a].append((b,c))
lines=['\\data\\',f'ngram 1={len(uni)}',f'ngram 2={len(B)}','','\\1-grams:']
bo={}
for a,lst in foll.items():
    ca=sum(c for b,c in lst); left=D*len(lst)/ca
    bo[a]=math.log10(left/max(1e-9,1-sum(uni[b] for b,c in lst)))
for w,p in uni.items(): lines.append(f'{math.log10(p):.4f} {w} {bo.get(w,0):.4f}')
lines+=['','\\2-grams:']
for (a,b),c in B.items():
    ca=sum(cc for bb,cc in foll[a]); p=(c-D)/ca+ (D*len(foll[a])/ca)*uni[b]
    lines.append(f'{math.log10(p):.4f} {a} {b}')
lines+=['','\\end\\','']
open('shoptalk.lm','w').write('\n'.join(lines)); print('vocab',V,'bigrams',len(B))
