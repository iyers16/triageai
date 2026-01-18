import streamlit as st
import os
import re
import cv2
import numpy as np
import uuid
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_classic.prompts import PromptTemplate
from langchain_classic.chains import RetrievalQA

# IMPORT VISION
from vision import VisionTriage

# 1. SETUP & CONFIG
st.set_page_config(page_title="TriageAI | ESI System", page_icon="🏥", layout="wide")
load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    st.error("❌ GOOGLE_API_KEY missing. Please check your .env file.")
    st.stop()

# Initialize Session State
if 'patients' not in st.session_state:
    st.session_state.patients = []

# Initialize Vision System
if 'vision_system' not in st.session_state:
    st.session_state.vision_system = VisionTriage()

# 2. INITIALIZE AI ENGINE
@st.cache_resource
def load_chain():
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0.1,
        convert_system_message_to_human=True
    )

    template = """
    You are an expert Triage Nurse Assistant using the ESI (Emergency Severity Index).
    
    CONTEXT:
    {context}
    
    PATIENT COMPLAINT:
    {question}
    
    TASK:
    1. Determine the ESI Level (1-5).
    2. Start your response EXACTLY with "ESI LEVEL: X" where X is the number.
    3. Provide a brief 2-sentence medical summary for the nurse.
    4. List recommended immediate actions.
    
    ANALYSIS:
    """
    
    prompt = PromptTemplate(template=template, input_variables=["context", "question"])

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )
    return chain

try:
    qa_chain = load_chain()
except Exception as e:
    st.error(f"Failed to load knowledge base: {e}")
    st.stop()

def extract_esi(text):
    match = re.search(r"ESI LEVEL:\s*(\d)", text)
    if match:
        return int(match.group(1))
    return 5

# ==============================================================================
# UI LAYOUT
# ==============================================================================
st.title("🏥 TriageAI: Hospital Intake System")

tab_kiosk, tab_camera, tab_nurse = st.tabs(["Patient Kiosk", "🤖 Auto-Triage (Camera)", "Nurse Dashboard"])

# ------------------------------------------------------------------------------
# TAB 1: PATIENT KIOSK
# ------------------------------------------------------------------------------
with tab_kiosk:
    st.subheader("Welcome to General Hospital")
    st.caption("Please describe your symptoms to begin check-in.")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        name = st.text_input("Full Name", placeholder="John Doe")
        age = st.number_input("Age", min_value=0, max_value=120, value=30)
        
        input_method = st.radio("Input Method", ["Text Description", "Voice Transcript"])
        
        if input_method == "Text Description":
            complaint = st.text_area("What are your symptoms?", height=150, 
                                   placeholder="e.g., I have sharp chest pain...")
        else:
            complaint = st.text_area("Transcript", value="Subject states crushing chest pressure...", height=150)

        submit_btn = st.button("🚨 Submit for Triage", type="primary", use_container_width=True)

    with col2:
        if submit_btn and complaint and name:
            with st.status("Analyzing Vitals & Protocols...", expanded=True) as status:
                st.write("Consulting ESI Handbook...")
                
                response = qa_chain.invoke({"query": f"Age: {age}. Complaint: {complaint}"})
                result_text = response['result']
                esi_level = extract_esi(result_text)
                
                new_patient = {
                    "id": str(uuid.uuid4()), # Unique ID for button tracking
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "name": name,
                    "age": age,
                    "complaint": complaint,
                    "esi": esi_level,
                    "analysis": result_text,
                    "source_docs": response['source_documents'],
                    "status": "active", # active | completed
                    "snapshot": None # No image for text patients
                }
                st.session_state.patients.append(new_patient)
                
                status.update(label="Check-in Complete", state="complete", expanded=False)
            
            st.success("✅ Checked in.")

# ------------------------------------------------------------------------------
# TAB 2: AUTO-TRIAGE (Camera Override)
# ------------------------------------------------------------------------------
with tab_camera:
    st.subheader("Visual Anomaly Detection")
    st.caption("Active monitoring for Choking, Chest Pain, or Falls.")

    col_cam, col_log = st.columns([2, 1])

    with col_cam:
        run_camera = st.toggle("Activate Live Scanner", value=False)
        cam_placeholder = st.empty()

        if run_camera:
            cap = cv2.VideoCapture(0)
            
            while run_camera:
                ret, frame = cap.read()
                if not ret:
                    st.error("Cannot access camera.")
                    break
                
                # Run Vision Analysis
                annotated_frame, alert = st.session_state.vision_system.analyze_frame(frame)
                
                # Display Live Frame
                frame_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
                cam_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)

                # --- CODE BLACK OVERRIDE ---
                if alert:
                    # Deduplication: Check if the last patient is the same alert type
                    last_entry = st.session_state.patients[-1] if st.session_state.patients else None
                    
                    if not last_entry or last_entry['complaint'] != f"CODE BLACK: {alert}":
                        
                        # Capture the specific frame as evidence
                        snapshot_evidence = frame_rgb.copy()
                        
                        new_patient = {
                            "id": str(uuid.uuid4()),
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "name": "Unknown (Auto-Detected)",
                            "age": "N/A",
                            "complaint": f"CODE BLACK: {alert}",
                            "esi": 0, # PRIORITY 0 (Highest Possible)
                            "analysis": f"**VISUAL OVERRIDE:** System detected {alert}. \n\nSee attached snapshot for skeletal analysis.",
                            "source_docs": [],
                            "status": "active",
                            "snapshot": snapshot_evidence # Save the numpy array
                        }
                        
                        st.session_state.patients.append(new_patient)
                        st.toast(f"🚨 CODE BLACK: {alert}", icon="🚨")
                        
                        # Optional: Sleep briefly to avoid 60 duplicates per second
                        # time.sleep(2) 

            cap.release()
        else:
            cam_placeholder.info("Scanner Offline.")

    with col_log:
        st.markdown("### 📡 Live Telemetry")
        if run_camera:
            st.success("System Active")
            st.markdown("**Protocols:**\n* [x] Choking\n* [x] Chest Pain\n* [x] Fall Detection")
        else:
            st.warning("System Paused")

# ------------------------------------------------------------------------------
# TAB 3: NURSE DASHBOARD (Task Management)
# ------------------------------------------------------------------------------
with tab_nurse:
    
    # 1. Filter Lists
    active_patients = [p for p in st.session_state.patients if p['status'] == 'active']
    completed_patients = [p for p in st.session_state.patients if p['status'] == 'completed']

    # 2. Header Stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Queue", len(active_patients))
    c2.metric("Code Blacks", sum(1 for p in active_patients if p['esi'] == 0))
    c3.metric("Critical (ESI 1-2)", sum(1 for p in active_patients if 0 < p['esi'] < 3))
    c4.metric("Completed", len(completed_patients))
    
    st.divider()

    # 3. ACTIVE QUEUE
    st.subheader("🔥 Active Queue")
    
    if not active_patients:
        st.info("No active patients.")
    else:
        # Sort by ESI (0 is top priority)
        sorted_active = sorted(active_patients, key=lambda x: x['esi'])

        for p in sorted_active:
            # Color Coding
            if p['esi'] == 0:
                severity_label = "⚫ CODE BLACK (IMMEDIATE)"
                border_color = "black"
            elif p['esi'] == 1:
                severity_label = "🔴 CRITICAL (Resuscitation)"
                border_color = "red"
            elif p['esi'] == 2:
                severity_label = "🟠 EMERGENT (High Risk)"
                border_color = "orange"
            elif p['esi'] == 3:
                severity_label = "🟡 URGENT"
                border_color = "#ebd534"
            else:
                severity_label = "🟢 STABLE"
                border_color = "green"

            # Patient Card
            with st.expander(f"**[{severity_label}]** {p['name']} - {p['time']}"):
                
                # Layout: 3 Columns (Snapshot, Info, Actions)
                k1, k2, k3 = st.columns([2, 2, 1])

                with k1:
                    st.markdown("### 📸 Evidence")
                    if p['snapshot'] is not None:
                        st.image(p['snapshot'], caption="Auto-Capture Event", use_container_width=True)
                    else:
                        st.info("No visual evidence (Text Submission).")

                with k2:
                    st.markdown("### 📝 Clinical Data")
                    st.write(f"**Complaint:** {p['complaint']}")
                    st.write(f"**Age:** {p['age']}")
                    st.markdown("---")
                    st.write(p['analysis'])

                with k3:
                    st.markdown("### ⚡ Actions")
                    if st.button("✅ Mark Done", key=f"btn_done_{p['id']}"):
                        # Find original index and update
                        for i, original_p in enumerate(st.session_state.patients):
                            if original_p['id'] == p['id']:
                                st.session_state.patients[i]['status'] = 'completed'
                                st.rerun()

    # 4. COMPLETED SECTION
    st.divider()
    with st.expander("✅ Completed / Discharged Patients"):
        if not completed_patients:
            st.caption("No history yet.")
        else:
            for p in reversed(completed_patients): # Show most recent first
                st.markdown(f"**{p['name']}** (ESI {p['esi']}) - *Resolved at {datetime.now().strftime('%H:%M')}*")

# Sidebar Admin
with st.sidebar:
    st.header("⚙️ Admin")
    if st.button("Clear All Data"):
        st.session_state.patients = []
        st.rerun()