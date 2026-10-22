# AI 使用日志

## 概述

本项目开发过程中使用了 AI 编程工具辅助完成部分代码编写。使用的工具包括 **Claude**（对话式编程助手）和 **Qoder**（IDE 集成工具）。

---

## AI 使用记录

### 1. 数据库 Schema 结构生成

**工具**：Claude

**Prompt**：
> 请帮我生成 MongoDB 问卷系统的集合 JSON 结构示例，需要支持用户、问卷、四种题型（单选/多选/文本填空/数字填空）、跳转规则、校验规则。

**AI 返回**：四个集合（users、surveys、questions、responses）的 JSON 结构骨架。

**我的修改**：
- 增加 `survey_key` 字段（AI 未考虑唯一链接需求）
- 跳转目标从 `target_order` 改为 `target_question_id`（AI 的方案在题目重排序时会失效）
- 增加 `validation` 子文档，按题型分类存储校验规则（AI 将校验字段平铺在题目中）

### 2. 跳转逻辑 JavaScript 代码

**工具**：Claude

**Prompt**：
> 请帮我写前端 JavaScript，实现根据跳转规则动态显示/隐藏问卷题目。跳转规则存储在题目的 jump_rules 数组中。

**AI 返回**：`evaluateJumps()` 和 `evaluateCondition()` 函数的基本实现。

**我的修改**：
- 增加 `updateVisibleQuestions()` 函数，将可见题目 ID 同步到隐藏字段（AI 未考虑前后端联动）
- 修复多选题的条件判断逻辑（AI 的实现存在遗漏）

### 3. 统计功能 Python 代码

**工具**：Claude

**Prompt**：
> 请帮我写一个 Python 函数，根据题目类型分别统计单选题选项计数、多选题选项计数、文本回复列表、数字统计（均值/最值）。

**AI 返回**：`_compute_question_stats()` 函数的基本实现。

**我的修改**：
- 增加 `answered` 计数，区分"实际回答人数"和"总回复数"（AI 只统计了 total）
- 修复多选题的数组处理（AI 未考虑 value 可能不是列表的边界情况）

### 4. CSS 样式生成

**工具**：Claude

**Prompt**：
> 请帮我设计问卷系统的 CSS 样式，要求简洁现代。

**AI 返回**：约 300 行 CSS 代码。

**我的修改**：
- 调整主色调（蓝色 → indigo）
- 修复一处语法错误（`font font-size` 重复）

### 5. 内网穿透尝试

尝试使用 ngrok 进行内网穿透以实现公网访问，完成了 authtoken 配置和隧道建立，但因配置问题最终放弃该方案。

---

## AI 使用说明

**AI 帮了什么**：
- 快速生成了数据库 Schema 的 JSON 结构骨架
- 填充了 JavaScript 跳转逻辑和 Python 统计函数的具体代码
- 生成了 CSS 样式的初始版本

**AI 做错了什么**：
- 跳转规则使用 order 作为目标引用，重排序时会导致规则失效
- CSS 存在一处语法错误
- 统计函数未区分"回答人数"和"总回复数"
- 未考虑前后端联动机制（visible_questions）

**自己改了什么**：
- 将跳转目标从 order 改为 question_id
- 修复 CSS 语法错误
- 增加 answered 计数和边界处理
- 增加 visible_questions 前后端联动机制
- 增加删除题目时的级联清理逻辑

**自己设计了什么**：
- 整体系统架构和模块划分
- 数据库集合划分和索引设计
- 跳转规则的 ID 引用方案
- visible_questions 前后端联动机制
- 问卷状态机（draft → published → closed）
- 权限控制逻辑
- 答题时长统计和最大回复数限制功能
