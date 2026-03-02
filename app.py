import streamlit as st
import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from io import BytesIO

# ======================
# 로그인 (유지)
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
# 데이터 로드/저장 (유지)
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
# 합계 계산 (유지)
# ======================
orders["수량"] = pd.to_numeric(orders["수량"], errors="coerce").fillna(0)
orders["단가"] = pd.to_numeric(orders["단가"], errors="coerce").fillna(0)
orders["합계"] = orders["수량"] * orders["단가"]

# ======================
# 리스트 (🔥 위치만 교체)
# ======================
display = orders.copy()

display = display[[
    "삭제","날짜","고객명","상품번호",
    "수량","단가","합계","입금여부"  # ← 여기만 위치 변경
]]

st.subheader("📋 주문 리스트")
edited = st.data_editor(display, use_container_width=True)

edited["수량"] = pd.to_numeric(edited["수량"], errors="coerce").fillna(0)
edited["단가"] = pd.to_numeric(edited["단가"], errors="coerce").fillna(0)
edited["합계"] = edited["수량"] * edited["단가"]

# ======================
# 🔥 PDF 한글 완전 해결
# ======================
st.subheader("📄 고객 정산서")

if not edited.empty:
    customer_list = edited["고객명"].dropna().unique()
    selected_customer = st.selectbox("고객 선택", customer_list)

    if st.button("정산서 PDF 생성"):

        # 한글 폰트 등록
        font_path = "NanumGothic.ttf"

        if not os.path.exists(font_path):
            st.error("NanumGothic.ttf 파일을 GitHub에 업로드해주세요.")
            st.stop()

        pdfmetrics.registerFont(TTFont("Nanum", font_path))

        data = edited[edited["고객명"] == selected_customer].copy()
        pdf_columns = ["날짜","상품번호","수량","단가","합계","입금여부"]
        data = data[pdf_columns]

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)

        table_data = [pdf_columns] + data.values.tolist()

        table = Table(table_data)
        table.setStyle([
            ("GRID",(0,0),(-1,-1),1,colors.black),
            ("FONTNAME",(0,0),(-1,-1),"Nanum"),
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
