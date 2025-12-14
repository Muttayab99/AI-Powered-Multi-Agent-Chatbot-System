# backend/youtube_mcp.py - YouTube MCP server
import os
import json
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any
import logging
import yt_dlp
import torch

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("youtube-mcp")
app = FastMCP(server)

# Global storage for vector databases
vector_db_store = {}

import re

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return url

def get_transcript(video_url: str) -> str:
    """Get transcript from YouTube video"""
    try:
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_id = info['id']
            
        # Try to get captions
        caption_url = f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en"
        response = requests.get(caption_url)
        
        if response.status_code == 200 and response.text.strip():
            try:
                # Try XML captions (TTML)
                root = ET.fromstring(response.text)
                lines = [elem.text for elem in root.iter() if elem.text]
                return "\n".join(lines)
            except ET.ParseError:
                try:
                    # Try JSON-based captions
                    data = json.loads(response.text)
                    if isinstance(data, dict) and "events" in data:
                        all_text = []
                        for event in data["events"]:
                            if "segs" in event:
                                for seg in event["segs"]:
                                    if "utf8" in seg:
                                        all_text.append(seg["utf8"])
                        return "\n".join(all_text)
                except json.JSONDecodeError:
                    pass
                
                # Fall back to plain text (SRT/VTT)
                lines = []
                for line in response.text.splitlines():
                    if line.strip() == "" or "-->" in line or line.strip().isdigit():
                        continue
                    lines.append(line.strip())
                if not lines:
                    raise Exception("Subtitle format not valid XML/JSON/plain text.")
                return "\n".join(lines)
        else:
            raise Exception("No captions available for this video.")
            
    except Exception as e:
        logger.error(f"Error getting transcript: {str(e)}")
        raise

def process_video(video_url: str) -> str:
    """Process video and return video ID"""
    transcript = get_transcript(video_url)
    docs = [Document(page_content=transcript)]
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(chunks, embeddings)

    video_id = extract_video_id(video_url)
    vector_db_store[video_id] = vectorstore
    return video_id

def run_qa_with_flan_t5(video_url: str, query: str) -> Dict[str, Any]:
    """Run Q&A on video content"""
    try:
        video_id = extract_video_id(video_url)
        if video_id not in vector_db_store:
            process_video(video_url)
        
        retriever = vector_db_store[video_id].as_retriever()

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
        response = qa_chain.run(query)

        return {"response": response}
        
    except Exception as e:
        logging.error(f"Error in run_qa_with_flan_t5: {e}")
        return {"error": str(e)}

@server.tool("process_video")
async def process_video_tool(video_url: str) -> Dict[str, Any]:
    """
    Process a YouTube video to extract transcript and prepare for Q&A.
    """
    try:
        video_id = process_video(video_url)
        return {
            "reply": f"Video processed successfully. Video ID: {video_id}",
            "intent": "youtubebot",
            "success": True,
            "video_id": video_id
        }
    except Exception as e:
        return {
            "reply": f"Error processing video: {str(e)}",
            "intent": "youtubebot",
            "success": False,
            "error": str(e)
        }

@server.tool("chat_with_video")
async def chat_with_video_tool(video_url: str, query: str) -> Dict[str, Any]:
    """
    Chat with a YouTube video by asking questions about its content.
    """
    try:
        if not query:
            return {
                "reply": "Missing query parameter.",
                "intent": "youtubebot",
                "success": False
            }

        if not video_url:
            return {
                "reply": "Please provide a YouTube video URL to analyze.",
                "intent": "youtubebot",
                "success": False
            }

        result = run_qa_with_flan_t5(video_url, query)
        
        if "error" in result:
            return {
                "reply": result["error"],
                "intent": "youtubebot",
                "success": False
            }

        return {
            "reply": result["response"],
            "intent": "youtubebot",
            "success": True
        }
        
    except Exception as e:
        error_msg = f"YouTube Bot Error: {str(e)}"
        logging.error(error_msg)
        return {
            "reply": error_msg,
            "intent": "youtubebot",
            "success": False
        }

@server.tool("query_video")
async def query_video_tool(
    session_id: str,
    query: str,
    video_url: str
) -> Dict[str, Any]:
    """
    Query a YouTube video with a question. This is the main tool for video Q&A.
    """
    try:
        if not query:
            return {
                "reply": "Missing query parameter.",
                "intent": "youtubebot",
                "success": False,
                "session_id": session_id
            }

        if not video_url:
            return {
                "reply": "Please provide a YouTube video URL to analyze.",
                "intent": "youtubebot",
                "success": False,
                "session_id": session_id
            }

        result = run_qa_with_flan_t5(video_url, query)
        
        if "error" in result:
            return {
                "reply": result["error"],
                "intent": "youtubebot",
                "success": False,
                "session_id": session_id
            }

        return {
            "reply": result["response"],
            "intent": "youtubebot",
            "success": True,
            "session_id": session_id
        }
        
    except Exception as e:
        error_msg = f"YouTube Bot Error: {str(e)}"
        logging.error(error_msg)
        return {
            "reply": error_msg,
            "intent": "youtubebot",
            "success": False,
            "session_id": session_id
        }

@server.tool("health")
async def health_tool() -> Dict[str, Any]:
    """
    Check the health of the YouTube MCP server.
    """
    try:
        video_count = len(vector_db_store)
        return {
            "reply": f"YouTube MCP server is healthy with {video_count} processed videos",
            "intent": "health_check",
            "success": True,
            "status": "healthy",
            "processed_videos": video_count
        }
    except Exception as e:
        logger.error(f"Error in health_tool: {str(e)}")
        return {
            "reply": f"YouTube MCP server health check failed: {str(e)}",
            "intent": "health_check",
            "success": False,
            "status": "unhealthy"
        }

@server.tool("list_videos")
async def list_videos_tool() -> Dict[str, Any]:
    """
    List all processed videos.
    """
    try:
        video_ids = list(vector_db_store.keys())
        return {
            "reply": f"Found {len(video_ids)} processed videos",
            "intent": "video_management",
            "success": True,
            "videos": video_ids
        }
    except Exception as e:
        logger.error(f"Error in list_videos_tool: {str(e)}")
        return {
            "reply": f"Error listing videos: {str(e)}",
            "intent": "video_management",
            "success": False
        }

if __name__ == "__main__":
    logger.info("Starting YouTube MCP Server (FastMCP)...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
