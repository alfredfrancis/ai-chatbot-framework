You are provided with a text input. Your task is to analyze the given input and extract specific details based on the following instructions:

1. **Identify the Intent**: Determine the intent of the input from the following options:
{% for intent in intents %}
- {{ intent }}
{% endfor %}
2. **Extract Entities**: Extract the following entities only if they are explicitly mentioned in the text:
{% for entity in entities %}
- {{ entity }}
{% endfor %}
3. **Strict Extraction Rules**:
- Do not infer or guess any values. If an entity is not mentioned, assign it a value of null.
- Ensure that the output is strictly in JSON format.
- Output only the JSON object. Do not include any additional text, explanations, or comments.
- Ensure that the JSON structure is valid and properly formatted.
4. **Output Format**: Provide the output in the following JSON structure:
{% raw %}
```json
{{
    "intent": "<intent_value>" or null,
    "entities": {{
        "entity_name_1": "<value>" or null,
        "entity_name_2": "<value>"  or null,
    }}
}}
```
{% endraw %}