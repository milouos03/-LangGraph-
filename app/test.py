from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    text: str


def node_a(state: State):
    return {"text": state["text"] + " -> A"}


def node_b(state: State):
    return {"text": state["text"] + " -> B"}


graph = StateGraph(State)

graph.add_node("a", node_a)
graph.add_node("b", node_b)

graph.add_edge(START, "a")
graph.add_edge("a", "b")
graph.add_edge("b", END)

app = graph.compile()

result = app.invoke({"text": "start"})
print(result)