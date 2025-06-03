from typing import Dict, Any, Optional
import os
from jira import JIRA
from jira.exceptions import JIRAError
from pydantic import BaseModel
from app.utils.logger import app_logger

class JiraConfig(BaseModel):
    url: str
    email: str
    api_token: str

class JiraService:
    def __init__(self, config: Optional[JiraConfig] = None):
        self.config = config or JiraConfig(
            url=os.getenv("JIRA_URL", ""),
            email=os.getenv("JIRA_EMAIL", ""),
            api_token=os.getenv("JIRA_API_TOKEN", "")
        )
        app_logger.info("Initializing Jira service", extra={"url": self.config.url})
        self.client = JIRA(
            server=self.config.url,
            basic_auth=(self.config.email, self.config.api_token)
        )

    async def get_ticket_details(self, ticket_id: str) -> Dict[str, Any]:
        """
        Fetch details for a specific Jira ticket
        """
        app_logger.info("Fetching Jira ticket details", extra={"ticket_id": ticket_id})
        try:
            issue = self.client.issue(ticket_id)
            custom_fields = self._extract_custom_fields(issue)
            
            ticket_details = {
                "id": issue.key,
                "summary": issue.fields.summary,
                "description": issue.fields.description,
                "status": issue.fields.status.name,
                "type": issue.fields.issuetype.name,
                "assignee": issue.fields.assignee.displayName if issue.fields.assignee else None,
                "created": issue.fields.created,
                "updated": issue.fields.updated,
                "labels": issue.fields.labels,
                "custom_fields": custom_fields
            }
            
            app_logger.info(
                "Successfully fetched Jira ticket details",
                extra={
                    "ticket_id": ticket_id,
                    "status": issue.fields.status.name,
                    "type": issue.fields.issuetype.name
                }
            )
            return ticket_details
            
        except JIRAError as e:
            app_logger.error(
                "Failed to fetch Jira ticket details",
                extra={"ticket_id": ticket_id, "error": str(e)},
                exc_info=True
            )
            raise Exception(f"Failed to fetch Jira ticket details: {str(e)}")

    def _extract_custom_fields(self, issue) -> Dict[str, Any]:
        """
        Extract custom fields from Jira ticket
        """
        app_logger.debug(
            "Extracting custom fields",
            extra={"ticket_id": issue.key}
        )
        custom_fields = {}
        for field_name, field_value in issue.raw['fields'].items():
            if field_name.startswith('customfield_'):
                try:
                    field_meta = self.client.field_by_key(field_name)
                    custom_fields[field_meta['name']] = field_value
                except:
                    custom_fields[field_name] = field_value
                    
        app_logger.debug(
            "Custom fields extracted",
            extra={
                "ticket_id": issue.key,
                "num_custom_fields": len(custom_fields)
            }
        )
        return custom_fields

    async def check_connection(self) -> Dict[str, Any]:
        """
        Check Jira API connection
        """
        app_logger.info("Checking Jira connection")
        try:
            # Try to get server info
            server_info = self.client.server_info()
            status = {
                "status": "connected",
                "version": server_info.get("version"),
                "base_url": server_info.get("baseUrl")
            }
            app_logger.info(
                "Jira connection successful",
                extra={"version": server_info.get("version")}
            )
            return status
        except JIRAError as e:
            app_logger.error(
                "Jira connection check failed",
                extra={"error": str(e)},
                exc_info=True
            )
            return {
                "status": "error",
                "error": str(e)
            }

    def extract_acceptance_criteria(self, description: str) -> list[str]:
        """
        Extract acceptance criteria from Jira ticket description
        """
        app_logger.debug("Extracting acceptance criteria from description")
        if not description:
            app_logger.warning("Empty description provided for acceptance criteria extraction")
            return []
            
        # Simple extraction - look for lines starting with AC: or Acceptance Criteria:
        criteria = []
        for line in description.split('\n'):
            line = line.strip()
            if line.lower().startswith(('ac:', 'acceptance criteria:')):
                criteria.append(line)
                
        app_logger.info(
            "Extracted acceptance criteria",
            extra={"num_criteria": len(criteria)}
        )
        return criteria 