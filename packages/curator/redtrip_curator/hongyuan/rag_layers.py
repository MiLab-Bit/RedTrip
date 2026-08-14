"""三层 Agentic RAG（冻结规则）。

L1 Evidence RAG — 馆藏取证（claims / sources）；史实唯一来源；Gate 终审。
L2 Lexicon lottery — 红鸢静态词库抽签（情绪/风格/叙事/延伸/节奏）；受时长·调性·同行约束。
L3 Hotword RAG — 小红书上海周热词，景点优先检索；每周二更新；只润色当代口吻。

L2 / L3 均不得发明史实；失败回退模板叙事。
"""

LAYER_NAMES = ("evidence", "lexicon", "hotwords")
