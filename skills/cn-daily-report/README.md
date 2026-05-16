# A 股持仓日报 - 定时任务配置指南

## 📋 功能概述

本技能自动分析你的 A 股持仓，每个交易日生成两份报告：
- **午间快评** (11:35): 30 秒快读 + 下午操作建议
- **晚间复盘** (15:30): 详细分析 + 明日策略

紧急情况下单独推送（突破/跌破关键位、成交量异常等）。

## 🚀 快速开始

### 1. 安装依赖

```powershell
pip install pandas numpy requests beautifulsoup4
```

### 2. 测试运行

```powershell
# 测试午间报告
cd C:\Users\<USERNAME>\.openclaw\workspace\skills\cn-daily-report\scripts
python run_report.py noon

# 测试晚间报告
python run_report.py evening

# 检查紧急预警
python run_report.py emergency
```

### 3. 配置 OpenClaw 定时任务

在 OpenClaw 中添加以下定时任务配置：

#### 方式 1：使用 OpenClaw 内置定时任务（推荐）

在你的 OpenClaw 配置中添加：

```json
{
  "cron": [
    {
      "name": "持仓午间快评",
      "schedule": "35 11 * * 1-5",
      "command": "python C:\\Users\\<NAME>\\.openclaw\\workspace\\skills\\cn-daily-report\\scripts\\run_report.py noon",
      "enabled": true
    },
    {
      "name": "持仓晚间复盘",
      "schedule": "30 15 * * 1-5",
      "command": "python C:\\Users\\<NAME>\\.openclaw\\workspace\\skills\\cn-daily-report\\scripts\\run_report.py evening",
      "enabled": true
    },
    {
      "name": "紧急预警扫描",
      "schedule": "*/30 9-15 * * 1-5",
      "command": "python C:\\Users\\<NAME>\\.openclaw\\workspace\\skills\\cn-daily-report\\scripts\\run_report.py emergency",
      "enabled": true
    }
  ]
}
```

**Cron 表达式说明**：
- `35 11 * * 1-5` → 周一至周五 11:35
- `30 15 * * 1-5` → 周一至周五 15:30
- `*/30 9-15 * * 1-5` → 交易时段每 30 分钟扫描预警

#### 方式 2：使用 Windows 任务计划程序

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器（交易日 11:35 和 15:30）
4. 设置操作：启动程序
   - 程序：`python.exe`
   - 参数：`C:\Users\<USERNAME>\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py noon`
   - 起始于：`C:\Users\<USERNAME>\.openclaw\workspace\skills\cn-daily-report\scripts`

### 4. 配置飞书推送（可选）

编辑 `config/settings.json`：

```json
{
  "feishu": {
    "enabled": true,
    "chat_id": "你的飞书群聊 ID"
  }
}
```

**获取飞书群聊 ID**：
1. 打开飞书群聊
2. 查看 URL：`https://feishu.cn/group/XXXXXX`
3. `XXXXXX` 就是 chat_id

## 📁 文件结构

```
cn-daily-report/
├── SKILL.md                          # 技能定义
├── README.md                         # 本文档
├── scripts/
│   ├── run_report.py                 # 主入口（OpenClaw 调用）
│   ├── daily_report_noon.py          # 午间报告独立脚本
│   ├── daily_report_evening.py       # 晚间报告独立脚本
│   ├── emergency_alert.py            # 紧急预警独立脚本
│   ├── test_all.py                   # 自测脚本
│   ├── utils.py                      # 工具函数
│   ├── data_fetcher.py               # 数据获取
│   ├── key_levels.py                 # 关键位置分析
│   ├── resonance_analyzer.py         # 共振分析
│   ├── event_calendar.py             # 事件日历
│   └── report_generator.py           # 报告生成
└── config/
    └── settings.json                 # 配置文件
```

## 📊 输出说明

### 本地报告

路径：`C:\Users\<USERNAME>\Desktop\持仓日报\`

文件命名：
- `持仓日报_2026-03-30_午间.md`
- `持仓日报_2026-03-30_晚间.md`

### 飞书推送（配置后）

午间版（简洁）：
```
📊 持仓午间快评 [2026-03-30 11:35]

⚡ 30 秒快读
• 持仓涨跌：3 涨 2 跌，平均 +0.52%
• 最佳：招商银行 (+1.2%)
• 最差：食品饮料 ETF (-0.8%)

💰 北向资金：流入 25.3 亿元

📋 下午操作建议
[表格形式展示各持仓建议]
```

晚间版（详细）：
```
📊 持仓晚间复盘 [2026-03-30]

🌍 市场环境
• 北向资金：流入 25.3 亿元
• 近期宏观事件：3 项

📈 持仓详细分析
[逐个分析每只持仓]

📋 持仓总结
• 技术面排名
• 可加仓/持有/注意风险分类

🎯 明日整体策略
```

### 紧急预警（单独推送）

```
🚨 紧急预警

🔴 招商银行 (600036)
   类型：突破阻力
   详情：突破阻力位 40.00 元，当前 40.50 元 (+1.25%)
```

## 🔧 自定义配置

### 修改持仓文件

编辑：`C:\Users\<USERNAME>\Desktop\The stocks and ETFs I bought.txt`

格式：
```
1、食品饮料 ETF 515170
2、美的集团 000333
3、创新药 ETF 515120
4、招商银行 600036
5、长江电力 600900
```

### 调整预警阈值

编辑 `config/settings.json`：

```json
{
  "alert": {
    "breakout_threshold": 0.03,      // 突破阈值 3%
    "volume_ratio_threshold": 3.0,   // 量比阈值 3 倍
    "price_change_threshold": 0.07   // 单日涨跌阈值 7%
  }
}
```

### 修改报告时间

编辑 `config/settings.json`：

```json
{
  "report": {
    "noon_time": "11:35",    // 午间报告时间
    "evening_time": "15:30"  // 晚间报告时间
  }
}
```

## ⚠️ 注意事项

1. **交易日判断**：自动排除周末和中国法定节假日
2. **数据时效**：非交易时间数据可能为空或延迟
3. **依赖安装**：首次运行需要安装 Python 依赖
4. **飞书权限**：推送飞书需要配置正确的 chat_id
5. **投资建议**：报告仅供参考，不构成投资建议

## 🐛 故障排查

### 问题 1：持仓读取失败

**检查**：
- 文件路径是否正确
- 文件格式是否符合要求
- 文件编码是否为 UTF-8

### 问题 2：行情数据为空

**原因**：
- 非交易时间（周末/节假日/盘中休市）
- 网络问题

**解决**：
- 等待交易时间再试
- 检查网络连接

### 问题 3：飞书推送失败

**检查**：
- chat_id 是否正确
- 飞书应用权限是否配置
- 网络是否可达

## 📝 更新日志

- 2026-03-29 v1.0: 初始版本
  - ✅ 午间快评
  - ✅ 晚间复盘
  - ✅ 紧急预警
  - ✅ 飞书推送
  - ✅ 本地 Markdown 报告

## 📞 支持

如有问题，请查看：
- 技能文档：`SKILL.md`
- 自测脚本：`python test_all.py`
- 日志文件：`C:\Users\<USERNAME>\Desktop\持仓日报\`
