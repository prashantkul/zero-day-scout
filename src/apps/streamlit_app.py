"""
Streamlit app to demonstrate the RAG pipeline functionality.
"""
import os
import time
import streamlit as st
from dotenv import load_dotenv

from src.rag.pipeline import VertexRagPipeline
from src.rag.gcs_utils import GcsManager
from config.config_manager import get_config

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="Zero-Day Scout RAG Demo",
    page_icon="🔍",
    layout="wide",
)


def initialize_session_state():
    """Initialize session state variables."""
    if "pipeline" not in st.session_state:
        try:
            st.session_state.pipeline = VertexRagPipeline()
            st.session_state.pipeline_initialized = True
        except Exception as e:
            st.session_state.pipeline_initialized = False
            st.session_state.init_error = str(e)
    
    if "gcs_manager" not in st.session_state:
        try:
            st.session_state.gcs_manager = GcsManager()
            st.session_state.gcs_initialized = True
        except Exception as e:
            st.session_state.gcs_initialized = False
            st.session_state.gcs_error = str(e)
    
    if "history" not in st.session_state:
        st.session_state.history = []


def main():
    """Main function to run the Streamlit app."""
    # Initialize session state
    initialize_session_state()
    
    # Header
    st.title("Zero-Day Scout RAG Demo")
    st.markdown("Explore documents and ask questions using the RAG pipeline.")
    
    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        config = get_config()
        
        # Display current configuration
        st.subheader("Current Settings")
        st.markdown(f"**Project ID:** {config.get('project_id')}")
        st.markdown(f"**Corpus Name:** {config.get('corpus_name')}")
        st.markdown(f"**GCS Bucket:** {config.get('gcs_bucket')}")
        st.markdown(f"**Model:** {config.get('generative_model')}")
        
        # Connection status
        st.subheader("Connection Status")
        if st.session_state.pipeline_initialized:
            st.success("✅ RAG Pipeline: Connected")
        else:
            st.error(f"❌ RAG Pipeline: Error - {st.session_state.init_error}")
        
        if st.session_state.gcs_initialized:
            st.success("✅ GCS Bucket: Connected")
        else:
            st.error(f"❌ GCS Bucket: Error - {st.session_state.gcs_error}")
    
    # Main content - tabs
    tab1, tab2, tab3 = st.tabs(["Query RAG", "Ingest Documents", "View Files"])
    
    # Tab 1: Query RAG
    with tab1:
        st.header("Ask a Question")
        
        # User input
        query = st.text_input("Enter your question:")
        col1, col2 = st.columns(2)
        with col1:
            show_context = st.checkbox("Show retrieved context", value=True)
        with col2:
            use_direct_integration = st.checkbox("Use direct RAG integration", value=False)
        
        # Advanced options (collapsible)
        with st.expander("Advanced Options", expanded=False):
            temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.1)
            top_k = st.slider("Number of documents to retrieve", min_value=1, max_value=20, value=5)
        
        # Query button
        if st.button("Generate Answer") and query:
            if not st.session_state.pipeline_initialized:
                st.error("RAG Pipeline not initialized. Check connection status.")
                return
            
            with st.spinner("Generating answer..."):
                try:
                    # Retrieve context if showing it
                    retrievals = None
                    if show_context:
                        retrievals = st.session_state.pipeline.retrieve_context(
                            query=query,
                            top_k=top_k
                        )
                    
                    # Generate answer
                    start_time = time.time()
                    if use_direct_integration:
                        answer = st.session_state.pipeline.direct_rag_response(
                            query=query,
                            temperature=temperature,
                            top_k=top_k
                        )
                    else:
                        answer = st.session_state.pipeline.generate_answer(
                            query=query,
                            temperature=temperature,
                            retrievals=retrievals
                        )
                    elapsed_time = time.time() - start_time
                    
                    # Add to history
                    st.session_state.history.append({
                        "query": query,
                        "answer": answer,
                        "retrievals": retrievals,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "elapsed": elapsed_time
                    })
                    
                    # Display answer
                    st.success(f"Answer generated in {elapsed_time:.2f} seconds")
                except Exception as e:
                    st.error(f"Error generating answer: {e}")
        
        # Display context and answer if available
        if st.session_state.history:
            latest = st.session_state.history[-1]
            
            # Display answer
            st.subheader("Answer")
            st.markdown(latest["answer"])
            
            # Display context if requested
            if show_context and latest["retrievals"]:
                with st.expander("Retrieved Context", expanded=True):
                    for i, retrieval in enumerate(latest["retrievals"]):
                        st.markdown(f"**Document {i+1}**")
                        
                        # Extract and display content
                        content = None
                        if hasattr(retrieval, "text"):
                            content = retrieval.text
                        elif hasattr(retrieval, "chunk") and hasattr(retrieval.chunk, "data"):
                            content = retrieval.chunk.data
                        elif hasattr(retrieval, "content"):
                            content = retrieval.content
                        
                        if content:
                            st.markdown(content)
                        else:
                            st.markdown("_No content found_")
                        
                        st.divider()
    
    # Tab 2: Ingest Documents
    with tab2:
        st.header("Ingest Documents")
        
        # Two options: from GCS or upload local
        option = st.radio(
            "Choose ingestion method:",
            ["Ingest from GCS bucket", "Upload local files"]
        )
        
        if option == "Ingest from GCS bucket":
            st.subheader("Ingest from GCS")
            
            prefix = st.text_input("GCS Path Prefix (optional):")
            
            if st.button("List Files"):
                if not st.session_state.gcs_initialized:
                    st.error("GCS connection not initialized. Check connection status.")
                    return
                
                with st.spinner("Listing files..."):
                    try:
                        gcs_paths_result = st.session_state.gcs_manager.list_files(prefix)
                        
                        # Handle potential pager objects
                        try:
                            gcs_paths = list(gcs_paths_result)
                        except Exception:
                            # If conversion fails, try to iterate manually
                            gcs_paths = []
                            for path in gcs_paths_result:
                                gcs_paths.append(path)
                        
                        if gcs_paths:
                            st.session_state.gcs_paths = gcs_paths
                            st.success(f"Found {len(gcs_paths)} files")
                            
                            # Display files
                            with st.expander("Files Found", expanded=True):
                                for path in gcs_paths:
                                    st.text(path)
                        else:
                            st.warning("No files found with the given prefix")
                    except Exception as e:
                        st.error(f"Error listing files: {e}")
            
            # Ingest button (only enabled if files are listed)
            ingest_button = st.button(
                "Ingest Documents",
                disabled="gcs_paths" not in st.session_state
            )
            
            if ingest_button:
                if not st.session_state.pipeline_initialized:
                    st.error("RAG Pipeline not initialized. Check connection status.")
                    return
                
                with st.spinner("Ingesting documents..."):
                    try:
                        import_op = st.session_state.pipeline.ingest_documents(
                            st.session_state.gcs_paths
                        )
                        st.success(f"Started ingestion of {len(st.session_state.gcs_paths)} documents")
                        
                        # Check if operation has a wait method
                        if import_op and hasattr(import_op, "operation"):
                            wait = st.checkbox("Wait for ingestion to complete?")
                            if wait:
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                                
                                # Simple progress simulation
                                for i in range(100):
                                    progress_bar.progress(i + 1)
                                    status_text.text(f"Processing... ({i+1}%)")
                                    time.sleep(0.1)
                                
                                # Actual wait
                                status_text.text("Waiting for operation to complete...")
                                import_op.operation.wait()
                                status_text.text("Ingestion completed!")
                                st.balloons()
                    except Exception as e:
                        st.error(f"Error ingesting documents: {e}")
        
        else:  # Upload local files
            st.subheader("Upload Local Files")
            
            # File uploader (multi-file)
            uploaded_files = st.file_uploader(
                "Choose files to upload",
                accept_multiple_files=True,
                type=["pdf", "txt", "md", "docx"]
            )
            
            # Display upload status
            if uploaded_files:
                st.success(f"Selected {len(uploaded_files)} files for upload")
                
                # Display selected files
                with st.expander("Selected Files", expanded=True):
                    for file in uploaded_files:
                        st.write(f"- {file.name} ({file.type}) - {file.size} bytes")
            
            # Upload options
            upload_col1, upload_col2 = st.columns(2)
            with upload_col1:
                gcs_prefix = st.text_input("GCS Prefix for uploaded files:", value="uploaded_papers/")
            with upload_col2:
                include_timestamp = st.checkbox("Add timestamp to filenames", value=True)
            
            if st.button("Upload and Ingest") and uploaded_files:
                if not st.session_state.gcs_initialized or not st.session_state.pipeline_initialized:
                    st.error("GCS or RAG Pipeline not initialized. Check connection status.")
                    return
                
                with st.spinner("Uploading and ingesting documents..."):
                    try:
                        # Create temp directory for files
                        import tempfile
                        import uuid
                        
                        # Track uploaded GCS paths
                        uploaded_gcs_paths = []
                        
                        # Progress indicators
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Process each file
                        for i, file in enumerate(uploaded_files):
                            # Update progress
                            progress = (i / len(uploaded_files))
                            progress_bar.progress(progress)
                            status_text.text(f"Uploading {file.name}...")
                            
                            # Create a temporary file
                            temp_dir = tempfile.mkdtemp()
                            temp_path = os.path.join(temp_dir, file.name)
                            
                            # Write the uploaded file to the temp file
                            with open(temp_path, "wb") as f:
                                f.write(file.getbuffer())
                            
                            # Determine GCS path
                            filename = file.name
                            if include_timestamp:
                                name, ext = os.path.splitext(filename)
                                timestamp = time.strftime("%Y%m%d-%H%M%S")
                                unique_id = str(uuid.uuid4())[:8]  # Use part of a UUID for uniqueness
                                filename = f"{name}_{timestamp}_{unique_id}{ext}"
                            
                            gcs_path = os.path.join(gcs_prefix, filename)
                            
                            # Upload to GCS
                            gcs_uri = st.session_state.gcs_manager.upload_file(temp_path, gcs_path)
                            uploaded_gcs_paths.append(gcs_uri)
                            
                            # Clean up temp file
                            os.remove(temp_path)
                            os.rmdir(temp_dir)
                        
                        # Update progress to show completion of uploads
                        progress_bar.progress(1.0)
                        status_text.text(f"Successfully uploaded {len(uploaded_gcs_paths)} files. Starting ingestion...")
                        
                        # Ingest uploaded documents
                        import_op = st.session_state.pipeline.ingest_documents(uploaded_gcs_paths)
                        
                        # Show success message
                        st.success(f"Successfully uploaded and started ingestion of {len(uploaded_gcs_paths)} documents")
                        st.json({
                            "uploaded_files": [path.split('/')[-1] for path in uploaded_gcs_paths],
                            "ingestion_status": "in_progress"
                        })
                        
                        # Wait for ingestion to complete
                        wait = st.checkbox("Wait for ingestion to complete?")
                        if wait and hasattr(import_op, "operation"):
                            wait_status = st.empty()
                            wait_progress = st.progress(0)
                            
                            # Wait with a simulated progress bar
                            wait_status.text("Waiting for ingestion to complete...")
                            for i in range(100):
                                wait_progress.progress(i + 1)
                                time.sleep(0.1)
                            
                            # Actual wait
                            import_op.operation.wait()
                            wait_status.text("Ingestion completed!")
                            st.balloons()
                            
                    except Exception as e:
                        st.error(f"Error uploading and ingesting documents: {e}")
                        st.exception(e)
    
    # Tab 3: View Files
    with tab3:
        st.header("Corpus Files")
        
        if st.button("List Corpus Files"):
            if not st.session_state.pipeline_initialized:
                st.error("RAG Pipeline not initialized. Check connection status.")
                return
            
            with st.spinner("Listing corpus files..."):
                try:
                    # Get files - ListRagFilesPager needs to be converted to a list
                    files_pager = st.session_state.pipeline.list_corpus_files()
                    
                    # Convert pager to list
                    try:
                        files = list(files_pager)
                        if files:
                            st.success(f"Found {len(files)} files in corpus")
                            
                            # Display files table
                            file_data = []
                            for file_info in files:
                                file_data.append({
                                    "ID": file_info.name if hasattr(file_info, "name") else "Unknown",
                                    "Name": file_info.display_name if hasattr(file_info, "display_name") else "Unknown",
                                    "State": file_info.state if hasattr(file_info, "state") else "Unknown",
                                })
                            
                            if file_data:
                                st.table(file_data)
                            else:
                                st.warning("Files found but could not extract their details")
                        else:
                            st.warning("No files found in corpus")
                    except Exception as pager_error:
                        st.error(f"Error processing file list: {pager_error}")
                        
                        # Alternative: try to iterate manually
                        st.info("Trying alternative method to list files...")
                        file_data = []
                        file_count = 0
                        
                        try:
                            for file_info in files_pager:
                                file_count += 1
                                file_data.append({
                                    "ID": file_info.name if hasattr(file_info, "name") else "Unknown",
                                    "Name": file_info.display_name if hasattr(file_info, "display_name") else "Unknown",
                                    "State": file_info.state if hasattr(file_info, "state") else "Unknown",
                                })
                            
                            if file_data:
                                st.success(f"Found {file_count} files in corpus")
                                st.table(file_data)
                            else:
                                st.warning("No files found in corpus")
                        except Exception as iteration_error:
                            st.error(f"Error during manual iteration: {iteration_error}")
                    
                except Exception as e:
                    st.error(f"Error listing corpus files: {e}")


if __name__ == "__main__":
    main()