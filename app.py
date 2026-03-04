import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

st.set_page_config(layout="wide")

FILE = "orders.xlsx"

# PDF 한글폰트
if os.path.exists("NanumGothic.ttf"):
    pdfmetrics.registerFont(TTFont("Nanum", "NanumGothic.ttf"))
    FONT = "Nanum"
else:
    FONT = "Helvetica"


def load():
    if os.path.exists(FILE):
        return pd.read_excel(FILE)

    return pd.DataFrame(columns=[
        "삭제", "날짜", "고객명", "상품번호", "수량", "단가", "입금여부"
    ])


def save(df):
    df.to_excel(FILE, index=False)


orders = load()

orders["수량"] = pd.to_numeric(orders["수량"], errors="coerce").fillna(0)
orders["단가"] = pd.to_numeric(orders["단가"], errors="coerce").fillna(0)

orders["합계"] = orders["수량"] * orders["단가"]

st.title("HYE LIVE ORDER SYSTEM")


# 상단버튼
c1, c2, c3 = st.columns(3)

with c1:
    buf = BytesIO()
    orders.to_excel(buf, index=False)
    st.download_button("엑셀다운", buf.getvalue(), "orders.xlsx")

with c2:
    if st.button("초기화"):
        orders = orders.iloc[0:0]
        save(orders)
        st.rerun()

with c3:
    if st.button("월초기화"):
        today = datetime.today()
        orders["날짜"] = pd.to_datetime(orders["날짜"])

        orders = orders[
            ~((orders["날짜"].dt.year == today.year) &
              (orders["날짜"].dt.month == today.month))
        ]

        save(orders)
        st.rerun()


# 매출요약
total = orders["합계"].sum()
paid = orders[orders["입금여부"] == True]["합계"].sum()
unpaid = orders[orders["입금여부"] == False]["합계"].sum()

m1, m2, m3 = st.columns(3)

m1.metric("총매출", f"{total:,.0f}")
m2.metric("입금액", f"{paid:,.0f}")
m3.metric("미입금", f"{unpaid:,.0f}")


# 주문리스트
display = orders.copy()

st.subheader("주문리스트")

edited = st.data_editor(
    display[["삭제", "날짜", "고객명", "상품번호", "수량", "단가", "합계", "입금여부"]],
    use_container_width=True
)

# 🔥 엔터 입력시 합계 자동 적용
edited["수량"] = pd.to_numeric(edited["수량"], errors="coerce").fillna(0)
edited["단가"] = pd.to_numeric(edited["단가"], errors="coerce").fillna(0)

edited["합계"] = edited["수량"] * edited["단가"]

save(edited.drop(columns="합계"))


# 고객정산서
st.subheader("고객정산서")

customer = st.selectbox("고객명", edited["고객명"].unique())

df = edited[edited["고객명"] == customer]

pdf_buffer = BytesIO()

table_data = [df.columns.tolist()] + df.values.tolist()

doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)

doc.build([Table(table_data)])

c1, c2 = st.columns(2)

with c1:
    st.download_button("PDF다운", pdf_buffer.getvalue(), f"{customer}.pdf")

with c2:
    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False)
    st.download_button("고객 엑셀다운", excel_buffer.getvalue(), f"{customer}.xlsx")


# 고객별 합계
c1, c2 = st.columns(2)

with c1:
    st.subheader("고객별 미입금")
    unpaid_df = edited[edited["입금여부"] == False]
    st.dataframe(unpaid_df.groupby("고객명")["합계"].sum())

with c2:
    st.subheader("고객별 합계")
    group = edited.groupby("고객명")["합계"].sum()
    st.dataframe(group)


# VIP
st.subheader("고객 등급(50만원 이상)")

vip = group.reset_index()

vip["등급"] = vip["합계"].apply(
    lambda x: "👑VIP" if x >= 500000 else "일반"
)

st.dataframe(vip)


# 매출그래프
st.subheader("이번달 일별 매출")

chart = orders.copy()

chart["날짜"] = pd.to_datetime(chart["날짜"])

today = datetime.today()

chart = chart[
    (chart["날짜"].dt.year == today.year) &
    (chart["날짜"].dt.month == today.month)
]

chart["일"] = chart["날짜"].dt.day

daily = chart.groupby("일")["합계"].sum()

if len(daily) > 0:

    fig, ax = plt.subplots()

    ax.plot(daily.index, daily.values, marker="o")

    ax.set_xlabel("날짜")
    ax.set_ylabel("금액")

    ax.yaxis.set_major_locator(MultipleLocator(10000))

    st.pyplot(fig)
