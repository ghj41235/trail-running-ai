# 越野跑AI助手 - 桌面端专业版

基于 Flask + Kimi大模型的越野跑智能规划系统。

## 功能特性

- **路线分析**: GPX文件导入，智能动态分段，地形图显示，海拔/坡度分析
- **风险预警**: 仅显示真实危险路段，红黄分级预警
- **AI策略**: 基于体能-地形耦合模型的分段配速建议
- **AI训练计划**: Kimi大模型生成，失败自动降级本地算法
- **AI教练**: 越野跑训练咨询、装备建议、比赛策略

## 技术栈

- **后端**: Flask + Python 3
- **前端**: Tailwind CSS + ECharts + Leaflet
- **AI**: Kimi (moonshot-v1)

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用
python app.py

# 浏览器访问
http://localhost:5000
```

## 项目结构

```
trail_ai/
├── app.py              # Flask主应用
├── config.py           # 配置文件
├── requirements.txt    # 依赖列表
├── services/           # 核心算法模块
│   ├── ai_service.py   # AI服务封装
│   ├── gpx_service.py  # GPX解析
│   ├── risk_analyzer.py # 风险分析
│   ├── segmenter.py    # 智能分段
│   └── state_model.py  # 体能-地形耦合模型
├── templates/          # HTML模板
│   └── index.html
└── static/             # 静态资源
    ├── css/
    └── js/
```

## 配置

编辑 `config.py` 设置 Kimi API Key:

```python
KIMI_API_KEY = 'your-api-key-here'
```

## 作者

方竣博 - 燕京理工学院
