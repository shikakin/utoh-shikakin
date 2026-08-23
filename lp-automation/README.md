# シカキン パートナー歯科医院LP 自動生成基盤 v2

目的: 承認済み `shikakin_MASTER_LP_Ver3_mobile_safe_template.html` を必ず複製し、指定箇所だけを医院データで置換して、GitHub Pages公開用フォルダを生成する。

## 絶対ルール
- MASTERから新規デザインを作らない。
- MASTERはSHA-256で固定し、ハッシュが一致しない場合は生成を停止する。
- 推薦文本文は変更しない。医院名の置換のみ行う。
- 不明情報を推測しない。
- 氏名未入力スタッフは出力しない。
- 人物写真はBase64埋め込みにせず、`assets/*.jpg`として再エンコードして配置する。
- `validate_lp.py`がPASSするまで公開しない。
- 公開後に実URLをPC/スマホで目視確認して初めて「完成」とする。

## 入力
医院ごとに`lp-automation/clinics/<slug>/clinic.json`と人物写真を置く。写真は`clinic.json`の`source_photo`で対応を明示する。

```text
lp-automation/clinics/<slug>/
  clinic.json
  doctor-01.png
  therapist-01.png
```

必須項目は`clinic.example.json`を正とする。slugは英小文字・数字・ハイフンだけを使用し、既存の同名・類似フォルダがないことを生成前と公開直前に確認する。

## 生成
リポジトリ直下で実行する。

```bash
python lp-automation/build_lp.py \
  --master shikakin_MASTER_LP_Ver3_mobile_safe_template.html \
  --config lp-automation/clinics/<slug>/clinic.json \
  --out dist/<slug>
python lp-automation/validate_lp.py \
  --dir dist/<slug> \
  --config lp-automation/clinics/<slug>/clinic.json
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
検証PASS後、`index.html`と`assets/`をGitHub Pages公開リポジトリの新規`<slug>/`へ配置する。`_MASTER_snapshot.html`は検証用であり公開不要。公開URLは`https://shikakin.github.io/utoh-shikakin/<slug>/`。

GitHub Actionsは、push内で変更された`lp-automation/clinics/<slug>/`だけを再生成する。既存医院を一括再生成・上書きしない。手動実行時はslugを明示する。

## MASTER復元
承認済みMASTERが欠落した場合に限り、既存の検証済み派生元と`lp-automation/master-assets/`から次のコマンドで完全復元できる。復元結果は承認済みSHA-256と一致しなければ保存されない。

```bash
python lp-automation/restore_master.py \
  --source utoh_shikakin_lp_embedded.html \
  --output shikakin_MASTER_LP_Ver3_mobile_safe_template.html
```

GitHub ActionsもMASTER欠落時だけ同じ復元を実行する。通常の医院生成では、`main`に保存されたMASTERを直接使用する。

## 完了条件
- `〇〇歯科医院`などのプレースホルダー残存0
- 医院名・氏名・役職・職種反映
- 人物写真ファイル存在・JPEGデコード正常・人物との対応一致
- 医院HP・予約URL・住所・電話・アクセス・Google Map反映
- MASTERスナップショットのハッシュ一致
- PC/スマホ実URL表示確認
