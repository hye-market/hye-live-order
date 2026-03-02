import streamlit as st
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from io import BytesIO

# ======================
# 로그인 (유지)
# ======================
USERS = {"HYE": "102108"}

if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("HYE 관리자 로그인")
    u = st.text_input("아이디")
    p = st.text_input("비밀번호", type="password")
    if st.button("로그인"):
        if u in USERS and USERS[u] == p:
            st.session_state.login = True
            st.rerun()
        else:
            st.error("로그인 실패")
    st.stop()

st.set_page_config(layout="wide")
st.title("💎 HYE LIVE ORDER SYSTEM")

DATA_FILE = "orders_data.xlsx"

BASE_COLUMNS = [
    "삭제","날짜","고객명","상품번호",
    "수량","단가","입금여부"
]

# ======================
# 데이터 로드 / 저장 (유지)
# ======================
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_excel(DATA_FILE)
        return df.reindex(columns=BASE_COLUMNS)
    return pd.DataFrame(columns=BASE_COLUMNS)

def save_data(df):
    df.to_excel(DATA_FILE, index=False)

orders = load_data()

orders["수량"] = pd.to_numeric(orders["수량"], errors="coerce").fillna(0)
orders["단가"] = pd.to_numeric(orders["단가"], errors="coerce").fillna(0)
orders["합계"] = orders["수량"] * orders["단가"]

# ======================
# 🔎 검색창 (복구)
# ======================
search = st.text_input("🔎 고객 검색")

display = orders.copy()

if search:
    display = display[display["고객명"].astype(str).str.contains(search, na=False)]

# ======================
# 리스트 (위치 유지)
# ======================
display = display[[
    "삭제","날짜","고객명","상품번호",
    "수량","단가","합계","입금여부"
]]

st.subheader("📋 주문 리스트")
edited = st.data_editor(display, use_container_width=True)

# ======================
# 🔥 합계 자동 반영 + 저장 수정
# ======================
edited["수량"] = pd.to_numeric(edited["수량"], errors="coerce").fillna(0)
edited["단가"] = pd.to_numeric(edited["단가"], errors="coerce").fillna(0)
edited["합계"] = edited["수량"] * edited["단가"]

# BASE 구조로 재저장
save_df = edited[[
    "삭제","날짜","고객명","상품번호",
    "수량","단가","입금여부"
]]

if not save_df.equals(orders[BASE_COLUMNS]):
    save_data(save_df)
    st.rerun()

# ======================
# 고객 묶음 합계 (유지)
# ======================
st.subheader("👥 고객별 묶음 합계")
group = edited.groupby("고객명")["합계"].sum().reset_index()
st.dataframe(group.sort_values(by="합계", ascending=False))

# ======================
# VIP (유지)
# ======================
st.subheader("💎 고객 등급")
vip = group.copy()
vip["등급"] = vip["합계"].apply(lambda x: "💎 VIP" if x >= 1000000 else "🟢 일반")
st.dataframe(vip)

# ======================
# 고객별 미입금 (유지)
# ======================
st.subheader("⚠ 고객별 미입금")
unpaid = edited[edited["입금여부"]==False].groupby("고객명")["합계"].sum().reset_index()
st.dataframe(unpaid.sort_values(by="합계", ascending=False))

# ======================
# 정산 요약 (유지)
# ======================
total = edited["합계"].sum()
paid = edited[edited["입금여부"]==True]["합계"].sum()
unpaid_total = edited[edited["입금여부"]==False]["합계"].sum()

c1,c2,c3 = st.columns(3)
c1.metric("총매출", f"{total:,.0f}원")
c2.metric("입금액", f"{paid:,.0f}원")
c3.metric("미입금", f"{unpaid_total:,.0f}원")

# ======================
# 정산서 (위치 유지)
# ======================
st.subheader("📄 고객 정산서")

if not orders.empty:
    customer_list = orders["고객명"].dropna().unique()
    selected_customer = st.selectbox("고객 선택", customer_list)

    if st.button("정산서 PDF 생성"):
        pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))

        data = orders[orders["고객명"] == selected_customer].copy()
        pdf_columns = ["날짜","상품번호","수량","단가","합계","입금여부"]
        data = data[pdf_columns].astype(str)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)

        table_data = [pdf_columns] + data.values.tolist()

        table = Table(table_data)
        table.setStyle([
            ("GRID",(0,0),(-1,-1),1,colors.black),
            ("FONTNAME",(0,0),(-1,-1),'HYSMyeongJo-Medium'),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("BACKGROUND",(0,0),(-1,0),colors.lightgrey)
        ])

        doc.build([table])

        st.download_button(
            "📥 PDF 다운로드",
            data=buffer.getvalue(),
            file_name=f"{selected_customer}_정산서.pdf",
            mime="application/pdf"
        )

# ======================
# 일별 매출 (유지)
# ======================
st.subheader("📊 이번달 일별 매출")

edited["날짜"] = pd.to_datetime(edited["날짜"])
today = datetime.today()

month_data = edited[
    (edited["날짜"].dt.year == today.year) &
    (edited["날짜"].dt.month == today.month)
]

if not month_data.empty:
    month_data["일"] = month_data["날짜"].dt.day.astype(int)
    daily = month_data.groupby("일")["합계"].sum().reset_index()

    fig, ax = plt.subplots()
    ax.plot(daily["일"], daily["합계"], marker="o")
    ax.set_xticks(daily["일"])
    ax.set_xticklabels(daily["일"].astype(str))
    ax.set_xlabel("일자")
    ax.set_ylabel("매출")
    st.pyplot(fig)
