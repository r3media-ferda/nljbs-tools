import json,re
words=json.load(open('words_t.json'))
norm=lambda s: re.sub(r"[^a-z0-9]","",s.lower())
W=[norm(w['w']) for w in words]
def find(phrase,after=0):
    p=[norm(x) for x in phrase.split()]
    for i in range(after,len(W)-len(p)):
        if W[i:i+len(p)]==p: return i
    raise Exception('not found: '+phrase)
def rng(a,b,after=0,**kw):
    i=find(a,after); j=find(b,i)+len(b.split())-1; return dict(r=[i,j],**kw)
BW=[562,587,596,601,609.5,613.5,617.5,621.5]          # black & gray dog portraits on the OBS (mic time)
R=[
 dict(id='01',slug='camera',kind='talk',handle=None,title="He asked me to pause it 17 times",
  hook=rng("he asked me to pause it","seventeen times"),
  body=[rng("he's not the only one that ever thought","a fucking camera"),
        rng("I remember doing one doing an episode","he's like, pause it"),
        rng("So the rest of that podcast","didn't do it"),
        rng("Skivers doing fucking magic tricks","no video at all"),
        rng("You're the next David Blaine","like Tupac, man",end_t=174.2)]),
 dict(id='02',slug='chesko-eyes',kind='tattoo',handle='chadchesko',sect='S1',title="Nobody puts eyes behind the knee",
  hook=rng("You definitely don't appreciate","the eyes become"),
  body=[rng("it just fills the gap","it's so nailed"),
        rng("right in the back of that knee","coming out of the shorts"),
        rng("Go back to the drawing","There's hardly anything there"),
        rng("It's got that, like, old pulp cover","old pulp cover to it"),
        rng("He's ready to take over Richmond","Tesco in Richmond")]),
 dict(id='03',slug='tiger-dogs',kind='tattoo',handle='tiger_ramos',sect='S2',title="He's cheesing so hard he can't breathe",
  hook=rng("that motherfucker's cheesing hard","barely breathe"),
  body=[rng("I'm a huge fan of this lady","it's Tiger Ramos"),
        rng("She just put up some of her doggie","just unbelievable"),
        rng("Textures on the nose","you can't believe it"),
        rng("That guy. Oh, wow.","Happy to be alive"),
        rng("Nobody's ever looked at a corgi","I'm sad",broll=[550.5,576.5])]),
 dict(id='04',slug='bng-holds-heals',kind='tattoo',handle='tiger_ramos',sect='S2',title="Black and gray looks too dark day one",
  hook=rng("I remember getting home and going","way too dark",faces=True),
  body=[rng("this stuff has got the right values","everything's got structure",broll=[596.0,617.5,587.0]),
        rng("yes, it will hold","done right",broll=[621.5,601.0]),
        rng("how many times have you said","lighten up a whole bunch",faces=True),
        rng("The very first black and gray tattoo","I got",faces=True,start_t=1093.5,end_t=1095.85),
        rng("And then two weeks later","softened up just right",faces=True)]),
 dict(id='05',slug='stewart-heal',kind='tattoo',handle='stewart_modernclassic',sect='S3',title="Fresh vs healed on the same backpiece",
  hook=rng("the lower splash is fresh","upper splash is healed"),
  body=[rng("When this tattoo is completely healed","It'll match the top"),
        rng("he's got some good depth in there","in between the splashes"),
        rng("I remember being a customer","really soft gray"),
        rng("I bet you that darker part","create that separation")]),
 dict(id='06',slug='stewart-koi',kind='tattoo',handle='stewart_modernclassic',sect='S3',title="He used rocks like wind bars",
  hook=rng("Look at that elbow","that's a screamer"),
  body=[rng("we hadn't picked a Stuart","all those rocks"),
        rng("It's a koi, like, with lots of rocks","handling his business"),
        rng("he used that rock like you would use","wants it to go"),
        rng("What's still popping for me","on the head"),
        rng("I've always found Stuart's work","striking and so good")]),
 dict(id='07',slug='bathroom-guy',kind='talk',handle=None,title="Shirtless in the bathroom guy",
  hook=rng("you can find me at Porter","shirtless in the bathroom"),
  body=[rng("Mr. Andrew Connor","at Connor"),
        rng("Sometimes he's headphone guy","slippers in the bathroom guy"),
        rng("Sometimes I'm no shirt in the bathroom","Costanza bro"),
        rng("He comes out and he's tucking","What is this?"),
        rng("Anyway, you can find me at Porter","Every time. Every time")]),
]
for r in R:
    tot=0
    for x in [r['hook']]+r['body']:
        a,b=x['r']; s,e=words[a]['s'],words[b]['e']; tot+=e-s
        print(r['id'],f"{s:7.1f}-{e:7.1f} {e-s:5.1f}s |",' '.join(w['w'] for w in words[a:b+1])[:80])
    print('   total ~',round(tot),'s')
# refine.py compatibility: hook/body as [a,b]
legacy=[dict(r,hook=r['hook']['r'],body=[x['r'] for x in r['body']]) for r in R]
json.dump(R,open('specs2.json','w'),indent=1); json.dump(legacy,open('specs.json','w'),indent=1)
