import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime,date
from io import BytesIO
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

st.set_page_config(layout="wide")

st.markdown("""
<style>
button{height:48px;font-size:18px;}
[data-testid="stDataFrame"]{font-size:18px;}
</style>
""",unsafe_allow_html=True)

# ------------------
# 로그인
# ------------------

if "login_expire" not in st.session_state:
    st.session_state.login_expire=0

if time.time()>st.session_state.login_expire:

    st.title("HYE ERP LOGIN")

    user=st.text_input("아이디")
    pw=st.text_input("비밀번호",type="password")

    if st.button("로그인"):
        if user=="HYE" and pw=="102108":
            st.session_state.login_expire=time.time()+86400
            st.rerun()

    st.stop()

# ------------------
# 데이터
# ------------------

DATA="orders.xlsx"

def load():
    if os.path.exists(DATA):
        return pd.read_excel(DATA)
    return pd.DataFrame(columns=["삭제","날짜","고객명","상품번호","수량","단가","입금여부"])

def save(df):
    df.to_excel(DATA,index=False)

orders=load()

orders["수량"]=pd.to_numeric(orders["수량"],errors="coerce").fillna(0)
orders["단가"]=pd.to_numeric(orders["단가"],errors="coerce").fillna(0)

orders["합계"]=orders["수량"]*orders["단가"]

st.title("HYE LIVE ORDER SYSTEM")

# ------------------
# 상단버튼
# ------------------

c1,c2,c3=st.columns(3)

with c1:
    buf=BytesIO()
    orders.to_excel(buf,index=False)
    st.download_button("엑셀다운",buf.getvalue(),"orders.xlsx")

with c2:
    if st.button("초기화"):
        orders=orders.iloc[0:0]
        save(orders)
        st.rerun()

with c3:
    if st.button("월초기화"):
        today=datetime.today()
        orders["날짜"]=pd.to_datetime(orders["날짜"])
        orders=orders[~((orders["날짜"].dt.month==today.month)&(orders["날짜"].dt.year==today.year))]
        save(orders)
        st.rerun()

# ------------------
# 매출
# ------------------

total=orders["합계"].sum()
paid=orders[orders["입금여부"]==True]["합계"].sum()
unpaid=orders[orders["입금여부"]==False]["합계"].sum()

m1,m2,m3=st.columns(3)

m1.metric("총매출",f"{total:,.0f}")
m2.metric("입금액",f"{paid:,.0f}")
m3.metric("미입금",f"{unpaid:,.0f}")

# ------------------
# 주문입력
# ------------------

st.subheader("주문입력")

c1,c2,c3,c4,c5,c6=st.columns(6)

d=c1.date_input("날짜",date.today())
name=c2.text_input("고객명")
product=c3.text_input("상품번호")
qty=c4.number_input("수량",1)
price=c5.number_input("단가",0)
paid=c6.checkbox("입금완료")

total_price=qty*price
st.write("합계:",total_price)

if st.button("엔터주문추가") or st.session_state.get("enter",False):

    new=pd.DataFrame([{
    "삭제":False,
    "날짜":d.strftime("%y-%m-%d"),
    "고객명":name,
    "상품번호":product,
    "수량":qty,
    "단가":price,
    "입금여부":paid
    }])

    orders=pd.concat([orders,new],ignore_index=True)
    save(orders)
    st.rerun()

# ------------------
# 전체입금 삭제
# ------------------

c1,c2=st.columns(2)

if c1.button("전체입금"):
    orders["입금여부"]=True
    save(orders)
    st.rerun()

if c2.button("전체삭제"):
    orders=orders.iloc[0:0]
    save(orders)
    st.rerun()

# ------------------
# 고객검색
# ------------------

search=st.text_input("고객검색")

display=orders.copy()

if search:
    display=display[display["고객명"].str.contains(search)]

display["합계"]=display["수량"]*display["단가"]

# ------------------
# 주문리스트
# ------------------

edited=st.data_editor(display,use_container_width=True)

edited["합계"]=edited["수량"]*edited["단가"]

save(edited.drop(columns="합계"))

# ------------------
# 선택삭제
# ------------------

if st.button("선택삭제"):
    edited=edited[edited["삭제"]==False]
    save(edited.drop(columns="합계"))
    st.rerun()

# ------------------
# 고객정산서
# ------------------

st.subheader("고객정산서")

customer=st.selectbox("고객명",edited["고객명"].unique())

c1,c2=st.columns(2)

data=edited[edited["고객명"]==customer]

with c1:

    pdf=BytesIO()
    p=canvas.Canvas(pdf)
    y=800

    for i,row in data.iterrows():
        p.drawString(50,y,str(row.values))
        y-=20

    p.save()

    st.download_button("PDF다운",pdf.getvalue(),f"{customer}.pdf")

with c2:

    excel=BytesIO()
    data.to_excel(excel,index=False)

    st.download_button("고객엑셀다운",excel.getvalue(),f"{customer}.xlsx")

# ------------------
# 고객 미입금 / 합계
# ------------------

c1,c2=st.columns(2)

with c1:
    st.subheader("고객별 미입금")
    st.dataframe(edited[edited["입금여부"]==False].groupby("고객명")["합계"].sum())

with c2:
    st.subheader("고객별 합계")
    group=edited.groupby("고객명")["합계"].sum()
    st.dataframe(group)

# ------------------
# VIP
# ------------------

st.subheader("고객 등급(50만원 이상)")

vip=group.reset_index()

vip["등급"]=vip["합계"].apply(lambda x:"⭐VIP" if x>=500000 else "일반")

st.dataframe(vip)

# ------------------
# 매출 그래프
# ------------------

st.subheader("이번달 일별 매출")

chart=orders.copy()

chart["날짜"]=pd.to_datetime(chart["날짜"])

today=datetime.today()

chart=chart[(chart["날짜"].dt.month==today.month)&(chart["날짜"].dt.year==today.year)]

if not chart.empty:

    chart["일"]=chart["날짜"].dt.day

    daily=chart.groupby("일")["합계"].sum()

    fig,ax=plt.subplots()

    ax.plot(daily.index,daily.values,marker="o")

    ax.yaxis.set_major_locator(MultipleLocator(5000))

    st.pyplot(fig)
