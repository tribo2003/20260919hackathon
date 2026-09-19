# Please install OpenAI SDK first: pip3 install openai

import os
from openai import OpenAI

export IFM_MODEL="IFM/K2-Horizon-375B-A23B"

client = OpenAI(
    base_url=os.environ["IFM_BASE_URL"],
    api_key=os.environ["IFM_API_KEY"],
)

resp = client.chat.completions.create(
    model=os.environ["IFM_MODEL"],
    messages=[{"role": "user", "content": "hello"}],
)
print(resp.choices[0].message.content)