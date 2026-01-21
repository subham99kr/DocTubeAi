import streamlit as st
from modules.handle_pdf_upload import handle_pdf_upload
from modules.url_submit import handle_url_click

def render_context_bar():
    with st.expander("📎 Add Context", expanded=False):

        # 1. Injection CSS
        st.markdown("""
            <style>
            .header-anchor {
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

        st.markdown('<div class="header-anchor">', unsafe_allow_html=True)

        # --- PDF UPLOAD ---
        uploaded_files = st.file_uploader(
            "UP",
            type=['pdf'],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key=f"pdf_uploader_{st.session_state.uploader_key}",
        )

        if uploaded_files:
            upload_clicked = st.button(
                "⬆️ Upload",
                disabled=st.session_state.processing,
            )
            if upload_clicked and not st.session_state.processing:
                st.session_state.processing = True
                handle_pdf_upload(uploaded_files)

        # --- URL SECTION ---
        url_col, btn_col = st.columns([3, 1], gap="small")

        with url_col:
            st.text_input(
                "URL",
                placeholder="Enter URL...",
                label_visibility="collapsed",
                key="header_url_input",
            )

        with btn_col:
            st.button(
                "⬆️",
                use_container_width=True,
                on_click=handle_url_click,
            )

        # --- CONTEXT VIEW ---
        with st.popover("📎 Current Context"):
            st.markdown("### PDFs")
            for p in st.session_state.uploaded_pdfs:
                st.write(f"📄 {p}")
            if not st.session_state.uploaded_pdfs:
                st.caption("No PDFs")

            st.divider()

            st.markdown("### Links")
            for u in st.session_state.urls:
                st.write(f"🔗 {u}")
            if not st.session_state.urls:
                st.caption("No Links")

        st.markdown('</div>', unsafe_allow_html=True)
