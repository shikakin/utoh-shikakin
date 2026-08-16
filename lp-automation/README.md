# シカキン パートナー歯科医院LP 自動生成基盤 v1

目的: 承認済み `shikakin_MASTER_LP_Ver3_mobile_safe_template.html` を必ず複製し、指定箇所だけを医院データで置換して、GitHub Pages公開用フォルダを生成する。

## 絶対ルール
- MASTERから新規デザインを作らない。
- 推薦文本文は変更しない。医院名の置換のみ。
- 不明情報を推測しない。
- 氏名未入力スタッフは出力しない。
- 人物写真はBase64埋め込みにせず、`assets/*.jpg` として再エンコードして配置する。
- `validate_lp.py` がPASSするまで公開しない。
- 公開後に実URLをPC/スマホで目視確認して初めて「完成」とする。

## 入力
医院ごとに `clinic.json` と人物写真を1フォルダに置く。

## 生成
```bash
python build_lp.py --master shikakin_MASTER_LP_Ver3_mobile_safe_template.html --config clinic.json --out dist/<slug>
python validate_lp.py --dir dist/<slug> --config clinic.json
```

## 出力
```text
dist/<slug>/
  index.html
  assets/
    doctor-01.jpg
    therapist-01.jpg
  _MASTER_snapshot.html
```

## 公開
検証PASS後、`dist/<slug>/` の `index.html` と `assets/` をGitHub Pages公開リポジトリの `<slug>/` へ配置する。公開URLは `https://shikakin.github.io/<repo>/<slug>/`。

## 完了条件
- 〇〇歯科医院残存 0
- 医院名・氏名・肩書反映
- 写真ファイル存在・デコード正常
- 予約URL反映
- Google Map反映
- MASTER変更禁止箇所を維持
- PC/スマホ実URL表示確認
