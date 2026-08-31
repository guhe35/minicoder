"""Small project prepared for the final agent demonstration."""

from __future__ import annotations


class TodoList:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    def add(self, title: str, priority: int = 2) -> None:
        if not title.strip():
            raise ValueError("title must not be empty")
        if priority not in {1, 2, 3}:
            raise ValueError("priority must be 1, 2, or 3")
        self.items.append({"title": title.strip(), "priority": priority, "done": False})

    def complete(self, index: int) -> None:
        self.items[index]["done"] = True

    def pending(self) -> list[dict[str, object]]:
        return [item.copy() for item in self.items if not item["done"]]

