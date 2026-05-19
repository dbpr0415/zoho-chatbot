import json
import logging
from typing import Optional, Dict, Any, Tuple
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from app.config import settings

logger = logging.getLogger("parser_service")

class ToolCallParserService:
    @staticmethod
    async def repair_tool_call(err_str: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Attempts to repair a malformed tool call using a structured JSON LLM retry.
        Completely replaces fragile regex parsing.
        Returns: (tool_name, arguments_dict)
        """
        try:
            # Enforce strict JSON output via model parameters
            llm = ChatGroq(
                model=settings.llm.model_name,
                api_key=settings.llm.api_key,
                temperature=0.0,
                model_kwargs={"response_format": {"type": "json_object"}}
            )
        except Exception as e:
            logger.error(f"Failed to initialize repair LLM: {str(e)}")
            return None, None

        sys_prompt = """You are a strict JSON repair parser.
The user will provide an error string containing a malformed tool call generation (e.g., XML tags or broken JSON).
Your job is to safely extract the intended tool name and its arguments.
You MUST output ONLY a valid JSON object matching this schema:
{
  "tool_name": "name_of_the_tool",
  "arguments": { "key": "value" }
}
If you cannot determine the tool, return an empty JSON object: {}"""

        try:
            resp = await llm.ainvoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=f"Error dump: {err_str}")
            ])
            
            data = json.loads(resp.content)
            
            tool_name = data.get("tool_name")
            arguments = data.get("arguments")
            
            if tool_name and isinstance(arguments, dict):
                logger.info(f"Successfully repaired tool call: {tool_name}")
                return tool_name, arguments
                
        except json.JSONDecodeError:
            logger.warning("Repair attempt returned invalid JSON.")
        except Exception as e:
            logger.warning(f"Structured repair attempt failed: {str(e)}")
            
        return None, None
