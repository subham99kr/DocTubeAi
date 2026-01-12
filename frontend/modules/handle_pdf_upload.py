import streamlit as st

def handle_pdf_upload(files):
    from api.upload_client import upload_pdfs_api
    st.session_state.processing = True
    response = upload_pdfs_api(files, st.session_state.active_session_id, st.session_state.access_token)
    
    if response:
        # Assuming backend returns {"filenames": [...]} 
        new_files = response.get("filenames", [f.name for f in files])  ###########################################
        
        # Append only new files to avoid duplicates in the UI
        for f in new_files:
            st.session_state.uploaded_pdfs.append(f)
                
        st.toast(f"✅ Added {len(new_files)} PDF(s)")
    
    st.session_state.processing = False
    st.rerun()

