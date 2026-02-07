import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import json

# ==========================================
# 👇 你的表格链接 (保持不变)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1Rxp_7Ash8-B9hfwlci-DbSZ976yNy4usVOkYe5xIG70/edit?gid=0#gid=0"
# ==========================================

@st.cache_resource
def init_connection():
    # 🕵️‍♂️ 自动侦探模式：
    # 1. 先看看是不是直接粘贴了 JSON (没有 google_key 的情况)
    if "type" in st.secrets and st.secrets["type"] == "service_account":
        return gspread.service_account_from_dict(st.secrets)

    # 2. 如果不是，再看看是不是用的 google_key 格式
    if "google_key" in st.secrets:
        # 情况 A: 它是字符串 (被 """ 包裹了)
        if isinstance(st.secrets["google_key"], str):
            try:
                key_dict = json.loads(st.secrets["google_key"])
                return gspread.service_account_from_dict(key_dict)
            except:
                pass
        # 情况 B: 它已经被自动识别为对象
        elif isinstance(st.secrets["google_key"], dict):
            return gspread.service_account_from_dict(st.secrets["google_key"])
            
    # 3. 最后尝试本地文件
    try:
        return gspread.service_account(filename='key.json')
    except:
        st.error("无法连接：请在 Secrets 里填入密钥")
        return None

def get_data():
    client = init_connection()
    if client:
        sheet = client.open_by_url(SHEET_URL).sheet1 
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    return pd.DataFrame()

def add_data(title, category, tags, rating, review):
    client = init_connection()
    if client:
        sheet = client.open_by_url(SHEET_URL).sheet1
        row = [title, category, tags, rating, review, str(datetime.now())]
        sheet.append_row(row)

def main():
    st.set_page_config(page_title="我的私人标记库", page_icon="📚")
    st.title("我的私人标记库")

    with st.expander("➕ 添加新记录", expanded=True):
        with st.form("entry_form", clear_on_submit=True):
            title = st.text_input("标题/番号")
            col1, col2 = st.columns(2)
            with col1:
                category = st.selectbox("分类", ["小说", "ASMR", "AV", "同人本", "动画"])
            with col2:
                rating = st.slider("评分", 0.0, 10.0, 7.5, 0.5)
            tags = st.text_input("标签 (空格分隔)")
            review = st.text_area("短评")
            
            if st.form_submit_button("保存到云端"):
                if title:
                    try:
                        with st.spinner("正在连接..."):
                            add_data(title, category, tags, rating, review)
                        st.success(f"已保存: {title}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"写入失败: {e}")

    st.divider()
    st.subheader("📚 最近收藏")
    try:
        df = get_data()
        if not df.empty:
            df = df.sort_values(by='created_at', ascending=False)
            for index, row in df.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{row['title']}** <small>[{row['category']}]</small>", unsafe_allow_html=True)
                    st.caption(f"🏷️ {row['tags']} | ⭐ {row['rating']}")
                    if row['review']: st.info(row['review'])
        else:
            st.info("表格是空的")
    except Exception as e:
        st.error(f"连接错误: {e}")

if __name__ == "__main__":
    main()