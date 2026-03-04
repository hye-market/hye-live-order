import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics

st.set_page_config(layout="wide")

DATA_FILE = "orders_data.xlsx"

# 데이터 로드
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_excel(DATA_FILE)
    return pd.DataFrame(columns=["삭제","날짜","고객명","상품번호","수량","단가","입금여부"])

def save_data(df):
    df.to_excel(DATA_FILE,index=False)

orders = load_data()
orders["수량"]=pd.to_numeric(orders["수량"],errors="coerce").fillna(0)
orders["단가"]=pd.to_numeric(orders["단가"],errors="coerce").fillna(0)
orders["합계"]=orders["수량"]*orders["단가"]

st.title("💎 HYE LIVE ORDER SYSTEM")

# =========================
# 1 상단 버튼
# =========================
c1,c2,c3=st.columns(3)

with c1:
    excel_buffer=BytesIO()
    orders.to_excel(excel_buffer,index=False)

    st.download_button(
        "엑셀다운로드",
        excel_buffer.getvalue(),
        file_name="orders.xlsx"
    )

with c2:
    if st.button("초기화"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.rerun()

with c3:
    if st.button("월초기화"):
        today=datetime.today()
        orders["날짜"]=pd.to_datetime(orders["날짜"],errors="coerce")
        orders=orders[
            ~((orders["날짜"].dt.year==today.year)&
              (orders["날짜"].dt.month==today.month))
        ]
        save_data(orders)
        st.rerun()

# =========================
# 2 매출 요약
# =========================
total=orders["합계"].sum()
paid=orders[orders["입금여부"]==True]["합계"].sum()
unpaid=orders[orders["입금여부"]==False]["합계"].sum()

s1,s2,s3=st.columns(3)
s1.metric("총매출액",f"{total:,.0f}")
s2.metric("입금액",f"{paid:,.0f}")
s3.metric("미입금",f"{unpaid:,.0f}")

# =========================
# 3 주문 입력
# =========================
st.subheader("주문입력")

with st.form("order_form",clear_on_submit=True):

    c1,c2,c3,c4,c5,c6,c7=st.columns(7)

    order_date=c1.date_input("날짜",value=date.today())
    name=c2.text_input("고객명")
    product=c3.text_input("상품번호")
    qty=c4.number_input("수량",min_value=1,value=1)
    price=c5.number_input("단가",min_value=0,value=0)
    paid=c6.checkbox("입금완료")

    submit=c7.form_submit_button("주문추가")

    if submit and name:

        new=pd.DataFrame([{
            "삭제":False,
            "날짜":order_date.strftime("%y-%m-%d"),
            "고객명":name,
            "상품번호":product,
            "수량":qty,
            "단가":price,
            "입금여부":paid
        }])

        orders=pd.concat([orders,new],ignore_index=True)
        save_data(orders)
        st.rerun()

# =========================
# 4 고객 검색
# =========================
search=st.text_input("고객검색")

display=orders.copy()

if search:
    display=display[display["고객명"].str.contains(search,na=False)]

display["합계"]=display["수량"]*display["단가"]

# =========================
# 5 주문 리스트
# =========================
st.subheader("주문리스트")

display=display[
["삭제","날짜","고객명","상품번호","수량","단가","합계","입금여부"]
]

edited=st.data_editor(display,use_container_width=True)

edited["합계"]=edited["수량"]*edited["단가"]

save_data(edited.drop(columns="합계"))

# =========================
# 6 선택삭제
# =========================
if st.button("선택삭제"):
    edited=edited[edited["삭제"]==False]
    save_data(edited.drop(columns="합계"))
    st.rerun()

# =========================
# 7 고객정산서
# =========================
st.subheader("고객정산서")

if not edited.empty:

    customer=st.selectbox("고객명",edited["고객명"].unique())

    if st.button("PDF다운"):

        pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))

        data=edited[edited["고객명"]==customer]

        buffer=BytesIO()

        doc=SimpleDocTemplate(buffer,pagesize=A4)

        table_data=[list(data.columns)]+data.astype(str).values.tolist()

        table=Table(table_data)

        table.setStyle([
            ("GRID",(0,0),(-1,-1),1,colors.black),
            ("FONTNAME",(0,0),(-1,-1),'HYSMyeongJo-Medium')
        ])

        doc.build([table])

        st.download_button(
            "정산서 다운로드",
            buffer.getvalue(),
            file_name=f"{customer}_정산서.pdf"
        )

# =========================
# 8 고객 미입금 / 고객 합계
# =========================
col1,col2=st.columns(2)

with col1:

    st.subheader("고객별 미입금")

    unpaid_df=edited[edited["입금여부"]==False]

    unpaid_sum=unpaid_df.groupby("고객명")["합계"].sum().reset_index()

    st.dataframe(unpaid_sum)

with col2:

    st.subheader("고객별 합계")

    group_sum=edited.groupby("고객명")["합계"].sum().reset_index()

    st.dataframe(group_sum)

# =========================
# 9 고객 등급
# =========================
st.subheader("고객 등급")

vip=group_sum.copy()

vip["등급"]=vip["합계"].apply(lambda x:"VIP" if x>=500000 else "일반")

st.dataframe(vip)

# =========================
# 10 매출 그래프
# =========================
st.subheader("이번달 일별 매출")

chart_df=edited.copy()

chart_df["날짜"]=pd.to_datetime(chart_df["날짜"],errors="coerce")

today=datetime.today()

month_df=chart_df[
(chart_df["날짜"].dt.year==today.year)&
(chart_df["날짜"].dt.month==today.month)
]

if not month_df.empty:

    month_df["일"]=month_df["날짜"].dt.day

    daily=month_df.groupby("일")["합계"].sum().reset_index()

    fig,ax=plt.subplots()

    ax.plot(daily["일"],daily["합계"],marker="o")

    ax.set_xticks(daily["일"])

    ax.yaxis.set_major_locator(MultipleLocator(5000))

    st.pyplot(fig)
