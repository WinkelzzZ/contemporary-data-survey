# 基于 MongoDB 的问卷系统

## 一、项目目标

本项目开发了一个简化版的在线问卷系统，功能类似于"问卷星"或 Google Forms。系统允许注册用户创建问卷，通过 URL 分发问卷，其他用户可填写问卷，系统自动统计问卷结果。

### 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 后端框架 | Flask (Python) | 轻量级 Web 框架 |
| 数据库 | MongoDB + pymongo | 文档型数据库 |
| 前端 | Jinja2 + HTML/CSS/JS | 服务端渲染 + 少量 JS |
| 密码安全 | werkzeug | 密码哈希存储 |

---

## 二、系统设计

### 2.1 系统架构

```
用户浏览器
    │
    ▼
Flask Web 服务器
    │
    ├── auth.py        用户认证（注册/登录/登出）
    ├── survey.py      问卷管理（创建/编辑/发布/关闭）
    ├── fill.py        问卷填写（展示/校验/提交）
    └── stats.py       统计结果（聚合计算/展示）
    │
    ▼
MongoDB 数据库
    ├── users          用户集合
    ├── surveys        问卷集合
    ├── questions      题目集合
    └── responses      回复集合
```

### 2.2 功能模块

1. **用户账号模块**：注册、登录、登出，基于 session 的认证
2. **问卷管理模块**：创建问卷、编辑设置、添加/编辑/删除题目、排序、发布/关闭
3. **题目类型模块**：单选题、多选题、文本填空、数字填空
4. **跳转逻辑模块**：根据回答动态跳转到不同题目
5. **校验模块**：必填检查、数量限制、字数限制、数值范围、整数检查
6. **填写模块**：问卷展示、客户端跳转、客户端校验、服务端校验、提交
7. **统计模块**：单选题/多选题选项统计、文本回复列表、数字统计（均值/最值）

---

## 三、MongoDB 数据库设计

### 3.1 集合设计

#### users 集合

```json
{
  "_id": ObjectId("..."),
  "username": "testuser",
  "password_hash": "pbkdf2:sha256:...",
  "created_at": ISODate("2026-10-21T10:00:00Z")
}
```

- `username` 建立唯一索引，保证用户名不重复
- 密码使用 werkzeug 的 `generate_password_hash` 进行哈希存储，不存储明文

#### surveys 集合

```json
{
  "_id": ObjectId("..."),
  "creator_id": ObjectId("..."),
  "title": "用户满意度调查",
  "description": "请填写您的使用体验",
  "allow_anonymous": true,
  "status": "published",
  "deadline": ISODate("2026-12-01T00:00:00Z"),
  "survey_key": "a1b2c3d4",
  "created_at": ISODate("2026-10-21T10:00:00Z"),
  "updated_at": ISODate("2026-10-21T12:00:00Z")
}
```

- `creator_id` 引用 users 集合，建立索引加速查询
- `survey_key` 是 8 位随机字符串，用于生成唯一的问卷链接，建立唯一索引
- `status` 有三种状态：`draft`（草稿）、`published`（已发布）、`closed`（已关闭）
- `deadline` 可为 null，表示不限制截止时间

#### questions 集合

```json
{
  "_id": ObjectId("..."),
  "survey_id": ObjectId("..."),
  "order": 1,
  "type": "single_choice",
  "title": "你的性别",
  "required": true,
  "options": ["男", "女", "其他"],
  "validation": {},
  "jump_rules": [
    {
      "condition_type": "equals",
      "condition_value": "男",
      "target_question_id": "6537..."
    }
  ]
}
```

- `survey_id` + `order` 建立复合唯一索引
- `type` 支持四种类型：`single_choice`、`multiple_choice`、`text_fill`、`number_fill`
- `options` 仅用于选择题类型
- `validation` 根据题目类型存储不同的校验规则：
  - 多选题：`{ "min_select": 2, "max_select": 3 }`
  - 文本填空：`{ "min_length": 10, "max_length": 200 }`
  - 数字填空：`{ "min_value": 0, "max_value": 120, "must_be_integer": true }`
- `jump_rules` 存储跳转规则，每条规则包含条件类型、条件值、目标题目 ID

#### responses 集合

```json
{
  "_id": ObjectId("..."),
  "survey_id": ObjectId("..."),
  "user_id": ObjectId("..."),
  "answers": [
    {
      "question_id": ObjectId("..."),
      "question_order": 1,
      "value": "男"
    },
    {
      "question_id": ObjectId("..."),
      "question_order": 2,
      "value": ["苹果", "香蕉"]
    }
  ],
  "submitted_at": ISODate("2026-10-21T14:00:00Z")
}
```

- `user_id` 可为 null（匿名填写时）
- `answers` 是嵌入文档数组，每个答案包含题目 ID、题目序号和回答值
- `value` 的类型根据题目类型不同：字符串（单选/填空）、字符串数组（多选）

### 3.2 为什么这样设计

#### 为什么使用四个独立集合而非单一集合

将所有数据存在一个集合中会导致文档过大、更新困难。本设计遵循以下原则：

1. **users 独立**：用户是独立实体，与问卷是多对多关系（一个用户可创建多个问卷）
2. **questions 独立于 surveys**：题目需要独立的 CRUD 操作、排序、跳转规则管理。如果嵌入 survey 文档中，每次修改题目都需要更新整个 survey 文档，且题目数量多时文档会过大
3. **responses 独立于 surveys**：一份问卷可能有大量回复，嵌入会导致 survey 文档无限增长。独立存储便于分页查询和聚合统计

#### 为什么 answers 嵌入在 responses 中

每次回复的答案总是作为一个整体被读取和保存，不需要单独查询某个答案。嵌入设计避免了额外的查询开销，符合 MongoDB "一起访问的数据一起存储" 的原则。

#### 为什么不用关系数据库结构

1. **灵活的 Schema**：不同题目类型有不同的校验规则和选项结构，MongoDB 的灵活文档模型天然支持这种异构数据，无需 NULL 列或 EAV 模式
2. **嵌套结构**：跳转规则是嵌套在题目中的变长数组，在关系数据库中需要额外的表和外键，在 MongoDB 中自然表达
3. **读取模式**：统计功能需要读取某问卷的所有回复进行聚合，MongoDB 的文档模型使得一次查询即可获取完整的回复数据
4. **无需复杂 JOIN**：本系统的关联查询很简单（通过 ID 引用），不需要关系数据库的 JOIN 能力

#### 索引设计

| 集合 | 索引 | 类型 | 用途 |
|------|------|------|------|
| users | username | 唯一 | 登录查询、防止重复 |
| surveys | survey_key | 唯一 | 通过链接访问问卷 |
| surveys | creator_id | 普通 | 查询用户创建的问卷 |
| questions | survey_id + order | 复合唯一 | 按顺序获取问卷题目 |
| responses | survey_id | 普通 | 统计时查询回复 |

---

## 四、API 说明

### 4.1 用户认证

| 方法 | 路径 | 说明 | 需要登录 |
|------|------|------|---------|
| GET/POST | `/register` | 注册页面/提交注册 | 否 |
| GET/POST | `/login` | 登录页面/提交登录 | 否 |
| GET | `/logout` | 退出登录 | 否 |

### 4.2 问卷管理

| 方法 | 路径 | 说明 | 需要登录 |
|------|------|------|---------|
| GET | `/dashboard` | 仪表盘（我的问卷列表） | 是 |
| GET/POST | `/survey/create` | 创建问卷页面/提交 | 是 |
| GET | `/survey/<id>/edit` | 编辑问卷页面 | 是（仅创建者） |
| POST | `/survey/<id>/settings` | 更新问卷设置 | 是（仅创建者） |
| POST | `/survey/<id>/publish` | 发布问卷 | 是（仅创建者） |
| POST | `/survey/<id>/close` | 关闭问卷 | 是（仅创建者） |
| POST | `/survey/<id>/question/add` | 添加题目 | 是（仅创建者） |
| POST | `/survey/<id>/question/<qid>/update` | 更新题目 | 是（仅创建者） |
| POST | `/survey/<id>/question/<qid>/delete` | 删除题目 | 是（仅创建者） |
| POST | `/survey/<id>/question/<qid>/move` | 移动题目（上移/下移） | 是（仅创建者） |

### 4.3 问卷填写

| 方法 | 路径 | 说明 | 需要登录 |
|------|------|------|---------|
| GET | `/s/<survey_key>` | 填写问卷页面 | 视问卷设置 |
| POST | `/s/<survey_key>/submit` | 提交问卷 | 视问卷设置 |
| GET | `/s/<survey_key>/thanks` | 提交成功页面 | 否 |

### 4.4 统计

| 方法 | 路径 | 说明 | 需要登录 |
|------|------|------|---------|
| GET | `/survey/<id>/stats` | 查看统计结果 | 是（仅创建者） |

---

## 五、关键逻辑说明

### 5.1 跳转逻辑设计

跳转规则存储在题目的 `jump_rules` 数组中，每条规则包含：

- `condition_type`：条件类型
- `condition_value`：条件值
- `target_question_id`：目标题目 ID

支持的条件类型：

| 条件类型 | 适用题型 | 说明 |
|---------|---------|------|
| `equals` | 单选/数字 | 回答等于指定值 |
| `contains` | 多选/文本 | 回答包含指定值 |
| `greater_than` | 数字 | 回答大于指定值 |
| `less_than` | 数字 | 回答小于指定值 |
| `between` | 数字 | 回答在指定范围内 |

**跳转规则不写死在代码中**，而是存储在数据库的问卷题目中，创建者可以在编辑问卷时自由设置。

**客户端实现**（fill_survey.html 中的 JavaScript）：

1. 页面加载时，将所有题目数据（包括跳转规则）传递给 JavaScript
2. 每次用户改变答案时，触发 `evaluateJumps()` 函数
3. 该函数遍历所有题目的跳转规则，检查当前答案是否匹配条件
4. 如果匹配，隐藏当前题目和目标题目之间的所有题目
5. 如果不匹配，恢复显示所有题目
6. 提交时，只发送可见题目的答案

**服务端实现**（fill.py）：

提交时通过 `visible_questions` 字段告知服务器哪些题目是可见的，服务器只验证和保存可见题目的答案。

### 5.2 校验逻辑设计

校验在客户端和服务端双重执行：

**客户端校验**（JavaScript，在 fill_survey.html 中）：
- 提交前检查所有可见题目的答案
- 实时显示错误提示
- 阻止无效提交

**服务端校验**（Python，在 fill.py 的 `_validate_answer` 函数中）：
- 作为安全兜底，防止绕过客户端校验
- 校验规则：
  - 必填题：检查答案是否为空
  - 单选题：检查选项是否有效
  - 多选题：检查选项有效性 + 数量限制（min_select / max_select）
  - 文本填空：检查字数限制（min_length / max_length）
  - 数字填空：检查数值格式 + 整数要求 + 范围限制（min_value / max_value）

### 5.3 统计逻辑设计

统计功能在 stats.py 中实现，按题目类型分别处理：

- **单选题**：统计每个选项的选择人数和占比，生成柱状图
- **多选题**：统计每个选项被选择的次数和占比
- **文本填空**：列出所有填写内容
- **数字填空**：计算平均值、最小值、最大值，列出所有数值

统计通过遍历所有回复的 answers 数组实现，利用 MongoDB 的文档模型，一次查询即可获取所有回复数据。

---

## 六、运行说明

### 6.1 环境要求

- Python 3.8+
- MongoDB 4.0+

### 6.2 安装步骤

```bash
# 进入项目目录
cd survey-system

# 安装依赖
pip install -r requirements.txt

# 确保 MongoDB 正在运行
# 默认连接 mongodb://localhost:27017

# 启动应用
python app.py
```

访问 http://localhost:5000 即可使用。

### 6.3 配置说明

通过环境变量或修改 `config.py` 配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB 连接地址 |
| `DB_NAME` | `survey_system` | 数据库名称 |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Flask session 密钥 |

---

## 七、测试用例

### 7.1 运行测试

```bash
# 确保 MongoDB 正在运行
python test_api.py
```

### 7.2 测试覆盖

| 测试类别 | 测试用例 | 说明 |
|---------|---------|------|
| 创建问卷 | test_create_survey | 正常创建问卷 |
| 创建问卷 | test_create_survey_without_title | 无标题被拒绝 |
| 添加题目 | test_add_single_choice_question | 添加单选题 |
| 添加题目 | test_add_multiple_choice_question | 添加多选题（含数量限制） |
| 添加题目 | test_add_text_fill_question | 添加文本填空（含字数限制） |
| 添加题目 | test_add_number_fill_question | 添加数字填空（含范围限制） |
| 添加题目 | test_add_multiple_questions_order | 多题顺序正确 |
| 跳转逻辑 | test_jump_logic_single_choice | 单选题跳转规则 |
| 跳转逻辑 | test_jump_logic_number_fill | 数字填空跳转规则 |
| 校验 | test_validation_required_single_choice | 必填校验 |
| 校验 | test_validation_number_range | 数字范围校验 |
| 校验 | test_validation_multiple_choice_count | 多选数量校验 |
| 校验 | test_validation_text_length | 文本长度校验 |
| 提交 | test_submit_survey_success | 正常提交 |
| 提交 | test_submit_multiple_responses | 多次提交 |
| 提交 | test_submit_closed_survey | 关闭问卷不可访问 |
| 统计 | test_statistics_single_choice | 单选题统计 |
| 统计 | test_statistics_number_fill | 数字统计 |
| 统计 | test_statistics_multiple_choice | 多选题统计 |
| 认证 | test_user_registration | 用户注册 |
| 认证 | test_duplicate_username | 重复用户名 |
| 认证 | test_dashboard_shows_own_surveys | 只看自己的问卷 |

---

## 八、AI 使用过程说明

### 8.1 AI 使用日志

#### 1. 数据库 Schema 结构生成

**工具**：Claude

**Prompt**：
> 请帮我生成 MongoDB 问卷系统的集合 JSON 结构示例，需要支持用户、问卷、四种题型（单选/多选/文本填空/数字填空）、跳转规则、校验规则。

**AI 返回**：四个集合（users、surveys、questions、responses）的 JSON 结构骨架。

**我的修改**：
- 增加 `survey_key` 字段（AI 未考虑唯一链接需求）
- 跳转目标从 `target_order` 改为 `target_question_id`（AI 的方案在题目重排序时会失效）
- 增加 `validation` 子文档，按题型分类存储校验规则（AI 将校验字段平铺在题目中）

#### 2. 跳转逻辑 JavaScript 代码

**工具**：Claude

**Prompt**：
> 请帮我写前端 JavaScript，实现根据跳转规则动态显示/隐藏问卷题目。跳转规则存储在题目的 jump_rules 数组中。

**AI 返回**：`evaluateJumps()` 和 `evaluateCondition()` 函数的基本实现。

**我的修改**：
- 增加 `updateVisibleQuestions()` 函数，将可见题目 ID 同步到隐藏字段（AI 未考虑前后端联动）
- 修复多选题的条件判断逻辑（AI 的实现存在遗漏）

#### 3. 统计功能 Python 代码

**工具**：Claude

**Prompt**：
> 请帮我写一个 Python 函数，根据题目类型分别统计单选题选项计数、多选题选项计数、文本回复列表、数字统计（均值/最值）。

**AI 返回**：`_compute_question_stats()` 函数的基本实现。

**我的修改**：
- 增加 `answered` 计数，区分"实际回答人数"和"总回复数"（AI 只统计了 total）
- 修复多选题的数组处理（AI 未考虑 value 可能不是列表的边界情况）

#### 4. CSS 样式生成

**工具**：Claude

**Prompt**：
> 请帮我设计问卷系统的 CSS 样式，要求简洁现代。

**AI 返回**：约 300 行 CSS 代码。

**我的修改**：
- 调整主色调（蓝色 → indigo）
- 修复一处语法错误（`font font-size` 重复）

#### 5. 内网穿透尝试

尝试使用 ngrok 进行内网穿透以实现公网访问，完成了 authtoken 配置和隧道建立，但因配置问题最终放弃该方案。

### 8.2 AI 使用说明

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

---

## 九、遇到的问题与解决方案

### 问题 1：跳转规则引用失效

**问题描述**：最初跳转规则使用题目 order 作为目标，当题目被删除或重排序后，跳转目标可能指向错误的题目。

**解决方案**：改为使用 `question_id` 作为跳转目标。在渲染页面时，通过 `question_id → order` 的映射表解析实际的目标位置。删除题目时，使用 `$pull` 操作清理所有引用该题目的跳转规则。

### 问题 2：跳转逻辑的前后端同步

**问题描述**：客户端 JavaScript 负责动态显示/隐藏题目，但服务端需要知道哪些题目是可见的，才能正确校验和保存答案。

**解决方案**：在表单中增加隐藏字段 `visible_questions`，JavaScript 在每次跳转评估后更新该字段的值（逗号分隔的可见题目 ID 列表）。提交时，服务端只处理在该列表中的题目。

### 问题 3：多选题的值类型处理

**问题描述**：多选题的答案是数组，但在某些边界情况下（只选一项或未选），值可能不是数组类型。

**解决方案**：在服务端校验和统计代码中，统一将值转换为数组处理：`if not isinstance(value, list): value = [value] if value else []`
