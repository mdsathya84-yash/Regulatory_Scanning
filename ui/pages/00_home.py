import streamlit as st

st.title("RegScan — AI Regulatory Intelligence Platform")
st.markdown(
    """
    Welcome to **RegScan**, an AI-powered regulatory monitoring and Q&A system.

    ### Features
    | Page | Description |
    |------|-------------|
    | **Chatbot** | Ask natural-language regulatory questions backed by RAG |
    | **Register** | Browse and search the live Compliance Obligation Register |

    ### Quick Start
    1. Set your `GROQ_API_KEY` in `.env`
    2. Run `python -m scraper.scheduler` to populate the vector store
    3. Navigate to the **Chatbot** page to start querying

    ---
    *Monitoring: NCSC (UK) · EEAS (EU Sanctions) · Ofcom (UK) · European Commission (EU)*
    """
)
