from johnllm import LMP, LLMModel
from pydantic import BaseModel


class Ans(BaseModel):
    answer: str

class Test(LMP):
    prompt = """
What is capital of greece?    
"""
    

res = LLMModel().invoke(
    """
What is capital of greece?
""",
    response_format=Ans,
    model_name="gpt-4.1"
)
print(res)