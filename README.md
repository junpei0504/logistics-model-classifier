# 物流企業ビジネスモデル診断

企業ホームページのURLを入力すると、公開ページから物流事業をA〜Hの8分類と詳細業態に暫定分類するブラウザアプリです。

## 起動

```bash
pip install -r requirements.txt
streamlit run app.py
```

APIキー不要。分類はキーワードベースの簡易推定であり、粗利構成に基づく確定分類ではありません。

## Streamlit Community Cloudへの公開

https://share.streamlit.io/ にログインし、GitHubリポジトリ `junpei0504/logistics-model-classifier` とブランチ `main`、ファイル `app.py` を指定してDeployします。
