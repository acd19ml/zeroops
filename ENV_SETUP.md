# 环境变量设置指南

## 概述

ZeroOps 项目需要配置 API 密钥来使用 AI 模型。本文档说明如何正确设置环境变量，包括模型配置、搜索后端、评估器设置等。

## 方法1：使用 .env 文件（推荐）

### 步骤1：创建 .env 文件
在项目根目录创建 `.env` 文件：

```bash
# Windows
copy env_example.txt .env

# macOS/Linux
cp env_example.txt .env
```

### 步骤2：编辑 .env 文件
用文本编辑器打开 `.env` 文件，填入你的 API 密钥和配置：

```env
# OpenAI API Key (必需)
OPENAI_API_KEY=sk-your-actual-api-key-here

# 或者使用 Qiniu API (替代方案)
# QINIU_API_KEY=your_qiniu_api_key_here
# QINIU_ENDPOINT=https://openai.qiniu.com/v1

# 评估器模型配置 (必需)
EVALUATOR_LLM=gpt:gpt-oss-20b

# 搜索后端配置 (可选)
SEARCH_BACKEND=DuckDuckGo

# 终端显示配置 (可选)
NO_FORCE_TERMINAL=false
```

### 步骤3：保存文件
保存 `.env` 文件到项目根目录。

## 方法2：设置系统环境变量

### Windows
```cmd
set OPENAI_API_KEY=sk-your-actual-api-key-here
set EVALUATOR_LLM=gpt:gpt-4o-mini
set SEARCH_BACKEND=DuckDuckGo
set NO_FORCE_TERMINAL=false
```

### macOS/Linux
```bash
export OPENAI_API_KEY=sk-your-actual-api-key-here
export EVALUATOR_LLM=gpt:gpt-4o-mini
export SEARCH_BACKEND=DuckDuckGo
export NO_FORCE_TERMINAL=false
```

## 环境变量详细说明

### 必需配置

#### `OPENAI_API_KEY`
**描述**: OpenAI API 密钥，用于访问 GPT 模型
**格式**: `sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
**获取方式**: [OpenAI Platform](https://platform.openai.com/api-keys)
**示例**: `OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

#### `EVALUATOR_LLM`
**描述**: 评估器使用的语言模型
**格式**: 支持多种格式
**选项**:
- `gpt:model_name` - OpenAI GPT 模型
- `manual` - 手动输入模式
- `fake` - 假响应模式（默认，用于测试）
- `http://endpoint` - 自定义 HTTP API 端点

### 可选配置

#### `QINIU_API_KEY` 和 `QINIU_ENDPOINT`
**描述**: 七牛云 API 配置，作为 OpenAI 的替代方案
**格式**: 
- `QINIU_API_KEY=qiniu_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- `QINIU_ENDPOINT=https://openai.qiniu.com/v1`
**默认端点**: `https://openai.qiniu.com/v1`
**备用端点**: `https://api.qnaigc.com/v1`

#### `SEARCH_BACKEND`
**描述**: 搜索工具使用的后端搜索引擎
**默认值**: `DuckDuckGo`
**选项**: 支持任何兼容的搜索后端
**示例**: `SEARCH_BACKEND=DuckDuckGo`

#### `NO_FORCE_TERMINAL`
**描述**: 控制是否强制使用终端样式
**默认值**: `false`
**选项**: `true` 或 `false`
**用途**: 在非终端环境中禁用富文本样式

## 支持的模型配置

### OpenAI 官方模型
```env
# GPT-4 系列
EVALUATOR_LLM=gpt:gpt-4o-mini
EVALUATOR_LLM=gpt:gpt-4o
EVALUATOR_LLM=gpt:gpt-4-turbo

# GPT-3.5 系列
EVALUATOR_LLM=gpt:gpt-3.5-turbo
EVALUATOR_LLM=gpt:gpt-3.5-turbo-16k
```

### 开源大模型
```env
# GPT-OSS 系列
EVALUATOR_LLM=gpt:gpt-oss-120b
EVALUATOR_LLM=gpt:gpt-oss-20b

# DeepSeek 系列
EVALUATOR_LLM=gpt:deepseek-v3

# GLM 系列
EVALUATOR_LLM=gpt:glm-4.5
EVALUATOR_LLM=gpt:glm-4.5-air

# Qwen 系列
EVALUATOR_LLM=gpt:qwen-turbo
EVALUATOR_LLM=gpt:qwen-max-2025-01-25
EVALUATOR_LLM=gpt:qwen3-32b

# 其他模型
EVALUATOR_LLM=gpt:kimi-k2
EVALUATOR_LLM=gpt:MiniMax-M1
EVALUATOR_LLM=gpt:nvidia/llama-3.3-nemotron-super-49b-v1.5
```

## 验证设置

### 基础验证
运行测试来验证环境变量是否正确加载：

```bashs
python -m agents.base.model
```

如果看到 "✅ API key found: sk-xxxxx..." 说明设置成功。

### 评估器验证
测试评估器是否正常工作：

```bash
python -c "from agents.evaluator import Evaluator; e = Evaluator(); print('✅ Evaluator 初始化成功！')"
```
