# 前端 — AI多平台视频下载分析平台

Vue 3 + Vite 7 + Tailwind CSS 4 用户端与管理后台。

## 本地开发

```bash
npm install
npm run dev
```

| 页面 | 地址 |
|------|------|
| 用户端 | http://localhost:5173 |
| 管理后台 | http://localhost:5173/admin |

后端需单独启动，见 [保姆级本地运行指南](../docs/保姆级本地运行指南.md)。

## 生产构建

```bash
npm run build
```

产物在 `dist/`，由 Nginx 托管。详见 [部署指南](../docs/部署指南.md)。

## 目录说明

```
src/
├── App.vue              # 用户端根组件
├── components/          # 落地页、视频解析、AI 总结等
├── admin/               # 管理后台 AdminApp.vue
├── api/                 # 接口封装
└── constants/brand.js   # 品牌名常量
```

完整文档见项目根目录 [README.md](../README.md) 与 [开发文档](../docs/开发文档.md)。
