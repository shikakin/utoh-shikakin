#!/usr/bin/env python3
import argparse,json,re,shutil
from pathlib import Path
from PIL import Image,ImageOps

def staff_cards(items, kind):
    cards=[]
    for i,x in enumerate(items,1):
        if not x.get('name','').strip(): continue
        cards.append(f'''<div class="staff-card"><div class="staff-photo"><img alt="{x['name']}" src="assets/{x['photo']}"></div><div class="staff-meta"><div class="staff-position">{x.get('position','')}<br>{x.get('role','')}</div><div class="staff-name">{x['name']}</div></div></div>''')
    return '\n'.join(cards)

def normalize_image(src,dst):
    im=Image.open(src); im=ImageOps.exif_transpose(im).convert('RGB')
    im.thumbnail((1600,1600),Image.Resampling.LANCZOS)
    dst.parent.mkdir(parents=True,exist_ok=True)
    im.save(dst,'JPEG',quality=90,optimize=True)
    Image.open(dst).verify()

def main():
    p=argparse.ArgumentParser();p.add_argument('--master',required=True);p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    cfg=json.loads(Path(a.config).read_text(encoding='utf-8')); out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    master=Path(a.master).read_text(encoding='utf-8'); html=master
    # Only approved text/config replacements.
    html=html.replace('〇〇歯科医院',cfg['clinic_name'])
    replacements={
      'clinicName':cfg['clinic_name'], 'reservationUrl':cfg.get('reservation_url','未設定'),
      'ctaMainUrl':cfg.get('reservation_url','未設定')
    }
    # Replace CONFIG values where keys exist; preserve all unrelated MASTER markup/assets.
    for key,val in replacements.items():
        pat=rf'({re.escape(key)}\s*:\s*)["\'][^"\']*["\']'
        html=re.sub(pat,lambda m:m.group(1)+json.dumps(val,ensure_ascii=False),html,count=1)
    info='<br>'.join(filter(None,[cfg['clinic_name'],cfg.get('address','未設定'),('TEL：'+cfg['phone']) if cfg.get('phone') not in ('',None,'未設定') else 'TEL：未設定',cfg.get('access','未設定'),cfg.get('hours_html','未設定')]))
    html=re.sub(r'(clinicInfoHtml\s*:\s*)["\'].*?["\']\s*,',lambda m:m.group(1)+json.dumps(info,ensure_ascii=False)+',',html,count=1,flags=re.S)
    # Replace staff grid contents only, if MASTER ids are present.
    html=re.sub(r'(<div[^>]+id=["\']doctorStaffGrid["\'][^>]*>).*?(</div>\s*</div>)',lambda m:m.group(1)+staff_cards(cfg.get('doctors',[]),'doctor')+m.group(2),html,count=1,flags=re.S)
    html=re.sub(r'(<div[^>]+id=["\']therapistStaffGrid["\'][^>]*>).*?(</div>\s*</div>)',lambda m:m.group(1)+staff_cards(cfg.get('therapists',[]),'therapist')+m.group(2),html,count=1,flags=re.S)
    # Normalize uploaded people photos; MASTER embedded imagery remains untouched.
    base=Path(a.config).parent
    for group in ('doctors','therapists'):
        for x in cfg.get(group,[]):
            if not x.get('name','').strip(): continue
            normalize_image(base/x['photo'],out/'assets'/x['photo'])
    (out/'index.html').write_text(html,encoding='utf-8')
    shutil.copy2(a.master,out/'_MASTER_snapshot.html')
    print(out/'index.html')
if __name__=='__main__': main()
