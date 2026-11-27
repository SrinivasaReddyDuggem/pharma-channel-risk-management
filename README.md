# pharma-channel-risk-management
pharmaceutical channel Risk Management

# Project Sankalp pilot: starter

An optional skeleton for the recommended path. It already deploys to Vercel: a FastAPI backend, a LangGraph tool loop and a
plain HTML page. It proves your pipeline works on day one. Replace the graph, the tools and
the page with your own design.

```
app.py            FastAPI entrypoint (Vercel looks for `app` here)
agent/llm.py      the only file that knows the model provider (OpenRouter)
agent/tools.py    tools that read data/; exact facts come from here
agent/graph.py    the LangGraph graph; replace it with yours
data/             put the four CSVs from the data pack here
public/           index.html, app.js, style.css: the frontend
tests/            run with pytest; no API key needed
AGENTS.md         instructions for your AI coding agent
```

## Run it on your laptop

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt uvicorn pytest httpx
cp .env.example .env               # then put your OpenRouter key in .env
pytest -q
streamlit run streamlit_app.py
```

Streamlit opens the risk analysis page in your browser. Select shortage, expiry, or
oversupply risk and submit to view the result table.

To run the optional FastAPI service, use `uvicorn app:app --reload`.

## Deploy

Follow the step-by-step section in the Build and Deploy Guide. In short: push to GitHub,
import the repository in Vercel, add `OPENROUTER_API_KEY` as an environment variable, deploy.

To Run the Application : 

python -m streamlit run streamlit_app.py

stream Lit app : URL : https://pharma-channel-risk-management-hrqcwknatvkfnrgqhrkkuj.streamlit.app/