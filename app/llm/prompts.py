from typing import List, Dict, Any, Optional

DEFAULT_TOOL_INSTRUCTIONS = """
You have access to the following approved local Windows PC tools:
{tool_descriptions}

To call a tool, respond ONLY with a JSON block in this exact format:
```json
{{
  "tool": "tool_name",
  "arguments": {{
    "arg1": "value"
  }}
}}
```

CRITICAL RULES:
1. Only call tools that are listed above.
2. If no tool is needed, respond naturally to the user without JSON formatting.
3. Keep spoken voice responses concise, conversational, and direct (1-3 sentences unless asked for details).
4. Never pretend you executed an action unless the system tool returned a confirmed result.
"""


def build_system_prompt(
    assistant_name: str = "FOXSI",
    custom_system_prompt: Optional[str] = None,
    response_style: str = "conversational",
    tools: Optional[List[Dict[str, Any]]] = None,
) -> str:
    base = custom_system_prompt or (
        f"You are {assistant_name}, a local AI voice assistant running on the user's Windows PC. "
        "You are helpful, concise, technically capable, and privacy-first. "
        "You operate completely locally. Never claim to have executed an operating-system "
        "action unless the tool system confirms that it actually happened."
    )

    if response_style == "concise":
        base += " Be extremely direct and use as few words as possible."
    elif response_style == "technical":
        base += " Provide precise technical details, hardware statistics, and exact explanations."
    elif response_style == "friendly":
        base += " Maintain an enthusiastic, friendly, and warm conversational tone."

    if tools:
        tool_desc_lines = []
        for t in tools:
            desc = f"- {t['name']}({', '.join(t.get('parameters', {}).keys())}): {t.get('description', '')}"
            tool_desc_lines.append(desc)
        tool_block = DEFAULT_TOOL_INSTRUCTIONS.format(tool_descriptions="\n".join(tool_desc_lines))
        return f"{base}\n\n{tool_block}"

    return base
