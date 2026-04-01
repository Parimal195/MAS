from google import genai
from google.genai import types
from pydantic import BaseModel
import os
import json
from typing import Type, Any, Optional

class Agent:
    def __init__(self, name: str, instructions: str, model: str = "gemini-2.5-flash", client: Optional[genai.Client] = None):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.client = client or genai.Client()
        self.config = types.GenerateContentConfig(
            system_instruction=instructions,
            temperature=0.7,
        )

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None) -> Any:
        print(f"[{self.name}] Thinking...")
        if schema:
            config = types.GenerateContentConfig(
                system_instruction=self.instructions,
                temperature=0.7,
                response_mime_type="application/json",
                response_schema=schema,
            )
        else:
            config = self.config

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config
        )
        
        if schema:
            try:
                return schema.model_validate_json(response.text)
            except Exception as e:
                print(f"[{self.name}] Failed to parse JSON. Raw output: {response.text}")
                raise e
        return response.text
