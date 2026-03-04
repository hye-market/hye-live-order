import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime, date
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from io import BytesIO

st.set_page_config(layout="wide")

# --------------------------
# 태블릿 UI
# --------------------------

st.markdown("""
<style>
button {
height:45px;
font-size:18px;
}
[data-testid="stDataFrame"] {
font-size:18px;
}
</style>
""",unsafe_allow_html=True)

# --------------------------
# 로그인 24시간 유지
# --------------------------

SESSION_TIME=60*60*24

if "login" not in st.session_state:
    st.session_state.login=False

if "login_time" not in st.session_state:
    st.session_state.login_time=0

if time.time()-st.session_state.login_time>SESSION_TIME:
    st.session_state.login=False

if not st.session_state.login:

    st.title("HYE ERP 로그인")

    user=st.text_input("아이디")
    pw=st.text_input("비밀번호",type="password")

    if st.button("로그인"):
        if user=="HYE" and pw=="102108":
            st.session_state.login=True
            st.session_state.login_time=time.time()
            st.rerun()

    st.stop()

# --------------------------
# 데이터 로드
# --------------------------

DATA_FILE="orders.xlsx"

def load():

    if os.path.exists(DATA_FILE):
        return pd.read_excel(DATA_FILE)

    return pd.DataFrame(columns=[
    "삭제","날짜","고객명","상품번호",
    "수량","단가","입금여부","방송ID"
    ])

def save(df):
    df.to_excel(DATA_FILE,index=False)

orders=load()

orders["수량"]=pd.to_numeric(orders["수량"],errors="coerce").fillna(0)
orders["단가"]=pd.to_numeric(orders["단가"],errors="coerce").fillna(0)

orders["합계"]=orders["수량"]*orders["단가"]

st.title("HYE LIVE ORDER SYSTEM")

# --------------------------
# 상단 버튼
# --------------------------

c1,c2,c3=st.columns(3)

with c1:

    buffer=BytesIO()

    orders.to_excel(buffer,index=False)

    st.download_button("엑셀다운",buffer.getvalue(),"orders.xlsx")

with c2:

    if st.button("초기화"):
        orders=orders.iloc[0:0]
        save(orders)
        st.rerun()

with c3:

    if st.button("월초기화"):

        today=datetime.today()

        orders["날짜"]=pd.to_datetime(orders["날짜"],errors="coerce")

        orders=orders[
        ~((orders["날짜"].dt.year==today.year)&
        (orders["날짜"].dt.month==today.month))
        ]

        save(orders)

        st.rerun()

# --------------------------
# 매출 요약
# --------------------------

total=orders["합계"].sum()

paid=orders[orders["입금여부"]==True]["합계"].sum()

unpaid=orders[orders["입금여부"]==False]["합계"].sum()

m1,m2,m3=st.columns(3)

m1.metric("총매출",f"{total:,.0f}")
m2.metric("입금액",f"{paid:,.0f}")
m3.metric("미입금",f"{unpaid:,.0f}")

# --------------------------
# 주문 입력
# --------------------------

st.subheader("주문입력")

with st.form("order_form",clear_on_submit=True):

    c1,c2,c3,c4,c5,c6,c7,c8=st.columns(8)

    d=c1.date_input("날짜",date.today())

    name=c2.text_input("고객명")

    product=c3.text_input("상품번호")

    qty=c4.number_input("수량",1)

    price=c5.number_input("단가",0)

    paid=c6.checkbox("입금완료")

    broadcast=c7.text_input("방송ID")

    submit=c8.form_submit_button("주문추가")

    if submit and name:

        new=pd.DataFrame([{

        "삭제":False,
        "날짜":d.strftime("%y-%m-%d"),
        "고객명":name,
        "상품번호":product,
        "수량":qty,
        "단가":price,
        "입금여부":paid,
        "방송ID":broadcast

        }])

        orders=pd.concat([orders,new],ignore_index=True)

        save(orders)

        st.rerun()

# --------------------------
# 고객 검색
# --------------------------

search=st.text_input("고객검색")

display=orders.copy()

if search:
    display=display[display["고객명"].astype(str).str.contains(search)]

display["합계"]=display["수량"]*display["단가"]

# --------------------------
# 리스트 전체 버튼
# --------------------------

b1,b2=st.columns(2)

with b1:

    if st.button("전체 입금"):
        orders["입금여부"]=True
        save(orders)
        st.rerun()

with b2:

    if st.button("전체 삭제"):
        orders=orders.iloc[0:0]
        save(orders)
        st.rerun()

# --------------------------
# 주문 리스트
# --------------------------

st.subheader("주문리스트")

edited=st.data_editor(

display[
["삭제","날짜","고객명","상품번호","수량","단가","합계","입금여부"]
],

use_container_width=True
)

edited["합계"]=edited["수량"]*edited["단가"]

save(edited.drop(columns="합계"))

# --------------------------
# 선택 삭제
# --------------------------

if st.button("선택삭제"):

    edited=edited[edited["삭제"]==False]

    save(edited.drop(columns="합계"))

    st.rerun()

# --------------------------
# 고객 정산서
# --------------------------

st.subheader("고객정산서")

customer=st.selectbox("고객명",edited["고객명"].unique())

buffer=BytesIO()

edited[edited["고객명"]==customer].to_excel(buffer,index=False)

st.download_button("PDF다운",buffer.getvalue(),f"{customer}.xlsx")

# --------------------------
# 고객별 미입금 / 합계
# --------------------------

c1,c2=st.columns(2)

with c1:

    st.subheader("고객별 미입금")

    unpaid_df=edited[edited["입금여부"]==False]

    st.dataframe(unpaid_df.groupby("고객명")["합계"].sum())

with c2:

    st.subheader("고객별 합계")

    group=edited.groupby("고객명")["합계"].sum()

    st.dataframe(group)

# --------------------------
# VIP
# --------------------------

st.subheader("고객 등급")

vip=group.reset_index()

vip["등급"]=vip["합계"].apply(lambda x:"VIP" if x>=500000 else "일반")

st.dataframe(vip)

# --------------------------
# 방송 매출
# --------------------------

st.subheader("방송별 매출")

broadcast_sales=orders.groupby("방송ID")["합계"].sum()

st.bar_chart(broadcast_sales)

# --------------------------
# 일별 매출
# --------------------------

st.subheader("이번달 일별 매출")

chart=orders.copy()

chart["날짜"]=pd.to_datetime(chart["날짜"],errors="coerce")

today=datetime.today()

chart=chart[
(chart["날짜"].dt.year==today.year)&
(chart["날짜"].dt.month==today.month)
]

if not chart.empty:

    chart["일"]=chart["날짜"].dt.day

    daily=chart.groupby("일")["합계"].sum()

    fig,ax=plt.subplots()

    ax.plot(daily.index,daily.values,marker="o")

    ax.yaxis.set_major_locator(MultipleLocator(5000))

    st.pyplot(fig)
