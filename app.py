import streamlit as st
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

# ======================
# 로그인 (수정 완료)
# ======================
USERS = {
    "HYE": "102108"
}

if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("HYE 관리자 로그인")
    username = st.text_input("아이디")
    password = st.text_input("비밀번호", type="password")

    if st.button("로그인"):
        if username in USERS and USERS[username] == password:
            st.session_state.login = True
            st.rerun()
        else:
            st.error("로그인 실패")

    st.stop()

# ======================
# 기본 설정
# ======================
st.set_page_config(page_title="HYE LIVE ORDER", layout="wide")

st.title("💎 HYE LIVE ORDER SYSTEM")

DATA_FILE = "orders_data.xlsx"

COLUMNS = [
    "삭제","날짜","고객명","상품번호",
    "수량","단가","입금여부"
]

# ======================
# 데이터 로드 / 저장
# ======================
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_excel(DATA_FILE)
        return df.reindex(columns=COLUMNS)
    return pd.DataFrame(columns=COLUMNS)

def save_data(df):
    df.to_excel(DATA_FILE, index=False)
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(backup_name, index=False)

orders = load_data()

# ======================
# 엑셀 다운로드
# ======================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "rb") as f:
        st.download_button("📥 엑셀 다운로드", f, file_name="HYE_DATA.xlsx")

# ======================
# 초기화
# ======================
col1, col2 = st.columns(2)

with col1:
    if st.button("🧹 전체 초기화"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.success("초기화 완료")
        st.stop()

with col2:
    if st.button("📅 이번달 월초기화"):
        if not orders.empty:
            orders["날짜"] = pd.to_datetime(orders["날짜"])
            today = datetime.today()
            orders = orders[
                ~((orders["날짜"].dt.year == today.year) &
                  (orders["날짜"].dt.month == today.month))
            ]
            save_data(orders)
            st.success("월 데이터 삭제 완료")
            st.rerun()

# ======================
# 주문 입력 (버튼 오른쪽)
# ======================
st.subheader("주문 입력")

with st.form("order_form", clear_on_submit=True):
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    date = c1.date_input("날짜", datetime.today())
    name = c2.text_input("고객명")
    product = c3.text_input("상품번호")
    qty = c4.number_input("수량", 1)
    price = c5.number_input("단가", 0)

    submit = c6.form_submit_button("주문 추가")

    if submit:
        new = pd.DataFrame([{
            "삭제": False,
            "날짜": str(date),
            "고객명": name,
            "상품번호": product,
            "수량": qty,
            "단가": price,
            "입금여부": False
        }])
        orders = pd.concat([orders, new], ignore_index=True)
        save_data(orders)
        st.rerun()

# ======================
# 합계 계산
# ======================
orders["수량"] = pd.to_numeric(orders["수량"], errors="coerce").fillna(0)
orders["단가"] = pd.to_numeric(orders["단가"], errors="coerce").fillna(0)
orders["합계"] = orders["수량"] * orders["단가"]

# ======================
# 고객 검색
# ======================
search = st.text_input("🔎 고객 검색")
display = orders
if search:
    display = orders[orders["고객명"].str.contains(search, na=False)]

display = display.sort_values(by=["고객명","날짜"])

st.subheader("📋 주문 리스트")

edited = st.data_editor(display, use_container_width=True)

edited["수량"] = pd.to_numeric(edited["수량"], errors="coerce").fillna(0)
edited["단가"] = pd.to_numeric(edited["단가"], errors="coerce").fillna(0)
edited["합계"] = edited["수량"] * edited["단가"]

if not edited[COLUMNS].equals(display[COLUMNS]):
    save_data(edited[COLUMNS])
    st.rerun()

if st.button("🗑 선택 삭제"):
    updated = edited[edited["삭제"] != True]
    save_data(updated[COLUMNS])
    st.rerun()

# ======================
# 🔥 고객별 묶음 합계
# ======================
st.subheader("👥 고객별 묶음 합계")
group = edited.groupby("고객명")["합계"].sum().reset_index()
st.dataframe(group.sort_values(by="합계", ascending=False))

# ======================
# 🔥 VIP 자동 분류
# ======================
st.subheader("💎 고객 등급")
vip = edited.groupby("고객명")["합계"].sum().reset_index()
vip["등급"] = vip["합계"].apply(lambda x: "💎 VIP" if x >= 1000000 else "🟢 일반")
st.dataframe(vip.sort_values(by="합계", ascending=False))

# ======================
# 🔥 고객별 미입금
# ======================
st.subheader("⚠ 고객별 미입금")
unpaid = edited[edited["입금여부"]==False].groupby("고객명")["합계"].sum().reset_index()
st.dataframe(unpaid.sort_values(by="합계", ascending=False))

# ======================
# 정산 요약
# ======================
total = edited["합계"].sum()
paid = edited[edited["입금여부"]==True]["합계"].sum()
unpaid_total = edited[edited["입금여부"]==False]["합계"].sum()

c1,c2,c3 = st.columns(3)
c1.metric("총매출", f"{total:,.0f}원")
c2.metric("입금액", f"{paid:,.0f}원")
c3.metric("미입금", f"{unpaid_total:,.0f}원")

# ======================
# 📊 일별 매출 (10만원 단위)
# ======================
st.subheader("📊 이번달 일별 매출")

edited["날짜"] = pd.to_datetime(edited["날짜"])
today = datetime.today()

month_data = edited[
    (edited["날짜"].dt.year == today.year) &
    (edited["날짜"].dt.month == today.month)
]

if not month_data.empty:
    month_data["일"] = month_data["날짜"].dt.day
    daily = month_data.groupby("일")["합계"].sum().reset_index()

    plt.figure()
    plt.plot(daily["일"], daily["합계"], marker="o")
    plt.xticks(range(1,32))
    plt.yticks(range(0, int(daily["합계"].max())+100000, 100000))
    plt.xlabel("일자")
    plt.ylabel("매출")
    st.pyplot(plt)
