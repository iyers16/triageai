# services.py
import os
import re
import uuid
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_classic.prompts import PromptTemplate
from langchain_classic.chains import RetrievalQA

class PatientManager:
    """Manages the in-memory patient queue."""
    def __init__(self):
        self.patients = []

    def get_all(self):
        # Sort: Code Black (0) -> Critical (1-2) -> Stable (3-5)
        # Also sort Active before Completed
        return sorted(self.patients, key=lambda x: (x['status'] == 'completed', x['esi']))

    def get_active(self):
        return [p for p in self.patients if p['status'] == 'active']

    def add_patient(self, name, age, complaint, esi, analysis, source_docs=[], snapshot=None):
        new_patient = {
            "id": str(uuid.uuid4()),
            "time": datetime.now().strftime("%H:%M:%S"),
            "name": name,
            "age": age,
            "complaint": complaint,
            "esi": esi,
            "analysis": analysis,
            "source_docs": source_docs, # Note: Objects might need serialization for JSON API
            "status": "active",
            "snapshot": snapshot # Base64 string or path ideally, or raw bytes if internal
        }
        self.patients.append(new_patient)
        return new_patient

    def mark_done(self, patient_id):
        for p in self.patients:
            if p['id'] == patient_id:
                p['status'] = 'completed'
                return True
        return False

class TriageService:
    """Handles the RAG / LLM Logic."""
    def __init__(self):
        load_dotenv()
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("❌ GOOGLE_API_KEY missing.")
        
        self.chain = self._load_chain()

    def _load_chain(self):
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
        5. Space out the analysis section for clarity.
        6. Do not use markdown formatting, txt will do.

        ANALYSIS:
        """
        prompt = PromptTemplate(template=template, input_variables=["context", "question"])

        return RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": prompt},
            return_source_documents=True
        )

    def analyze(self, age, complaint):
        try:
            response = self.chain.invoke({"query": f"Age: {age}. Complaint: {complaint}"})
            result_text = response['result']
            
            # Extract ESI
            match = re.search(r"ESI LEVEL:\s*(\d)", result_text)
            esi = int(match.group(1)) if match else 5
            
            # Serialize docs for JSON response (get page content only)
            docs = [doc.page_content[:200] + "..." for doc in response['source_documents']]
            
            return esi, result_text, docs
        except Exception as e:
            return 5, f"Error: {e}", []