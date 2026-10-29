"""Render the note-type banners in Media/Banners/Note Types/. Needs Pillow.

360x60 logical pixels, nearest-neighbour 5x scale, 72 frames at 90ms.
Usage, from this folder:
    python render_note_banners.py <outdir> [scene ...]
Positions and label shifts come from note_banner_layouts.json (see the
README in the parent folder for its format). Render to a scratch outdir,
review <name>-frames.png and <name>-crops.png, then copy the GIFs into your
banners folder, for example Media/Banners/Note Types.
"""
from pathlib import Path
import json
import math
import random
import sys

from PIL import Image, ImageDraw, ImageChops, ImageStat

HERE = Path(__file__).resolve().parent
LAYOUTS = json.loads((HERE/'note_banner_layouts.json').read_text(encoding='utf-8'))
W, H, SCALE, FRAMES, MS = 360, 60, 5, 72, 90
TAU = math.tau
P = {
    'wall': '#1d2434', 'wall2': '#242d40', 'dark': '#131a28',
    'outline': '#101621', 'wood': '#60442e', 'woodlight': '#896140',
    'wooddark': '#453025', 'paper': '#e5e9f2', 'white': '#faf2db',
    'muted': '#98a6bd', 'steel': '#6f7f99', 'blue': '#6bb8f5',
    'teal': '#6ed4c4', 'green': '#9ac56a', 'orange': '#efb363',
    'pink': '#ed8ca6', 'violet': '#b59ae6', 'ink': '#43536f',
    'skin': '#e8b477', 'skin2': '#b77b4c', 'hair': '#5b392b',
}
FONT = {
    'A': '010/101/111/101/101', 'B': '110/101/110/101/110',
    'C': '011/100/100/100/011', 'D': '110/101/101/101/110',
    'E': '111/100/110/100/111', 'F': '111/100/110/100/100',
    'G': '011/100/101/101/011', 'H': '101/101/111/101/101',
    'I': '111/010/010/010/111', 'J': '001/001/001/101/010',
    'K': '101/101/110/101/101', 'L': '100/100/100/100/111',
    'M': '10001/11011/10101/10101/10101', 'N': '101/111/111/111/101',
    'O': '010/101/101/101/010', 'P': '110/101/110/100/100',
    'Q': '010/101/101/111/011', 'R': '110/101/110/101/101',
    'S': '011/100/010/001/110', 'T': '111/010/010/010/010',
    'U': '101/101/101/101/111', 'V': '101/101/101/101/010',
    'W': '10101/10101/10101/11011/10001', 'X': '101/101/010/101/101',
    'Y': '101/101/010/010/010', 'Z': '111/001/010/100/111',
    '0': '111/101/101/101/111', '1': '010/110/010/010/111',
    '2': '110/001/010/100/111', '3': '110/001/010/001/110',
    '4': '101/101/111/001/001', '5': '111/100/110/001/110',
    '6': '011/100/111/101/111', '7': '111/001/010/010/010',
    '8': '111/101/111/101/111', '9': '111/101/111/001/110',
    ':': '0/1/0/1/0', ' ': '000/000/000/000/000',
}


class Canvas:
    def __init__(self):
        self.im = Image.new('RGB', (W, H), P['wall'])
        self.d = ImageDraw.Draw(self.im)

    def rect(self, x, y, w, h, color):
        x, y, w, h = round(x), round(y), round(w), round(h)
        if w > 0 and h > 0:
            self.d.rectangle((x, y, x+w-1, y+h-1), fill=P.get(color, color))

    def line(self, points, color, width=1):
        self.d.line([(round(x), round(y)) for x, y in points], fill=P.get(color, color), width=width)

    def poly(self, points, color):
        self.d.polygon([(round(x), round(y)) for x, y in points], fill=P.get(color, color))

    def text(self, x, y, text, color='paper'):
        for ch in text.upper():
            rows = FONT[ch].split('/')
            for j, row in enumerate(rows):
                for i, bit in enumerate(row):
                    if bit == '1':
                        self.rect(x+i, y+j, 1, 1, color)
            x += len(rows[0])+1

    def label(self, text, accent):
        width = sum(len(FONT[ch].split('/')[0])+1 for ch in text)-1
        self.rect(180-width//2-4, 10, width+8, 9, 'dark')
        self.text(180-width//2, 12, text, accent)
        self.rect(180-width//2-4, 19, width+8, 1, accent)


def window(c, t, x=14, y=9, width=58, height=29, dawn=False):
    t %= 1
    c.rect(x-2, y-2, width+4, height+4, 'steel')
    c.rect(x, y, width, height, '#19223d' if not dawn else '#555071')
    c.rect(x, y+height-10, width, 10, '#2b354e' if not dawn else '#ba7e83')
    rnd = random.Random(8)
    for i in range(14):
        sx, sy = x+rnd.randrange(width), y+rnd.randrange(max(1, height-12))
        c.rect(sx, sy, 1, 1, 'muted' if math.sin(TAU*(t+i/7)) < 0 else 'white')
    for i in range(9):
        bx, bh = x+i*7, 4+(i*7)%12
        c.rect(bx, y+height-bh, 6, bh, 'dark')
        for wy in range(y+height-bh+2, y+height-1, 3):
            c.rect(bx+2, wy, 1, 1, 'orange' if i%2 else 'muted')
    c.rect(x+width-13, y+4, 5, 5, 'white')
    c.rect(x+width-11, y+3, 4, 4, '#19223d' if not dawn else '#555071')
    c.rect(x+width//2, y, 2, height, 'steel')
    c.rect(x-4, y+height, width+8, 2, 'woodlight')


def plant(c, t, x, y, pot='orange'):
    sway = round(math.sin(TAU*t))
    c.rect(x-5, y-6, 11, 2, pot)
    c.rect(x-4, y-4, 9, 5, pot)
    c.rect(x, y-20, 1, 14, 'green')
    for dx, dy in [(-5, -17), (3, -21), (-4, -12), (4, -15)]:
        c.line([(x, y-8), (x+dx+sway, y+dy)], '#558963')
        c.rect(x+dx+sway-1, y+dy, 3, 2, 'green')


def mug(c, t, x, y, color='paper'):
    c.rect(x, y, 7, 6, color)
    c.rect(x+7, y+1, 3, 4, color)
    c.rect(x+7, y+2, 2, 2, 'wall')
    c.rect(x+1, y, 5, 1, 'wooddark')
    for k in range(3):
        phase = (t*2+k/3)%1
        sx = x+2+round(2*math.sin(TAU*(phase+k/5)))
        c.rect(sx, y-2-round(phase*7), 1, 2, 'steel' if phase < .65 else 'wall2')


def shelves(c, x=285, y=12):
    for sy in (y, y+16):
        c.rect(x-2, sy+12, 57, 2, 'woodlight')
        for i in range(10):
            h = 6+(i*3)%6
            col = ['violet', 'green', 'orange', 'blue', 'pink'][i%5]
            c.rect(x+i*5, sy+12-h, 4, h, col)
            c.rect(x+i*5+1, sy+12-h+2, 2, 1, 'paper')


def clock(c, t, x=311, y=20):
    c.poly([(x-6,y-8),(x+6,y-8),(x+8,y-6),(x+8,y+6),(x+6,y+8),(x-6,y+8),(x-8,y+6),(x-8,y-6)], 'steel')
    c.rect(x-6, y-6, 13, 13, 'paper')
    for dx,dy in [(0,-5),(0,5),(-5,0),(5,0)]: c.rect(x+dx,y+dy,1,1,'ink')
    c.line([(x,y),(x,y-4)], 'ink')
    c.line([(x,y),(x+3,y+2)], 'ink')
    c.line([(x,y),(x+round(5*math.sin(TAU*t)),y-round(5*math.cos(TAU*t)))], 'pink')


def base(t, accent='blue', daylight=False):
    c = Canvas()
    for x in range(0, W, 18): c.rect(x, 0, 1, 45, 'wall2')
    window(c, t, dawn=daylight)
    c.rect(0, 43, W, 3, 'woodlight')
    c.rect(0, 46, W, 14, 'wood')
    for x,y,w in [(12,53,39),(81,49,63),(259,54,52),(175,58,31)]: c.rect(x,y,w,1,'wooddark')
    c.rect(0, 45, W, 1, 'wooddark')
    c.rect(104, 41, 153, 2, 'dark')
    return c


def portrait(c, x, y, shirt='blue', skin='skin', blink=False, size=1):
    # 12x15 miniature portrait; coordinate system deliberately integer-aligned.
    def r(dx,dy,w,h,col): c.rect(x+dx*size,y+dy*size,w*size,h*size,col)
    r(3,0,7,3,'hair'); r(2,2,9,2,'hair'); r(3,3,7,6,skin)
    r(2,4,1,3,skin); r(10,4,1,3,skin)
    if not blink:
        r(4,4,1,1,'ink'); r(8,4,1,1,'ink')
    else:
        r(4,5,2,1,'hair'); r(8,5,2,1,'hair')
    r(6,7,2,1,'white'); r(5,9,3,2,skin)
    r(2,11,9,4,shirt); r(0,13,13,2,shirt)


def person(t):
    c = base(t, 'orange')
    c.label('PERSON', 'orange')
    # One contact card rather than the hub's collection of portraits.
    c.rect(130, 23, 99, 20, 'outline'); c.rect(132, 24, 95, 18, 'paper')
    c.rect(134, 26, 19, 14, '#b8cbda')
    portrait(c, 137, 26, 'blue', blink=(.47 < t < .50))
    c.rect(159, 27, 40, 2, 'ink'); c.rect(159, 31, 59, 1, 'muted')
    c.rect(159, 34, 47, 1, 'muted'); c.rect(159, 37, 32, 1, 'muted')
    c.rect(210, 27, 9, 2, 'green')
    for k in range(3):
        x,y = 96+k*9, 28+(k%2)*6
        c.rect(x,y,6,8,['pink','violet','green'][k])
        c.rect(x+2,y+1,2,1,'white')
    # Photos, plant and gently pulsing connection pins.
    shelves(c)
    plant(c,t,270,43,'pink'); mug(c,t,244,36,'orange')
    for i,(x,y) in enumerate([(116,24),(240,24),(262,18)]):
        c.rect(x,y,3,3,'orange' if math.sin(TAU*(t+i/3)) > .2 else 'woodlight')
    return c.im


def check(c, x, y, phase, color='green'):
    if phase > .18: c.line([(x,y+2),(x+2,y+4)],color)
    if phase > .4: c.line([(x+2,y+4),(x+6,y)],color)


def task(t):
    c = base(t,'teal')
    c.label('TASK', 'teal')
    c.rect(132,23,93,21,'outline'); c.rect(134,24,89,18,'paper')
    c.rect(169,22,20,3,'steel'); c.rect(174,22,10,1,'muted')
    for i in range(3):
        y = 27+i*5
        c.rect(140,y,4,4,'muted'); c.rect(141,y+1,2,2,'paper')
        c.rect(150,y+1,48-i*8,1,'muted')
        if i < 2: check(c,140,y-1,1)
        else: check(c,140,y-1,(1-math.cos(TAU*t))/2)
    c.rect(204,27,12,3,'teal'); c.rect(204,33,12,4,'blue')
    # Laptop and moving three-dot progress indicator.
    c.rect(82,29,31,14,'steel'); c.rect(84,31,27,10,'dark')
    c.rect(86,33,18,1,'blue'); c.rect(86,36,10,1,'teal')
    for i in range(3): c.rect(104+i*2,39,1,1,'teal' if int(t*6)%3==i else 'ink')
    c.rect(79,43,37,1,'muted')
    clock(c,t); plant(c,t,276,43,'orange'); mug(c,t,247,36,'teal')
    return c.im


def bubble(c, x, y, t, phase, color):
    c.rect(x,y,17,7,color); c.rect(x+3,y+7,2,2,color)
    for k in range(3):
        c.rect(x+4+k*4,y+3,2,1,'white' if int((t+phase)*6)%3==k else 'ink')


def meeting(t):
    c = base(t,'violet')
    c.label('MEETING','violet')
    # Three colleagues at a round-table discussion, distinct from video-call hub.
    for i,x in enumerate([143,173,203]):
        portrait(c,x,26,['teal','violet','orange'][i], ['skin2','skin','skin2'][i], .62<t<.65 and i==1)
    c.rect(130,39,100,3,'woodlight'); c.poly([(130,42),(230,42),(240,46),(120,46)],'wooddark')
    for i,x in enumerate([143,177,210]):
        c.rect(x,39,12,3,'paper'); c.rect(x+2,40,7,1,'muted')
    bubble(c,137,19,t,0,'teal'); bubble(c,201,19,t,.33,'violet')
    c.rect(89,23,29,18,'steel'); c.rect(91,25,25,14,'paper')
    for i in range(3):
        c.rect(94,27+i*4,2,2,'ink'); c.rect(100,27+i*4,12-i*2,1,'muted')
    plant(c,t,282,43,'violet'); clock(c,t,314,21)
    mug(c,t,249,36,'paper')
    return c.im


def gear(c, x, y, t, col='blue'):
    c.rect(x-4,y-4,9,9,col); c.rect(x-2,y-2,5,5,'wall')
    for i in range(8):
        a=TAU*(t+i/8)
        c.rect(x+round(5*math.cos(a))-1,y+round(5*math.sin(a))-1,3,3,col)


def project(t):
    c = base(t,'blue')
    c.rect(117,8,128,35,'steel'); c.rect(119,10,124,31,'#24456b')
    for x in range(120,243,6): c.rect(x,10,1,31,'#30577d')
    for y in range(10,41,6): c.rect(119,y,124,1,'#30577d')
    c.label('PROJECT','blue')
    for i in range(4):
        x = 130+i*25
        if i<3: c.line([(x,28),(x+25,28)],'muted')
        c.rect(x-2,26,5,5,'teal' if i<2 else 'blue')
        c.rect(x-1,27,3,3,'wall')
        c.rect(x-5,34,11,2,'muted')
    cursor=130+round(75*(1-math.cos(TAU*t))/2)
    c.rect(cursor-1,24,3,1,'white'); c.rect(cursor-1,31,3,1,'white')
    # Sketch rocket with cycling exhaust beside blueprint.
    c.poly([(266,16),(271,24),(271,33),(261,33),(261,24)],'paper')
    c.rect(264,23,4,4,'blue'); c.rect(265,24,2,2,'dark')
    c.poly([(261,28),(256,35),(262,33)],'pink'); c.poly([(271,28),(276,35),(270,33)],'pink')
    flame = 3+round(2*(1+math.sin(TAU*t*3)))
    c.poly([(263,34),(269,34),(266,34+flame)],'orange')
    gear(c,101,33,t,'blue'); shelves(c,292,10)
    mug(c,t,83,36,'teal')
    return c.im


def reference(t):
    c = base(t,'green')
    c.label('REFERENCE','green')
    shelves(c,88,10); shelves(c,275,10)
    # Open book; a lifted right-hand leaf rocks on a periodic path.
    c.poly([(142,27),(175,30),(175,43),(142,40)],'outline')
    c.poly([(177,30),(210,27),(210,40),(177,43)],'outline')
    c.poly([(144,26),(176,29),(176,41),(144,38)],'white')
    c.poly([(177,29),(208,26),(208,38),(177,41)],'paper')
    for y in (30,33,36):
        c.line([(148,y),(169,y+2)],'muted')
        c.line([(183,y+2),(202,y)],'muted')
    lift=round(3*(1-math.cos(TAU*t))/2)
    c.poly([(178,29),(205,26-lift),(205,38-lift),(178,41)],'#d5dfec')
    for y in (30,33,36): c.line([(184,y+2),(200,y-lift)],'muted')
    c.rect(175,29,2,13,'woodlight'); c.rect(175,38,2,7,'pink')
    # Lamp over book and a little bookmark stack.
    c.rect(230,24,2,18,'steel'); c.rect(222,41,16,2,'steel')
    c.poly([(223,23),(236,23),(239,28),(220,28)],'orange')
    c.rect(224,28,11,1,'white')
    c.rect(247,38,16,3,'violet'); c.rect(247,36,14,2,'paper')
    mug(c,t,120,36,'green')
    return c.im


def envelope(c,x,y,color='paper'):
    c.rect(x,y,25,15,'outline'); c.rect(x+1,y+1,23,13,color)
    c.line([(x+1,y+1),(x+12,y+8),(x+23,y+1)],'muted')
    c.line([(x+1,y+13),(x+8,y+7)],'muted')
    c.line([(x+23,y+13),(x+16,y+7)],'muted')


def communication(t):
    c = base(t,'pink')
    c.label('COMMS','pink')
    c.rect(143,23,67,21,'outline'); c.rect(145,25,63,16,'steel')
    c.rect(147,26,59,14,'dark')
    bubble(c,151,28,t,0,'blue'); bubble(c,182,32,t,.33,'pink')
    c.rect(140,43,73,1,'muted')
    envelope(c,109,28,'white'); envelope(c,223,29,'paper')
    # Tiny signal glides between letter and conversation, returning smoothly.
    x = 136+round(82*(1-math.cos(TAU*t))/2)
    c.rect(x,24,2,2,'pink'); c.rect(x-2,25,1,1,'violet')
    shelves(c,284,9); plant(c,t,269,43,'pink'); mug(c,t,89,36,'blue')
    return c.im


def workout(t):
    c = base(t,'orange',True)
    c.label('WORKOUT','orange')
    # Rack, bench and a gently lifting barbell, all under the crop-safe label.
    c.rect(132,23,3,19,'steel'); c.rect(223,23,3,19,'steel')
    c.rect(131,23,6,2,'muted'); c.rect(221,23,6,2,'muted')
    y=28+round(2*math.sin(TAU*t))
    c.rect(141,y,76,2,'paper')
    for x in (144,151,202,209):
        c.rect(x,y-4,4,10,'dark'); c.rect(x+1,y-4,2,10,'steel')
    c.rect(155,38,49,3,'pink'); c.rect(157,41,3,4,'steel'); c.rect(199,41,3,4,'steel')
    # Wall timer and live pulse display.
    c.rect(88,22,31,18,'outline'); c.rect(90,24,27,14,'dark')
    c.text(92,26,'30:00','green')
    c.line([(92,35),(96,35),(98,32),(101,37),(104,33),(107,35),(114,35)],'teal')
    c.rect(92+round(22*(1-math.cos(TAU*t))/2),35,2,1,'white')
    c.rect(262,21,36,18,'steel'); c.rect(264,23,32,14,'paper')
    for i in range(3):
        c.rect(268,26+i*4,3,3,'muted')
        check(c,268,25+i*4,1 if i<2 else (1-math.cos(TAU*t))/2)
        c.rect(277,27+i*4,14,1,'muted')
    # Bottle and rolled mat.
    c.rect(242,32,6,11,'blue'); c.rect(244,30,2,2,'muted')
    c.rect(310,36,24,7,'violet'); c.rect(313,38,18,1,'wall2')
    plant(c,t,344,43,'green')
    return c.im


SCENES = {
    'person-note': person, 'task-note': task, 'meeting-note': meeting,
    'project-note': project, 'reference-note': reference,
    'communication-note': communication, 'workout-note': workout,
}


def positioned(im, name):
    shift=LAYOUTS[name]['scene-shift']
    if not shift: return im
    result=Image.new('RGB',(W,H),P['wall'])
    d=ImageDraw.Draw(result)
    for x in range(0,W,18): d.line([(x,0),(x,shift)],fill=P['wall2'])
    result.paste(im.crop((0,0,W,H-shift)),(0,shift))
    return result


def simulate(im, pane, layout=None):
    layout=layout or {'banner-height':200,'banner-x':50,'banner-y':50,'content-start':101}
    height=layout['banner-height']
    scale=max(pane/im.width,height/im.height)
    big=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST)
    x=round((big.width-pane)*layout.get('banner-x',50)/100)
    y=round((big.height-height)*layout['banner-y']/100)
    crop=big.crop((x,y,x+pane,y+height)).convert('RGBA')
    # Match the installed Pixel Banner CSS mask and configured -40% fade:
    # opaque through 60% of banner height, then fade to the note background.
    mask=Image.new('L',(pane,height),255)
    md=ImageDraw.Draw(mask)
    for row in range(round(height*.6),height):
        alpha=round(255*(height-1-row)/(height*.4-1))
        md.line([(0,row),(pane,row)],fill=max(0,min(255,alpha)))
    crop.putalpha(mask)
    return Image.alpha_composite(Image.new('RGBA',crop.size,'#1e1e1e'),crop).convert('RGB')


def main():
    if len(sys.argv)<2: sys.exit(__doc__)
    out=Path(sys.argv[1])
    unknown=[name for name in sys.argv[2:] if name not in SCENES]
    if unknown: sys.exit(f'unknown scene(s): {" ".join(unknown)}; choose from {" ".join(SCENES)}')
    selected={name:SCENES[name] for name in (sys.argv[2:] or SCENES)}
    out.mkdir(parents=True,exist_ok=True)
    gallery=Image.new('RGB',(900,len(selected)*177),'#171c28')
    gd=ImageDraw.Draw(gallery)
    for row,(name,fn) in enumerate(selected.items()):
        logical=[positioned(fn(i/FRAMES),name) for i in range(FRAMES)]
        assert fn(0).tobytes()==fn(1).tobytes(), f'{name}: loop is not periodic'
        # One shared palette prevents temporal colour flicker.
        atlas=Image.new('RGB',(W,H*FRAMES))
        for i,im in enumerate(logical): atlas.paste(im,(0,i*H))
        palette=atlas.quantize(colors=128,method=Image.Quantize.MEDIANCUT)
        frames=[im.quantize(palette=palette,dither=Image.Dither.NONE).resize((W*SCALE,H*SCALE),Image.Resampling.NEAREST) for im in logical]
        path=out/(name+'.gif')
        frames[0].save(path,save_all=True,append_images=frames[1:],duration=MS,loop=0,optimize=False,disposal=1)
        with Image.open(path) as gif:
            assert gif.size==(1800,300) and gif.n_frames>1 and gif.info['loop']==0
            encoded_frames=gif.n_frames
            durations=[]
            for i in range(encoded_frames):
                gif.seek(i)
                durations.append(gif.info['duration'])
            assert sum(durations)==FRAMES*MS and all(d%MS==0 for d in durations)
        still=logical[FRAMES//4].resize((1800,300),Image.Resampling.NEAREST)
        gallery.paste(still.resize((900,150),Image.Resampling.NEAREST),(0,row*177+24))
        gd.text((12,row*177+6),name,fill=P['paper'])
        crops=Image.new('RGB',(1900,4*225),'#171c28')
        cd=ImageDraw.Draw(crops)
        for k,pane in enumerate((800,1100,1500,1900)):
            layout=LAYOUTS[name]
            cd.text((8,k*225+5),f'{pane}px pane / Y {layout["banner-y"]}% / X {layout.get("banner-x",50)}% / content at {layout["content-start"]}px / fade -40%',fill=P['paper'])
            crops.paste(simulate(still,pane,layout),(0,k*225+23))
            scale=max(pane/1800,200/300)
            top=round((round(300*scale)-200)*layout['banner-y']/100)/scale/5
            assert top <= 12+layout['scene-shift'], f'{name}: label cropped at {pane}px'
        crops.save(out/(name+'-crops.png'))
        sample=Image.new('RGB',(900,4*155),'#171c28')
        for k,f in enumerate((0,18,36,54)):
            sample.paste(logical[f].resize((900,150),Image.Resampling.NEAREST),(0,k*155))
        sample.save(out/(name+'-frames.png'))
        # Compare wraparound transition to ordinary animation steps.
        def change(a,b): return sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)/3
        wrap=change(logical[-1],logical[0])
        steps=[change(logical[i],logical[(i+1)%FRAMES]) for i in range(FRAMES)]
        assert wrap<=max(steps)+1e-6
        line=f'{name}: {encoded_frames} encoded frames ({FRAMES} sampled), {FRAMES*MS/1000:.2f}s loop, {path.stat().st_size/1024:.0f} KiB, wrap delta {wrap:.3f} (max step {max(steps):.3f})'
        print(line)
    gallery.save(out/'gallery.png')


if __name__=='__main__': main()
