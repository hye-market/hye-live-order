import os
import shutil
import threading
import uuid
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

st.set_page_config(page_title="HYE LIVE ORDER", layout="wide")

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
FILE = "orders.xlsx"
BACKUP_DIR = "backups"          # 하루 한 번 자동 백업 (최근 14개 보관)
BACKUP_KEEP = 14
DATE_FMT = "%y-%m-%d"           # 기존 데이터와 같은 저장 형식 유지
ID_COL = "주문번호"              # 기기 여러 대에서 같은 주문을 정확히 찾기 위한 고유번호
BASE_COLS = ["삭제", "날짜", "고객명", "상품번호", "수량", "단가", "입금여부"]
ALL_COLS = [ID_COL] + BASE_COLS
EDIT_COLS = BASE_COLS
VIP_LIMIT = 500_000


@st.cache_resource
def _lock():
    # 컴퓨터·태블릿·폰이 동시에 저장해도 파일이 꼬이지 않도록 하는 잠금
    return threading.RLock()


LOCK = _lock()


# ─────────────────────────────────────────────
# 데이터 정리 (옛 파일도 그대로 읽히도록)
# ─────────────────────────────────────────────
def _is_blank(v):
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(v, str) and v.strip() == ""


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if _is_blank(v):
        return False
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() in ("true", "1", "y", "yes", "o", "v", "입금", "입금완료")


def parse_date(v):
    """'26-03-05' 같은 기존 형식을 '2026년 3월 5일'로 정확히 읽습니다."""
    if _is_blank(v):
        return pd.NaT
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(v)
    t = str(v).strip()
    for fmt in (DATE_FMT, "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%y.%m.%d", "%Y.%m.%d", "%Y/%m/%d", "%y/%m/%d"):
        try:
            return pd.Timestamp(datetime.strptime(t, fmt))
        except ValueError:
            continue
    return pd.NaT


def _fmt_date(v):
    d = parse_date(v)
    if pd.isna(d):
        return "" if _is_blank(v) else str(v).strip()
    return d.strftime(DATE_FMT)


def _to_text(v):
    if _is_blank(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def new_id():
    return uuid.uuid4().hex[:10]


def normalize(df):
    df = df.copy()
    df = df.drop(columns=[c for c in ("합계",) if c in df.columns])
    for c in ALL_COLS:
        if c not in df.columns:
            df[c] = None

    ids = df[ID_COL].map(_to_text)
    seen = set()
    fixed = []
    for i in ids:
        if not i or i in seen:
            i = new_id()
        seen.add(i)
        fixed.append(i)
    df[ID_COL] = fixed

    df["삭제"] = df["삭제"].map(_to_bool)
    df["입금여부"] = df["입금여부"].map(_to_bool)
    df["날짜"] = df["날짜"].map(_fmt_date)
    df["고객명"] = df["고객명"].map(_to_text)
    df["상품번호"] = df["상품번호"].map(_to_text)
    df["수량"] = pd.to_numeric(df["수량"], errors="coerce").fillna(0)
    df["단가"] = pd.to_numeric(df["단가"], errors="coerce").fillna(0)
    return df[ALL_COLS].reset_index(drop=True)


def with_total(df):
    df = df.copy()
    df["합계"] = df["수량"] * df["단가"]
    return df


# ─────────────────────────────────────────────
# 파일 읽기 / 저장
# ─────────────────────────────────────────────
def _read_raw():
    try:
        return pd.read_excel(FILE, dtype=object)
    except Exception as e:  # 파일이 깨졌으면 덮어쓰지 않고 멈춤
        st.error(f"orders.xlsx를 읽지 못했어요. 파일을 덮어쓰지 않도록 여기서 멈춥니다. ({e})")
        st.stop()


def _needs_ids(raw):
    return len(raw) > 0 and (ID_COL not in raw.columns or raw[ID_COL].map(_is_blank).any())


def load():
    if not os.path.exists(FILE):
        return normalize(pd.DataFrame(columns=ALL_COLS))
    raw = _read_raw()
    if _needs_ids(raw):
        # 옛 파일: 주문번호만 한 번 붙여서 저장 (다른 내용은 그대로, 저장 전 자동 백업)
        with LOCK:
            raw = _read_raw()          # 다른 기기가 먼저 붙였을 수 있으니 다시 확인
            if _needs_ids(raw):
                save(normalize(raw))
                raw = _read_raw()
    return normalize(raw)


def _daily_backup():
    if not os.path.exists(FILE):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    target = os.path.join(BACKUP_DIR, f"orders_{datetime.now():%Y%m%d}.xlsx")
    if not os.path.exists(target):
        shutil.copy2(FILE, target)
        olds = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("orders_"))
        for f in olds[:-BACKUP_KEEP]:
            os.remove(os.path.join(BACKUP_DIR, f))


def save(df):
    df = normalize(df)
    _daily_backup()
    tmp = FILE + ".tmp.xlsx"
    df.to_excel(tmp, index=False)
    os.replace(tmp, FILE)  # 저장 도중 끊겨도 기존 파일이 깨지지 않음


def mutate(fn):
    """항상 '지금 파일'을 새로 읽어서 바꾼 뒤 저장 → 다른 기기에서 넣은 주문을 지우지 않음"""
    with LOCK:
        df = load()
        df = fn(df)
        save(df)
        return df


def excel_bytes(df):
    buf = BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


# ─────────────────────────────────────────────
# 한글 PDF
# ─────────────────────────────────────────────
@st.cache_resource
def korean_font():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "NanumGothic.ttf"),
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",   # Streamlit Cloud (packages.txt: fonts-nanum)
        "C:/Windows/Fonts/malgun.ttf",                        # 윈도우 맑은 고딕
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf", # 맥
        "/Library/Fonts/AppleGothic.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont("KR", p))
                return "KR"
            except Exception:
                continue
    pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
    return "HYGothic-Medium"


def statement_pdf(customer, df):
    font = korean_font()
    title = ParagraphStyle("t", fontName=font, fontSize=18, leading=24, textColor=colors.HexColor("#d6336c"))
    body = ParagraphStyle("b", fontName=font, fontSize=10, leading=15)

    total = df["합계"].sum()
    paid = df.loc[df["입금여부"], "합계"].sum()

    rows = [["날짜", "상품번호", "수량", "단가", "합계", "입금"]]
    for _, r in df.iterrows():
        rows.append([
            r["날짜"], r["상품번호"], f"{r['수량']:,.0f}", f"{r['단가']:,.0f}",
            f"{r['합계']:,.0f}", "입금" if r["입금여부"] else "미입금",
        ])
    rows.append(["", "", "", "총액", f"{total:,.0f}", ""])

    t = Table(rows, colWidths=[25 * mm, 40 * mm, 18 * mm, 28 * mm, 30 * mm, 22 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ffe3ec")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e6fcf5")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ALIGN", (2, 0), (4, -1), "RIGHT"),
        ("ALIGN", (5, 0), (5, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    doc.build([
        Paragraph("혜마켓 고객 정산서", title),
        Spacer(1, 6),
        Paragraph(f"고객명: {customer}  |  발행일: {date.today():%Y-%m-%d}", body),
        Paragraph(f"총액 {total:,.0f}원  /  입금 {paid:,.0f}원  /  미입금 {total - paid:,.0f}원", body),
        Spacer(1, 10),
        t,
    ])
    return buf.getvalue()


# ─────────────────────────────────────────────
# 화면
# ─────────────────────────────────────────────
st.title("HYE LIVE ORDER SYSTEM")

orders = with_total(load())

# 매출 요약
total = orders["합계"].sum()
paid_sum = orders.loc[orders["입금여부"], "합계"].sum()
m1, m2, m3, m4 = st.columns(4)
m1.metric("총매출", f"{total:,.0f}")
m2.metric("입금액", f"{paid_sum:,.0f}")
m3.metric("미입금", f"{total - paid_sum:,.0f}")
m4.metric("주문수", f"{len(orders):,}")

# 백업 · 복원
with st.expander("💾 백업 · 복원 (수정본을 올리기 전에 꼭 백업하세요)"):
    st.download_button(
        "전체 주문 엑셀 다운로드(백업)",
        excel_bytes(orders),
        f"orders_backup_{datetime.now():%y%m%d_%H%M}.xlsx",
    )
    st.caption("서버가 다시 시작되면 저장된 주문이 사라질 수 있어요. 방송이 끝날 때마다 백업해 두세요.")

    st.session_state.setdefault("up_key", 0)
    up = st.file_uploader("백업 엑셀로 복원", type=["xlsx"], key=f"up_{st.session_state.up_key}")
    if up is not None:
        try:
            restored = normalize(pd.read_excel(up, dtype=object))
        except Exception as e:
            st.error(f"파일을 읽지 못했어요: {e}")
            restored = None
        if restored is not None:
            st.info(f"이 파일: 주문 {len(restored):,}건 · 합계 {(restored['수량'] * restored['단가']).sum():,.0f}원")
            mode = st.radio("복원 방식", ["지금 주문에 합치기(이미 있는 주문은 건너뜀)", "지금 주문을 지우고 이 파일로 바꾸기"])
            ok = st.checkbox("확인했어요")
            if st.button("복원 실행", disabled=not ok, type="primary"):
                if mode.startswith("지금 주문에 합치기"):
                    def _merge(df):
                        # 1) 같은 주문번호는 건너뜀
                        cand = restored[~restored[ID_COL].isin(df[ID_COL])]
                        # 2) 주문번호가 없던 옛 엑셀: 날짜·고객명·상품번호·수량·단가가 같은 주문은
                        #    이미 있는 개수만큼 건너뛰고, 모자란 개수만 추가 (같은 주문 2번 산 경우도 정확히 계산)
                        def sig(d):
                            return (d["날짜"].astype(str) + "|" + d["고객명"].astype(str) + "|"
                                    + d["상품번호"].astype(str) + "|"
                                    + d["수량"].astype(float).map("{:g}".format) + "|"
                                    + d["단가"].astype(float).map("{:g}".format))
                        have = sig(df).value_counts().to_dict()
                        keep = []
                        for i, s in zip(cand.index, sig(cand)):
                            if have.get(s, 0) > 0:
                                have[s] -= 1
                            else:
                                keep.append(i)
                        return pd.concat([df, cand.loc[keep]], ignore_index=True)
                    mutate(_merge)
                else:
                    mutate(lambda df: restored)
                st.session_state.up_key += 1
                st.toast("복원했어요")
                st.rerun()

# 일괄 작업 (확인 후 실행)
with st.expander("⚠️ 일괄 작업 (전체입금 · 월초기화 · 전체삭제)"):
    a1, a2, a3 = st.columns(3)
    with a1:
        c = st.checkbox("전체 입금 처리 확인", key="chk_allpaid")
        if st.button("전체입금", disabled=not c):
            def _allpaid(df):
                df["입금여부"] = True
                return df
            mutate(_allpaid)
            st.rerun()
    with a2:
        c = st.checkbox("이번 달 주문 삭제 확인", key="chk_month")
        if st.button("월초기화", disabled=not c):
            def _month(df):
                today = datetime.today()
                d = df["날짜"].map(parse_date)
                this_month = d.map(lambda x: not pd.isna(x) and x.year == today.year and x.month == today.month)
                return df[~this_month.astype(bool)]
            mutate(_month)
            st.rerun()
    with a3:
        c = st.checkbox("모든 주문 삭제 확인", key="chk_all")
        if st.button("전체삭제", disabled=not c):
            mutate(lambda df: df.iloc[0:0])
            st.rerun()

# 주문 입력
st.subheader("주문입력")
with st.form("order", clear_on_submit=True):
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    d = c1.date_input("날짜", date.today())
    name = c2.text_input("고객명")
    product = c3.text_input("상품번호")
    qty = c4.number_input("수량", min_value=1, value=1, step=1)
    price = c5.number_input("단가", min_value=0, value=0, step=1000)
    is_paid = c6.checkbox("입금완료")
    submit = c7.form_submit_button("엔터주문추가")

if submit:
    if not name.strip():
        st.warning("고객명을 입력해 주세요.")
    else:
        row = {
            ID_COL: new_id(), "삭제": False, "날짜": d.strftime(DATE_FMT),
            "고객명": name.strip(), "상품번호": product.strip(),
            "수량": qty, "단가": price, "입금여부": is_paid,
        }
        mutate(lambda df: pd.concat([df, pd.DataFrame([row])], ignore_index=True))
        st.toast(f"{name} 주문 추가")
        st.rerun()

# 주문 리스트
st.subheader("주문리스트")
search = st.text_input("고객검색", placeholder="이름 일부를 입력하세요")

view = orders
if search.strip():
    view = view[view["고객명"].str.contains(search.strip(), case=False, regex=False, na=False)]
view = view.sort_values(["고객명", "날짜"], kind="stable")
table = view.set_index(ID_COL)[["삭제", "날짜", "고객명", "상품번호", "수량", "단가", "합계", "입금여부"]]

# 표 내용이 바뀌면 편집기를 새로 만듦 → 이전 편집이 엉뚱한 줄에 다시 적용되는 일 방지
table_key = "ed_" + str(int(pd.util.hash_pandas_object(table, index=True).sum()) & 0xFFFFFFFF)
edited = st.data_editor(
    table,
    key=table_key,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    column_config={
        "삭제": st.column_config.CheckboxColumn("삭제"),
        "수량": st.column_config.NumberColumn("수량", min_value=0, step=1, format="localized"),
        "단가": st.column_config.NumberColumn("단가", min_value=0, step=100, format="localized"),
        "합계": st.column_config.NumberColumn("합계", format="localized", disabled=True),
        "입금여부": st.column_config.CheckboxColumn("입금여부"),
    },
)


def _same(a, b):
    if _is_blank(a) and _is_blank(b):
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


# 바뀐 칸만 골라서 저장 (검색 중이어도 다른 고객 주문은 그대로)
changes = {}
for oid in edited.index:
    diff = {c: edited.at[oid, c] for c in EDIT_COLS if not _same(table.at[oid, c], edited.at[oid, c])}
    if diff:
        changes[oid] = diff

if changes:
    def _apply(df):
        for oid, diff in changes.items():
            hit = df[ID_COL] == oid
            for col, val in diff.items():
                df.loc[hit, col] = val
        return df
    mutate(_apply)
    st.rerun()

marked = table.index[table["삭제"]].tolist()
if st.button(f"선택삭제 ({len(marked)}건)", disabled=not marked):
    mutate(lambda df: df[~df[ID_COL].isin(marked)])
    st.rerun()

# 고객 정산서
st.subheader("고객정산서")
customers = sorted(c for c in orders["고객명"].unique() if c)
if not customers:
    st.info("주문이 들어오면 고객별 정산서를 만들 수 있어요.")
else:
    customer = st.selectbox("고객명", customers)
    cdf = orders[orders["고객명"] == customer].sort_values("날짜", kind="stable")
    ctotal = cdf["합계"].sum()
    cpaid = cdf.loc[cdf["입금여부"], "합계"].sum()
    st.caption(f"총액 {ctotal:,.0f}원 · 입금 {cpaid:,.0f}원 · 미입금 {ctotal - cpaid:,.0f}원")
    st.dataframe(cdf[["날짜", "상품번호", "수량", "단가", "합계", "입금여부"]], hide_index=True, width="stretch")
    p1, p2 = st.columns(2)
    with p1:
        st.download_button("PDF다운", statement_pdf(customer, cdf), f"{customer}.pdf", mime="application/pdf")
    with p2:
        st.download_button(
            "고객 엑셀다운",
            excel_bytes(cdf[["날짜", "고객명", "상품번호", "수량", "단가", "합계", "입금여부"]]),
            f"{customer}.xlsx",
        )

# 고객별 미입금 / 합계 · 등급 (검색과 상관없이 전체 기준)
if len(orders):
    summary = orders.groupby("고객명").agg(
        주문수=("합계", "size"),
        합계=("합계", "sum"),
        입금액=("합계", lambda s: s[orders.loc[s.index, "입금여부"]].sum()),
    )
    summary["미입금"] = summary["합계"] - summary["입금액"]
    summary["등급"] = summary["합계"].map(lambda x: "👑VIP" if x >= VIP_LIMIT else "일반")

    s1, s2 = st.columns(2)
    with s1:
        st.subheader("고객별 미입금")
        unpaid = summary[summary["미입금"] > 0][["미입금"]].sort_values("미입금", ascending=False)
        if len(unpaid):
            st.dataframe(unpaid, width="stretch")
        else:
            st.success("미입금 고객이 없어요.")
    with s2:
        st.subheader(f"고객별 합계 · 등급({VIP_LIMIT // 10000}만원 이상 VIP)")
        st.dataframe(summary[["주문수", "합계", "등급"]].sort_values("합계", ascending=False), width="stretch")

# 이번달 일별 매출
st.subheader("이번달 일별 매출")
today = datetime.today()
chart = orders.copy()
chart["d"] = chart["날짜"].map(parse_date)
chart = chart[chart["d"].map(lambda x: not pd.isna(x) and x.year == today.year and x.month == today.month)]
if len(chart):
    daily = chart.groupby(chart["d"].map(lambda x: x.day))["합계"].sum()
    daily = daily.reindex(range(1, today.day + 1), fill_value=0)
    daily.index.name = "일"
    st.bar_chart(daily.rename("매출"))
else:
    st.caption("이번 달 주문이 아직 없어요.")
