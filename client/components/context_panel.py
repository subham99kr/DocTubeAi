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
            gap: 8px;
        }
        .header-anchor .stButton button {
            height: 32px;
            padding: 0 12px;
        }
        </style>
    """, unsafe_allow_html=True)

    # 2. The combined Container
    with st.container():
        st.markdown('<div class="header-anchor">', unsafe_allow_html=True)
        
        # u_key = st.session_state.get("uploader_key", 0)
        
        uploaded_files = st.file_uploader(
            "UP", type=['pdf'], 
            accept_multiple_files=True,
            label_visibility="collapsed", 
            key=f"pdf_uploader_{st.session_state.uploader_key}"
        )
        if uploaded_files:
            upload_clicked = st.button(
                "⬆️ Upload",
                disabled=not uploaded_files or st.session_state.processing,
            )
            if upload_clicked and not st.session_state.processing:
                st.session_state.processing = True
                handle_pdf_upload(uploaded_files)
            
        
        # --- URL SECTION ---
        url_col, btn_col = st.columns([3, 2], gap="small")

        with url_col:
            url_val = st.text_input(
                "URL",
                placeholder="Enter URL...",
                label_visibility="collapsed",
                key="header_url_input",
            )

        with btn_col:
            add_clicked = st.button(
                "⬆️",
                key="header_url_btn",
                use_container_width=True,
            )

        if add_clicked:
            if url_val:
                handle_url_submit(url_val)
            else:
                st.toast("⚠️ Enter a URL first")


        # --- CONTEXT DROPDOWN ---
        with st.popover("📎 Context", use_container_width=True):
            st.markdown("### 📎 Session Context")
            
            # PDFs List
            st.markdown("**PDFs**")
            for p in st.session_state.uploaded_pdfs:
                st.write(f"📄 {p}")
            if not st.session_state.uploaded_pdfs:
                st.caption("No PDFs")

            st.divider()

            # URLs List
            st.markdown("**Links**")
            for u in st.session_state.urls:
                st.write(f"🔗 {u}")
            if not st.session_state.urls:
                st.caption("No Links")

        st.markdown('</div>', unsafe_allow_html=True)

    # # ---- debugging ----
    # if st.session_state.uploaded_once and not st.session_state.processing:
    #     handle_pdf_upload(st.session_state.files_to_upload)
    #     st.session_state.uploaded_once = False
