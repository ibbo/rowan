# SCD Agent - Multi-Agent Architecture

## Overview

The new `scd_agent.py` implements a **multi-agent LangGraph architecture** with two specialized agents:

1. **Prompt Checker Agent**: Validates incoming queries for Scottish Country Dance relevance
2. **Dance Planner Agent**: Processes valid queries using database tools

## Architecture

```
┌─────────────┐
│   START     │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Prompt Checker  │ ◄── Validates query relevance
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌──────────────┐
│ Reject │  │ Dance Planner│ ◄── Plans response with tools
└───┬────┘  └──────┬───────┘
    │              │
    │         ┌────┴────┐
    │         │         │
    │         ▼         ▼
    │    ┌────────┐  ┌─────┐
    │    │ Tools  │  │ END │
    │    └───┬────┘  └─────┘
    │        │
    │        └──────┐
    │               │
    ▼               ▼
┌─────────────────────┐
│  Rejection Handler  │
└──────────┬──────────┘
           │
           ▼
       ┌───────┐
       │  END  │
       └───────┘
```

## Key Features

### 1. Prompt Checker Node
- **Purpose**: Filter out non-SCD queries before expensive tool calls
- **Method**: Uses GPT-4o-mini to classify queries as ACCEPT/REJECT
- **Benefits**: 
  - Prevents wasted API calls
  - Provides clear user feedback for off-topic queries
  - Maintains focus on Scottish Country Dancing

### 2. Dance Planner Node
- **Purpose**: Process valid SCD queries using database tools
- **Tools Available**:
  - `find_dances`: Search by name, type, formation, bars, RSCDS status
  - `get_dance_detail`: Get full dance information including crib
  - `search_cribs`: Full-text search of dance instructions
- **Features**:
  - Automatic tool selection based on query
  - Multi-step reasoning with tool chaining
  - Conversation memory via checkpointer

### 3. Tool Executor Node
- **Purpose**: Execute tool calls asynchronously
- **Features**:
  - Parallel tool execution support
  - Error handling per tool
  - Results fed back to Dance Planner

### 4. Rejection Handler Node
- **Purpose**: Provide polite rejection for off-topic queries
- **Response**: Guides users back to SCD topics

## State Management

```python
class State(TypedDict):
    messages: Annotated[list, add_messages]  # Conversation history
    is_scd_query: bool                        # Validation result
    route: str                                # Routing decision
```

## Usage

### Interactive Mode

```bash
export OPENAI_API_KEY="your-key-here"
uv run scd_agent.py
```

### Programmatic Usage

```python
from scd_agent import SCDAgent
import asyncio

async def main():
    agent = SCDAgent()
    config = {"configurable": {"thread_id": "my_session"}}
    
    result = await agent.ainvoke("Find me some 32-bar reels", config)
    print(result["messages"][-1].content)

asyncio.run(main())
```

### Testing

```bash
uv run test_scd_agent.py
```

## Comparison with Original Agent

| Feature | Original (`dance_agent.py`) | New (`scd_agent.py`) |
|---------|----------------------------|----------------------|
| Architecture | Single ReAct agent | Multi-agent graph |
| Prompt Validation | Pre-model hook (regex) | Dedicated LLM agent |
| Tool Execution | Built-in ReAct | Custom async executor |
| Routing | Linear | Conditional branching |
| Extensibility | Limited | Highly modular |
| Debugging | Harder to trace | Clear node boundaries |

## Benefits of Multi-Agent Architecture

1. **Separation of Concerns**: Each agent has a single responsibility
2. **Better Observability**: Clear logging at each node
3. **Easier Testing**: Can test nodes independently
4. **Flexible Routing**: Conditional edges enable complex workflows
5. **Scalability**: Easy to add new agents/nodes (e.g., response formatter, caching layer)

## Future Enhancements

Potential additions to the graph:

- **Response Formatter Node**: Format dance information beautifully
- **Caching Node**: Cache frequent queries
- **Feedback Collector**: Learn from user interactions
- **Multi-Query Planner**: Handle complex multi-part questions
- **Dance Programme Builder**: Specialized agent for programme planning

## Dependencies

- `langgraph`: Graph-based agent framework
- `langchain-openai`: OpenAI LLM integration
- `langchain-core`: Core LangChain components
- `dance_tools`: MCP-based database tools
- `python-dotenv`: Environment variable management

## Configuration

Environment variables:
- `OPENAI_API_KEY`: Required for LLM access
- `SCDDB_SQLITE`: Path to dance database (default: `data/scddb/scddb.sqlite`)
- `SCDDB_LOG_LEVEL`: Logging level (default: `WARNING`)

## Performance Considerations

- **Prompt Checker**: Fast (~200-500ms) - prevents expensive tool calls
- **Tool Executor**: Async execution with connection pooling
- **Checkpointer**: In-memory for development, can use Redis/Postgres for production
- **LLM Calls**: Using `gpt-4o-mini` for cost-effectiveness

## Debugging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Each node prints status to stderr:
- 🔍 Prompt Checker
- 🎯 Dance Planner
- 🔧 Tool Executor
- ❌ Rejection Handler

## License

Same as parent project.
