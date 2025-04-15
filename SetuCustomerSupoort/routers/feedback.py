from fastapi import APIRouter
from models import FeedbackInput
from datetime import datetime

router = APIRouter(prefix="/feedback", tags=["Feedback"])

feedback_store = {}

@router.post("")
def submit_feedback(data: FeedbackInput):
    feedback_store.setdefault(data.question, []).append({
        "answer": data.answer,
        "feedback": "👍" if data.thumbs_up else "👎",
        "timestamp": datetime.now().isoformat()
    })
    return {"message": "Feedback recorded."}