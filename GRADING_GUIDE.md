# 自动批改系统使用指南

## 项目结构

```
coursezju.auto/
├── main.py                 # 主入口，协调整个批改流程
├── grading_config.py       # 评分配置和 Prompt 模板
├── llm_grader.py          # LLM 评分模块，调用 OpenAI API
├── submission_scraper.py   # 提交内容爬取模块
├── config.toml            # 配置文件
├── assignment_template.md  # 作业要求模板
└── GRADING_GUIDE.md       # 使用文档
```

## 快速开始

### 1. 配置 API Key

设置环境变量（推荐）：
```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-..."

# Windows CMD
set OPENAI_API_KEY=sk-...

# Linux/Mac
export OPENAI_API_KEY="sk-..."
```

或在 `config.toml` 中添加：
```toml
[grading]
openai_api_key = "sk-..."
```

### 2. 准备作业要求

脚本会从课程页面自动提取作业要求。如果自动提取失败，可以：

**方式 A：手动提供作业要求文件**

1. 复制 `assignment_template.md` 为 `assignment_requirements.md`
2. 填写具体的作业要求内容
3. 在 `config.toml` 中指定文件路径：
```toml
[grading]
assignment_requirements_file = "assignment_requirements.md"
```

**方式 B：运行时手动输入**

如果页面无法提取作业要求，脚本会提示你手动输入。

### 3. 运行脚本

```bash
# 使用 uv（推荐）
uv run python main.py

# 或使用普通 Python
python main.py
```

### 4. 工作流程

1. 脚本自动登录课程网站
2. 导航到课程页面
3. **自动提取作业要求**（从页面或文件）
4. 导航到批改页面（教师视角）
5. **自动提取学生提交内容**：
   - 从列表页面批量提取（首选）
   - 如果失败，提示用户提供提交详情页 URL
   - 逐个访问提交详情页提取
6. 调用 LLM 进行批改
7. 保存结果到 `grading_results/` 目录

## 学生作业内容获取说明

脚本通过以下方式获取学生提交的作业内容：

### 方式 1：从批改列表页面批量提取（首选）

脚本会尝试从教师批改列表页面直接提取所有学生的提交内容。

**页面特征：**
- URL 包含 `/homework/xxx/submissions` 或类似路径
- 页面显示所有学生提交列表
- 每个提交项包含学生姓名、学号、提交内容

**提取逻辑：**
1. 查找 `.submission-item` 或 `.homework-row` 元素
2. 从 `.homework-content .comment-area` 提取提交文本
3. 从附件区域提取附件文件名

### 方式 2：从单个提交详情页提取

如果列表页面无法提取内容，脚本会提示你访问每个学生的提交详情页。

**操作步骤：**
1. 在批改列表中点击某个学生姓名
2. 页面跳转到该学生的提交详情页
3. 脚本自动提取内容后提示继续下一个

### 方式 3：手动提供提交 URL

如果自动提取都失败，可以手动收集所有提交的 URL：

```
请输入提交 URL，每行一个（空行结束）：
https://courses.zju.edu.cn/course/96393/homework/123/submissions/456
https://courses.zju.edu.cn/course/96393/homework/123/submissions/457
...
（空行）
```

## 配置说明

### config.toml

```toml
[account]
username = "你的学号"
password = "你的密码"

[course]
url = "课程 URL"

[grading]
model_name = "gpt-4o-mini"  # 使用的模型
max_tokens = 2000            # 最大输出长度
temperature = 0.3            # 创造性程度（0-1）

# 可选：直接配置作业 URL
assignment_url = "作业页面 URL"
submissions_url = "提交列表 URL"

# 可选：作业要求文件路径
assignment_requirements_file = "assignment_requirements.md"

[grading.criteria]
total_points = 100
dimensions = ["correctness", "completeness", "creativity", "formatting"]
```

## 输出结果

批改结果保存在 `grading_results/` 目录：

- `{assignment_name}_{timestamp}.json` - 详细评分结果（JSON 格式）
- `{assignment_name}_{timestamp}_summary.csv` - 评分汇总（CSV 格式）

### JSON 输出示例

```json
{
  "12521280": {
    "total_score": 85,
    "dimensions": {
      "correctness": {"score": 35, "comment": "大部分答案正确"},
      "completeness": {"score": 25, "comment": "完成了所有必做题"},
      "creativity": {"score": 15, "comment": "有一定的创新思考"},
      "formatting": {"score": 10, "comment": "格式规范"}
    },
    "overall_comment": "整体表现良好，继续保持！",
    "strengths": ["代码结构清晰", "注释完整"],
    "improvements": ["可以增加更多测试用例", "部分算法可以优化"]
  }
}
```

## 自定义 Prompt

如需自定义评分 Prompt，在 `config.toml` 中添加：

```toml
[grading.prompt]
system_prompt = """
你是一位经验丰富的课程助教。请根据以下标准评分：
1. 严格但公平
2. 给出具体反馈
3. 鼓励学生进步
"""

user_prompt_template = """
## 作业要求
{assignment_requirements}

## 评分标准
总分：{total_points}分
维度：{dimensions}

## 学生提交
{submission_content}

请评分并给出详细反馈。
"""
```

## 注意事项

1. **API 费用**：使用 OpenAI API 会产生费用，请注意控制使用量
2. **页面结构**：如果课程网站页面结构变化，可能需要更新 `submission_scraper.py` 中的选择器
3. **批量批改**：大量学生时建议设置 `delay_between_requests` 避免 API 限流
4. **隐私保护**：不要将学生数据上传到公共模型

## 故障排除

### 无法提取作业要求
- 检查页面是否完全加载
- 手动复制作业要求到 `assignment_requirements.md` 文件

### 无法找到学生提交
- 确认已导航到正确的提交列表页面（教师视角）
- 检查网页结构是否变化
- 尝试手动提供提交详情页 URL

### API 调用失败
- 检查 API Key 是否正确
- 确认网络连接正常
- 查看 `grading.log` 获取详细错误信息
