import certifi; certifi.where=lambda: "/root/.ccr/ca-bundle.crt"
import asyncio,edge_tts,requests,json,subprocess,sys,textwrap,os,urllib.request,ssl
from PIL import Image,ImageDraw,ImageFont
from gtts import gTTS
os.environ["REQUESTS_CA_BUNDLE"]="/root/.ccr/ca-bundle.crt"
ctx=ssl.create_default_context(cafile="/root/.ccr/ca-bundle.crt")
KEY=os.environ["PIXABAY_KEY"]
spec=json.load(open(sys.argv[1])); out=sys.argv[2]
B="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def run(*a): subprocess.run(["ffmpeg","-y","-loglevel","error",*a],check=True)
used=set(); segs=[]
for i,s in enumerate(spec["cenas"]):
    asyncio.run(edge_tts.Communicate(s["fala"],"pt-BR-AntonioNeural",rate="+10%").save(f"b{i}.mp3"))
    dur=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f"b{i}.mp3"]))+0.3
    hits=[]
    if s.get("id"): hits=requests.get("https://pixabay.com/api/videos/",params=dict(key=KEY,id=s["id"]),timeout=30).json()["hits"]
    for q in ([] if hits else s["busca"]):
        d=requests.get("https://pixabay.com/api/videos/",params=dict(key=KEY,q=q,per_page=20,safesearch="true"),timeout=30).json()
        hits+= [h for h in d["hits"] if h["id"] not in used]
    h=hits[0]; used.add(h["id"])
    v=h["videos"]["medium"]["url"] or h["videos"]["small"]["url"]
    open(f"c{i}.mp4","wb").write(requests.get(v,timeout=120).content)
    im=Image.new("RGBA",(1080,1920),(0,0,0,0)); d=ImageDraw.Draw(im)
    d.rectangle([0,0,1080,150],fill=(0,0,0,170))
    d.text((40,50),spec["marca"],font=ImageFont.truetype(B,40),fill=(255,170,0))
    f=ImageFont.truetype(B,76 if i==0 else 62); lines=textwrap.wrap(s["tela"],20 if i==0 else 24)
    y=1250; d.rectangle([0,y-40,1080,y+len(lines)*90+(70 if s.get("sub") else 0)+40],fill=(0,0,0,175))
    for l in lines:
        w=d.textlength(l,font=f); d.text(((1080-w)/2,y),l,font=f,fill=(255,255,255),stroke_width=3,stroke_fill=(0,0,0)); y+=90
    if s.get("sub"):
        f2=ImageFont.truetype(B,44)
        for l in textwrap.wrap(s["sub"],36):
            w=d.textlength(l,font=f2); d.text(((1080-w)/2,y+10),l,font=f2,fill=(255,200,90)); y+=58
    im.save(f"o{i}.png")
    run("-stream_loop","-1","-i",f"c{i}.mp4","-i",f"o{i}.png","-i",f"b{i}.mp3","-t",str(dur),
        "-filter_complex","[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30[v];[v][1:v]overlay=0:0[o]",
        "-map","[o]","-map","2:a","-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p","-c:a","aac","-ar","44100","-ac","2",f"s{i}.mp4")
    segs.append(f"s{i}.mp4")
open("list.txt","w").write("".join(f"file '{x}'\n" for x in segs))
run("-f","concat","-safe","0","-i","list.txt","-c","copy",out)
