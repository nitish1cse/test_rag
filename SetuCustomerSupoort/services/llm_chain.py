from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import config
from db.storage import retrieve_secret
from services.vectorstore import get_product_specific_retriever


feedback_store = {}

TROUBLESHOOT_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are a helpful assistant trained on Setu's product documentation.
Use the following context to help answer questions about Setu's products
for AA json based use below example. 
    If applicable, clearly identify root causes (e.g. FIP_DENIED, data block empty, notification not received) and next steps.
Bharat bill payments SYSTem (BOU), whitelabel app for BOU  (COU), Unified merchant aquring platform (UMAP), Insights, Collect, data  Insights (DI), and Bridge.
If applicable, clearly identify root causes for issues and suggest next steps.
If question references JSON, respond based on parsed meaning.
If you don't know the answer, just say you don't know. Don't make up an answer.

Context:
{context}

Question:
{question}

Answer:
"""
)


def get_conversational_chain(product=None):
    # Get the API key from the config or retrieve it from storage
    api_key = config.OPENAI_API_KEY or retrieve_secret("OPENAI_API_KEY")
    
    if config.VECTORSTORE is None:
        print("Warning: Vectorstore is not initialized")
        return None, feedback_store
        
    if api_key is None:
        print("Warning: OpenAI API key not found")
        return None, feedback_store
        
    print(f"Initializing LLM with API key: {api_key[:5]}...")
    
    llm = ChatOpenAI(model_name="o1", streaming=True, openai_api_key=api_key)

    # Use product-specific retriever if product is provided
    if product:
        print(f"Using product-specific retriever for {product}")
        retriever = get_product_specific_retriever(product)
        if retriever is None:
            print(f"No product-specific retriever available for {product}, using default retriever")
            retriever = config.VECTORSTORE.as_retriever(search_kwargs={"k": 10})
    else:
        retriever = config.VECTORSTORE.as_retriever(search_kwargs={"k": 10})

    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=config.MEMORY,
        return_source_documents=True,
        output_key="answer",
        combine_docs_chain_kwargs={"prompt": TROUBLESHOOT_PROMPT}
    )

    return conversation_chain, feedback_store