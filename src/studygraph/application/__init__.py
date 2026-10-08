"""应用层：用例编排。

- `ports.py`  对外部世界的抽象（Protocol）。
- `question_writer.py`  "让模型写题、失败回退模板"这条编排。
- `learning_service.py` 学习闭环用例（错题/出题/复习/记忆/规划）。
- `state.py` / `routing.py` / `tools.py` / `graph.py`  Agent 回合的编排（LangGraph）。
"""
