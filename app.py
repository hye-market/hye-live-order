# ======================
# 브랜드 UI 설정
# ======================
st.markdown("""
    <style>
        .main {background-color:#0e1117;}
        h1, h2, h3 {color:#ffffff;}
        .stButton>button {
            background-color:#c9a86a;
            color:black;
            border-radius:12px;
            height:50px;
            font-weight:bold;
        }
    </style>
""", unsafe_allow_html=True)

st.image("hye_logo.png", width=200)
st.markdown("## HYE LIVE ORDER SYSTEM")
import streamlit as st
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt

st.set_page_config(page_title="HYE LIVE ORDER FINAL 2.2", layout="wide")

DATA_FILE = "orders_data.xlsx"

COLUMNS = [
    "삭제","날짜","고객명","상품번호",
    "수량","단가","입금여부"
]

# --------------------
# 데이터 로드
# --------------------
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_excel(DATA_FILE)
        df = df.reindex(columns=COLUMNS)
        return df
    return pd.DataFrame(columns=COLUMNS)

# --------------------
# 저장 + 자동백업
# --------------------
def save_data(df):
    df.to_excel(DATA_FILE, index=False)
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(backup_name, index=False)

orders = load_data()

st.title("💎 HYE LIVE ORDER FINAL 2.2")

# =====================
# 🔥 엑셀 저장 버튼 상단 이동
# =====================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE,"rb") as f:
        st.download_button("📥 엑셀 다운로드",f,file_name="HYE_DATA.xlsx")

# --------------------
# 상단 버튼
# --------------------
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
                ~(
                    (orders["날짜"].dt.year == today.year) &
                    (orders["날짜"].dt.month == today.month)
                )
            ]
            save_data(orders)
            st.success("이번달 데이터 삭제 완료")
            st.rerun()

# --------------------
# 주문 입력
# --------------------
st.subheader("주문 입력")

with st.form("form", clear_on_submit=True):
    c1,c2,c3,c4,c5 = st.columns(5)
    d = c1.date_input("날짜", datetime.today())
    name = c2.text_input("고객명")
    product = c3.text_input("상품번호")
    qty = c4.number_input("수량",1)
    price = c5.number_input("단가",0)

    if st.form_submit_button("주문추가"):
        new = pd.DataFrame([{
            "삭제":False,
            "날짜":str(d),
            "고객명":name,
            "상품번호":product,
            "수량":qty,
            "단가":price,
            "입금여부":False
        }])
        orders = pd.concat([orders,new],ignore_index=True)
        save_data(orders)
        st.rerun()

# --------------------
# 숫자 안정 변환 + 합계
# --------------------
orders["수량"]=pd.to_numeric(orders["수량"],errors="coerce").fillna(0)
orders["단가"]=pd.to_numeric(orders["단가"],errors="coerce").fillna(0)
orders["합계"]=orders["수량"]*orders["단가"]

# --------------------
# 고객 검색
# --------------------
search = st.text_input("🔎 고객 검색")

if search:
    display = orders[orders["고객명"].str.contains(search,na=False)]
else:
    display = orders

display = display.sort_values(by=["고객명","날짜"])

st.subheader("📋 주문 리스트")

# 🔥 미입금 자동 강조
def highlight_unpaid(row):
    if row["입금여부"] == False:
        return ['background-color: #ffe6e6']*len(row)
    return ['']*len(row)

styled = display.style.apply(highlight_unpaid,axis=1)

edited = st.data_editor(display,use_container_width=True)

# 합계 재계산
edited["수량"]=pd.to_numeric(edited["수량"],errors="coerce").fillna(0)
edited["단가"]=pd.to_numeric(edited["단가"],errors="coerce").fillna(0)
edited["합계"]=edited["수량"]*edited["단가"]

if not edited[COLUMNS].equals(display[COLUMNS]):
    save_data(edited[COLUMNS])
    st.rerun()

# --------------------
# 삭제
# --------------------
if st.button("🗑 선택 삭제"):
    updated = edited[edited["삭제"]!=True]
    save_data(updated[COLUMNS])
    st.rerun()

# --------------------
# 고객별 묶음 합계
# --------------------
st.subheader("👥 고객별 묶음 합계")

group_summary = (
    edited.groupby("고객명")["합계"]
    .sum()
    .reset_index()
    .sort_values(by="합계",ascending=False)
)

st.dataframe(group_summary,use_container_width=True)

# --------------------
# 💎 고객 등급 자동 분류
# --------------------
st.subheader("💎 고객 등급")

vip = (
    edited.groupby("고객명")["합계"]
    .sum()
    .reset_index()
)

vip["등급"] = vip["합계"].apply(
    lambda x: "💎 VIP" if x >= 1000000 else "🟢 일반"
)

st.dataframe(vip.sort_values(by="합계",ascending=False),use_container_width=True)

# --------------------
# 고객별 미입금
# --------------------
st.subheader("⚠ 고객별 미입금")

unpaid = (
    edited[edited["입금여부"]==False]
    .groupby("고객명")["합계"]
    .sum()
    .reset_index()
    .sort_values(by="합계",ascending=False)
)

st.dataframe(unpaid,use_container_width=True)

# --------------------
# 정산 요약
# --------------------
total=edited["합계"].sum()
paid=edited[edited["입금여부"]==True]["합계"].sum()
unpaid_total=edited[edited["입금여부"]==False]["합계"].sum()

c1,c2,c3=st.columns(3)
c1.metric("총매출",f"{total:,.0f}원")
c2.metric("입금액",f"{paid:,.0f}원")
c3.metric("미입금",f"{unpaid_total:,.0f}원")

# --------------------
# 🔥 그래프 날짜 정상 수정
# --------------------
st.subheader("📊 이번달 일별 매출")

edited["날짜"]=pd.to_datetime(edited["날짜"])
today=datetime.today()

month_data=edited[
    (edited["날짜"].dt.year==today.year)&
    (edited["날짜"].dt.month==today.month)
]

if not month_data.empty:
    month_data["일"]=month_data["날짜"].dt.day
    daily=month_data.groupby("일")["합계"].sum().reset_index()

    plt.figure()
    plt.plot(daily["일"],daily["합계"],marker="o")
    plt.xticks(range(1,32))
    plt.xlabel("일")
    plt.ylabel("매출")
    st.pyplot(plt)