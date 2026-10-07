# 光伏电站运维管理平台

面向光伏组件、逆变器、汇流箱、变压器、储能与升压站运行监视的集中式电站运维后台。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/            每个业务模块一个页面
│   ├── src/api/              统一请求封装
│   ├── src/stores/           会话与筛选状态
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   ├── app/store.py          内存数据仓库与示例数据
│   └── app/summary_store.py  运营概览汇总落库（SQLite）
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 光伏阵列 | `pv_array` | 光伏阵列 | 阵列编号、所属片区、组件型号 |
| 逆变器监视 | `inverter` | 逆变器 | 逆变器编号、品牌型号、额定功率 |
| 汇流箱检测 | `combiner_box` | 汇流箱 | 汇流箱编号、所属阵列、输入路数 |
| 变压器监视 | `transformer` | 变压器 | 变压器编号、电压等级、额定容量 |
| 储能电池组 | `energy_storage` | 储能电池组 | 电池组编号、电池类型、额定容量 |
| 升压站监视 | `boosting_station` | 升压站 | 升压站编号、进线电压、出线电压 |
| 关口计量 | `meter` | 关口表计 | 表计编号、计量点名称、表计精度 |
| 环境监测站 | `environment` | 环境监测站 | 站点编号、安装位置、辐照度 |
| 组件清洗 | `cleaning` | 清洗任务 | 任务编号、清洗区域、清洗方式 |
| 巡视检查 | `patrol` | 巡视记录 | 记录编号、巡视区域、巡视日期 |
| 缺陷管理 | `defect` | 设备缺陷 | 缺陷编号、发现日期、缺陷设备 |
| 检修计划 | `maintenance` | 检修计划 | 计划编号、检修设备、检修类别 |
| 备品备件 | `spare_parts` | 备件物料 | 备件编号、备件名称、规格型号 |
| 告警事件 | `alarm` | 告警事件 | 告警编号、所属片区、告警来源 |
| 调度指令 | `dispatch` | 调度指令单 | 指令编号、下发单位、指令类型 |
| 安全措施 | `safety` | 安全措施票 | 措施编号、措施类型、涉及设备 |
| 运维合同 | `contract` | 运维合同 | 合同编号、合同名称、签约甲方 |
| 运行月报 | `report` | 运行月报 | 月报编号、统计月份、发电量 |

## 运营概览

概览汇总口径全平台只有一份，收在 `backend/app/services/overview.py`：

- **待处理**：按状态推导——告警未消除、缺陷未关闭，不读记录上残留的标记；
- **异常量**：只算未闭环的告警（未消除）和未验收的缺陷（未验收也未关闭）；
- **今日新增**：业务日期固定按 UTC+8 日切，等于统计日期的告警/缺陷，跨零点基数不错位；
- 概览按片区列出待处理量与异常量，卡片由各片区行汇总得出；
- 汇总结果落库（SQLite，`backend/data/overview_summary.db`），按 `(统计日期, 片区)` 唯一，
  同一片区一天重复提交只留最新一版；卡片、片区明细、告警/缺陷列表统计三处读同一份落库数据，
  口径打架时以概览为准；
- 2026-10-07 起用新口径（v2）；之前已生成的历史概览沿用旧口径（v1）不按新口径重算，
  重算只作用于口径调整之后的日期；服务启动时存量汇总按月份自动回填（只补缺、不覆盖），
  也可 `POST /api/overview/backfill` 手动触发。

相关接口：

| 接口 | 说明 |
| --- | --- |
| `GET /api/overview?day=YYYY-MM-DD` | 某天概览（默认今天）：卡片 + 各片区待处理/异常量 |
| `GET /api/overview/details?day=&region=` | 某片区某天的汇总明细，与卡片同一份落库数据 |
| `GET /api/overview/snapshots?month=YYYY-MM` | 已落库的汇总清单，含每版的统计口径 |
| `POST /api/overview/backfill` | 存量汇总按月份回填，已存在的不动 |
| `GET /api/alarm/stats`、`GET /api/defect/stats` | 模块统计卡片，与概览同一份落库汇总 |

## 约定

- 每个模块的前端页面在 `frontend/src/views/<模块>/index.vue`，后端接口在
  `backend/app/routers/<模块>.py`，业务规则在 `backend/app/services/<模块>.py`。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。
