"""基础设施层：端口的具体实现（适配器）。

这里才允许 import 具体技术：SQLite、OpenAI SDK、pypdf 等。上层（应用/领域）
只认识 `application/ports.py` 里的 Protocol，换实现不用改业务代码。
"""
