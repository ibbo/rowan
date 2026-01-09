#!/usr/bin/env python3
"""Test the agent with skip change of step query."""

import asyncio
from dotenv import load_dotenv

async def test_agent():
    """Test the agent directly."""
    
    # Import after loading env
    load_dotenv()
    
    # Check which database is being loaded
    from dance_tools import _load_manual_vectorstore
    
    print("="*80)
    print("CHECKING WHICH DATABASE IS LOADED")
    print("="*80)
    
    # Force reload
    from dance_tools import _manual_vectorstore
    import dance_tools
    dance_tools._manual_vectorstore = None  # Clear cache
    
    vectorstore = _load_manual_vectorstore()
    
    if vectorstore:
        # Check a sample document
        sample_docs = vectorstore._collection.get(limit=5, include=['metadatas'])
        
        print(f"\nDatabase loaded successfully")
        print(f"Sample metadata from first doc:")
        if sample_docs['metadatas']:
            import json
            print(json.dumps(sample_docs['metadatas'][0], indent=2))
    
    print("\n" + "="*80)
    print("TESTING AGENT WITH SKIP CHANGE OF STEP")
    print("="*80)
    
    try:
        from scd_agent import SCDAgent
        
        agent = SCDAgent()
        
        result = await agent.ainvoke(
            {"messages": [("user", "how to teach skip change of step")]},
            config={"configurable": {"thread_id": "test_thread"}}
        )
        
        final_message = result["messages"][-1].content
        
        print("\nAGENT RESPONSE:")
        print(final_message)
        
        # Check if it mentions pas de basque incorrectly
        if "pas de basque" in final_message.lower() and "skip change" not in final_message.lower():
            print("\n⚠️  ERROR: Agent returned pas de basque instead of skip change of step!")
        elif "skip change" in final_message.lower():
            print("\n✅ Agent correctly mentions skip change of step")
        
    except Exception as e:
        print(f"\n❌ Error testing agent: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent())
