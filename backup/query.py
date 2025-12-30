from dotenv import load_dotenv
load_dotenv()

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

DB_FAISS_PATH = "vectorstore/db_faiss"

def ask_question(query):
    # Embeddings
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # Load vector DB
    db = FAISS.load_local(
    DB_FAISS_PATH,
    embeddings,
    allow_dangerous_deserialization=True
)


    retriever = db.as_retriever(search_kwargs={"k": 3})

    # LLM
    llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0
)

    # Prompt
    prompt = ChatPromptTemplate.from_template(
        """
        Answer the question using ONLY the context below.
        If the answer is not in the context, say "I don't know".

        Context:
        {context}

        Question:
        {question}
        """
    )

    # LCEL Chain
    chain = (
        {
            "context": retriever,
            "question": RunnablePassthrough()
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    result = chain.invoke(query)
    print("\n🤖 Answer:\n", result)

if __name__ == "__main__":
    while True:
        q = input("\nAsk a question (type 'exit' to quit): ")
        if q.lower() == "exit":
            break
        ask_question(q)
