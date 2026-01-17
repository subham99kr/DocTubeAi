import streamlit as st

def handle_pdf_upload(files):
    from api.upload_client import upload_pdfs_api

    
    # if st.session_state.processing:
    #     return
    
    # st.session_state.processing = True
    
    response = upload_pdfs_api(files, st.session_state.active_session_id, st.session_state.access_token)
    
    if response:
        # Backend returns {"filenames": [...]} 
        backend_files  = response.get("filenames", [])  
        
        for fname in backend_files:
            if fname not in st.session_state.uploaded_pdfs:
                st.session_state.uploaded_pdfs.append(fname)

        if backend_files:
            st.toast(f"✅ Added {len(backend_files)} PDF(s)")
            st.session_state.uploader_key += 1  # reset uploader safely
    
    st.session_state.processing = False
    st.rerun()

