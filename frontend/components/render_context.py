import streamlit as st

def render_context(on_pdf_upload, on_link_submit):
    # Check if we are currently waiting for a response
    is_busy = st.session_state.get("processing", False)

    st.markdown("### 📎 Session Context")

    # --- 1. UPLOAD SECTION (Disabled when is_busy) ---
    with st.container(border=True):
        st.markdown("##### ➕ Add Context")
        
        uploaded_pdfs = st.file_uploader(
            "Upload PDFs", 
            type=["pdf"], 
            accept_multiple_files=True,
            label_visibility="collapsed",
            disabled=is_busy  # LOCK INPUT
        )
        
        if uploaded_pdfs:
            # Disable button while processing
            if st.button("Confirm PDF Upload", use_container_width=True, disabled=is_busy):
                on_pdf_upload(uploaded_pdfs)

        st.divider()

        new_url = st.text_input(
            "Paste Link here", 
            placeholder="https://...", 
            label_visibility="collapsed",
            disabled=is_busy  # LOCK INPUT
        )
        if st.button("Add Link", use_container_width=True, disabled=is_busy):
            if new_url.strip():
                on_link_submit(new_url)

    st.divider()

    # --- 2. DISPLAY SECTION ---
    pdfs = st.session_state.get("uploaded_pdfs", [])
    urls = st.session_state.get("urls", [])

    with st.expander(f"📄 Uploaded PDFs ({len(pdfs)})", expanded=True):
        if pdfs:
            for p in pdfs:
                # These are already confirmed from the backend (Dark Text)
                st.markdown(f"**• {p}**") 
        else:
            st.caption("No PDFs uploaded.")

    with st.expander(f"🔗 Reference Links ({len(urls)})", expanded=True):
        if urls:
            for u in urls:
                # Backend title is used here (Dark Bold Text)
                title = u.get("title")
                st.markdown(f"**• [{title}]({u.get('url')})**")
        else:
            st.caption("No links used.")
            
    # Visual cue when busy
    if is_busy:
        st.info("⌛ Backend is processing...")