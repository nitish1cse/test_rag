from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from app.services import GitLabService, JiraService, LLMService
from app.middleware.logging_middleware import LoggingMiddleware
from app.utils.logger import app_logger

# Load environment variables
load_dotenv()

app = FastAPI(
    title="AI MergeMate",
    description="AI-powered code review assistant for GitLab Merge Requests",
    version="1.0.0"
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
gitlab_service = GitLabService()
jira_service = JiraService()
llm_service = LLMService()

class GitLabUser(BaseModel):
    id: int
    name: str
    username: str
    avatar_url: Optional[str] = None
    email: Optional[str] = None

class GitLabProject(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    web_url: str
    path_with_namespace: str
    default_branch: str

class GitLabCommit(BaseModel):
    id: str
    message: str
    title: str
    timestamp: str
    url: str
    author: Dict[str, str]

class GitLabObjectAttributes(BaseModel):
    id: int
    iid: int
    title: str
    description: str
    source_branch: str
    target_branch: str
    state: str
    created_at: str
    updated_at: str
    merge_status: str
    merge_when_pipeline_succeeds: bool
    merge_user_id: Optional[int] = None
    merge_error: Optional[str] = None
    merge_commit_sha: Optional[str] = None
    draft: bool
    work_in_progress: bool
    url: str
    action: str
    last_commit: Optional[GitLabCommit] = None

class GitLabWebhook(BaseModel):
    object_kind: str
    event_type: str
    user: GitLabUser
    project: GitLabProject
    object_attributes: GitLabObjectAttributes
    labels: List[Dict[str, Any]]
    changes: Optional[Dict[str, Any]] = None
    repository: Dict[str, Any]

@app.get("/")
async def root():
    """Health check endpoint"""
    app_logger.info("Health check endpoint called")
    return {"status": "healthy", "service": "AI MergeMate"}

@app.post("/gitlab-hook")
async def gitlab_webhook(request: Request, webhook: GitLabWebhook):
    """
    Handle GitLab webhook events for merge requests
    """
    app_logger.info(
        "Received GitLab webhook",
        extra={
            "object_kind": webhook.object_kind,
            "event_type": webhook.event_type,
            "mr_id": webhook.object_attributes.iid,
            "project_id": webhook.project.id
        }
    )

    # Verify webhook secret if configured
    webhook_secret = os.getenv("GITLAB_WEBHOOK_SECRET")
    if webhook_secret:
        signature = request.headers.get("X-GitLab-Token")
        if not signature or signature != webhook_secret:
            app_logger.warning(
                "Invalid webhook signature",
                extra={"received_signature": signature}
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Only process merge request events
    if webhook.object_kind != "merge_request":
        app_logger.info(
            "Ignoring non-merge request event",
            extra={"object_kind": webhook.object_kind}
        )
        return {"status": "ignored", "message": "Not a merge request event"}

    # Extract merge request details
    mr = webhook.object_attributes
    if mr.state not in ["opened", "reopened"]:
        app_logger.info(
            "Ignoring MR not in review state",
            extra={
                "mr_id": mr.iid,
                "state": mr.state
            }
        )
        return {"status": "ignored", "message": "MR is not in review state"}

    try:
        # 1. Extract Jira ID from MR title/branch (optional)
        jira_id = gitlab_service.extract_jira_id(mr.title, mr.source_branch)
        jira_context = None
        acceptance_criteria = []

        if jira_id:
            app_logger.info(
                "Found Jira ticket ID",
                extra={
                    "jira_id": jira_id,
                    "mr_title": mr.title,
                    "branch_name": mr.source_branch
                }
            )
            # Fetch Jira ticket details if ID is found
            try:
                jira_ticket = await jira_service.get_ticket_details(jira_id)
                acceptance_criteria = jira_service.extract_acceptance_criteria(jira_ticket.get("description", ""))
                jira_context = jira_ticket
                app_logger.info(
                    "Successfully fetched Jira ticket details",
                    extra={"jira_id": jira_id}
                )
            except Exception as e:
                app_logger.warning(
                    "Failed to fetch Jira ticket details, proceeding without Jira context",
                    extra={"jira_id": jira_id, "error": str(e)}
                )
        else:
            app_logger.info(
                "No Jira ticket ID found, proceeding with basic review",
                extra={
                    "mr_title": mr.title,
                    "branch_name": mr.source_branch
                }
            )
            # Create basic context from MR details
            jira_context = {
                "id": None,
                "summary": mr.title,
                "description": mr.description,
                "type": "Merge Request"
            }

        app_logger.info(
            "Processing merge request",
            extra={
                "mr_id": mr.iid,
                "project_id": webhook.project.id,
                "jira_id": jira_id,
                "has_acceptance_criteria": bool(acceptance_criteria)
            }
        )

        # 2. Get MR diff from GitLab
        mr_details = await gitlab_service.get_merge_request_diff(webhook.project.id, mr.iid)
        
        # Format the diff for review
        diff_text = "\n\n".join([
            f"File: {change['new_path']}\n"
            f"```diff\n{change['diff']}\n```"
            for change in mr_details["changes"]
        ])

        # 3. Send to LLM for review
        app_logger.info(
            "Starting code review with LLM",
            extra={
                "jira_id": jira_id,
                "has_jira_context": bool(jira_context),
                "num_acceptance_criteria": len(acceptance_criteria)
            }
        )
        review = await llm_service.review_code(
            diff=diff_text,
            jira_context=jira_context,
            acceptance_criteria=acceptance_criteria
        )

        # 4. Post review as MR comment
        app_logger.info("Posting review comment", extra={"mr_id": mr.iid})
        comment = review["raw_response"]
        await gitlab_service.post_comment(webhook.project.id, mr.iid, comment)

        app_logger.info(
            "Code review completed successfully",
            extra={
                "mr_id": mr.iid,
                "project_id": webhook.project.id,
                "jira_id": jira_id
            }
        )

        return {
            "status": "success",
            "message": "Code review completed and posted",
            "mr_id": mr.iid,
            "project_id": webhook.project.id,
            "jira_id": jira_id,
            "review_summary": review["structured_review"]["summary"]
        }

    except Exception as e:
        app_logger.error(
            "Error processing webhook",
            extra={
                "mr_id": mr.iid,
                "project_id": webhook.project.id,
                "error": str(e)
            },
            exc_info=True
        )
        return {
            "status": "error",
            "message": f"Failed to process merge request: {str(e)}",
            "mr_id": mr.iid,
            "project_id": webhook.project.id
        }

@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    app_logger.info("Detailed health check requested")
    
    try:
        health_status = {
            "status": "healthy",
            "version": "1.0.0",
            "services": {
                "gitlab": await check_gitlab_connection(),
                "jira": await check_jira_connection(),
                "llm": await check_llm_connection()
            }
        }
        app_logger.info("Health check completed", extra={"status": health_status})
        return health_status
    except Exception as e:
        app_logger.error("Health check failed", exc_info=True)
        raise

async def check_gitlab_connection() -> Dict[str, Any]:
    """Check GitLab API connection"""
    try:
        status = await gitlab_service.check_connection()
        app_logger.info("GitLab connection check", extra={"status": status})
        return status
    except Exception as e:
        app_logger.error("GitLab connection check failed", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }

async def check_jira_connection() -> Dict[str, Any]:
    """Check Jira API connection"""
    try:
        status = await jira_service.check_connection()
        app_logger.info("Jira connection check", extra={"status": status})
        return status
    except Exception as e:
        app_logger.error("Jira connection check failed", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }

async def check_llm_connection() -> Dict[str, Any]:
    """Check LLM API connection"""
    try:
        status = await llm_service.check_connection()
        app_logger.info("LLM connection check", extra={"status": status})
        return status
    except Exception as e:
        app_logger.error("LLM connection check failed", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    app_logger.info("Starting AI MergeMate server")
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True
    ) 