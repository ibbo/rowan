#!/usr/bin/env python3
"""
Visualize the SCD Agent graph structure.
Requires: pip install graphviz (and system graphviz package)
"""

from scd_agent import SCDAgent
from dotenv import load_dotenv


def main():
    """Generate and save the graph visualization."""
    load_dotenv()
    
    print("Creating SCD Agent...")
    agent = SCDAgent()
    
    print("Generating graph visualization...")
    
    try:
        # Get the graph
        graph = agent.graph
        
        # Try to generate a visual representation
        # This requires the graphviz library and system package
        try:
            from IPython.display import Image, display
            display(Image(graph.get_graph().draw_mermaid_png()))
            print("✅ Graph displayed (Jupyter environment)")
        except ImportError:
            # Save as mermaid diagram
            mermaid = graph.get_graph().draw_mermaid()
            with open("scd_agent_graph.mmd", "w") as f:
                f.write(mermaid)
            print("✅ Mermaid diagram saved to: scd_agent_graph.mmd")
            print("\nYou can visualize it at: https://mermaid.live/")
            print("\nOr install graphviz:")
            print("  sudo apt-get install graphviz")
            print("  pip install graphviz")
    
    except Exception as e:
        print(f"❌ Error generating visualization: {e}")
        print("\nGraph structure:")
        print("  START → prompt_checker")
        print("  prompt_checker → [dance_planner | rejection_handler]")
        print("  dance_planner → [tool_executor | END]")
        print("  tool_executor → dance_planner (loop)")
        print("  rejection_handler → END")


if __name__ == "__main__":
    main()
