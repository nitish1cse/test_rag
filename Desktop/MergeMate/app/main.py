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

        # 2. Get MR diff details from GitLab (needed for inline comments)
        mr_details = await gitlab_service.get_merge_request_diff(webhook.project.id, mr.iid)

        # 3. Send to LLM for review
        # Format the diff for LLM review - include old and new paths and the diff content
        diff_text = "\n\n".join([
            f"File: {change.get('old_path','N/A')} -> {change.get('new_path', 'N/A')}\n"
            f"```diff\n{change.get('diff', '')}\n```"
            for change in mr_details.get("changes", [])
        ])

        app_logger.info(
            "Starting code review with LLM",
            extra={
                "jira_id": jira_id,
                "has_jira_context": bool(jira_context),
                "num_acceptance_criteria": len(acceptance_criteria)
            }
        )
        review_results = await llm_service.review_code(
            diff=diff_text,
            jira_context=jira_context,
            acceptance_criteria=acceptance_criteria
        )

        # 4. Post overall review as MR comment
        overall_review_comment = review_results["raw_response"]
        if overall_review_comment and overall_review_comment.strip():
             app_logger.info("Posting overall review comment", extra={"mr_id": mr.iid})
             await gitlab_service.post_comment(webhook.project.id, mr.iid, overall_review_comment)
        else:
             app_logger.warning("No overall review content to post", extra={"mr_id": mr.iid})

        # 5. Post inline comments
        inline_comments = review_results.get("inline_comments", [])
        if inline_comments:
            app_logger.info(
                "Posting inline comments",
                extra={
                    "mr_id": mr.iid,
                    "num_inline_comments": len(inline_comments)
                }
            )

            diff_refs = mr_details.get('diff_refs', {})
            base_sha = diff_refs.get('base_sha')
            head_sha = diff_refs.get('head_sha')
            start_sha = diff_refs.get('start_sha')

            if not (base_sha and head_sha and start_sha):
                 app_logger.error("Missing diff_refs, cannot post inline comments with position.", extra=diff_refs)
            else:
                for comment_data in inline_comments:
                     file_path = comment_data.get("file")
                     line_info = comment_data.get("line")
                     comment_body = comment_data.get("comment")

                     if not file_path or not comment_body:
                         app_logger.warning("Skipping invalid inline comment data", extra=comment_data)
                         continue

                     # Find the relevant change in mr_details based on file_path
                     target_change = None
                     for change in mr_details.get('changes', []) : # Iterate through changes from get_merge_request_diff
                         if change.get('new_path') == file_path or change.get('old_path') == file_path:
                             target_change = change
                             break

                     if not target_change:
                         app_logger.warning(f"Could not find diff change for file {file_path} to post inline comment", extra={'line': line_info, 'comment_preview': comment_body[:100] + '...'})
                         # Post as a general comment if file change is not found in diff details
                         try:
                            note = gitlab_service.client.projects.get(webhook.project.id).mergerequests.get(mr.iid).notes.create({
                                'body': f"Inline comment on {file_path} (Line: {line_info or 'N/A'}):\n\n{comment_body}"
                            })
                            app_logger.info(
                                "Posted inline comment as general comment (file change not found)",
                                extra={
                                    "mr_id": mr.iid,
                                    "file": file_path,
                                    "line": line_info,
                                    "note_id": note.id
                                }
                            )
                         except Exception as e:
                             app_logger.error(
                                 "Failed to post general comment fallback for inline comment",
                                 extra={
                                     "mr_id": mr.iid,
                                     "file": file_path,
                                     "line": line_info,
                                     "error": str(e)
                                 },
                                 exc_info=True
                             )
                         continue # Move to the next comment


                     # Attempt to map the LLM's line number to the diff hunk
                     target_line_in_diff = None
                     position_type = 'text'

                     if line_info is not None:
                          # Convert line_info to string to handle both int and str ranges
                          line_info_str = str(line_info)

                          # Parse the diff hunk to find the line
                          diff_lines = target_change.get('diff', '').splitlines()
                          # Keep track of original line numbers in the new file
                          new_line_num_in_hunk = 0
                          old_line_num_in_hunk = 0

                          for i, diff_line in enumerate(diff_lines):
                              # Lines starting with + are additions in the new file
                              if diff_line.startswith('+'):
                                  new_line_num_in_hunk += 1
                                  # Check if this line corresponds to the LLM's suggested line number
                                  # This is a simplified check and might need more complex diff parsing
                                  if isinstance(line_info, int) and new_line_num_in_hunk == line_info:
                                      target_line_in_diff = i + 1 # Line number in the diff hunk (1-based)
                                      position_type = 'text' # Position refers to a line in the text diff
                                      break
                              # Lines starting with - are deletions from the old file
                              elif diff_line.startswith('-'):
                                   old_line_num_in_hunk += 1
                                   # If the comment is for an old line (less likely with current prompt but for completeness)
                                   if isinstance(line_info, int) and old_line_num_in_hunk == line_info and target_change.get('old_path') == file_path:
                                       target_line_in_diff = i + 1
                                       position_type = 'text'
                                       # Need to set old_path and old_line in position_params
                                       break
                              # Lines starting with ' ' are context lines
                              elif diff_line.startswith(' '):
                                   new_line_num_in_hunk += 1
                                   old_line_num_in_hunk += 1
                                   # Check if this context line corresponds to the LLM's suggested line number
                                   if isinstance(line_info, int) and new_line_num_in_hunk == line_info:
                                       target_line_in_diff = i + 1
                                       position_type = 'text'
                                       break
                              # Handle @@ line (hunk header) - does not increment line numbers within the hunk
                              elif diff_line.startswith('@@'):
                                   # Extract starting line numbers from the hunk header if needed for more accurate mapping
                                   pass # For now, we rely on incrementing within the hunk

                          if target_line_in_diff is None:
                               app_logger.warning(f"Could not find line {line_info_str} in diff hunk for {file_path}")
                               # If line not found in diff hunk, fallback to general comment
                               try:
                                  note = gitlab_service.client.projects.get(webhook.project.id).mergerequests.get(mr.iid).notes.create({
                                      'body': f"Inline comment on {file_path} (Line: {line_info_str or 'N/A'}):\n\n{comment_body}"
                                  })
                                  app_logger.info(
                                      "Posted inline comment as general comment (line not found in diff)",
                                      extra={
                                          "mr_id": mr.iid,
                                          "file": file_path,
                                          "line": line_info_str,
                                          "note_id": note.id
                                      }
                                  )
                               except Exception as e:
                                   app_logger.error(
                                       "Failed to post general comment fallback for inline comment (line not found)",
                                       extra={
                                           "mr_id": mr.iid,
                                           "file": file_path,
                                           "line": line_info_str,
                                           "error": str(e)
                                       },
                                       exc_info=True
                                   )
                               continue # Move to the next comment


                     position_params = None
                     # Construct position parameters for inline comment if a line was found in the diff
                     if target_line_in_diff is not None:
                         position_params = {
                             'base_sha': base_sha,
                             'head_sha': head_sha,
                             'start_sha': start_sha,
                             'position_type': position_type,
                             'new_path': target_change.get('new_path', file_path), # Use new_path from change if available
                             'new_line': target_line_in_diff # Use the line number within the diff hunk
                             # For comments on old lines, you would use 'old_path' and 'old_line'
                             # For now, we assume comments are on new or context lines in the new file view
                         }
                         # If the change is a deletion, we might need old_path and old_line instead
                         if target_change.get('deleted_file'):
                             position_params['old_path'] = target_change.get('old_path', file_path)
                             position_params['old_line'] = target_line_in_diff # Need to map to old line in diff hunk
                             del position_params['new_path']
                             del position_params['new_line'] # Assuming comments on deletions refer to old lines

                         app_logger.debug("Attempting to post inline comment with position", extra=position_params)


                     try:
                         if position_params:
                             # Post inline comment with position
                             note = gitlab_service.client.projects.get(webhook.project.id).mergerequests.get(mr.iid).notes.create({
                                 'body': comment_body,
                                 'position': position_params
                             })
                             app_logger.info(
                                 "Successfully posted inline comment",
                                 extra={
                                     "mr_id": mr.iid,
                                     "file": file_path,
                                     "line": line_info,
                                     "note_id": note.id
                                 }
                             )
                         else:
                             # If we can't determine the position, post as a general MR comment
                             app_logger.warning("Could not determine position for inline comment, posting as general comment", extra={'file': file_path, 'line': line_info, 'comment_preview': comment_body[:100] + '...'})
                             note = gitlab_service.client.projects.get(webhook.project.id).mergerequests.get(mr.iid).notes.create({
                                 'body': f"Inline comment on {file_path} (Line: {line_info or 'N/A'}):\n\n{comment_body}"
                             })
                             app_logger.info(
                                 "Posted inline comment as general comment (position unknown)",
                                 extra={
                                     "mr_id": mr.iid,
                                     "file": file_path,
                                     "line": line_info,
                                     "note_id": note.id
                                 }
                             )

                     except Exception as e:
                         app_logger.error(
                             "Failed to post inline comment",
                             extra={
                                 "mr_id": mr.iid,
                                 "file": file_path,
                                 "line": line_info,
                                 "error": str(e)
                             },
                             exc_info=True
                         )
                         # Continue to the next comment even if one fails
                         pass # Or implement a retry mechanism

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
            "review_summary": review_results["structured_review"]["summary"],
            "num_inline_comments_posted": len([c for c in inline_comments if 'note_id' in c]) # Simple count of attempted posts
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