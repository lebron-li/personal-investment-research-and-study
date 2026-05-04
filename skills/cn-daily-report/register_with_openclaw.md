# 在 OpenClaw 中注册定时任务

## 方法 1: 使用 OpenClaw 内置命令（如果支持）

在你的 OpenClaw 聊天窗口中，依次发送以下消息：

```
/cron add 📊 持仓午间快评 "35 11 * * 1-5" "python C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py noon" --timezone Asia/Shanghai
```

```
/cron add 📊 持仓晚间复盘 "30 15 * * 1-5" "python C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py evening" --timezone Asia/Shanghai
```

```
/cron add 🚨 持仓紧急预警 "0,30 9-15 * * 1-5" "python C:\Users\李正材\.openclaw\workspace\skills\cn-daily-report\scripts\run_report.py emergency" --timezone Asia/Shanghai
```

然后验证：
```
/cron list
```

## 方法 2: 让我帮你配置

直接对我说：
```
"帮我配置持仓日报的定时任务"
```

我会使用 OpenClaw 的内部 API 来注册这些任务。

## 方法 3: 手动编辑配置文件

1. 找到 OpenClaw 配置文件
2. 添加 cron 配置（见 CRON_SETUP.md）
3. 重启 OpenClaw

---

## 已配置信息

✅ **时区**: Asia/Shanghai (北京时间)  
✅ **飞书会话 ID**: `oc_0d8760ab9b20345f32d4219973d4cc43`  
✅ **报告目录**: `C:\Users\李正材\Desktop\持仓日报\`

### 定时任务详情

| 任务 | Cron 表达式 | 北京时间 | 说明 |
|------|-----------|---------|------|
| 午间快评 | `35 11 * * 1-5` | 周一到周五 11:35 | 生成午间报告并推送飞书 |
| 晚间复盘 | `30 15 * * 1-5` | 周一到周五 15:30 | 生成晚间报告并推送飞书 |
| 紧急预警 | `0,30 9-15 * * 1-5` | 周一到周五 9:00-15:00 每 30 分钟 | 扫描预警，有预警时推送 |

### 节假日自动跳过

系统会自动跳过：
- 周六、周日
- 中国法定节假日（元旦、春节、清明、劳动节、端午、中秋、国庆）

下一个执行时间：**2026-03-30 (周一) 11:35**
