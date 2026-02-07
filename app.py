import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import json

# ==========================================
# 👇 你的表格链接 (保持不变)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1Rxp_7Ash8-B9hfwlci-DbSZ976yNy4usVOkYe5xIG70/edit?gid=0#gid=0"
# ==========================================

# --- 1. 连接功能 (保持最稳的容错版) ---
@st.cache_resource
def init_connection():
    # 尝试读取 Secrets (云端模式)
    try:
        if "type" in st.secrets and st.secrets["type"] == "service_account":
            return gspread.service_account_from_dict(st.secrets)
        if "google_key" in st.secrets:
            # 处理 google_key 可能是字符串或对象的情况
            secret_val = st.secrets["google_key"]
            if isinstance(secret_val, str):
                # 如果是字符串（被引号包围），尝试解析 JSON
                try:
                    key_dict = json.loads(secret_val)
                    return gspread.service_account_from_dict(key_dict)
                except:
                    # 如果解析失败，可能是单引号包裹的纯文本，尝试不用解析直接用？
                    # 这里的逻辑比较复杂，通常上面两步能覆盖大多数情况
                    pass
            elif isinstance(secret_val, dict):
                return gspread.service_account_from_dict(secret_val)
    except:
        pass
    
    # 本地模式
    try:
        return gspread.service_account(filename='key.json')
    except:
        return None

# --- 2. 核心功能：读、写、全量更新 ---
def get_data():
    client = init_connection()
    if client:
        try:
            sheet = client.open_by_url(SHEET_URL).sheet1
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"读取失败: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def append_row(row_data):
    """追加一行新数据"""
    client = init_connection()
    if client:
        sheet = client.open_by_url(SHEET_URL).sheet1
        sheet.append_row(row_data)

def update_entire_sheet(df):
    """【新功能】把修改后的整个表格写回 Google Sheets"""
    client = init_connection()
    if client:
        sheet = client.open_by_url(SHEET_URL).sheet1
        # 1. 清空原表
        sheet.clear()
        # 2. 准备数据：先把列名放进去，再放数据
        # (gspread 需要列表格式，不能直接传 DataFrame)
        val_list = [df.columns.values.tolist()] + df.values.tolist()
        # 3. 写入
        sheet.update(val_list)

# --- 3. 页面主逻辑 ---
def main():
    st.set_page_config(page_title="私人标记库 V2.0", page_icon="🗂️", layout="wide")
    st.title("🗂️ 我的私人标记库")

    # 使用 Tab 分页：一个用来快速录入，一个用来管理数据
    tab1, tab2 = st.tabs(["➕ 快速录入", "🛠️ 数据管理 (修改/搜索/删除)"])

    # === Tab 1: 快速录入 (手机端用这个方便) ===
    with tab1:
        with st.form("entry_form", clear_on_submit=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                title = st.text_input("标题/番号")
            with col2:
                category = st.selectbox("分类", ["小说", "ASMR", "AV", "同人本", "动画", "漫画"])
            
            rating = st.slider("评分", 0.0, 10.0, 7.5, 0.5)
            tags = st.text_input("标签 (空格分隔)")
            review = st.text_area("短评", height=100)
            
            if st.form_submit_button("保存到云端"):
                if title:
                    with st.spinner("正在写入..."):
                        row = [title, category, tags, rating, review, str(datetime.now())]
                        append_row(row)
                    st.success(f"✅ 已保存: {title}")
                    st.rerun()
                else:
                    st.warning("标题不能为空")

    # === Tab 2: 数据管理 (电脑端用这个爽) ===
    with tab2:
        st.info("💡 提示：双击单元格可以直接修改。选中行按 Delete 键可以删除（需点击下方保存按钮生效）。")
        
        # 1. 加载数据
        df = get_data()
        
        if not df.empty:
            # 2. 搜索框
            search_term = st.text_input("🔍 搜索 (标题/标签/短评)", placeholder="输入关键词...")
            
            # 如果有搜索词，过滤一下显示的数据
            if search_term:
                mask = df.apply(lambda x: x.astype(str).str.contains(search_term, case=False).any(), axis=1)
                display_df = df[mask]
            else:
                display_df = df

            # 3. 【核心】可编辑的数据表格
            # num_rows="dynamic" 允许你添加或删除行
            edited_df = st.data_editor(
                display_df,
                num_rows="dynamic",
                use_container_width=True,
                height=500,
                key="editor"
            )

            # 4. 保存按钮
            # 只有当数据发生变化时，用户手动点击保存，我们才去覆盖 Google Sheets
            # (为了防止误操作，我们做一个对比或者直接让用户确认)
            if st.button("💾 保存修改到云端 (慎点)"):
                with st.spinner("正在同步修改到 Google Sheets..."):
                    # 如果用户在搜索状态下修改，我们需要把修改合并回原表比较复杂
                    # V2.0 简单粗暴逻辑：目前只支持在“全量模式”下保存最稳
                    # 或者我们直接假定用户是在编辑 display_df
                    
                    if search_term:
                        st.warning("⚠️ 请清除搜索关键词后再进行【保存】操作，以免数据丢失！")
                    else:
                        update_entire_sheet(edited_df)
                        st.success("🎉 云端数据已更新！")
                        st.rerun()
        else:
            st.warning("暂无数据，或者连接失败。")

if __name__ == "__main__":
    main()