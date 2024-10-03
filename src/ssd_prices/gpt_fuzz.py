from joblib import Memory
from openai import AsyncOpenAI
import pydantic

memory = Memory("cache")

client: AsyncOpenAI = None


def init_client(api_key: str):
    global client
    client = AsyncOpenAI(api_key=api_key)


system_prompt = """\
Take in the name of an Amazon listing, and a list of possible matches, and return the best match or null.

Consider the following factors when determining the best match:
- Exact match first.
- Highest similarity in terms of wording and key product attributes (e.g., brand, model, size, color).
- Number of matched keywords.

# Steps

1. Compare the Amazon listing name with each possible match.
2. Check for exact match; if found, select it.
3. Determine the similarity based on shared keywords and product attributes.
4. Rank each possible match based on similarity.
5. Select the highest-ranking match or None if no suitable match is found.

# Output Format

JSON:
```json
{
  "best_match": "name_of_the_best_matching_listing_or_None"
}
```

# Examples

**Example 1:**

**Input:**
```json
{
  "listing_name": "Apple iPhone 13, 128GB, Blue",
  "possible_matches": [
    "Apple iPhone 13, 128GB, Red",
    "Samsung Galaxy S21, 256GB, Gray",
    "Apple iPhone 13 Pro, 128GB, Blue",
    "Apple iPhone 13, 128GB, Blue"
  ]
}
```

**Reasoning Order:**
- Compare each possible match with "Apple iPhone 13, 128GB, Blue".
- An exact match is found with "Apple iPhone 13, 128GB, Blue".

**Output:**
```json
{
  "best_match": "Apple iPhone 13, 128GB, Blue"
}
```

**Example 2:**

**Input:**
```json
{
  "listing_name": "Sony WH-1000XM4 Wireless Noise-Cancelling Headphones, Black",
  "possible_matches": [
    "Sony WH-1000XM3 Wireless Noise-Cancelling Headphones, Black",
    "Sony WH-1000XM4 Wireless Noise-Cancelling Headphones, Silver",
    "Bose QuietComfort 35 II Wireless Bluetooth Headphones, Black"
  ]
}
```

**Reasoning Order:**
- Compare each possible match with "Sony WH-1000XM4 Wireless Noise-Cancelling Headphones, Black".
- No exact match is found.
- Highest similarity match is "Sony WH-1000XM4 Wireless Noise-Cancelling Headphones, Silver".

**Output:**
```json
{
  "best_match": "Sony WH-1000XM4 Wireless Noise-Cancelling Headphones, Silver"
}
```

**Example 3:**

**Input:**
```json
{
  "listing_name": "Lenovo ThinkPad X1 Carbon Gen 9, 14\" Ultrabook, Black",
  "possible_matches": [
    "HP Spectre x360, 13.3\" Touch Laptop, Silver",
    "Dell XPS 13, 13.4\" FHD Laptop, White",
    "Asus ZenBook 14, 14\" Laptop, Blue"
  ]
}
```

**Reasoning Order:**
- Compare each possible match with "Lenovo ThinkPad X1 Carbon Gen 9, 14\" Ultrabook, Black".
- No exact match is found.
- No suitable matches based on similarity.

**Output:**
```json
{
  "best_match": null
}
```

# Notes

- If no possible match has significant similarity (e.g., very few common keywords), return `None`.
- Generalize comparison logic to various product categories.
"""


class MatchRequest(pydantic.BaseModel):
    listing_name: str
    possible_matches: list[str]


@memory.cache
async def match_listing(match_request: MatchRequest) -> str | None:
    class MatchResponse(pydantic.BaseModel):
        best_match: str | None = pydantic.Field(
            json_schema_extra={"enum": list(match_request.possible_matches) + [None]}
        )

    res = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": match_request.model_dump_json(),
            },
        ],
        response_format=MatchResponse,
    )

    return res.choices[0].message.parsed.best_match
