import json,re
words=json.load(open('words_r.json'))
norm=lambda s: re.sub(r"[^a-z0-9]","",s.lower())
W=[norm(w['w']) for w in words]
def find(phrase,after=0):
    p=[norm(x) for x in phrase.split()]
    for i in range(after,len(W)-len(p)):
        if W[i:i+len(p)]==p: return i
    raise Exception('not found: '+phrase)
def rng(a,b,after=0):
    i=find(a,after); j=find(b,i)+len(b.split())-1; return [i,j]
R=[
 dict(id='01',slug='camera',kind='talk',handle=None,
      title="He asked me to pause it 17 times",
      hook=rng("And every time I pretended","didn't do it"),
      body=[rng("he's not the only one that ever thought","handful of them motherfuckers did"),
            rng("I remember doing one doing an episode","didn't do it"),
            rng("Skivers doing fucking magic tricks","like Tupac, man")]),
 dict(id='02',slug='chesko-eyes',kind='tattoo',handle='chadchesko',sect='S1',
      title="Nobody puts eyes behind the knee",
      hook=rng("You definitely don't appreciate","the eyes become"),
      body=[rng("it just fills the gap","it's so nailed"),
            rng("create another focal point","coming out of the shorts"),
            rng("Go back to the drawing","I fucking love that")]),
 dict(id='03',slug='tiger-dogs',kind='tattoo',handle='tiger_ramos',sect='S2',
      title="He's cheesing so hard he can't breathe",
      hook=rng("that motherfucker's cheesing hard","barely breathe"),
      body=[rng("She just put up some of her doggie","just unbelievable"),
            rng("But look how good some of these","you can't believe it"),
            rng("That guy. Oh, wow.","Happy to be alive"),
            rng("That looks like my old dog","Holy shit")]),
 dict(id='04',slug='tiger-bng-holds',kind='tattoo',handle='tiger_ramos',sect='S2',
      title="Will a black and gray dog portrait hold?",
      hook=rng("yes, it will hold","done right"),
      body=[rng("this stuff has got the right values","done right"),
            rng("The hairs that or the covering","been like, I'm sad")]),
 dict(id='05',slug='stewart-heal',kind='tattoo',handle='stewart_modernclassic',sect='S3',
      title="\"He f*cked it, it's way too dark\"",
      hook=rng("I remember getting home and going","way too dark"),
      body=[rng("the lower splash is fresh","pre and post heal"),
            rng("how many times have you said","softened up just right"),
            rng("when I got that cat on the back","healed beautifully")]),
 dict(id='06',slug='stewart-koi',kind='tattoo',handle='stewart_modernclassic',sect='S3',
      title="He used rocks like wind bars",
      hook=rng("Look at that elbow","that's a screamer"),
      body=[rng("It's a koi, like, with lots of rocks","how simple it is"),
            rng("Those darks in behind there","that's a screamer")]),
 dict(id='07',slug='bathroom-guy',kind='talk',handle=None,
      title="Shirtless in the bathroom guy",
      hook=rng("you can find me at Porter","shirtless in the bathroom"),
      body=[rng("Mr. Andrew Connor","in real life"),
            rng("Sometimes he's headphone guy","shirtless in the bathroom"),
            rng("Yep yep yep. Every time","Every time. Yeah")]),
]
for r in R:
    tot=0
    for a,b in [r['hook']]+r['body']:
        s,e=words[a]['s'],words[b]['e']; tot+=e-s
        print(r['id'],f"{int(s//60)}:{s%60:05.2f}-{int(e//60)}:{e%60:05.2f} {e-s:5.1f}s |",' '.join(w['w'] for w in words[a:b+1])[:90])
    print('   total ~',round(tot),'s')
json.dump(R,open('specs.json','w'),indent=1)
