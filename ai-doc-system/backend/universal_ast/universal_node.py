from dataclasses import dataclass


@dataclass
class UniversalNode:

    node_type: str

    name: str

    language: str

    semantic_role: str

    line: int