from typing import Dict, Any, Optional, List
import os
from enum import Enum
from pydantic import BaseModel
import openai
from anthropic import Anthropic
from app.utils.logger import app_logger

class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"

class LLMConfig(BaseModel):
    # Configuration for LLM service
    provider: LLMProvider  # Which LLM provider to use (OpenAI, Anthropic, etc.)
    model: str  # Model name/identifier
    max_tokens: int = 2000  # Maximum tokens for completion (reduced from 4000 to leave room for context)
    temperature: float = 0.7  # Controls randomness in responses (0.0 = deterministic, 1.0 = creative)
    max_context_tokens: int = 6000  # Maximum tokens allowed for context (messages)
    chunk_size_tokens: int = 4000  # Maximum tokens per chunk when splitting large diffs

    def get_model_params(self) -> Dict[str, Any]:
        """Get model-specific parameters.
        
        Returns:
            Dict[str, Any]: Parameters specific to the current model
        """
        if self.model == "o1-mini":
            # o1-mini has specific restrictions:
            # - Uses max_completion_tokens instead of max_tokens
            # - Only supports default temperature (1.0)
            # - Doesn't support system role
            return {
                "max_completion_tokens": self.max_tokens,
                "temperature": 1.0  # Force default temperature
            }
        else:
            # Standard parameters for other models
            return {
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }

class LLMService:
    def __init__(self, config: Optional[LLMConfig] = None):
        # Initialize with provided config or use environment variables
        self.config = config or LLMConfig(
            provider=LLMProvider(os.getenv("DEFAULT_LLM_PROVIDER", "openai")),
            model=os.getenv("LLM_MODEL", "o1-mini"),  # Default to o1-mini if not specified
            max_tokens=int(os.getenv("MAX_TOKENS", "2000")),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_context_tokens=int(os.getenv("MAX_CONTEXT_TOKENS", "6000")),
            chunk_size_tokens=int(os.getenv("CHUNK_SIZE_TOKENS", "4000"))
        )
        
        # Log initialization details
        app_logger.info(
            "Initializing LLM service",
            extra={
                "provider": self.config.provider,
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
        )
        
        # Initialize the appropriate client based on provider
        if self.config.provider == LLMProvider.OPENAI:
            self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif self.config.provider == LLMProvider.ANTHROPIC:
            self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            error_msg = "Unsupported LLM provider: {}".format(self.config.provider)
            app_logger.error(error_msg)
            raise ValueError(error_msg)

    def _split_diff_into_chunks(self, diff: str, max_chunk_size: Optional[int] = None) -> List[str]:
        # Split a large diff into smaller chunks that fit within token limits
        # Args:
        #     diff: The complete diff text
        #     max_chunk_size: Maximum number of tokens per chunk (defaults to config value)
        # Returns:
        #     List[str]: List of diff chunks
        
        # Use provided chunk size or default from config
        max_chunk_size = max_chunk_size or self.config.chunk_size_tokens
        
        # Split diff into individual file changes
        file_changes = diff.split("\n\nFile: ")
        chunks = []
        current_chunk = []
        current_size = 0
        
        for change in file_changes:
            # Add back the "File: " prefix except for the first chunk
            if chunks or current_chunk:
                change = "File: " + change
                
            # Rough estimate of tokens (4 chars ≈ 1 token)
            change_size = len(change) // 4
            
            # Handle large individual file changes by splitting them into smaller pieces
            if change_size > max_chunk_size:
                # Split the change into lines and regroup
                lines = change.split("\n")
                current_lines = []
                current_lines_size = 0
                
                for line in lines:
                    line_size = len(line) // 4
                    # If adding this line would exceed chunk size, start a new chunk
                    if current_lines_size + line_size > max_chunk_size and current_lines:
                        if current_chunk:
                            chunks.append("\n\n".join(current_chunk))
                        current_chunk = ["\n".join(current_lines)]
                        current_size = current_lines_size
                        current_lines = [line]
                        current_lines_size = line_size
                    else:
                        current_lines.append(line)
                        current_lines_size += line_size
                
                # Add any remaining lines as a new chunk
                if current_lines:
                    if current_chunk:
                        chunks.append("\n\n".join(current_chunk))
                    current_chunk = ["\n".join(current_lines)]
                    current_size = current_lines_size
            # If adding this change would exceed chunk size, start a new chunk
            elif current_size + change_size > max_chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [change]
                current_size = change_size
            else:
                current_chunk.append(change)
                current_size += change_size
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
            
        app_logger.debug(
            "Split diff into chunks",
            extra={
                "num_chunks": len(chunks),
                "total_files": len(file_changes),
                "max_chunk_size": max_chunk_size
            }
        )
        return chunks

    async def _review_chunk(
        self,
        chunk: str,
        jira_context: Dict[str, Any],
        acceptance_criteria: List[str],
        chunk_num: int,
        total_chunks: int
    ) -> Dict[str, Any]:
        """Review a single chunk of the diff.
        
        Args:
            chunk: A portion of the diff to review
            jira_context: Context from Jira ticket
            acceptance_criteria: List of acceptance criteria
            chunk_num: Current chunk number
            total_chunks: Total number of chunks
            
        Returns:
            Dict[str, Any]: Review results for this chunk
        """
        prompt = self._build_review_prompt(
            chunk,
            jira_context,
            acceptance_criteria,
            chunk_num,
            total_chunks
        )
        
        try:
            if self.config.provider == LLMProvider.OPENAI:
                response = await self._get_openai_review(prompt)
            elif self.config.provider == LLMProvider.ANTHROPIC:
                response = await self._get_anthropic_review(prompt)
            else:
                raise ValueError("Unsupported provider: {}".format(self.config.provider))
                
            return self._parse_review_response(response)
        except Exception as e:
            app_logger.error(
                "Failed to review chunk {}/{}".format(chunk_num, total_chunks),
                extra={"error": str(e)},
                exc_info=True
            )
            raise

    def _build_review_prompt(
        self,
        diff: str,
        jira_context: Dict[str, Any],
        acceptance_criteria: List[str],
        chunk_num: int = 1,
        total_chunks: int = 1
    ) -> str:
        # Build the prompt for code review.
        # Args:
        #     diff: The code changes to review
        #     jira_context: Context from Jira ticket (if available)
        #     acceptance_criteria: List of acceptance criteria (if available)
        #     chunk_num: Current chunk number (for batched reviews)
        #     total_chunks: Total number of chunks (for batched reviews)
        # Returns:
        #     str: The formatted prompt for the LLM
        app_logger.debug("Building review prompt")
        
        # Build context section based on available information
        context_sections = []
        
        if jira_context and jira_context.get("id"):
            context_sections.extend([
                "Jira Ticket: {}".format(jira_context.get("id")),
                "Summary: {}".format(jira_context.get("summary")),
                "Type: {}".format(jira_context.get("type"))
            ])
        else:
            context_sections.extend([
                "Merge Request Title: {}".format(jira_context.get("summary", "N/A")),
                "Description: {}".format(jira_context.get("description", "N/A"))
            ])

        if acceptance_criteria:
            context_sections.append("\nAcceptance Criteria:")
            context_sections.extend(["- {}".format(ac) for ac in acceptance_criteria])
            
        if total_chunks > 1:
            context_sections.append("\nNote: This is part {} of {} of the complete review.".format(
                chunk_num, total_chunks
            ))
        
        context_text = "\n".join(context_sections)
        
        # Build the prompt using string concatenation
        prompt_parts = [
            "You are an expert code reviewer. Please review the following code changes and provide feedback.\n\n",
            context_text,
            "\n\nCode Changes:\n",
            diff,
            "\n\nPlease provide a code review that:\n",
            "1. Analyzes the code changes for quality and best practices\n",
            "2. Identifies potential bugs or issues\n",
            "3. Suggests improvements for code quality\n",
            "4. Notes any security concerns\n",
            "5. Provides specific, actionable feedback\n",
            "6. Includes inline comments for specific lines that need attention"
        ]
        
        if acceptance_criteria:
            prompt_parts.append("\n7. Verifies implementation against acceptance criteria")
            
        prompt_parts.extend([
            "\n\nFormat your review as follows:\n",
            "## Summary\n",
            "[Brief summary of the changes and overall assessment]\n\n",
            "## Code Quality\n",
            "[Feedback on code structure, readability, and best practices]\n\n",
            "## Potential Issues\n",
            "[List any bugs, edge cases, or concerns]\n\n",
            "## Security\n",
            "[Any security-related observations]\n\n",
            "## Suggestions\n",
            "[Specific recommendations for improvement]\n\n",
            "## Inline Comments\n",
            "For each file that needs attention, provide inline comments in this format:\n",
            "```\n",
            "File: path/to/file\n",
            "Line X: [Comment about this specific line]\n",
            "Line Y-Z: [Comment about this block of code]\n",
            "```\n",
            "Focus on:\n",
            "- Lines with potential bugs or issues\n",
            "- Code that could be improved\n",
            "- Security concerns\n",
            "- Best practices violations\n",
            "- Complex or unclear code that needs explanation"
        ])
        
        if acceptance_criteria:
            prompt_parts.extend([
                "\n\n## Acceptance Criteria Check\n",
                "[Verification of each acceptance criterion]"
            ])
            
        prompt = "".join(prompt_parts)
        
        app_logger.debug(
            "Review prompt built",
            extra={
                "prompt_length": len(prompt),
                "has_jira_context": bool(jira_context and jira_context.get("id")),
                "has_acceptance_criteria": bool(acceptance_criteria),
                "chunk_num": chunk_num,
                "total_chunks": total_chunks
            }
        )
        return prompt

    def _merge_reviews(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple chunk reviews into a single review.
        
        Args:
            reviews: List of review results from individual chunks
            
        Returns:
            Dict[str, Any]: Merged review results
        """
        app_logger.debug(
            "Merging reviews",
            extra={
                "num_reviews": len(reviews),
                "review_lengths": [len(r["raw_response"]) for r in reviews]
            }
        )
        
        if not reviews:
            app_logger.error("No reviews to merge")
            return {
                "raw_response": "No review content was generated. Please try again.",
                "structured_review": {
                    "summary": "No review content was generated.",
                    "quality": "No review content was generated.",
                    "issues": "No review content was generated.",
                    "security": "No review content was generated.",
                    "suggestions": "No review content was generated.",
                    "acceptance_check": "No review content was generated."
                }
            }
            
        merged_sections = {
            "summary": [],
            "quality": [],
            "issues": [],
            "security": [],
            "suggestions": [],
            "acceptance_check": []
        }
        
        for i, review in enumerate(reviews, 1):
            app_logger.debug(
                f"Processing review {i}/{len(reviews)}",
                extra={
                    "review_length": len(review["raw_response"]),
                    "has_structured": bool(review.get("structured_review"))
                }
            )
            structured = review.get("structured_review", {})
            for section in merged_sections:
                if structured.get(section):
                    merged_sections[section].append(structured[section])
        
        # Combine sections with clear separation
        final_sections = {
            section: "\n\n".join(content) if content else "No specific feedback provided."
            for section, content in merged_sections.items()
        }
        
        # Create a summary of summaries
        if len(reviews) > 1:
            summary_prefix = "## Complete Review Summary ({} parts)\n".format(len(reviews))
            summary_prefix += "This review was split into multiple parts due to size. "
            summary_prefix += "Below is a combined analysis of all changes.\n\n"
            final_sections["summary"] = summary_prefix + final_sections["summary"]
        
        # Combine raw responses
        raw_responses = [review["raw_response"] for review in reviews]
        if len(reviews) > 1:
            raw_response = "## Complete Review\n\n" + "\n\n---\n\n".join(raw_responses)
        else:
            raw_response = raw_responses[0]
            
        # Log the final merged review
        app_logger.debug(
            "Reviews merged",
            extra={
                "final_length": len(raw_response),
                "sections": {k: len(v) for k, v in final_sections.items()},
                "has_content": any(len(v) > 0 for v in final_sections.values())
            }
        )
            
        return {
            "raw_response": raw_response,
            "structured_review": final_sections
        }

    async def review_code(
        self,
        diff: str,
        jira_context: Dict[str, Any],
        acceptance_criteria: List[str]
    ) -> Dict[str, Any]:
        """Generate a code review using the configured LLM.
        
        Args:
            diff: The code changes to review
            jira_context: Context from Jira ticket
            acceptance_criteria: List of acceptance criteria
            
        Returns:
            Dict[str, Any]: Review results including structured review and inline comments
        """
        app_logger.info(
            "Starting code review",
            extra={
                "jira_id": jira_context.get("id"),
                "provider": self.config.provider,
                "model": self.config.model,
                "num_acceptance_criteria": len(acceptance_criteria)
            }
        )
        
        try:
            # Split diff into manageable chunks
            chunks = self._split_diff_into_chunks(diff)
            app_logger.info(
                "Split diff into chunks for review",
                extra={"num_chunks": len(chunks)}
            )
            
            # Review each chunk
            chunk_reviews = []
            all_inline_comments = []
            
            for i, chunk in enumerate(chunks, 1):
                app_logger.info(
                    "Reviewing chunk {}/{}".format(i, len(chunks)),
                    extra={"chunk_size": len(chunk)}
                )
                review_result = await self._review_chunk(
                    chunk,
                    jira_context,
                    acceptance_criteria,
                    i,
                    len(chunks)
                )
                chunk_reviews.append({
                    "raw_response": review_result["raw_response"],
                    "structured_review": review_result["structured_review"]
                })
                # Collect inline comments from each chunk
                if "inline_comments" in review_result and review_result["inline_comments"]:
                    all_inline_comments.extend(review_result["inline_comments"])

            # Merge structured reviews from all chunks
            final_structured_review = self._merge_reviews(chunk_reviews) # This now only merges structured parts
            
            app_logger.info(
                "Code review completed successfully",
                extra={
                    "jira_id": jira_context.get("id"),
                    "num_chunks": len(chunks),
                    "review_summary_preview": final_structured_review["structured_review"]["summary"][:100] + "...",
                    "total_inline_comments": len(all_inline_comments)
                }
            )
            
            # Return both the merged structured review and all collected inline comments
            return {
                "raw_response": final_structured_review["raw_response"], # Still include raw response for overall view
                "structured_review": final_structured_review["structured_review"],
                "inline_comments": all_inline_comments # Return collected inline comments
            }
            
        except Exception as e:
            app_logger.error(
                "Failed to generate code review",
                extra={
                    "jira_id": jira_context.get("id"),
                    "error": str(e)
                },
                exc_info=True
            )
            raise Exception("Failed to generate code review: {}".format(str(e)))

    async def _get_openai_review(self, prompt: str) -> str:
        # Get review from OpenAI
        # Args:
        #     prompt: The review prompt to send to OpenAI
        # Returns:
        #     str: The review response from OpenAI
        # Raises:
        #     Exception: If the OpenAI request fails

        # Log request details including token estimates
        app_logger.debug(
            "Requesting review from OpenAI",
            extra={
                "model": self.config.model,
                "prompt_length": len(prompt),
                "estimated_tokens": len(prompt) // 4
            }
        )
        try:
            # Estimate tokens in the prompt (rough estimate: 4 chars ≈ 1 token)
            estimated_tokens = len(prompt) // 4

            # Check if prompt exceeds context limit
            if estimated_tokens > self.config.max_context_tokens:
                app_logger.warning(
                    "Prompt exceeds max context tokens",
                    extra={
                        "estimated_tokens": estimated_tokens,
                        "max_context_tokens": self.config.max_context_tokens
                    }
                )
                # Truncate the prompt if necessary, preserving the most important parts
                max_chars = self.config.max_context_tokens * 4
                prompt = prompt[:max_chars] + "\n\n[Content truncated due to length]"

            # Get model-specific parameters
            model_params = self.config.get_model_params()

            # Prepare messages based on model capabilities
            if self.config.model == "o1-mini":
                # o1-mini doesn't support system role, so we'll prepend the system message
                # to the user message to maintain the same functionality
                messages = [
                    {
                        "role": "user",
                        "content": "You are an expert code reviewer. " + prompt
                    }
                ]
                # For o1-mini, we need to use the raw API parameters
                # The client library doesn't support max_completion_tokens directly
                # Also, o1-mini only supports temperature=1.0 (handled in get_model_params)

                app_logger.debug("Making OpenAI API call for o1-mini", extra={
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": model_params["temperature"],
                    "extra_body": {"max_completion_tokens": model_params["max_completion_tokens"]}
                })

                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=model_params["temperature"],  # Use model-specific temperature
                    extra_body={
                        "max_completion_tokens": model_params["max_completion_tokens"]
                    }
                )
            else:
                # For other models, use separate system and user messages
                messages = [
                    {"role": "system", "content": "You are an expert code reviewer."},
                    {"role": "user", "content": prompt}
                ]
                # Use standard parameters for other models (handled in get_model_params)

                app_logger.debug("Making OpenAI API call for other model", extra={
                    "model": self.config.model,
                    "messages": messages,
                    "max_tokens": model_params["max_tokens"],
                    "temperature": model_params["temperature"]
                })

                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    max_tokens=model_params["max_tokens"],
                    temperature=model_params["temperature"]
                )

            # Log successful response details
            app_logger.debug(
                "Received response from OpenAI",
                extra={
                    "model": self.config.model,
                    "response_id": getattr(response, 'id', 'N/A'), # Log response ID if available
                    "response_object": getattr(response, 'object', 'N/A'), # Log response object type
                    "response_created": getattr(response, 'created', 'N/A'), # Log creation timestamp
                    "response_model": getattr(response, 'model', 'N/A'), # Log model used in response
                    "response_usage": getattr(response, 'usage', 'N/A'), # Log token usage
                    "response_choices_count": len(response.choices) if hasattr(response, 'choices') else 0, # Log number of choices
                    "response_first_choice_finish_reason": getattr(response.choices[0], 'finish_reason', 'N/A') if hasattr(response, 'choices') and response.choices else 'N/A', # Log finish reason of first choice
                    "response_first_choice_message_content": getattr(response.choices[0].message, 'content', '')[:200] + '...' if hasattr(response, 'choices') and response.choices and hasattr(response.choices[0], 'message') and hasattr(response.choices[0].message, 'content') else '' # Log preview of content
                }
            )

            # Return the content of the first choice's message
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                 return response.choices[0].message.content
            else:
                 app_logger.warning("OpenAI response is missing expected content", extra={
                     "response_id": getattr(response, 'id', 'N/A'),
                     "response_object": getattr(response, 'object', 'N/A'),
                     "response_choices_count": len(response.choices) if hasattr(response, 'choices') else 0
                 })
                 return "" # Return empty string if content is missing

        except Exception as e:
            # Log and re-raise any errors
            app_logger.error(
                "OpenAI review request failed",
                extra={
                    "error": str(e),
                    "model": self.config.model,
                    "model_params": model_params if 'model_params' in locals() else None,
                    "prompt_length": len(prompt) # Include prompt length in error logs
                },
                exc_info=True
            )
            raise

    async def _get_anthropic_review(self, prompt: str) -> str:
        """Get review from Anthropic.
        
        Args:
            prompt: The review prompt to send to Anthropic
            
        Returns:
            str: The review response from Anthropic
            
        Raises:
            Exception: If the Anthropic request fails
        """
        app_logger.debug(
            "Requesting review from Anthropic",
            extra={"model": self.config.model}
        )
        try:
            # Get model-specific parameters
            model_params = self.config.get_model_params()
            
            response = await self.client.messages.create(
                model=self.config.model,
                max_tokens=model_params["max_tokens"],
                temperature=model_params["temperature"],
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            app_logger.debug(
                "Received response from Anthropic",
                extra={
                    "model": self.config.model,
                    "response_length": len(response.content[0].text),
                    "model_params": model_params
                }
            )
            return response.content[0].text
        except Exception as e:
            app_logger.error(
                "Anthropic review request failed",
                extra={
                    "error": str(e),
                    "model": self.config.model,
                    "model_params": model_params if 'model_params' in locals() else None
                },
                exc_info=True
            )
            raise

    def _parse_review_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM response into a structured format.
        
        Args:
            response: The raw response from the LLM
            
        Returns:
            Dict[str, Any]: Structured review with sections and inline comments
        """
        app_logger.debug(
            "Parsing review response",
            extra={
                "response_length": len(response),
                "response_preview": response[:200] + "..." if len(response) > 200 else response
            }
        )
        
        if not response or len(response.strip()) == 0:
            app_logger.error("Empty review response received from LLM")
            return {
                "raw_response": "No review content was generated. Please try again.",
                "structured_review": {
                    "summary": "No review content was generated.",
                    "quality": "No review content was generated.",
                    "issues": "No review content was generated.",
                    "security": "No review content was generated.",
                    "suggestions": "No review content was generated.",
                    "acceptance_check": "No review content was generated."
                },
                "inline_comments": [] # Return empty list for inline comments
            }
            
        sections = {
            "summary": "",
            "alignment": "",
            "quality": "",
            "issues": "",
            "security": "",
            "suggestions": "",
            "acceptance_check": ""
        }
        
        current_section = None
        section_content = []
        in_code_block = False
        current_file = None
        # Store parsed inline comments with file and line info
        parsed_inline_comments = [] 
        current_comment_lines = []
        current_line_info = None # Store line number/range for the current comment
        
        for line in response.split("\n"):
            # Handle code blocks for inline comments
            if line.strip() == "```":
                if in_code_block:
                    # End of an inline comments code block
                    # Add any remaining comments from the last file
                    if current_file and current_comment_lines:
                        parsed_inline_comments.append({
                            "file": current_file,
                            "line": current_line_info, # Can be None, single int, or range string
                            "comment": "\n".join(current_comment_lines).strip()
                        })
                    current_file = None
                    current_comment_lines = []
                    current_line_info = None
                in_code_block = not in_code_block
                continue
                
            if in_code_block:
                # Parse file path and line information within the code block
                if line.strip().startswith("File: "):
                    if current_file and current_comment_lines:
                         # Save comments from the previous file/section before starting a new one
                        parsed_inline_comments.append({
                            "file": current_file,
                            "line": current_line_info,
                            "comment": "\n".join(current_comment_lines).strip()
                        })
                    current_file = line.strip()[6:].strip()
                    current_comment_lines = []
                    current_line_info = None # Reset line info for the new file
                elif current_file and (line.strip().startswith("Line ") or line.strip().startswith("Lines ")):
                     if current_comment_lines:
                         # Save the previous comment before starting a new one for a different line
                         parsed_inline_comments.append({
                            "file": current_file,
                            "line": current_line_info,
                            "comment": "\n".join(current_comment_lines).strip()
                        })
                     # Extract line number or range
                     line_info_str = line.strip()[len("Line "):].strip()
                     if '-' in line_info_str:
                         current_line_info = line_info_str # Store as range string
                     else:
                          try:
                              current_line_info = int(line_info_str.split(":")[0]) # Store as int
                          except ValueError:
                              current_line_info = line_info_str # Store as string if not simple int

                     current_comment_lines = [line.strip().split(":", 1)[1].strip()] if ':' in line.strip() else []

                elif current_file:
                    # Add lines within the current file/comment section
                    current_comment_lines.append(line)
                continue
            
            # Handle regular sections
            if line.startswith("## "):
                if current_section:
                    sections[current_section] = "\n".join(section_content).strip()
                # Ignore the inline comments section header for general review body
                if line.strip() != "## Inline Comments":
                    current_section = line[3:].lower().replace(" ", "_")
                    section_content = []
                else:
                    current_section = None # Don't add inline comments section to general review
                    section_content = []
            elif current_section:
                section_content.append(line)
                
        # Add any remaining content from the last section (if not inline comments block)
        if current_section:
            sections[current_section] = "\n".join(section_content).strip()
            
        # Add any remaining inline comments from the last file block
        if in_code_block and current_file and current_comment_lines:
             parsed_inline_comments.append({
                 "file": current_file,
                 "line": current_line_info,
                 "comment": "\n".join(current_comment_lines).strip()
             })
             
        # Log the parsed sections and inline comments
        app_logger.debug(
            "Review response parsed",
            extra={
                "sections": {k: len(v) for k, v in sections.items()},
                "has_content": any(len(v) > 0 for v in sections.values()),
                "num_inline_comments": len(parsed_inline_comments),
                "inline_comments_preview": parsed_inline_comments[:5] # Log a preview of parsed inline comments
            }
        )
        
        # If no sections were found (excluding inline comments section), treat the entire response (excluding inline comments block) as a summary
        # Find the start and end of the inline comments block to exclude it from the general summary fallback
        response_lines = response.split("\n")
        inline_block_start = -1
        inline_block_end = -1
        
        for i, line in enumerate(response_lines):
            if line.strip() == "## Inline Comments":
                inline_block_start = i
                # Find the next ``` after ## Inline Comments to mark the end of the structured inline comments block
                for j in range(i + 1, len(response_lines)):
                     if response_lines[j].strip() == "```":
                         inline_block_end = j
                         break
                break # Found the inline block header and attempted to find its end
        
        general_review_content = []
        for i, line in enumerate(response_lines):
             # Include lines that are not part of the inline comments block or its header
             if not (inline_block_start <= i <= inline_block_end or (inline_block_start != -1 and i > inline_block_end and response_lines[i].strip() == "```")):
                 general_review_content.append(line)

        if not any(sections.values()):
            app_logger.warning("No structured sections found in review response (excluding inline comments), treating remaining content as summary")
            # Use the content outside the inline comments block as the summary fallback
            sections["summary"] = "\n".join(general_review_content).strip()


        return {
            "raw_response": response,
            "structured_review": sections,
            "inline_comments": parsed_inline_comments # Return parsed inline comments separately
        }

    async def check_connection(self) -> Dict[str, Any]:
        # Check LLM API connection.
        # Returns:
        #     Dict[str, Any]: Connection status and provider details
        # Raises:
        #     Exception: If the connection check fails
        app_logger.info(
            "Checking LLM connection",
            extra={"provider": self.config.provider}
        )
        try:
            if self.config.provider == LLMProvider.OPENAI:
                # Try to list models (synchronous call)
                models = self.client.models.list()
                status = {
                    "status": "connected",
                    "provider": "openai",
                    "available_models": [model.id for model in models.data]
                }
                app_logger.info(
                    "OpenAI connection successful",
                    extra={"available_models": status["available_models"]}
                )
                return status
            elif self.config.provider == LLMProvider.ANTHROPIC:
                # Try to get model info (synchronous call)
                model = self.client.models.retrieve(self.config.model)
                status = {
                    "status": "connected",
                    "provider": "anthropic",
                    "model": model.id
                }
                app_logger.info(
                    "Anthropic connection successful",
                    extra={"model": model.id}
                )
                return status
            else:
                error_msg = "Unsupported provider: {}".format(self.config.provider)
                app_logger.error(error_msg)
                return {
                    "status": "error",
                    "error": error_msg
                }
        except Exception as e:
            app_logger.error(
                "LLM connection check failed",
                extra={"error": str(e)},
                exc_info=True
            )
            return {
                "status": "error",
                "error": str(e)
            } 