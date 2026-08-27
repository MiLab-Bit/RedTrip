# redtrip_curator

Curator pipeline: Intent → Evidence → Join → Plan → Narrative → gate_lite.

Narrative is **template-based** in W4 (no LLM). All factual sentences cite EvidencePack sources.

```python
from redtrip_curator import curate
from redtrip_library import SlcClient

result = curate(slots={...}, client=SlcClient())
```
