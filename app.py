import streamlit as st
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_classic.prompts import PromptTemplate
from langchain_classic.chains import RetrievalQA

# 1. SETUP & CONFIG
st.set_page_config(page_title="TriageAI | ESI System", page_icon="🏥", layout="wide")
load_dotenv()

# Check for API Key
if not os.getenv("GOOGLE_API_KEY"):
    st.error("❌ GOOGLE_API_KEY missing. Please check your .env file.")
    st.stop()

# Initialize Session State for Patient Queue
if 'patients' not in st.session_state:
    st.session_state.patients = []

# 2. INITIALIZE AI ENGINE
@st.cache_resource
def load_chain():
    # A. Load Vector DB
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    # B. Load LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0.1,
        convert_system_message_to_human=True
    )

    # C. Define Persona (Optimized for Extraction)
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

# Helper to extract ESI Level from text
def extract_esi(text):
    match = re.search(r"ESI LEVEL:\s*(\d)", text)
    if match:
        return int(match.group(1))
    return 5 # Default to low priority if unknown

# ==============================================================================
# UI LAYOUT
# ==============================================================================
st.title("🏥 CodeBludhbcjwhwbceeeee")

# Create Tabs
tab_kiosk, tab_nurse = st.tabs(["Patient Kiosk (Public)", "Nurse Dashboard (Private)"])

# ------------------------------------------------------------------------------
# TAB 1: PATIENT KIOSK (The Input)
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
        # UX: Show a calming "Processing" state instead of raw data
        if submit_btn and complaint and name:
            with st.status("Analyzing Vitals & Protocols...", expanded=True) as status:
                st.write("Consulting ESI Handbook...")
                
                # Run AI
                response = qa_chain.invoke({"query": f"Age: {age}. Complaint: {complaint}"})
                result_text = response['result']
                esi_level = extract_esi(result_text)
                
                # Save to Queue
                new_patient = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "name": name,
                    "age": age,
                    "complaint": complaint,
                    "esi": esi_level,
                    "analysis": result_text,
                    "source_docs": response['source_documents']
                }
                st.session_state.patients.append(new_patient)
                
                status.update(label="Check-in Complete", state="complete", expanded=False)
            
            st.success("✅ You have been checked in. Please take a seat in the waiting area.")
            st.info("A nurse has been notified of your condition.")

# ------------------------------------------------------------------------------
# TAB 2: NURSE DASHBOARD (The Output)
# ------------------------------------------------------------------------------
with tab_nurse:
    st.header("📋 Triage Queue")
    
    if not st.session_state.patients:
        st.info("No patients in queue.")
    else:
        # SORTING LOGIC: ESI 1 (Critical) -> ESI 5 (Non-urgent)
        sorted_patients = sorted(st.session_state.patients, key=lambda x: x['esi'])
        
        # Display Stats
        c1, c2, c3 = st.columns(3)
        c1.metric("Wait Time (Avg)", "12 min")
        c2.metric("Critical Patients", sum(1 for p in sorted_patients if p['esi'] < 3))
        c3.metric("Total In Queue", len(sorted_patients))
        
        st.divider()

        for p in sorted_patients:
            # Color Code the Banner based on Severity
            if p['esi'] == 1:
                severity_color = "🔴 CRITICAL (Resuscitation)"
                border_color = "red"
            elif p['esi'] == 2:
                severity_color = "🟠 EMERGENT (High Risk)"
                border_color = "orange"
            elif p['esi'] == 3:
                severity_color = "🟡 URGENT"
                border_color = "#ebd534"
            else:
                severity_color = "🟢 STABLE"
                border_color = "green"

            # The Patient Card
            with st.expander(f"**[{severity_color}]** {p['name']} ({p['age']}y) - {p['time']}"):
                
                m1, m2 = st.columns([1, 1])
                
                with m1:
                    st.markdown("### 🗣️ Patient Presentation")
                    st.info(p['complaint'])
                    
                with m2:
                    st.markdown("### 🤖 AI Assessment")
                    # Clean up the output to hide the "ESI LEVEL" line if desired
                    st.write(p['analysis'])
                
                st.divider()
                st.caption("📚 Referenced Protocols:")
                for doc in p['source_docs']:
                    st.text(doc.page_content[:200] + "...")

# Sidebar Admin Tools
with st.sidebar:
    st.header("⚙️ Admin")
    if st.button("Clear Queue"):
        st.session_state.patients = []
        st.rerun()