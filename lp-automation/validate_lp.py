#!/usr/bin/env python3
import argparse,json,re,sys
from pathlib import Path
from PIL import Image

def main():
 p=argparse.ArgumentParser();p.add_argument('--dir',required=True);p.add_argument('--config',required=True);a=p.parse_args();d=Path(a.dir);cfg=json.loads(Path(a.config).read_text(encoding='utf-8'));h=(d/'index.html').read_text(encoding='utf-8');errs=[]
 if '〇〇歯科医院' in h: errs.append('〇〇歯科医院が残存')
 if cfg['clinic_name'] not in h: errs.append('医院名未反映')
 for x in cfg.get('doctors',[])+cfg.get('therapists',[]):
  if not x.get('name','').strip(): continue
  if x['name'] not in h: errs.append('氏名未反映: '+x['name'])
  if x.get('role','') not in h: errs.append('肩書未反映: '+x['name'])
  f=d/'assets'/x['photo']
  if not f.exists(): errs.append('写真なし: '+str(f)); continue
  try: Image.open(f).verify()
  except Exception as e: errs.append('写真破損: '+str(f))
 url=cfg.get('reservation_url','未設定')
 if url!='未設定' and url not in h: errs.append('予約URL未反映')
 if errs:
  print('FAIL');[print('- '+e) for e in errs];sys.exit(1)
 print('PASS')
 print('clinic:',cfg['clinic_name']);print('placeholder_count:',h.count('〇〇歯科医院'));print('images: OK')
if __name__=='__main__':main()
