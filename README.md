# 图片压缩工具 · Image Compressor

> 高质量桌面图片压缩工具，支持 JPEG / PNG / WebP。
> A high-quality desktop image compression tool supporting JPEG, PNG, and WebP.

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![License MIT](https://img.shields.io/badge/License-MIT-green)

---

## 功能 Features

| 功能 | 说明 |
|---|---|
| 目标大小压缩 | 输入你想要的目标文件大小 (如 500KB)，自动找到最优质量 |
| 批量处理 | 一次添加多张图片或整个文件夹 |
| 多格式支持 | JPEG · PNG · WebP · BMP · GIF · TIFF |
| 格式转换 | 压缩同时可转换输出格式 |
| EXIF 控制 | 可选保留或移除 EXIF 元数据（GPS/相机信息）|
| 拖拽支持 | 拖入图片文件或文件夹（需要 tkinterdnd2）|
| 后台压缩 | 多线程处理，不阻塞界面 |
| 可取消 | 批量操作中途可取消 |
| 彩色日志 | 成功/警告/错误用颜色区分 |
| 多语言 | 中文 / English / 日本語 |
| 高 DPI | 正确适配 HiDPI 显示器 |

---

## 安装 Installation

```bash
# 1. 克隆项目
git clone <repo-url>
cd tupianyasuo

# 2. 安装依赖（含拖拽等扩展功能）
pip install -r requirements.txt

# 3. 运行
python run.py
# 或者
python -m src.main
```

> **仅使用基础功能**（无拖拽）只需要 Pillow：
> ```bash
> pip install Pillow>=10.0.0
> ```

---

## 开发 Development

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/ -v

# Lint 代码
python -m ruff check src/ tests/

# 构建 exe
pyinstaller build.spec
```

---

## 项目结构 Project Structure

```
src/
├── app.py              # 主窗口
├── main.py             # 入口
├── core/
│   ├── compressor.py   # 压缩引擎（纯逻辑）
│   ├── models.py       # 数据模型
│   └── utils.py        # 工具函数
├── ui/
│   ├── file_panel.py   # 文件列表面板
│   ├── settings_panel.py # 设置面板
│   ├── log_panel.py    # 日志面板
│   ├── widgets.py      # 可复用控件
│   └── theme.py        # 主题颜色/字体
├── workers/
│   └── compress_worker.py # 后台线程
└── i18n/
    └── strings.py      # 多语言字符串

tests/
├── test_utils.py
├── test_compressor.py
└── test_models.py
```

---

## 使用方法 Usage

1. 点击**添加图片**或直接拖入图片 / 文件夹
2. 输入**目标大小**（如 `500KB`、`1.5MB`）
3. 选择**输出格式**和**输出位置**
4. 点击**开始压缩**

输出文件自动命名为 `原文件名_compressed.扩展名`。

---

## 许可证 License

MIT © 2026
