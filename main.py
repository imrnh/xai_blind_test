from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
import motor.motor_asyncio
from datetime import datetime
import os
from random import shuffle
import httpx


app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB configuration
MONGO_URI = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.saliency_voting

# Define collection
USERS_COLLECTION = "xai_blind_voting_users"

# Constants
TOTAL_FOLDERS = 290  # Adjust as needed
HEATMAP_METHODS = ['beyond_intuition', 'gradcam', 'integrated_gradient', 'our', 'rollout']
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/imrnh/xai_blind_test/main/data/output"

# Models
class UserCreate(BaseModel):
    user_id: str

class Vote(BaseModel):
    user_id: str
    folder_id: int
    heatmap_method: str

# Routes
@app.post("/api/users/")
async def create_user(user: UserCreate):
    existing_user = await db[USERS_COLLECTION].find_one({"user_id": user.user_id})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    await db[USERS_COLLECTION].insert_one({
        "user_id": user.user_id,
        "created_at": datetime.utcnow(),
        "votes": {},
        "last_voted": 0
    })
    return {"message": "User created successfully"}

@app.get("/api/check_user/{user_id}")
async def check_user(user_id: str):
    user = await db[USERS_COLLECTION].find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"exists": True}

@app.get("/api/next_image/{user_id}")
async def get_next_image(user_id: str):
    user = await db[USERS_COLLECTION].find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    last_voted = user.get("last_voted", 0)
    next_folder_id = last_voted + 1

    if next_folder_id > TOTAL_FOLDERS:
        return {"status": "complete", "message": "All images have been voted on"}

    shuffled_methods = HEATMAP_METHODS.copy()
    shuffle(shuffled_methods)

    name_txt_url = f"{GITHUB_RAW_BASE}/{next_folder_id}/name.txt"

    async with httpx.AsyncClient() as client:
        name_response = await client.get(name_txt_url)
        if name_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch object name")
        object_name = name_response.text.strip()

    return {
        "folder_id": next_folder_id,
        "original_image": f"{GITHUB_RAW_BASE}/{next_folder_id}/image.png",
        "object_name": object_name,
        "heatmaps": [
            {
                "method": method,
                "image_path": f"{GITHUB_RAW_BASE}/{next_folder_id}/heatmap_{method}.jpg"
            } for method in shuffled_methods
        ]
    }

@app.post("/api/vote/")
async def record_vote(vote: Vote):
    user = await db[USERS_COLLECTION].find_one({"user_id": vote.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updated_votes: Dict[str, str] = user.get("votes", {})
    updated_votes[f"folder_{vote.folder_id}"] = vote.heatmap_method

    await db[USERS_COLLECTION].update_one(
        {"user_id": vote.user_id},
        {
            "$set": {
                "votes": updated_votes,
                "last_voted": vote.folder_id
            }
        }
    )

    return {"message": "Vote recorded successfully"}
