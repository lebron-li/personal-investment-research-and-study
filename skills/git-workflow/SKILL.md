# git-workflow Skill

Windows 环境下 Git 操作的标准流程。解决中文用户目录编码、SSH 鉴权、PowerShell 语法差异等常见问题。

## 前置检查（任何 Git 操作前必须执行）

### 1. 确认 SSH 环境可用

```powershell
# 检查 SSH 密钥是否存在
Get-ChildItem $env:USERPROFILE\.ssh\id_*

# 如果不存在，生成密钥
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519 -N '""'
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
# 让用户把公钥添加到 GitHub → Settings → SSH and GPG keys
```

### 2. 所有 Git 远程操作必须使用此环境变量

由于 Windows 中文用户名导致路径编码问题，每次 git push/pull/clone 都必须设置：

```powershell
$env:GIT_SSH_COMMAND = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -i ' + $env:USERPROFILE + '\.ssh\id_ed25519'
```

**绝对不要**在命令中硬编码包含中文的用户路径！使用 `$env:USERPROFILE` 拼接。

### 3. PowerShell 语法要点

- 多命令分隔：用 `;` 不用 `&&`
- 重定向 stderr：用 `2>&1` 不用 `2>/dev/null`
- 环境变量：`$env:VAR = 'value'` 不用 `export VAR=value`
- 路径：反斜杠 `\`，在字符串中需要双写 `\\`
- rm 替代：`Remove-Item -Recurse -Force` 不用 `rm -rf`

---

## 场景一：将现有文件夹初始化为 Git 仓库并推送

用户说"把这个文件夹变成 git 项目"时适用。

```
输入：用户指定的文件夹路径（如未指定则用当前工作目录）
输出：已初始化的 git 仓库，已关联远程，已推送
```

### 流程

```powershell
# Step 1: 进入目录，初始化
cd <目标目录>
git init

# Step 2: 确认 SSH key 存在（见前置检查）

# Step 3: 让用户提供远程仓库地址
# 询问："远程仓库地址是什么？"（如 https://github.com/user/repo.git）

# Step 4: 添加远程
git remote add origin <用户提供的地址>

# Step 5: 如果远程是 HTTPS 格式，改成 SSH
git remote set-url origin git@github.com:<user>/<repo>.git

# Step 6: 添加、提交
git add .
git commit -m "<用户指定的提交信息>"

# Step 7: 推送（使用修复后的 SSH 命令）
$env:GIT_SSH_COMMAND = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -i ' + $env:USERPROFILE + '\.ssh\id_ed25519'
git push -u origin <branch>
```

---

## 场景二：克隆 GitHub 项目到 frontEnd 文件夹

用户给一个 GitHub 链接，要求克隆到 `D:\webCode\frontEnd` 并配置好工作环境。

```
输入：GitHub 仓库 URL
输出：已克隆的项目，可正常进行 git 操作
```

### 流程

```powershell
# Step 1: 解析 URL，提取仓库名
# 从 https://github.com/user/repo.git 提取 "repo"

# Step 2: 设置 SSH 环境
$env:GIT_SSH_COMMAND = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -i ' + $env:USERPROFILE + '\.ssh\id_ed25519'

# Step 3: 克隆（使用 SSH URL）
$sshUrl = <URL>.Replace('https://github.com/', 'git@github.com:')
$targetPath = "D:\webCode\frontEnd\<repo-name>"
git clone $sshUrl $targetPath

# Step 4: 如果克隆失败（SSH 问题），排查：
# - ssh -T git@github.com 是否返回 "Hi <user>!"
# - $env:USERPROFILE\.ssh\id_ed25519 是否存在
# - 公钥是否已添加到 GitHub

# Step 5: 确认远程配置正确
cd $targetPath
git remote -v
# 确保 remote 是 SSH 格式：git@github.com:user/repo.git

# Step 6: 如果项目有 package.json，安装依赖
if (Test-Path "package.json") { npm install }
```

---

## 场景三：创建分支、提交、合并、推送

常用工作流。

```powershell
# 先设置 SSH 环境
$env:GIT_SSH_COMMAND = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -i ' + $env:USERPROFILE + '\.ssh\id_ed25519'

# 创建并切换到新分支
git checkout -b <branch-name>

# 修改文件后
git add .
git commit -m "<message>"

# 推新分支
git push -u origin <branch-name>

# 合并到 main
git checkout main
git merge <branch-name> --allow-unrelated-histories -m '<message>'
git push origin main
```

---

## 常见错误速查

| 错误 | 原因 | 解决 |
|------|------|------|
| `Failed to connect to github.com port 443` | 网络阻断 HTTPS | 改用 SSH URL |
| `Permission denied (publickey)` | 未配 SSH key 或路径不对 | 用 `-i` 显式指定私钥路径 |
| `Host key verification failed` | known_hosts 无记录 | 加 `-o StrictHostKeyChecking=no` |
| `Could not create directory '/c/Users/乱码/.ssh'` | 中文用户名编码问题 | 用 `-o UserKnownHostsFile=NUL` + 显式 `-i` 路径 |
| `refusing to merge unrelated histories` | 两个仓库无共同祖先 | 加 `--allow-unrelated-histories` |
| `&&` 语法错误 | PowerShell 不支持 | 改用 `;` |
| `export` 语法错误 | PowerShell 不支持 | 改用 `$env:VAR = 'value'` |

## 核心原则

1. **Never trust `~` in git commands on Windows with Chinese usernames.** Always use `$env:USERPROFILE`.
2. **Always set `$env:GIT_SSH_COMMAND` before any remote git operation.**
3. **Prefer SSH over HTTPS for GitHub.** SSH URL format: `git@github.com:user/repo.git`.
4. **Check SSH connectivity first:** `ssh -T git@github.com` should succeed.
5. **Don't hardcode paths with Chinese characters in commands.** Use PowerShell variables that resolve correctly.
