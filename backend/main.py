import uvicorn
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_anthropic import ChatAnthropic
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_unstructured import UnstructuredLoader
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import json
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from starlette.responses import StreamingResponse

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]


class RAGSystem:
    def __init__(self):
        self.llm = ChatAnthropic(
            model_name="claude-sonnet-4-6",
            api_key=api_key,
            temperature=0,
        )

        embedding_function = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
        )


        persist_dir = "./chroma_db"

        if os.path.exists(persist_dir) and os.listdir(persist_dir):
            print("[INFO] Loading existing vector store...")
            self.vector_store = Chroma(
                collection_name="example_collection",
                embedding_function=embedding_function,
                persist_directory=persist_dir
            )
        else:
            print("Creating new vector store...")
            file_paths=[
                './project_documents/001-146-156-Design-and-Access-Statement.pdf',
                './project_documents/002-158-Design-and-Access-Statement.pdf',
                './project_documents/003-BPZ#1-Technical-Report.pdf',
                './project_documents/004-BUILD-PLANET-ZERO-HOUSING-REGENERATION_#2_technical report.pdf',
                './project_documents/005-ECO-AUDIT-REPORT.docx',
                './project_documents/006-Demand-Data-Previous-Data.xlsx',
                './project_documents/007-UKNZCBS-Pilot-Version.pdf'
            ]
            all_documents = [] # This is used to store all the documents
            # To loop below is to load all the documents into the array
            for file_path in file_paths:
                document_loader = UnstructuredLoader(file_path)
                data = document_loader.load()
                all_documents.extend(data)

            # Better chunking for your structured document
            splitter = RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", ". ", " ", ""],
                chunk_size=512,
                chunk_overlap=50,
                add_start_index=True
            )

            def clean_metadata(documents):
                """Convert complex types to strings"""
                for doc in documents:
                    cleaned_metadata = {}
                    for key, value in doc.metadata.items():
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            cleaned_metadata[key] = value
                        elif isinstance(value, (dict, list)):
                            # Convert to JSON string
                            cleaned_metadata[key] = json.dumps(value)
                    doc.metadata = cleaned_metadata
                return documents

            docs = splitter.split_documents(all_documents)
            splits = clean_metadata(docs)
            batch_size = 500

            for i in range(0, len(splits), batch_size):
                batch = splits[i:i + batch_size]
                print(f"Processing {len(batch)} documents...")
                self.vector_store = Chroma(
                    collection_name="example_collection",
                    embedding_function=embedding_function,
                    persist_directory=persist_dir,
                )
                self.vector_store.add_documents(batch)
            print(f"Indexed {len(splits)} chunks")

        # Retrieve MORE chunks for better coverage
        self.retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 15,
                "fetch_k": 50
            }  # Get top 15
        )

        # Better prompt that handles vague questions
        template = """Use the context below to answer the question. The context contains information from a document.

Context:
{context}

Question: {question}

Instructions:
- If the answer is in the context, provide it clearly and concisely
- If the context has relevant information but the question is vague (like "give details"), provide a summary of the relevant information
- If the information is truly not in the context, say "That information is not in the documentation"

Answer:"""

        self.prompt = ChatPromptTemplate.from_template(template)

        self.rag_chain = (
                {
                    "context": self.retriever | self._format_docs,
                    "question": RunnablePassthrough()
                }
                | self.prompt
                | self.llm
                | StrOutputParser()
        )

    def _format_docs(self, docs):
        return "\n\n---\n\n".join(doc.page_content for doc in docs)


print("Initializing RAG system...")
rag = RAGSystem()
print("RAG system ready!")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        user_query = request.messages[-1].content

        # For better context, include previous message if asking for "details" or using pronouns
        if len(request.messages) > 1 and any(
                word in user_query.lower() for word in ['their', 'them', 'it', 'details', 'those', 'these']):
            # Combine with previous question for better context
            prev_query = request.messages[-2].content if len(request.messages) >= 2 else ""
            combined_query = f"{prev_query} {user_query}"
            response = rag.rag_chain.invoke(combined_query)
        else:
            response = rag.rag_chain.invoke(user_query)

        return {
            "message": response,
            "role": "assistant"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        try:
            user_query = request.messages[-1].content

            # Same context handling for streaming
            if len(request.messages) > 1 and any(
                    word in user_query.lower() for word in ['their', 'them', 'it', 'details', 'those', 'these']):
                prev_query = request.messages[-2].content if len(request.messages) >= 2 else ""
                combined_query = f"{prev_query} {user_query}"
            else:
                combined_query = user_query

            for chunk in rag.rag_chain.stream(combined_query):
                if chunk:
                    yield f"data: {json.dumps({'content': chunk})}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"Error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)