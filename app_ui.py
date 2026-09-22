"""
JP Faceless YouTube Factory - Streamlit UI
Ứng dụng tự động hóa pipeline sản xuất video YouTube faceless Nhật Bản.
"""
import asyncio
import streamlit as st
from pathlib import Path
import os

from core.state import create_project, load_state, list_projects, STEPS
from core.brand import DISCLAIMER_JP, MASCOT_LOCK, STYLE_LOCK
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.flowkit_bridge import start_bridge_background

# Page config
st.set_page_config(
    page_title="JP Faceless YouTube Factory",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
.stButton > button {
    width: 100%;
    font-size: 16px;
    padding: 10px;
}
.step-card {
    background: #f0f2f6;
    border-radius: 10px;
    padding: 20px;
    margin: 10px 0;
}
.error-box {
    background: #ffe6e6;
    border-left: 4px solid #ff4444;
    padding: 15px;
    margin: 10px 0;
}
.success-box {
    background: #e6ffe6;
    border-left: 4px solid #44ff44;
    padding: 15px;
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)

# Initialize bridge in background (run once)
if "bridge_started" not in st.session_state:
    try:
        asyncio.run(start_bridge_background())
        st.session_state.bridge_started = True
        st.sidebar.success("✅ FlowKit Bridge đã khởi động")
    except Exception as e:
        st.sidebar.warning(f"⚠️ FlowKit Bridge chưa kết nối: {e}")

# Sidebar controls
st.sidebar.title("⚙️ Điều khiển")

# Project selection
if "pid" not in st.session_state:
    pid = create_project()
    st.session_state.pid = pid
else:
    pid = st.session_state.pid

st.sidebar.metric("Project ID", pid)

# Load state
state = load_state(pid)
if state is None:
    st.error("Không tìm thấy project. Tạo project mới...")
    st.session_state.pid = create_project()
    st.rerun()

current_step = state.get("step", "init")
st.sidebar.metric("Step hiện tại", current_step)

# Progress bar
step_idx = STEPS.index(current_step) if current_step in STEPS else 0
st.sidebar.progress(step_idx / len(STEPS))

st.sidebar.divider()

# Reset button
if st.sidebar.button("🔄 Tạo project mới"):
    st.session_state.pid = create_project()
    st.rerun()

# Main area
st.title("🎬 JP Faceless YouTube Factory")
st.markdown("Tự động hóa sản xuất video YouTube Nhật Bản (ngách tài chính/khởi nghiệp)")

# Initialize orchestrator
orchestrator = PipelineOrchestrator(pid)

# Step buttons with conditional enabling
st.header("📋 Các bước thực hiện")

col1, col2 = st.columns(2)

with col1:
    # Step 1: Suggest topics
    if st.button(
        "1️⃣ Gợi ý chủ đề",
        disabled=current_step != "init",
        key="btn_topics"
    ):
        with st.spinner("Đang生成 chủ đề..."):
            try:
                topics = orchestrator.suggest_topics()
                st.session_state.topics = topics
                st.success(f"✅ Đã生成 {len(topics)} chủ đề không trùng")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Lỗi: {e}")

    # Step 2: Select topic
    if "topics" in st.session_state or current_step == "topic":
        topics = st.session_state.get("topics", state.get("candidates", []))
        if topics:
            st.subheader("Chọn chủ đề:")
            for i, topic in enumerate(topics):
                topic_text = f"{topic['topic']} - {topic['angle']}"
                if st.button(f"📌 {topic_text}", key=f"topic_{i}"):
                    with st.spinner("Đang chọn chủ đề..."):
                        selected = orchestrator.select_topic(i)
                        st.session_state.selected_topic = selected
                        update_step_in_state(pid, "topic")
                        st.success(f"✅ Đã chọn: {selected['topic']}")
                        st.rerun()

with col2:
    # Step 3: Write script
    if st.button(
        "2️⃣ Viết kịch bản",
        disabled=current_step not in ["topic"],
        key="btn_script"
    ):
        with st.spinner("Đang viết kịch bản theo RULES..."):
            try:
                script = orchestrator.write_script()
                st.session_state.script = script
                st.success("✅ Kịch bản đã được生成 và validate")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Lỗi: {e}")

    # Step 4: Generate metadata
    if st.button(
        "3️⃣生成 Metadata",
        disabled=current_step not in ["script"],
        key="btn_meta"
    ):
        with st.spinner("Đang生成 titles, thumbnail text, hashtags..."):
            try:
                meta = orchestrator.generate_metadata()
                st.session_state.meta = meta
                st.success("✅ Metadata đã được生成")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Lỗi: {e}")

# Display current state
st.divider()
st.header("📊 Trạng thái hiện tại")

# Show topic
if state.get("topic"):
    st.subheader("📌 Chủ đề đã chọn")
    topic = state["topic"]
    st.info(f"**{topic['topic']}** - {topic['angle']}")

# Show script
if state.get("script"):
    st.subheader("📜 Kịch bản")
    with st.expander("Xem JSON kịch bản"):
        st.json(state["script"])
    
    # Show scenes table
    if state.get("scenes"):
        st.subheader("🎬 Phân cảnh")
        scenes_df = []
        for s in state["scenes"]:
            scenes_df.append({
                "ID": s.get("id"),
                "Section": s.get("section"),
                "Item": s.get("item_no"),
                "Duration": f"{s.get('dur', 0):.1f}s",
                "Start": f"{s.get('start', 0):.1f}s",
                "End": f"{s.get('end', 0):.1f}s"
            })
        st.table(scenes_df)

# Show metadata
if state.get("meta"):
    st.subheader("🏷️ Metadata")
    meta = state["meta"]
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Titles:**")
        for t in meta.get("titles", []):
            st.write(f"- {t}")
        st.write("**Thumbnail:**")
        thumb = meta.get("thumb", {})
        st.write(f"Main: {thumb.get('main')}")
        st.write(f"Sub: {thumb.get('sub')}")
    with col2:
        st.write("**Hashtags:**")
        for h in meta.get("hashtags", []):
            st.write(f"{h}")

# Show images
if state.get("images"):
    st.subheader("🖼️ Ảnh đã生成")
    images = state["images"]
    cols = st.columns(3)
    for i, (scene_id, img_path) in enumerate(images.items()):
        if img_path and Path(img_path).exists():
            cols[i % 3].image(img_path, caption=f"Scene {scene_id}")

# Show TTS
if state.get("tts"):
    st.subheader("🔊 Audio TTS")
    tts_results = state["tts"]
    for tts in tts_results:
        if Path(tts["path"]).exists():
            st.audio(tts["path"])

# Show subtitles
if state.get("ass"):
    st.subheader("📝 Phụ đề .ass")
    ass_path = state["ass"]
    if Path(ass_path).exists():
        with open(ass_path, "r", encoding="utf-8") as f:
            st.code(f.read()[:2000], language="ass")
        st.download_button(
            "⬇️ Tải file .ass",
            open(ass_path, "rb"),
            file_name="subtitles.ass",
            mime="text/plain"
        )

# Show final video
if state.get("video"):
    st.subheader("🎥 Video cuối cùng")
    video_path = state["video"]
    if Path(video_path).exists():
        st.video(video_path)
        
        # Show thumbnail
        if state.get("thumb"):
            thumb_path = state["thumb"]
            if Path(thumb_path).exists():
                st.image(thumb_path, caption="Thumbnail", width=640)
        
        # Download description
        if state.get("desc"):
            desc_path = state["desc"]
            if Path(desc_path).exists():
                st.download_button(
                    "⬇️ Tải Description",
                    open(desc_path, "rb"),
                    file_name="description_final.txt",
                    mime="text/plain"
                )

# Helper function to update step
def update_step_in_state(pid: str, step: str):
    """Update step in state file."""
    from core.state import update_step
    try:
        update_step(pid, step)
    except Exception as e:
        st.error(f"Lỗi khi cập nhật step: {e}")

# Footer
st.divider()
st.caption("""
**JP Faceless YouTube Factory** v1.0
- Brand Kit: Mascot đồng nhất + Font Noto Sans JP
- Pipeline: Topics → Script → Metadata → Prompts → Images → TTS → Subtitles → Render
- Extension: FlowKit Bridge (WebSocket) để điều khiển Google Flow
""")
