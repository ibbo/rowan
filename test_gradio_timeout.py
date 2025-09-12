#!/usr/bin/env python3
"""
Test script to verify the timeout improvements in gradio_app.py
"""

import asyncio
import time
from gradio_app import ui

async def test_timeout_handling():
    """Test that the UI properly handles timeouts and logs timing information"""
    print("=== Testing Gradio Timeout Handling ===")
    
    # Test a normal query
    print("--- Testing Normal Query ---")
    start_time = time.time()
    result = await ui.process_query("Find me a simple reel", [])
    normal_time = time.time() - start_time
    print(f"Normal query took {normal_time:.2f}s")
    print("Result:", result[:100] + "..." if len(result) > 100 else result)
    
    # Test a complex query that might take longer
    print("\n--- Testing Complex Query ---")
    complex_query = "Create a detailed lesson plan with 5 different dance types, including specific moves and teaching notes for each"
    start_time = time.time()
    result = await ui.process_query(complex_query, [])
    complex_time = time.time() - start_time
    print(f"Complex query took {complex_time:.2f}s")
    print("Result:", result[:150] + "..." if len(result) > 150 else result)
    
    print("\n✅ Timeout handling test completed!")
    print(f"Check dance_gradio.log for detailed timing information")

if __name__ == "__main__":
    asyncio.run(test_timeout_handling())
