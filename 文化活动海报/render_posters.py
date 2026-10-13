"""Exact-copy bilingual 16:9 poster compositor. Final output requires approval."""
from pathlib import Path
import argparse, hashlib, json, shutil
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT_ROOT = Path('/Users/cici/.codex/skills/cultural-event-poster/assets/fonts')
FONTS = {
    'zh_title': FONT_ROOT/'performance-anime-members/ma-shan-zheng/MaShanZheng-Regular.ttf',
    'zh': FONT_ROOT/'performance-anime-members/source-han-sans-cn/SourceHanSansCN-Regular.otf',
    'zh_bold': FONT_ROOT/'performance-anime-members/source-han-sans-cn/SourceHanSansCN-Medium.otf',
    'en_title': FONT_ROOT/'performance-anime-members/spectral/Spectral-Regular.ttf',
    'en': FONT_ROOT/'performance-anime-members/barlow/Barlow-Regular.ttf',
    'en_bold': FONT_ROOT/'performance-anime-members/barlow/Barlow-Bold.ttf',
}
FONTS = {key: ROOT/'fonts'/path.name if (ROOT/'fonts'/path.name).exists() else path for key,path in FONTS.items()}
S = 2
INK = '#293D39'
CORAL = '#B74830'
GRAY = '#46564F'

def digest(copy):
    return hashlib.sha256(json.dumps(copy,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def render(lang, draft=True):
    master = json.loads((ROOT/'内容母本.json').read_text())
    copy = master['languages'][lang]
    if not draft:
        approval=master['copy_approval'][lang]
        if approval.get('status')!='approved' or not approval.get('confirmed_by') or approval.get('copy_sha256')!=digest(copy):
            raise ValueError('Final output requires explicit human approval of unchanged copy.')
    im=Image.open(ROOT/'主视觉底图.png').convert('RGB').resize((3840,2160),Image.Resampling.LANCZOS)
    d=ImageDraw.Draw(im)
    text_records=[]
    def text(value,x,y,size,font=None,color=INK):
        f=ImageFont.truetype(str(FONTS[font or lang]),round(size*S))
        b=d.textbbox((x*S,y*S),value,font=f,anchor='lt')
        assert b[0]>=0 and b[1]>=0 and b[2]<=3840 and b[3]<=2160,(value,b)
        d.text((x*S,y*S),value,font=f,fill=color,anchor='lt')
        text_records.append({'text':value,'bbox':b})
    def line(points,color,width=1):
        d.line([(int(x*S),int(y*S)) for x,y in points],fill=color,width=round(width*S))
    # Supplied SVG symbol: exact original path geometry; language-specific name follows.
    def logo(x,y):
        scale=.13
        def pts(seq): return [(x+a*scale,y+b*scale) for a,b in seq]
        line(pts([(96,352),(256,76),(416,352),(96,352)]),'#222831',18*scale)
        line(pts([(148,352),(256,168),(364,352),(148,352)]),'#222831',18*scale)
        cx,cy=x+256*scale,y+352*scale;r=28*scale
        d.ellipse(((cx-r)*S,(cy-r)*S,(cx+r)*S,(cy+r)*S),fill='#E87500')
    logo(78,48)
    text(copy['organizer'],151,75,25,font=lang+'_bold')
    line([(90,145),(178,145)],CORAL,3)
    if lang=='zh':
        title,subtitle=copy['title'].split('：',1)
        heritage_label,heritage_name=copy['heritage'].split('：',1)
        craft_label,craft_steps=copy['tagline'].split('：',1)
        hours,closed=copy['hours'].split('；',1)
        text(title,78,206,142,font='zh_title')
        text('：',637,250,50,font='zh_title')
        text(subtitle,90,382,43,font='zh_bold')
        text(heritage_label+'：',90,489,27,color=GRAY)
        text(heritage_name,90,535,34,font='zh_bold')
        line([(90,625),(865,625)],'#A9B3A4',1)
        text(craft_label+'：',90,659,25,color=GRAY)
        process=craft_steps.split('、')
        for i,p in enumerate(process):
            x=90+i*195
            text(p,x,699,49,font='zh_title',color=CORAL)
            if i<3: line([(x+82,727),(x+150,727)],'#9CADA0',1)
        text(copy['dates'],90,816,31,font='zh_bold')
        text(hours+'；',90,871,26,color=GRAY)
        text(closed,90,912,26,color=GRAY)
        text(copy['cta'],90,980,33,font='zh_bold',color=CORAL)
        mark='待核对'
    else:
        title,subtitle=copy['title'].split(': ',1)
        words=title.split()
        subtitle_a,subtitle_b=subtitle.split(' of ',1)
        heritage_label,heritage_name=copy['heritage'].split(': ',1)
        craft_label,craft_steps=copy['tagline'].split(': ',1)
        hours,closed=copy['hours'].rsplit('; ',1)
        text(' '.join(words[:2]),84,209,97,font='en_title')
        text(' '.join(words[2:])+':',84,319,97,font='en_title')
        text(subtitle_a+' of',90,448,37,font='en_bold')
        text(subtitle_b,90,495,37,font='en_bold')
        text(heritage_label+':',90,568,26,color=GRAY)
        text(heritage_name,90,611,33,font='en_bold')
        line([(90,690),(865,690)],'#A9B3A4',1)
        text(craft_label+':',90,723,25,color=GRAY)
        text(craft_steps,90,765,35,font='en_title',color=CORAL)
        text(copy['dates'],90,852,31,font='en_bold')
        text(hours+';',90,903,25,color=GRAY)
        text(closed,90,938,25,color=GRAY)
        text(copy['cta'],90,997,31,font='en_bold',color=CORAL)
        mark='DRAFT / UNCONFIRMED'
    if draft:
        # Obvious review label; never export an unmarked result before approval.
        fw=126 if lang=='zh' else 325
        x=1830-fw
        d.rectangle((x*S,40*S,1830*S,88*S),fill=CORAL)
        text(mark,x+14,53,24,color='#FFF7E8')
    path=ROOT/('风起鸢成_'+lang+('_待核对' if draft else '_正式')+'.png')
    im.save(path,optimize=True,dpi=(300,300))
    preview=im.copy();preview.thumbnail((1440,810))
    preview.save(ROOT/('预览_'+lang+'.jpg'),quality=95)
    (ROOT/('排版检查_'+lang+'.json')).write_text(json.dumps(text_records,ensure_ascii=False,indent=2))
    print(path,im.size,im.mode)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');args=p.parse_args()
    for lang in ['zh','en']:render(lang,not args.final)
