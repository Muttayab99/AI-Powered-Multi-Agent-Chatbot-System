# backend/document_mcp.py - Document MCP server
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import PyPDF2
from docx import Document as DocxDocument

from mcp.server import Server
from mcp.server.fastmcp import FastMCP
import uvicorn
import os

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_community.llms import HuggingFacePipeline

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("document-mcp")
app = FastMCP(server)

# Global storage for vector databases and full texts
vectorstores = {}
full_texts = {}

def read_pdf(file_path: str) -> str:
    """Read text from PDF file"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error reading PDF: {str(e)}")
        raise

def read_docx(file_path: str) -> str:
    """Read text from DOCX file"""
    try:
        doc = DocxDocument(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        logger.error(f"Error reading DOCX: {str(e)}")
        raise

def read_text_file(file_path: str) -> str:
    """Read text from plain text file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Error reading text file: {str(e)}")
        raise

def process_document(file_path: str, session_id: str) -> Dict[str, Any]:
    """Process document and create vector store"""
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read document based on file type
        if file_path.suffix.lower() == '.pdf':
            text = read_pdf(str(file_path))
        elif file_path.suffix.lower() == '.docx':
            text = read_docx(str(file_path))
        elif file_path.suffix.lower() in ['.txt', '.md']:
            text = read_text_file(str(file_path))
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
        
        # Store full text
        full_texts[session_id] = text
        
        # Create vector store
        docs = [Document(page_content=text)]
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = splitter.split_documents(docs)
        
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vectorstore = FAISS.from_documents(chunks, embeddings)
        vectorstores[session_id] = vectorstore
        
        return {
            "success": True,
            "text_length": len(text),
            "chunks": len(chunks),
            "file_name": file_path.name
        }
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def ask_question(vectorstore, question: str) -> str:
    """Ask a question about the document"""
    try:
        retriever = vectorstore.as_retriever()
        
        model_id = "google/flan-t5-small"
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
        
        pipe = pipeline(
            "text2text-generation",
            model=model,
            tokenizer=tokenizer,
            max_length=512,
            temperature=0.5,
            device=0 if torch.cuda.is_available() else -1
        )
        
        llm = HuggingFacePipeline(pipeline=pipe)
        qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
        response = qa_chain.run(question)
        
        return response
        
    except Exception as e:
        logger.error(f"Error asking question: {str(e)}")
        return f"Error processing question: {str(e)}"

def summarize(text: str) -> str:
    """Summarize the document text"""
    try:
        words = text.split()
        if len(words) <= 200:
            return text
        
        summary_words = words[:200]
        summary = " ".join(summary_words)
        return summary + "... (truncated)"
        
    except Exception as e:
        logger.error(f"Error summarizing: {str(e)}")
        return f"Error creating summary: {str(e)}"

def get_sentiment(text: str) -> str:
    """Get basic sentiment analysis"""
    try:
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'positive', 'beneficial']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'negative', 'harmful', 'damaging']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "Positive"
        elif negative_count > positive_count:
            return "Negative"
        else:
            return "Neutral"
            
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {str(e)}")
        return "Error analyzing sentiment"

@server.tool("upload_document")
async def upload_document_tool(
    session_id: str,
    file_path: str
) -> Dict[str, Any]:
    """
    Upload and process a document for Q&A.
    """
    try:
        result = process_document(file_path, session_id)
        
        if result["success"]:
            return {
                "reply": f"Document uploaded and processed successfully. {result['text_length']} characters, {result['chunks']} chunks created.",
                "intent": "docchatbot",
                "success": True,
                "session_id": session_id,
                "file_name": result["file_name"]
            }
        else:
            return {
                "reply": f"Error processing document: {result['error']}",
                "intent": "docchatbot",
                "success": False,
                "session_id": session_id
            }
            
    except Exception as e:
        logger.error(f"Error in upload_document_tool: {str(e)}")
        return {
            "reply": f"Error uploading document: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

@server.tool("ask_question")
async def ask_question_tool(
    session_id: str,
    question: str
) -> Dict[str, Any]:
    """
    Ask a question about the uploaded document.
    """
    try:
        vectorstore = vectorstores.get(session_id)
        if not vectorstore:
            return {
                "reply": "No document uploaded for this session. Please upload a document first.",
                "intent": "docchatbot",
                "success": False,
                "session_id": session_id
            }
        
        response = ask_question(vectorstore, question)
        return {
            "reply": response,
            "intent": "docchatbot",
            "success": True,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Error in ask_question_tool: {str(e)}")
        return {
            "reply": f"Error processing question: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

@server.tool("query")
async def query_tool(
    session_id: str,
    query: str
) -> Dict[str, Any]:
    """
    Handle document queries (alias for ask_question).
    """
    return await ask_question_tool(session_id, query)

@server.tool("summarize")
async def summarize_tool(session_id: str) -> Dict[str, Any]:
    """
    Get a summary of the uploaded document.
    """
    try:
        full_text = full_texts.get(session_id)
        if not full_text:
            return {
                "reply": "No document uploaded for this session. Please upload a document first.",
                "intent": "docchatbot",
                "success": False,
                "session_id": session_id
            }
        
        summary = summarize(full_text)
        return {
            "reply": summary,
            "intent": "docchatbot",
            "success": True,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Error in summarize_tool: {str(e)}")
        return {
            "reply": f"Error creating summary: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

@server.tool("sentiment")
async def sentiment_tool(session_id: str) -> Dict[str, Any]:
    """
    Get sentiment analysis of the uploaded document.
    """
    try:
        full_text = full_texts.get(session_id)
        if not full_text:
            return {
                "reply": "No document uploaded for this session. Please upload a document first.",
                "intent": "docchatbot",
                "success": False,
                "session_id": session_id
            }
        
        sentiment = get_sentiment(full_text)
        return {
            "reply": f"Document sentiment: {sentiment}",
            "intent": "docchatbot",
            "success": True,
            "session_id": session_id,
            "sentiment": sentiment
        }
        
    except Exception as e:
        logger.error(f"Error in sentiment_tool: {str(e)}")
        return {
            "reply": f"Error analyzing sentiment: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

@server.tool("health")
async def health_tool() -> Dict[str, Any]:
    """
    Check the health of the Document MCP server.
    """
    try:
        session_count = len(vectorstores)
        return {
            "reply": f"Document MCP server is healthy with {session_count} active sessions",
            "intent": "health_check",
            "success": True,
            "status": "healthy",
            "active_sessions": session_count
        }
    except Exception as e:
        logger.error(f"Error in health_tool: {str(e)}")
        return {
            "reply": f"Document MCP server health check failed: {str(e)}",
            "intent": "health_check",
            "success": False,
            "status": "unhealthy"
        }

@server.tool("list_sessions")
async def list_sessions_tool() -> Dict[str, Any]:
    """
    List all active document sessions.
    """
    try:
        sessions = list(vectorstores.keys())
        return {
            "reply": f"Found {len(sessions)} active document sessions",
            "intent": "docchatbot",
            "success": True,
            "sessions": sessions
        }
    except Exception as e:
        logger.error(f"Error in list_sessions_tool: {str(e)}")
        return {
            "reply": f"Error listing sessions: {str(e)}",
            "intent": "docchatbot",
            "success": False
        }

@server.tool("clear_session")
async def clear_session_tool(session_id: str) -> Dict[str, Any]:
    """
    Clear a specific document session.
    """
    try:
        if session_id in vectorstores:
            del vectorstores[session_id]
        if session_id in full_texts:
            del full_texts[session_id]
        
        return {
            "reply": f"Session {session_id} cleared successfully",
            "intent": "docchatbot",
            "success": True,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error in clear_session_tool: {str(e)}")
        return {
            "reply": f"Error clearing session: {str(e)}",
            "intent": "docchatbot",
            "success": False,
            "session_id": session_id
        }

if __name__ == "__main__":
    logger.info("Starting Document MCP Server (FastMCP)...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8002")))
