import streamlit as st
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from io import BytesIO

# =====================
# 로그인
# =====================
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

COLUMNS = [
    "삭제","날짜","고객명","상품번호",
    "수량","단가","입금여부"
]

# =====================
# 데이터
# =====================
def load():
    if os.path.exists(DATA_FILE):
        return pd.read_excel(DATA_FILE)
    return pd.DataFrame(columns=COLUMNS)

def save(df):
    df.to_excel(DATA_FILE, index=False)
    backup = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(backup, index=False)

orders = load()

# =====================
# 합계 계산 유지
# =====================
orders["수량"] = pd.to_numeric(orders["수량"], errors="coerce").fillna(0)
orders["단가"] = pd.to_numeric(orders["단가"], errors="coerce").fillna(0)
orders["합계"] = orders["수량"] * orders["단가"]

# =====================
# 🔥 고객 정산서 (오류 수정 완료)
# =====================
st.subheader("📄 고객 정산서")

if not orders.empty:
    customer_list = orders["고객명"].dropna().unique()
    selected_customer = st.selectbox("고객 선택", customer_list)

    if st.button("정산서 PDF 생성"):
        customer_data = orders[orders["고객명"] == selected_customer].copy()

        # 안전하게 컬럼 재정렬
        pdf_columns = ["날짜","상품번호","수량","단가","합계","입금여부"]
        customer_data = customer_data[pdf_columns]

        # 모든 값을 문자열로 변환 (PDF 안전처리)
        customer_data = customer_data.astype(str)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)

        table_data = [pdf_columns] + customer_data.values.tolist()

        table = Table(table_data)
        table.setStyle([
            ("GRID",(0,0),(-1,-1),1,colors.black),
            ("BACKGROUND",(0,0),(-1,0),colors.lightgrey)
        ])

        doc.build([table])

        st.download_button(
            label="📥 PDF 다운로드",
            data=buffer.getvalue(),
            file_name=f"{selected_customer}_정산서.pdf",
            mime="application/pdf"
        )
