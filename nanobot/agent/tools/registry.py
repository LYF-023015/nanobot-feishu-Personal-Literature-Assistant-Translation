"""Tool registry for dynamic tool management."""

from typing import Any

from nanobot.agent.tools.base import Tool


class ToolRegistry:
    """
    Registry for agent tools.
    
    Allows dynamic registration and execution of tools.
    """
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        return [tool.to_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """
        Execute a tool by name with given parameters.
        
        Args:
            name: Tool name.
            params: Tool parameters.
        
        Returns:
            Tool execution result as string.
        
        Raises:
            KeyError: If tool not found.
        """
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"

        if not isinstance(params, dict):
            return (
                f"Error: Invalid parameters for tool '{name}': arguments must be an object. "
                "This may happen when tool-call arguments are truncated. "
                "Please retry with shorter content or split the task into smaller tool calls."
            )

        parse_error = params.get("__nanobot_tool_args_error__")
        if parse_error:
            detail = params.get("__nanobot_tool_args_error_msg__", "unknown parse error")
            return (
                f"Error: Tool-call arguments for '{name}' could not be parsed ({detail}). "
                "This usually means the arguments were truncated. "
                "Please reduce argument size and retry. For long file output, use write_file for the first chunk and append_file for subsequent chunks."
            )

        try:
            errors = tool.validate_params(params)
            if errors:
                if name in {"write_file", "append_file"} and "missing required content" in "; ".join(errors):
                    return (
                        f"Error: Invalid parameters for tool '{name}': missing required content. "
                        "This often indicates argument truncation. Please shorten each content chunk and retry; "
                        "for large files, write in multiple append_file chunks."
                    )
                return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)
            return await tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"
    
    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
