from johnllm import LLMModel
from pydantic import BaseModel, Field

class Response(BaseModel):
    name: str

class Answer(BaseModel):
    answer: Response

model = LLMModel()
res = model.invoke("Name the capital of France", model_name="deepseek-chat", response_format=Answer)
print(res)
print(res.model_dump())