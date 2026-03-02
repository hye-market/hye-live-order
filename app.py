import streamlit as st
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from io import BytesIO

# =========================
# 로그인
# =========================
USERS = {"HYE": "102108"}

if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("HYE 관리자 로그인")
    user = st.text_input("아이디")
    pw = st.text_input("비밀번호", type="password")
    if st.button("로그인"):
        if user in USERS and USERS[user] == pw:
            st.session_state.login = True
            st.rerun()
        else:
            st.error("아이디 또는 비밀번호 오류")
    st.stop()

st.set_page_config(layout="wide")
st.title("💎 HYE LIVE ORDER SYSTEM")

DATA_FILE = "orders_data.xlsx"

BASE_COLUMNS = [
    "날짜","고객명","상품번호",
    "수량","단가","입금여부"
]

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_excel(DATA_FILE)
    return pd.DataFrame(columns=BASE_COLUMNS)

def save_data(df):
    df.to_excel(DATA_FILE, index=False)

orders = load_data()

if not orders.empty:
    orders["수량"] = pd.to_numeric(orders["수량"], errors="coerce").fillna(0)
    orders["단가"] = pd.to_numeric(orders["단가"], errors="coerce").fillna(0)
    orders["입금여부"] = orders["입금여부"].fillna(False)

orders["합계"] = orders["수량"] * orders["단가"]

# =========================
# 🔥 주문입력 묶음박스 확실 복구
# =========================
st.markdown("""
<style>
.order-box {
    border:2px solid #444;
    padding:20px;
    border-radius:10px;
    margin-bottom:20px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="order-box">', unsafe_allow_html=True)
st.subheader("📝 주문 입력")

with st.form("order_form", clear_on_submit=True):
    c1,c2,c3,c4,c5,c6,c7 = st.columns([1,1,1,1,1,1,1])

    date = c1.date_input("날짜", datetime.today())
    name = c2.text_input("고객명")
    product = c3.text_input("상품번호")
    qty = c4.number_input("수량", min_value=1, value=1)
    price = c5.number_input("단가", min_value=0, value=0)
    paid = c6.checkbox("입금완료")

    submit = c7.form_submit_button("주문 추가", use_container_width=True)

    if submit and name:
        new = pd.DataFrame([{
            "날짜":str(date),
            "고객명":name,
            "상품번호":product,
            "수량":qty,
            "단가":price,
            "입금여부":paid
        }])
        orders = pd.concat([orders,new],ignore_index=True)
        save_data(orders)
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 검색
# =========================
search = st.text_input("🔎 고객 검색")

display = orders.copy()
if search:
    display = display[display["고객명"].astype(str).str.contains(search, na=False)]

display["합계"] = display["수량"] * display["단가"]

# =========================
# 리스트 (삭제버튼 추가)
# =========================
st.subheader("📋 주문 리스트")

if not display.empty:
    for idx, row in display.iterrows():
        col1,col2,col3,col4,col5,col6,col7,col8,col9 = st.columns([1,1,1,1,1,1,1,1,1])

        col1.write(row["날짜"])
        col2.write(row["고객명"])
        col3.write(row["상품번호"])
        col4.write(row["수량"])
        col5.write(row["단가"])
        col6.write(row["합계"])
        col7.write("✔" if row["입금여부"] else "❌")

        if col8.button("삭제", key=f"del{idx}"):
            orders = orders.drop(idx)
            save_data(orders)
            st.rerun()

# =========================
# 엑셀 다운로드 (합계 포함 저장)
# =========================
excel_df = display.copy()
excel_buffer = BytesIO()
excel_df.to_excel(excel_buffer, index=False)

st.download_button("📥 엑셀 다운로드",
                   data=excel_buffer.getvalue(),
                   file_name="HYE_DATA.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =========================
# 고객별 묶음 합계
# =========================
st.subheader("👥 고객별 묶음 합계")
group = display.groupby("고객명")["합계"].sum().reset_index()
st.dataframe(group)

# =========================
# VIP
# =========================
st.subheader("💎 고객 등급")
vip = group.copy()
vip["등급"] = vip["합계"].apply(lambda x: "💎 VIP" if x >= 1000000 else "🟢 일반")
st.dataframe(vip)

# =========================
# 미입금
# =========================
st.subheader("⚠ 고객별 미입금")
unpaid = display[display["입금여부"]==False].groupby("고객명")["합계"].sum().reset_index()
st.dataframe(unpaid)

# =========================
# 정산 요약
# =========================
total = display["합계"].sum()
paid_sum = display[display["입금여부"]==True]["합계"].sum()
unpaid_sum = display[display["입금여부"]==False]["합계"].sum()

c1,c2,c3 = st.columns(3)
c1.metric("총매출", f"{total:,.0f}원")
c2.metric("입금액", f"{paid_sum:,.0f}원")
c3.metric("미입금", f"{unpaid_sum:,.0f}원")

# =========================
# 일별 매출 (만원 단위 강제)
# =========================
st.subheader("📊 이번달 일별 매출")

display["날짜"] = pd.to_datetime(display["날짜"], errors="coerce")
today = datetime.today()

month_data = display[
    (display["날짜"].dt.year == today.year) &
    (display["날짜"].dt.month == today.month)
]

if not month_data.empty:
    month_data["일"] = month_data["날짜"].dt.day
    daily = month_data.groupby("일")["합계"].sum().reset_index()

    fig, ax = plt.subplots()
    ax.plot(daily["일"], daily["합계"], marker="o")
    ax.yaxis.set_major_locator(MultipleLocator(10000))
    ax.set_xticks(daily["일"])
    st.pyplot(fig)
