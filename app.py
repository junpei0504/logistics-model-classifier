import re
import ipaddress
import socket
from collections import Counter, deque
from urllib.parse import urljoin, urlparse
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="物流企業ビジネスモデル診断",page_icon="🚚",layout="wide")
MODELS={
"A":("自社車両運行型",{"A1 地場・専属定期便":["定期便","専属便","ルート配送"],"A2 長距離・幹線輸送":["長距離","幹線輸送"],"A3 フリー・スポット輸送":["スポット便","フリー便"],"A4 ラストワンマイル":["宅配","ラストワンマイル"],"A5 専門輸送":["重量物輸送","冷凍輸送","危険物輸送","タンクローリー"]}),
"B":("ネットワーク・混載型",{"B1 路線・小口混載":["路線便","小口混載"],"B2 共同配送":["共同配送"],"B3 地域配送ネットワーク":["地域配送"],"B4 幹線ネットワーク":["幹線ネットワーク"]}),
"C":("利用運送・配車型",{"C1 一般利用運送":["貨物利用運送","利用運送"],"C2 水屋・スポット配車":["求貨求車","スポット配車"],"C3 荷主専属配車センター":["配車センター"],"C4 協力会社ネットワーク":["協力会社ネットワーク"]}),
"D":("倉庫スペース型",{"D1 保管中心":["保管料","保管サービス"],"D2 DC運営":["配送センター","DC運営"],"D3 TC・クロスドック":["クロスドック","通過型センター"],"D4 専門倉庫":["冷凍倉庫","危険物倉庫","保税倉庫"]}),
"E":("物流作業・加工型",{"E1 ECフルフィルメント":["EC物流","フルフィルメント"],"E2 流通加工":["流通加工","セット組"],"E3 梱包・輸出梱包":["輸出梱包","木枠梱包"],"E4 配送付帯サービス":["設置配送","組立配送"]}),
"F":("3PL・4PL型",{"F1 運営受託3PL":["3PL"],"F2 元請統括3PL":["一括受託"],"F3 4PL・コントロールタワー":["4PL","コントロールタワー"],"F4 SCM改善":["SCM改善"]}),
"G":("国際物流・港湾型",{"G1 フォワーダー":["フォワーディング","国際複合輸送"],"G2 通関":["通関業務","通関代行"],"G3 港湾・保税":["保税蔵置","港湾荷役"],"G4 国際一貫物流":["国際一貫物流"],"G5 越境EC":["越境EC"]}),
"H":("物流不動産・施設提供型",{"H1 賃貸・サブリース":["サブリース","倉庫賃貸"],"H2 物流不動産開発":["物流施設開発"],"H3 物流不動産仲介":["物流施設仲介"]})}
KEYWORDS={
"A":["自社車両","トラック輸送","一般貨物","定期便","チャーター便","貸切便","トレーラー","タンクローリー","大型車両","幹線輸送","ルート配送","重量物輸送"],
"B":["共同配送","混載","路線便","小口配送","ネットワーク配送","集約配送","ターミナル"],
"C":["利用運送","貨物利用運送","協力会社","運送取扱","配車センター","求貨求車","マッチング","配車手配"],
"D":["倉庫","保管","パレット保管","物流センター","入出庫","冷凍倉庫","冷蔵倉庫","定温倉庫"],
"E":["流通加工","ピッキング","検品","梱包","セット組","発送代行","フルフィルメント","EC物流","ラベル貼り"],
"F":["3PL","4PL","物流一括","物流アウトソーシング","物流管理受託","SCM","物流コンサルティング","包括受託"],
"G":["通関","フォワーディング","国際輸送","海上輸送","航空貨物","保税","港湾荷役","輸出入","コンテナ輸送"],
"H":["物流不動産","倉庫賃貸","倉庫開発","サブリース","物流施設開発","物流施設仲介"]}
HEADERS={"User-Agent":"LogisticsResearchClassifier/1.0","Accept":"text/html"}
def validate(url):
    if not re.match(r"^https?://",url,re.I):url="https://"+url
    p=urlparse(url)
    if p.scheme not in ("http","https") or not p.hostname or p.username or p.password or (p.port and p.port not in (80,443)):raise ValueError("公開サイトのHTTP/HTTPS URLを指定してください。")
    host=p.hostname.lower().rstrip(".")
    if host=="localhost" or host.endswith((".local",".internal")):raise ValueError("内部ネットワークにはアクセスできません。")
    addresses={a[4][0] for a in socket.getaddrinfo(host,p.port or (443 if p.scheme=="https" else 80),type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):raise ValueError("公開IPアドレスではありません。")
    return url
def fetch(url):
    with requests.Session() as sess:
        for _ in range(5):
            url=validate(url)
            with sess.get(url,headers=HEADERS,timeout=(5,12),allow_redirects=False,stream=True) as r:
                if r.status_code in (301,302,303,307,308):
                    url=urljoin(url,r.headers.get("Location",""))
                    continue
                r.raise_for_status()
                if "html" not in r.headers.get("Content-Type","").lower():raise ValueError("HTMLページではありません。")
                data=bytearray()
                for chunk in r.iter_content(32768):
                    data.extend(chunk)
                    if len(data)>1500000:raise ValueError("ページサイズ制限超過")
                r.encoding=r.apparent_encoding or "utf-8"
                return url,data.decode(r.encoding,errors="replace")
    raise ValueError("リダイレクトが多すぎます。")
def crawl(start,limit):
    start=validate(start);root=urlparse(start).hostname
    queue=deque([start]);seen=set();pages=[];errors=[]
    while queue and len(pages)<limit and len(seen)<limit*6:
        url=queue.popleft()
        if url in seen:continue
        seen.add(url)
        try:
            actual,html=fetch(url)
            if urlparse(actual).hostname!=root:continue
            soup=BeautifulSoup(html,"html.parser")
            links=[]
            for a in soup.find_all("a",href=True):
                nxt=urljoin(actual,a["href"]).split("#")[0]
                if urlparse(nxt).hostname==root and urlparse(nxt).scheme in ("https","http") and not re.search(r"\.(pdf|png|jpe?g|zip|docx?|xlsx?|pptx?)$",urlparse(nxt).path,re.I):
                    label=a.get_text(" ",strip=True)+" "+urlparse(nxt).path
                    score=sum(w in label.lower() for w in ("service","business","事業","サービス","輸送","倉庫","物流","about","設備"))
                    links.append((score,nxt))
            title=soup.title.get_text(" ",strip=True) if soup.title else actual
            for tag in soup(["script","style","nav","footer","header","noscript","svg"]):tag.decompose()
            pages.append({"title":title,"url":actual,"text":re.sub(r"\s+"," ",soup.get_text(" ",strip=True))[:11000]})
            for _,nxt in sorted(set(links),reverse=True):
                if nxt not in seen and nxt not in queue:queue.append(nxt)
        except Exception as e:errors.append(f"{url}: {str(e)[:120]}")
    return pages,errors
def classify(pages):
    text=" ".join(p["text"] for p in pages).lower()
    scores={k:sum(min(text.count(w.lower()),5) for w in ws) for k,ws in KEYWORDS.items()}
    ranked=sorted(scores,key=scores.get,reverse=True)
    primary=ranked[0] if scores[ranked[0]] else None
    secondary=[c for c in ranked[1:] if scores[c]>=max(2,scores[primary]*0.25)][:3] if primary else []
    subtype="未確定"
    evidence=[]
    if primary:
        ss={s:sum(min(text.count(w.lower()),3) for w in ws) for s,ws in MODELS[primary][1].items()}
        winner=max(ss,key=ss.get)
        if ss[winner]:subtype=winner+"（暫定）"
        for p in pages:
            for word in KEYWORDS[primary]:
                m=re.search(re.escape(word),p["text"],re.I)
                if m:
                    evidence.append({"url":p["url"],"excerpt":p["text"][max(0,m.start()-60):m.end()+100]})
                    break
            if len(evidence)>=4:break
    return primary,secondary,subtype,scores,evidence
st.title("🚚 物流企業 ビジネスモデル診断")
st.caption("API不要｜公開ホームページのキーワードから推定する簡易版。粗利構成や実態を保証するものではありません。")
with st.sidebar:
    st.header("診断設定")
    limit=st.slider("確認する最大ページ数",2,12,8)
    st.info("A〜Hの8分類・詳細業態を推定します。APIキーは不要です。")
    for k,(title,_) in MODELS.items():st.caption(f"{k}｜{title}")
with st.form("diagnose"):
    url=st.text_input("会社ホームページURL",placeholder="https://example.co.jp")
    submitted=st.form_submit_button("サイトを分析して分類",type="primary",use_container_width=True)
if submitted:
    if not url.strip():st.warning("URLを入力してください。")
    else:
        try:
            with st.spinner("公開ページを読み取っています…"):pages,errors=crawl(url.strip(),limit)
            if not pages:
                st.error("ページを取得できませんでした。アクセス制限やURLを確認してください。")
                with st.expander("取得エラー"):st.write(errors)
            else:st.session_state["data"]=(pages,errors,classify(pages))
        except Exception as e:st.error(f"分析できませんでした: {e}")
if "data" in st.session_state:
    pages,errors,result=st.session_state["data"]
    primary,secondary,subtype,scores,evidence=result
    st.divider();st.subheader(pages[0]["title"])
    a,b,c=st.columns(3)
    a.metric("推定主分類",f"{primary}｜{MODELS[primary][0]}" if primary else "判定保留")
    b.metric("詳細業態",subtype)
    c.metric("確認ページ数",len(pages))
    st.warning("判定確信度：低（キーワード推定）。事業別の売上・粗利構成は確認できていません。")
    st.write("**副分類：** "+("、".join(f"{x}｜{MODELS[x][0]}" for x in secondary) if secondary else "なし・要確認"))
    st.write("**カテゴリ別キーワードスコア**")
    st.bar_chart({f"{k} {MODELS[k][0]}":v for k,v in scores.items()})
    st.write("**判定根拠**")
    for e in evidence:st.markdown(f"- [{e['url']}]({e['url']})：{e['excerpt']}")
    with st.expander("取得したページ"):st.write([p["url"] for p in pages])
    if errors:
        with st.expander("取得できなかったページ"):st.write(errors)
    import pandas as pd
    rows=[{"企業名":pages[0]["title"],"URL":pages[0]["url"],"主分類":primary or "判定保留","詳細業態":subtype,"副分類":",".join(secondary),"判定確信度":"低（キーワード推定）","確認ページ数":len(pages)}]
    csv=pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
    st.download_button("診断結果をCSVダウンロード",csv,file_name="logistics_classification.csv",mime="text/csv")
