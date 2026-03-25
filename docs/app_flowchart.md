```mermaid
flowchart TD
    A["Start: streamlit run nl2sql_app.py"] --> B["Load config and DB params"]
    B --> C["Sidebar setup: model catalog, schema scope, vector store discovery, mode, language"]
    C --> D{"Prompt submitted?"}
    D -- "No" --> C
    D -- "Yes" --> E["Append user message to st.session_state.messages"]

    E --> F{"Mode"}

    F -- "Chat" --> G["chat_with_memory(selected model_id, recent history)"]
    G --> H["Render and store assistant text"]

    F -- "SQL" --> I["run_nl_sql(question, selected model_id)"]
    I --> J["Render table/text and optional generated SQL"]
    J --> K{"Explain enabled and rows <= threshold?"}
    K -- "Yes" --> L["explain_sql_result_with_llm(selected model_id)"]
    K -- "No" --> M["Skip explanation"]

    F -- "RAG" --> RA{"Vector stores discovered for selected schemas?"}
    RA -- "No" --> RB["Render schema-scoped ML_RAG error"]
    RA -- "Yes" --> RC["run_ml_rag(question + recent history, selected model_id, options.schema)"]
    RC --> RD["Render answer + optional RAG details"]

    F -- "Auto" --> N{"Router bundle ready?"}
    N -- "No" --> O["Fallback to Chat path"]
    O --> G
    N -- "Yes" --> P["CALL demo.smart_ask(question, @route, @answer)"]

    P --> Q{"Cache hit by question_hash?"}
    Q -- "Yes" --> R["Read ai_router_cache and log cache_hit in ai_router_log"]
    Q -- "No" --> S["Classify with ML_GENERATE (route + confidence)"]
    S --> T{"Confidence < threshold?"}
    T -- "Yes" --> U["Fusion: NL_SQL + ML_RAG + ML_GENERATE synthesis"]
    T -- "No" --> V["Route to SQL / RAG / LLM path"]

    R --> W{"Route"}
    U --> W
    V --> W

    W -- "SQL" --> X["Render SQL result + optional explanation"]
    W -- "RAG / FUSION" --> Y["Render router RAG answer directly"]
    W -- "LLM / fallback" --> ZA["chat_with_memory(selected model_id, router context)"]
    X --> Z["Render feedback buttons: 👍🏻 / 👎🏻"]
    Y --> Z
    ZA --> Z

    Z --> AB["CALL demo.submit_router_feedback(log_id, up/down)"]
    AB --> AC["Trigger updates demo.ai_router_route_metrics"]

    H --> AD["Footer + wait for next prompt"]
    L --> AD
    M --> AD
    J --> AD
    RD --> AD
    RB --> AD
    AC --> AD
```
