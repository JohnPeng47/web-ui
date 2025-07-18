from src.llm_models import claude_4_sonnet


res = claude_4_sonnet().invoke("What is the capital of France?")
print(res)