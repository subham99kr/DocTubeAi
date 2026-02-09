import streamlit as st
from modules.handle_pdf_upload import handle_pdf_upload
from modules.url_submit import handle_url_click

def render_context_bar():
    # 1. CSS - Move this OUTSIDE the expander
    st.markdown("""
    <style>
    /* 1. Position the expander shell as a fixed bar */
    div[data-testid="stExpander"] {
        position: fixed !important;
        top: 4rem !important;   /* Matches the Title Bar height */
        z-index: 99998 !important;
        background-color: #0e1117 !important;
        border-bottom: 1px solid #2c2f33 !important;
        border-radius: 0 !important;
        margin: 0 !important;
        width: 70%; /* Your requested width */
    }

    .header-anchor {
        padding: 5px 15px;
    }
    </style>

    <script>
    function fixContextBar() {
        const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
        const expander = window.parent.document.querySelector('div[data-testid="stExpander"]');
        
        if (!expander) return;

        // Dynamically get the sidebar width
        let sw = (sidebar && sidebar.offsetWidth > 0) ? sidebar.offsetWidth : 0;
        
        // YOUR LOGIC: Resize/Shift based on sidebar
        if (sw > 0) {
            expander.style.left = sw + "px";
            // Set width to 80% of the REMAINING space to prevent cutting
            expander.style.width = "calc(70% - " + (sw * 0.8) + "px)";
        } else {
            expander.style.left = "0px";
            expander.style.width = "70%";
        }
    }

    // High frequency interval (10ms) to track manual cursor dragging
    const ctxInterval = setInterval(fixContextBar, 10);
    setTimeout(() => clearInterval(ctxInterval), 5000);

    const ctxObserver = new ResizeObserver(fixContextBar);
    const sidebarElem = window.parent.document.querySelector('[data-testid="stSidebar"]');
    if (sidebarElem) ctxObserver.observe(sidebarElem);

    window.addEventListener('resize', fixContextBar);
    </script>
""", unsafe_allow_html=True)
    # 2. The Actual Bar
    with st.expander("📎 Add Context", expanded=False):
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
            upload_clicked = st.button("⬆️ Upload", disabled=st.session_state.processing)
            if upload_clicked and not st.session_state.processing:
                st.session_state.processing = True
                handle_pdf_upload(uploaded_files)

        # --- URL SECTION ---
        url_col, btn_col = st.columns([3, 1], gap="small")
        with url_col:
            st.text_input("URL", placeholder="Enter URL...", label_visibility="collapsed", key="header_url_input")
        with btn_col:
            st.button("⬆️", use_container_width=True, on_click=handle_url_click)

        # --- POPOVER ---
        with st.popover("📎 Current Context", use_container_width=True):
             # ... (your existing context view code) ...
             st.write(f"Current Files: {len(st.session_state.uploaded_pdfs)}")

        st.markdown('</div>', unsafe_allow_html=True)