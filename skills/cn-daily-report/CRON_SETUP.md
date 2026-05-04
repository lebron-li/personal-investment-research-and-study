# ⏰ 定时任务配置指南（北京时间）

## ✅ 已完成配置

| 配置项 | 值 |
|--------|-----|
| 时区 | Asia/Shanghai (北京时间) |
| 飞书会话 ID | `oc_0d8760ab9b20345f32d4219973d4cc43` |
| 报告输出目录 | `C:\Users\李正材\Desktop\持仓日报\` |

## 📋 定时任务列表

### 1. 午间快评
- **时间**: 每周一至周五 11:35 (北京时间)
- **Cron**: `35 11 * * 1-5`
- **功能**: 生成午间持仓快评，推送到飞书
- **命令**: 
  ```
  python C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py noon
  ```

### 2. 晚间复盘
- **时间**: 每周一至周五 15:30 (北京时间)
- **Cron**: `30 15 * * 1-5`
- **功能**: 生成晚间持仓复盘，推送到飞书
- **命令**: 
  ```
  python C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py evening
  ```

### 3. 紧急预警
- **时间**: 每周一至周五 09:00-15:00，每 30 分钟 (北京时间)
- **Cron**: `0,30 9-15 * * 1-5`
- **功能**: 扫描紧急预警，有预警时推送到飞书
- **命令**: 
  ```
  python C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py emergency
  ```

## 🔧 配置方法

### 方法 1: 通过 OpenClaw 配置（推荐）

OpenClaw 的定时任务配置方式可能因版本而异。请尝试以下方法：

#### 步骤 1: 检查 OpenClaw 是否支持 cron

在 OpenClaw 中执行：
```
/cron list
```

或
```
openclaw cron list
```

#### 步骤 2: 添加定时任务

如果支持 cron 命令，执行：

```bash
# 午间快评
/cron add --name "📊 持仓午间快评" \
  --schedule "35 11 * * 1-5" \
  --command "python C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py noon" \
  --timezone "Asia/Shanghai"

# 晚间复盘
/cron add --name "📊 持仓晚间复盘" \
  --schedule "30 15 * * 1-5" \
  --command "python C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py evening" \
  --timezone "Asia/Shanghai"

# 紧急预警
/cron add --name "🚨 持仓紧急预警" \
  --schedule "0,30 9-15 * * 1-5" \
  --command "python C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py emergency" \
  --timezone "Asia/Shanghai"
```

#### 步骤 3: 验证配置

```
/cron list
```

应该看到 3 个定时任务。

### 方法 2: 编辑 OpenClaw 配置文件

如果 OpenClaw 使用配置文件管理 cron：

1. 找到配置文件（可能位置）：
   - `~/.openclaw/config.json`
   - `~/.openclaw/cron.json`
   - `%APPDATA%\openclaw\config.json`

2. 添加 cron 配置：

```json
{
  "cron": [
    {
      "name": "📊 持仓午间快评",
      "schedule": "35 11 * * 1-5",
      "command": "python C:\\Users\\李正材\\.openclaw\\workspace\\skills\\cn-daily-report\\scripts\\run_report.py noon",
      "timezone": "Asia/Shanghai",
      "enabled": true
    },
    {
      "name": "📊 持仓晚间复盘",
      "schedule": "30 15 * * 1-5",
      "command": "python C:\\Users\\李正材\\.openclaw\\workspace\\skills\\cn-daily-report\\scripts\\run_report.py evening",
      "timezone": "Asia/Shanghai",
      "enabled": true
    },
    {
      "name": "🚨 持仓紧急预警",
      "schedule": "0,30 9-15 * * 1-5",
      "command": "python C:\\Users\\李正材\\.openclaw\\workspace\\skills\\cn-daily-report\\scripts\\run_report.py emergency",
      "timezone": "Asia/Shanghai",
      "enabled": true
    }
  ]
}
```

3. 保存并重启 OpenClaw

### 方法 3: 使用 Windows 任务计划程序

如果 OpenClaw 不支持 cron，使用 Windows 任务计划程序：

#### 创建批处理文件

创建 `C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_noon.bat`:
```batch
@echo off
cd /d "C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts"
python run_report.py noon
```

创建 `C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_evening.bat`:
```batch
@echo off
cd /d "C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts"
python run_report.py evening
```

创建 `C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_emergency.bat`:
```batch
@echo off
cd /d "C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts"
python run_report.py emergency
```

#### 导入任务

以管理员身份打开 PowerShell，执行：

```powershell
# 午间快评 - 每周一至周五 11:35
schtasks /Create /TN "OpenClaw_持仓午间快评" /TR "C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_noon.bat" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 11:35 /RU SYSTEM

# 晚间复盘 - 每周一至周五 15:30
schtasks /Create /TN "OpenClaw_持仓晚间复盘" /TR "C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_evening.bat" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:30 /RU SYSTEM

# 紧急预警 - 每周一至周五 9:00-15:00 每 30 分钟
schtasks /Create /TN "OpenClaw_持仓紧急预警" /TR "C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_emergency.bat" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:00 /DU 06:30 /RI 30 /RU SYSTEM
```

#### 验证任务

```powershell
schtasks /Query /TN "OpenClaw_持仓午间快评"
schtasks /Query /TN "OpenClaw_持仓晚间复盘"
schtasks /Query /TN "OpenClaw_持仓紧急预警"
```

## 🧪 测试步骤

### 1. 手动测试报告生成

```powershell
cd C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts

# 测试午间报告
python run_report.py noon

# 测试晚间报告
python run_report.py evening

# 测试紧急预警
python run_report.py emergency
```

### 2. 测试飞书推送

检查是否收到飞书消息。如果未收到：
- 检查 chat_id 是否正确
- 检查网络连接
- 查看日志文件

### 3. 等待自动执行

下一个交易日（周一）：
- 11:35 检查是否收到午间快评
- 15:30 检查是否收到晚间复盘

## 📊 日志查看

日志文件位置：
```
C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\logs\
```

查看最新日志：
```powershell
Get-ChildItem "C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\logs\" -OrderBy LastWriteTimeDescending | Select-Object -First 1 | Get-Content
```

## 🔍 故障排查

### 问题 1: 定时任务未执行

**检查**:
1. OpenClaw 是否正在运行
2. cron 配置是否正确
3. 时区是否为 Asia/Shanghai
4. 今天是否为交易日

**解决**:
```powershell
# 手动执行一次
python run_report.py noon
```

### 问题 2: 飞书推送未收到

**检查**:
1. chat_id 是否正确：`oc_0d8760ab9b20345f32d4219973d4cc43`
2. 飞书应用权限是否配置
3. 网络是否可达

**解决**:
- 检查 `config/settings.json` 中的 chat_id
- 手动测试推送功能

### 问题 3: 报告内容为空

**原因**: 非交易时间

**解决**: 等待交易时间再测试

## 📝 重要日期

- **今天**: 2026-03-29 (周日，非交易日)
- **下一个交易日**: 2026-03-30 (周一)
- **首次自动执行**: 2026-03-30 11:35

## ✅ 配置完成检查清单

- [ ] 定时任务已添加到 OpenClaw
- [ ] 飞书 chat_id 已配置
- [ ] 手动测试报告生成成功
- [ ] 手动测试飞书推送成功
- [ ] 日志目录已创建
- [ ] 等待下一个交易日验证自动执行

---

**配置完成时间**: 2026-03-29  
**时区**: Asia/Shanghai (北京时间)  
**飞书会话**: oc_0d8760ab9b20345f32d4219973d4cc43
