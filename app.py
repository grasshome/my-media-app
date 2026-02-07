import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime
import json

# ==========================================
# 👇 你的表格链接
SHEET_URL = "https://docs.google.com/spreadsheets/d/1Rxp_7Ash8-B9hfwlci-DbSZ976yNy4usVOkYe5xIG70/edit?gid=0#gid=0"
# ==========================================

# --- 1. 统一认证中心 (同时搞定表格和网盘) ---
@st.cache_resource
def get_creds():
    # 定义需要的权限范围：既能读写表格，也能读写网盘
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 尝试从 Secrets 读取
    if "google_key" in st.secrets:
        secret_val = st.secrets["google_key"]
        # 情况A: 是字符串（被引号包围）
        if isinstance(secret_val, str):
            try:
                # 兼容 JSON 字符串
                key_dict = json.loads(secret_val)
                return Credentials.from_service_account_info(key_dict, scopes=SCOPES)
            except:
                # 兼容单引号包裹的纯文本
                try:
                    # 极其暴力的容错：如果它是单引号包裹的，Streamlit读取时可能还是字符串
                    # 我们尝试把它当做dict结构处理（这里简化处理，通常上面的json.loads能搞定）
                    pass 
                except:
                    pass
        # 情况B: 已经被识别为字典对象
        elif isinstance(secret_val, dict):
            return Credentials.from_service_account_info(secret_val, scopes=SCOPES)
    
    # 本地模式
    try:
        return Credentials.from_service_account_file("key.json", scopes=SCOPES)
    except:
        return None

# --- 2. 核心功能：表格操作 ---
def get_sheet_client():
    creds = get_creds()
    if creds:
        client = gspread.authorize(creds)
        return client.open_by_url(SHEET_URL).sheet1
    return None

def get_data():
    sheet = get_sheet_client()
    if sheet:
        try:
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        except:
            return pd.DataFrame()
    return pd.DataFrame()

def update_entire_sheet(df):
    sheet = get_sheet_client()
    if sheet:
        sheet.clear()
        # gspread 需要将 dataframe 转换为 list 列表
        val_list = [df.columns.values.tolist()] + df.values.tolist()
        sheet.update(val_list)

# --- 3. 核心功能：网盘上传 ---
def upload_file_to_drive(uploaded_file):
    creds = get_creds()
    
    # 从 Secrets 获取文件夹 ID
    if "drive_folder_id" not in st.secrets:
        st.error("请在 Secrets 中配置 'drive_folder_id'")
        return None
        
    folder_id = st.secrets["drive_folder_id"]
    
    if creds and folder_id:
        # 构建 Drive 服务
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': uploaded_file.name,
            'parents': [folder_id]
        }
        
        # 转换文件流
        media = MediaIoBaseUpload(uploaded_file, mimetype=uploaded_file.type)
        
        # 执行上传
        try:
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            # 返回文件的查看链接
            return file.get('webViewLink')
        except Exception as e:
            st.error(f"Google Drive 上传错误: {e}")
            return None
    return None

# --- 4. 页面主逻辑 ---
def main():
    st.set_page_config(page_title="资源管理库 V3.0", page_icon="💾", layout="wide")
    st.title("💾 我的私人资源库")

    tab1, tab2 = st.tabs(["➕ 资源录入", "🛠️ 数据管理"])

    # === Tab 1: 录入 ===
    with tab1:
        with st.form("entry_form", clear_on_submit=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                title = st.text_input("标题/番号")
            with col2:
                category = st.selectbox("分类", ["刘备", "本子", "网黄", "AV", "ASMR", "COS", "L2D", "VAM"])
            
            # 评分滑块
            rating = st.slider("评分", 0.0, 10.0, 7.5, 0.5)
            
            tags = st.text_input("标签 (空格分隔)")
            review = st.text_area("短评", height=100)

            # 👇 【关键逻辑】如果评分 >= 8.0，显示文件上传框
            uploaded_file = None
            if rating >= 8.0:
                st.markdown("---")
                st.info("🌟 **高分作品判定！** 可以上传资源文件 (Zip/PDF/Audio/图片)")
                uploaded_file = st.file_uploader("选择文件上传 (将保存到 Google Drive)", 
                                               type=['zip', 'pdf', 'mp3', 'wav', 'jpg', 'png', 'txt'])

            submitted = st.form_submit_button("保存到云端")
            
            if submitted:
                if not title:
                    st.warning("标题不能为空")
                else:
                    with st.spinner("正在处理..."):
                        file_link = ""
                        # 1. 如果有文件，先上传文件
                        if uploaded_file:
                            with st.status("正在上传文件到 Google Drive...", expanded=True):
                                file_link = upload_file_to_drive(uploaded_file)
                                if file_link:
                                    st.write(f"✅ 文件上传成功！")
                                else:
                                    st.error("文件上传失败，将只保存文字信息。")
                        
                        # 2. 写入表格
                        sheet = get_sheet_client()
                        if sheet:
                            # 构造数据行，注意最后加了 file_link
                            # 确保顺序: title, category, tags, rating, review, created_at, file_link
                            row = [title, category, tags, rating, review, str(datetime.now()), file_link]
                            sheet.append_row(row)
                            st.success(f"✅ 记录已保存: {title}")
                            st.rerun()

    # === Tab 2: 管理 ===
    with tab2:
        st.info("💡 提示：双击单元格修改。如果包含文件链接，可以直接点击跳转下载。")
        df = get_data()
        
        if not df.empty:
            search_term = st.text_input("🔍 搜索", placeholder="输入关键词...")
            
            if search_term:
                mask = df.apply(lambda x: x.astype(str).str.contains(search_term, case=False).any(), axis=1)
                display_df = df[mask]
            else:
                display_df = df

            # 确保 file_link 列存在，防止报错
            if "file_link" not in display_df.columns:
                display_df["file_link"] = ""

            # 使用 Column Config 优化链接显示
            edited_df = st.data_editor(
                display_df,
                num_rows="dynamic",
                use_container_width=True,
                height=500,
                key="editor",
                column_config={
                    "file_link": st.column_config.LinkColumn(
                        "资源链接",
                        help="点击打开 Google Drive 文件",
                        validate="^https://.*",
                        max_chars=100,
                        display_text="🔗 下载文件"
                    ),
                    "rating": st.column_config.NumberColumn(
                        "评分",
                        min_value=0,
                        max_value=10,
                        step=0.5,
                        format="%.1f ⭐"
                    )
                }
            )

            if st.button("💾 保存表格修改"):
                with st.spinner("正在同步..."):
                    if search_term:
                        st.warning("请清除搜索词后再保存！")
                    else:
                        update_entire_sheet(edited_df)
                        st.success("更新完成！")
                        st.rerun()

if __name__ == "__main__":
    main()