"""Generates a Mermaid diagram for the chat graph's single, fixed topology using
LangGraph's built-in get_graph().draw_mermaid() introspection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.chat_api.graph.builder import build_chat_graph


class _DummyOrchestrator:
    """build_nodes() only closes over this; node bodies never run here."""
    pass


def main():
    orchestrator = _DummyOrchestrator()
    out_dir = Path(__file__).resolve().parents[1] / "docs" / "diagrams"
    out_dir.mkdir(parents=True, exist_ok=True)

    compiled = build_chat_graph(orchestrator)
    mermaid = compiled.get_graph(xray=True).draw_mermaid()

    out_file = out_dir / "chat_graph.mmd"
    out_file.write_text(mermaid, encoding="utf-8")

    print(mermaid)
    print(f"saved -> {out_file}\n")


if __name__ == "__main__":
    main()
