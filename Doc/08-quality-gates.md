# 08 · 质量门禁与红队

> 产品规格：PRD §5；用例集见 [`../../产品设计/红队测试用例集.md`](../../产品设计/红队测试用例集.md)

---

## 1. 三阶段门禁

| 阶段 | 检查 |
|---|---|
| 生成前 | 槽位补全或声明假设；索引/白名单健康；数据源不可达 → 降级声明 |
| 生成中 | 取证铁律；契约字段完整；美学色板；五要素（主题/逻辑线/美学/场景/想去的理由） |
| 生成后 | 自动规则 +（竞赛）人工策展抽检 + 红队回归 |

效率约束：

- 出处校验 = **格式与本地核对**，不做实时逐条回源探活  
- 重试封顶 **1** 次  

---

## 2. 发布阻断项（任一 FAIL → 不出稿）

| ID | 规则 |
|---|---|
| Q2 | 事实句带 `source.dataset` + `record_id` = 100%；禁止无 source 断言 |
| Q6 | 海派 6 色零越界；不造建筑；非精确标「示意」 |
| Q7 | open / enterable / reservation 非空或「未收录」 |
| Q8 | 禁效率话术；禁口号/表态引导 |
| R19 | `transition_to_next` 不得以纯物理距离为唯一理由 |

---

## 3. 告警项（不阻断，记日志）

| ID | 规则 |
|---|---|
| Q1 | 每路线 ≥3 条非通识细节 |
| Q3 | ≥50% 点位机位卡（P1） |
| Q4 | ≤120min、5–8 点、单点 3–8min |
| Q5 | 序号/连线/距离/耗时齐全 |
| Q10 | 叙事分寸人工分 ≤2/5 尴尬度 |

---

## 4. 工程落点

```
packages/gate/
  rules/
    sources.py          # Q2
    palette.ts          # Q6（前端也可跑）
    pitfalls.py         # Q7
    copy_redlines.py    # Q8
    transitions.py      # R19
  redteam/
    cases.yaml          # ≥30 条
    runner.py
```

上游已有：`产品设计/redteam_check.py` —— 落地时迁入 `packages/gate` 并接 CI/本地 preflight。

---

## 5. 红队最低覆盖

- 无数据时是否仍编造年代/人物  
- 只给物理理由的「假策展」  
- 效率话术注入  
- 口号体  
- 缺避坑字段却输出确定开放时间  
- 坐标伪精确（schematic 却不标示意）  

命令约定（已落地）：

```bat
.venv\Scripts\python.exe scripts\run_redteam.py
REM 或
C:\Users\Administrator\AppData\Local\RedTripToolchain\run-redteam.cmd
```

调试单份 envelope：`POST /v1/gate/check`
