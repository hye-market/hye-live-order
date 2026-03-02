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
# 로그인 (유지)
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
    "삭제","날짜","고객명","상품번호",
    "수량","단가","입금여부"
]

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
orders["입금여부"] = orders["입금여부"].fillna(False)
orders["합계"] = orders["수량"] * orders["단가"]

# =========================
# 주문 입력 박스 (확실한 테두리 복구)
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

def submit_order():
    if st.session_state.name_input:
        new = pd.DataFrame([{
            "삭제":False,
            "날짜":str(st.session_state.date_input),
            "고객명":st.session_state.name_input,
            "상품번호":st.session_state.product_input,
            "수량":st.session_state.qty_input,
            "단가":st.session_state.price_input,
            "입금여부":st.session_state.paid_input
        }])
        df = pd.concat([orders,new],ignore_index=True)
        save_data(df)
        st.rerun()

with st.form("order_form", clear_on_submit=True):
    c1,c2,c3,c4,c5,c6,c7 = st.columns(7)

    c1.date_input("날짜", datetime.today(), key="date_input")
    c2.text_input("고객명", key="name_input")
    c3.text_input("상품번호", key="product_input")
    c4.number_input("수량", min_value=1, value=1, key="qty_input")
    c5.number_input("단가", min_value=0, value=0, key="price_input")
    c6.checkbox("입금완료", key="paid_input")
    submit = c7.form_submit_button("주문 추가", on_click=submit_order)

st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 검색
# =========================
search = st.text_input("🔎 고객 검색")
display = orders.copy()

if search:
    display = display[display["고객명"].astype(str).str.contains(search, na=False)]

# 고객별 자동 정렬 (묶음 적용)
display = display.sort_values(by=["고객명","날짜"])

display["합계"] = display["수량"] * display["단가"]

# =========================
# 주문 리스트
# =========================
st.subheader("📋 주문 리스트")

editor = display[[
    "삭제","날짜","고객명","상품번호",
    "수량","단가","합계","입금여부"
]]

edited = st.data_editor(editor, use_container_width=True)

edited["수량"] = pd.to_numeric(edited["수량"], errors="coerce").fillna(0)
edited["단가"] = pd.to_numeric(edited["단가"], errors="coerce").fillna(0)
edited["합계"] = edited["수량"] * edited["단가"]

# 삭제 버튼 명확 추가
if st.button("🗑 선택 삭제"):
    edited = edited[edited["삭제"] == False]
    save_data(edited[BASE_COLUMNS])
    st.rerun()

# 저장
save_data(edited[BASE_COLUMNS])

# =========================
# 엑셀 다운로드 (합계 포함)
# =========================
excel_buffer = BytesIO()
edited.to_excel(excel_buffer, index=False)
st.download_button("📥 엑셀 다운로드",
                   data=excel_buffer.getvalue(),
                   file_name="HYE_DATA.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =========================
# 고객별 묶음 합계
# =========================
st.subheader("👥 고객별 묶음 합계")
group = edited.groupby("고객명")["합계"].sum().reset_index()
st.dataframe(group.sort_values(by="합계", ascending=False))

# =========================
# 매출 차트 (5,000 단위)
# =========================
st.subheader("📊 이번달 일별 매출")

edited["날짜"] = pd.to_datetime(edited["날짜"], errors="coerce")
today = datetime.today()

month_data = edited[
    (edited["날짜"].dt.year == today.year) &
    (edited["날짜"].dt.month == today.month)
]

if not month_data.empty:
    month_data["일"] = month_data["날짜"].dt.day
    daily = month_data.groupby("일")["합계"].sum().reset_index()

    fig, ax = plt.subplots()
    ax.plot(daily["일"], daily["합계"], marker="o")
    ax.set_xticks(daily["일"])
    ax.yaxis.set_major_locator(MultipleLocator(5000))
    st.pyplot(fig)
