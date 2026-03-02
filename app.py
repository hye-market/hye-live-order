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
# 로그인
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
# 데이터 로드 / 저장
# ======================
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_excel(DATA_FILE)
        return df.reindex(columns=BASE_COLUMNS)
    return pd.DataFrame(columns=BASE_COLUMNS)

def save_data(df):
    df.to_excel(DATA_FILE, index=False)

orders = load_data()

# ======================
# 합계 계산
# ======================
orders["수량"] = pd.to_numeric(orders["수량"], errors="coerce").fillna(0)
orders["단가"] = pd.to_numeric(orders["단가"], errors="coerce").fillna(0)
orders["합계"] = orders["수량"] * orders["단가"]

# ======================
# 상단 버튼 한줄 유지
# ======================
c1, c2, c3 = st.columns(3)

with c1:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            st.download_button("📥 엑셀 다운로드", f, "HYE_DATA.xlsx")

with c2:
    if st.button("🧹 초기화"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.success("전체 초기화 완료")
        st.stop()

with c3:
    if st.button("📅 이번달월초기화"):
        if not orders.empty:
            orders["날짜"] = pd.to_datetime(orders["날짜"])
            today = datetime.today()
            orders = orders[
                ~((orders["날짜"].dt.year == today.year) &
                  (orders["날짜"].dt.month == today.month))
            ]
            save_data(orders)
            st.success("이번달 데이터 삭제 완료")
            st.rerun()

# ======================
# 주문 입력 복구
# ======================
st.subheader("주문 입력")

with st.form("order_form", clear_on_submit=True):
    col1,col2,col3,col4,col5,col6 = st.columns(6)
    date = col1.date_input("날짜", datetime.today())
    name = col2.text_input("고객명")
    product = col3.text_input("상품번호")
    qty = col4.number_input("수량", 1)
    price = col5.number_input("단가", 0)
    submit = col6.form_submit_button("주문 추가")

    if submit and name != "":
        new = pd.DataFrame([{
            "삭제":False,
            "날짜":str(date),
            "고객명":name,
            "상품번호":product,
            "수량":qty,
            "단가":price,
            "입금여부":False
        }])
        orders = pd.concat([orders,new],ignore_index=True)
        save_data(orders)
        st.rerun()

# ======================
# 주문 리스트 유지
# ======================
display = orders[[
    "삭제","날짜","고객명","상품번호",
    "수량","단가","합계","입금여부"
]]

st.subheader("📋 주문 리스트")
edited = st.data_editor(display, use_container_width=True)

# ======================
# 고객 묶음 합계 복구
# ======================
st.subheader("👥 고객별 묶음 합계")
group = edited.groupby("고객명")["합계"].sum().reset_index()
st.dataframe(group.sort_values(by="합계", ascending=False))

# ======================
# VIP 복구
# ======================
st.subheader("💎 고객 등급")
vip = group.copy()
vip["등급"] = vip["합계"].apply(lambda x: "💎 VIP" if x >= 1000000 else "🟢 일반")
st.dataframe(vip)

# ======================
# 고객별 미입금 복구
# ======================
st.subheader("⚠ 고객별 미입금")
unpaid = edited[edited["입금여부"]==False].groupby("고객명")["합계"].sum().reset_index()
st.dataframe(unpaid.sort_values(by="합계", ascending=False))

# ======================
# 정산 요약 복구
# ======================
total = edited["합계"].sum()
paid = edited[edited["입금여부"]==True]["합계"].sum()
unpaid_total = edited[edited["입금여부"]==False]["합계"].sum()

c1,c2,c3 = st.columns(3)
c1.metric("총매출", f"{total:,.0f}원")
c2.metric("입금액", f"{paid:,.0f}원")
c3.metric("미입금", f"{unpaid_total:,.0f}원")

# ======================
# 일별 매출 복구
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

# ======================
# 고객 정산서 (한글 정상 유지)
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
