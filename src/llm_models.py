from langchain_openai import ChatOpenAI

openai_4o = ChatOpenAI(model="gpt-4o")

LLM_MODELS = {
    "openai_4o": openai_4o,
}