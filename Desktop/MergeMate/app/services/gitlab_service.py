from typing import Dict, Any, Optional
import os
import gitlab
from gitlab.exceptions import GitlabError
from pydantic import BaseModel
from app.utils.logger import app_logger

class GitLabConfig(BaseModel):
    url: str
    token: str

class GitLabService:
    def __init__(self, config: Optional[GitLabConfig] = None):
        self.config = config or GitLabConfig(
            url=os.getenv("GITLAB_URL", "https://gitlab.com"),
            token=os.getenv("GITLAB_TOKEN", "")
        )
        app_logger.info("Initializing GitLab service", extra={"url": self.config.url})
        self.client = gitlab.Gitlab(
            url=self.config.url,
            private_token=self.config.token
        )

    async def get_merge_request_diff(self, project_id: int, mr_iid: int) -> Dict[str, Any]:
        """
        Fetch the diff for a specific merge request
        """
        app_logger.info(
            "Fetching merge request diff",
            extra={"project_id": project_id, "mr_iid": mr_iid}
        )
        try:
            project = self.client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            changes = mr.changes()
            app_logger.info(
                "Successfully fetched merge request diff",
                extra={
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                    "num_changes": len(changes.get("changes", []))
                }
            )
            return {
                "title": mr.title,
                "description": mr.description,
                "source_branch": mr.source_branch,
                "target_branch": mr.target_branch,
                "changes": changes.get("changes", []),
                "author": mr.author.get("name"),
                "created_at": mr.created_at,
                "updated_at": mr.updated_at
            }
        except GitlabError as e:
            app_logger.error(
                "Failed to fetch merge request diff",
                extra={
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                    "error": str(e)
                },
                exc_info=True
            )
            raise Exception(f"Failed to fetch merge request diff: {str(e)}")

    async def post_comment(self, project_id: int, mr_iid: int, comment: str) -> Dict[str, Any]:
        """
        Post a comment on a merge request
        """
        app_logger.info(
            "Posting comment on merge request",
            extra={
                "project_id": project_id,
                "mr_iid": mr_iid,
                "comment_length": len(comment),
                "comment_preview": comment[:200] + "..." if len(comment) > 200 else comment,
                "has_content": bool(comment and comment.strip()),
                "num_lines": len(comment.split("\n")),
                "sections": [line.strip() for line in comment.split("\n") if line.strip().startswith("##")]
            }
        )
        
        if not comment or not comment.strip():
            app_logger.error(
                "Attempting to post empty comment",
                extra={
                    "project_id": project_id,
                    "mr_iid": mr_iid
                }
            )
            raise ValueError("Cannot post empty comment")
            
        try:
            project = self.client.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            
            # Log MR details before posting
            app_logger.debug(
                "Found merge request",
                extra={
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                    "mr_title": mr.title,
                    "mr_state": mr.state,
                    "mr_author": mr.author.get("name") if mr.author else None
                }
            )
            
            # Create the note
            note = mr.notes.create({"body": comment})
            
            # Log successful posting with note details
            app_logger.info(
                "Successfully posted comment",
                extra={
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                    "note_id": note.id,
                    "note_created_at": note.created_at,
                    "note_author": note.author.get("name") if note.author else None,
                    "note_length": len(note.body),
                    "note_preview": note.body[:200] + "..." if len(note.body) > 200 else note.body
                }
            )
            
            return {
                "id": note.id,
                "body": note.body,
                "created_at": note.created_at,
                "author": note.author.get("name") if note.author else None
            }
        except GitlabError as e:
            app_logger.error(
                "Failed to post comment",
                extra={
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "comment_length": len(comment),
                    "comment_preview": comment[:200] + "..." if len(comment) > 200 else comment
                },
                exc_info=True
            )
            raise Exception(f"Failed to post comment: {str(e)}")
        except Exception as e:
            app_logger.error(
                "Unexpected error while posting comment",
                extra={
                    "project_id": project_id,
                    "mr_iid": mr_iid,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "comment_length": len(comment),
                    "comment_preview": comment[:200] + "..." if len(comment) > 200 else comment
                },
                exc_info=True
            )
            raise

    async def check_connection(self) -> Dict[str, Any]:
        """
        Check GitLab API connection
        """
        app_logger.info("Checking GitLab connection")
        try:
            self.client.auth()
            user = self.client.user
            status = {
                "status": "connected",
                "version": self.client.version(),
                "user": user.username
            }
            app_logger.info(
                "GitLab connection successful",
                extra={"user": user.username, "version": self.client.version()}
            )
            return status
        except GitlabError as e:
            app_logger.error(
                "GitLab connection check failed",
                extra={"error": str(e)},
                exc_info=True
            )
            return {
                "status": "error",
                "error": str(e)
            }

    def extract_jira_id(self, mr_title: str, branch_name: str) -> Optional[str]:
        """
        Extract Jira ID from MR title or branch name
        Common formats:
        - PROJ-123
        - feature/PROJ-123
        - bugfix/PROJ-123
        """
        import re
        
        app_logger.info(
            "Extracting Jira ID",
            extra={
                "mr_title": mr_title,
                "branch_name": branch_name
            }
        )
        
        # Try to find Jira ID in title first
        jira_pattern = r'[A-Z]+-\d+'
        match = re.search(jira_pattern, mr_title)
        if match:
            jira_id = match.group(0)
            app_logger.info(
                "Found Jira ID in MR title",
                extra={"jira_id": jira_id, "source": "title"}
            )
            return jira_id
            
        # Try to find Jira ID in branch name
        match = re.search(jira_pattern, branch_name)
        if match:
            jira_id = match.group(0)
            app_logger.info(
                "Found Jira ID in branch name",
                extra={"jira_id": jira_id, "source": "branch"}
            )
            return jira_id
            
        app_logger.warning(
            "No Jira ID found",
            extra={"mr_title": mr_title, "branch_name": branch_name}
        )
        return None 