import unittest

from todo import TodoList


class TodoListTests(unittest.TestCase):
    def test_add_and_complete(self) -> None:
        todos = TodoList()
        todos.add("write report", priority=1)
        todos.add("drink water", priority=3)
        todos.complete(1)
        self.assertEqual(todos.pending(), [{"title": "write report", "priority": 1, "done": False}])

    def test_rejects_invalid_priority(self) -> None:
        todos = TodoList()
        with self.assertRaises(ValueError):
            todos.add("invalid", priority=8)


if __name__ == "__main__":
    unittest.main()

