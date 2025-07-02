# main.py
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import motor.motor_asyncio
from datetime import datetime
import os
from random import shuffle

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

# Define collection names
USERS_COLLECTION = "xai_blind_voting_users"
VOTES_COLLECTION = "xai_blind_votes"

# Models
class UserCreate(BaseModel):
    user_id: str

class Vote(BaseModel):
    user_id: str
    folder_id: int
    heatmap_method: str

# Utility functions
async def get_next_folder(user_id: str):
    user = await db.users.find_one({"user_id": user_id})
    last_voted = user.get("last_voted", 0) if user else 0
    
    # Count total folders (you'll need to implement this based on your actual folder structure)
    # For now, we'll assume there are 100 folders (adjust as needed)
    total_folders = 100
    
    if last_voted >= total_folders:
        return None  # All folders voted
    return last_voted + 1

# Endpoints
@app.post("/api/users/")
async def create_user(user: UserCreate):
    existing_user = await db[USERS_COLLECTION].find_one({"user_id": user.user_id})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    await db[USERS_COLLECTION].insert_one({
        "user_id": user.user_id,
        "created_at": datetime.utcnow(),
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
    last_voted = user.get("last_voted", 0) if user else 0
    
    # Count total folders (adjust as needed)
    # You might want to make this dynamic or set it to your actual folder count
    total_folders = 100  
    
    if last_voted >= total_folders:
        return {"status": "complete", "message": "All images have been voted on"}
    
    folder_id = last_voted + 1
    
    # GitHub raw content base URL
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com/imrnh/xai_blind_test/main/data/output"
    # Replace {username} with your GitHub username or organization name
    
    heatmap_methods = ['beyond_intuition', 'gradcam', 'integrated_gradient', 'our', 'rollout']
    shuffle(heatmap_methods)
    
    return {
        "folder_id": folder_id,
        "original_image": f"{GITHUB_RAW_BASE}/{folder_id}/image.jpg",
        "heatmaps": [
            {
                "method": method, 
                "image_path": f"{GITHUB_RAW_BASE}/{folder_id}/heatmap_{method}.jpg"
            } for method in heatmap_methods
        ]
    }

@app.post("/api/vote/")
async def record_vote(vote: Vote):
    # Record the vote
    await db.votes.insert_one({
        "user_id": vote.user_id,
        "folder_id": vote.folder_id,
        "heatmap_method": vote.heatmap_method,
        "voted_at": datetime.utcnow()
    })
    
    # Update user's last voted folder
    await db.users.update_one(
        {"user_id": vote.user_id},
        {"$set": {"last_voted": vote.folder_id}}
    )
    
    return {"message": "Vote recorded successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)