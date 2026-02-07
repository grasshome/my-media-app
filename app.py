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
    # 尝试 1: 如果本地有 key.json，直接用 (本地模式)
    try:
        return gspread.service_account(filename='key.json')
    except:
        pass
    
    # 尝试 2: 如果本地没有，尝试从 Streamlit Secrets 读取 (云端模式)
    # 我们稍后会在云端后台填入这个 google_key
    try:
        key_dict = json.loads(st.secrets["google_key"])
        return gspread.service_account_from_dict(key_dict)
    except Exception as e:
        st.error(f"无法加载密钥，请检查配置。错误: {e}")
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
        st.error(f"连接失败: {e}")

if __name__ == "__main__":
    main()