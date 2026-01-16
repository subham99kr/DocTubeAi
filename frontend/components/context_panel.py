import streamlit as st
from modules.handle_pdf_upload import handle_pdf_upload
from modules.handle_url_submit import handle_url_submit

def render_top_bar():
    # 1. Injection CSS to place the bar in the Header
    st.markdown("""
        <style>
        header[data-testid="stHeader"] {
            height: 3.5rem;
            z-index: 99;
        }
        .header-anchor {
            position: fixed;
            top: 10px;
            left: 60px;
            right: 180px;
            height: 40px;
            z-index: 1000000;
            display: flex;
            align-items: center;
            background: transparent;
        }
        /* Custom styling to keep widgets slim for the header */
        .header-anchor [data-testid="stFileUploader"] { margin-top: -25px; }
        .header-anchor .stButton button { height: 32px; padding: 0 10px; }
        .header-anchor .stTextInput input { height: 32px; }
        </style>
    """, unsafe_allow_html=True)

    # 2. The combined Container
    with st.container():
        st.markdown('<div class="header-anchor">', unsafe_allow_html=True)
        
        u_key = st.session_state.get("uploader_key", 0)
        
        uploaded_files = st.file_uploader(
            "UP", type=['pdf'], 
            accept_multiple_files=True,
            label_visibility="collapsed", 
            key=f"pdf_uploader_{u_key}"
        )
        # Logic: If files uploaded and not yet processed in this change
        if uploaded_files and not st.session_state.get('processing'):
            handle_pdf_upload(uploaded_files)

    # --- URL SECTION ---
    
        url_val = st.text_input(
            "URL", placeholder="Enter URL...", 
            label_visibility="collapsed", 
            key="header_url_input"
        )

    
        if st.button("🔗 Add", key="header_url_btn", use_container_width=True):
            if url_val:
                handle_url_submit(url_val)
            else:
                st.toast("⚠️ Enter a URL first")

    # --- CONTEXT DROPDOWN (POPOVER) ---
    
        with st.popover("📎 Context", use_container_width=True):
            st.markdown("### 📎 Session Context")
            
            # PDFs List
            st.markdown("**PDFs**")
            pdfs = st.session_state.get("uploaded_pdfs", [])
            if pdfs:
                for p in pdfs: st.write(f"📄 {p}")
            else: st.caption("No PDFs")

            st.divider()

            # URLs List
            st.markdown("**Links**")
            urls = st.session_state.get("urls", [])
            if urls:
                for u in urls: st.write(f"🔗 {u}")
            else: st.caption("No Links")

        st.markdown('</div>', unsafe_allow_html=True)
