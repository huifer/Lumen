---
name: python-store-or-falsy-len-trap
description: 自定义类实现 __len__ 后，`obj or Default()` 会在空对象时静默丢弃传入实例——必须用 `is None` 判空
type: gotcha
---

# `store or IndexStore()` 在定义了 `__len__` 的类上是陷阱

## Why

`IndexStore` 实现了 `__len__`（返回记录条数）→ 空索引时 `bool(store) is False` →
`store = store or IndexStore()` 会**丢弃调用方传入的实例**，新建一个空 store。
症状：API 明明 build 成功、磁盘也有 index.json，但 `/api/health` 的 `indexed_files` 一直是 0，
`/api/thumb` 报 403「该文件不在索引内」，而 `/api/search` 正常（因为它每次 `store.load()` 从磁盘兜底）。

## How to apply

- 任何"可为空"的自定义容器对象（定义了 `__len__`/`__bool__`）都不要用 `or` 做默认值，改用：
  ```python
  if store is None:
      store = IndexStore()
  ```
- 排查同类症状的顺序：先确认"写入用的对象"和"读取用的对象"是不是同一个实例，再看落盘是否成功。

## Related

- [[gdg-dev-lumen-demo]]
