# 前端研发技术雷达：分层 GitHub 清单

> 目的：这是长期技术储备清单，不是某个项目的安装依赖清单。
>
> 分类原则：按**状态所有权、输入模型、空间几何、渲染管线、执行位置**分层，而不是按页面功能平铺分类。
>
> 说明：同一库可能跨层；这里按其主要职责归档。涉及商业产品时，应在采用前再次核对当前许可证、版本与 hosted/Pro 边界。

---

## 0. 横切协议与基础设施层

这一层共享的是协议、Schema、同步、持久化与观测边界，**不接管**编辑器 transaction、画布 viewport 或拖拽过程等高频私有状态。

### 0.1 轻量客户端状态与状态机

| 库 | GitHub | 定位 |
|---|---|---|
| Zustand | [pmndrs/zustand](https://github.com/pmndrs/zustand) | 轻量全局 UI 状态、偏好、临时工作区状态 |
| Jotai | [pmndrs/jotai](https://github.com/pmndrs/jotai) | 原子状态、细粒度订阅 |
| Redux Toolkit | [reduxjs/redux-toolkit](https://github.com/reduxjs/redux-toolkit) | 严格事件流、团队规范、可追踪状态 |
| XState | [statelyai/xstate](https://github.com/statelyai/xstate) | 显式有限状态机、审批流、复杂交互状态 |
| TanStack Store | [TanStack/store](https://github.com/TanStack/store) | 框架无关、响应式状态容器 |

### 0.2 服务端状态、表单与 Schema

| 库 | GitHub | 定位 |
|---|---|---|
| TanStack Query | [TanStack/query](https://github.com/TanStack/query) | 请求缓存、Mutation、乐观更新、分页 |
| SWR | [vercel/swr](https://github.com/vercel/swr) | 数据获取、缓存、revalidate |
| React Hook Form | [react-hook-form/react-hook-form](https://github.com/react-hook-form/react-hook-form) | 高性能 React 表单 |
| TanStack Form | [TanStack/form](https://github.com/TanStack/form) | 类型优先、跨框架表单 |
| Zod | [colinhacks/zod](https://github.com/colinhacks/zod) | TypeScript Schema 与运行时校验 |
| Valibot | [fabian-hiller/valibot](https://github.com/fabian-hiller/valibot) | 更轻量的 Schema 校验 |

### 0.3 本地存储、协作与实时同步

| 库 | GitHub | 定位 |
|---|---|---|
| Dexie | [dexie/Dexie.js](https://github.com/dexie/Dexie.js) | IndexedDB 封装、离线数据 |
| RxDB | [pubkey/rxdb](https://github.com/pubkey/rxdb) | 本地优先数据库、同步 |
| localForage | [localForage/localForage](https://github.com/localForage/localForage) | IndexedDB/WebSQL/localStorage 统一接口 |
| Yjs | [yjs/yjs](https://github.com/yjs/yjs) | CRDT 协作核心 |
| Y-WebSocket | [yjs/y-websocket](https://github.com/yjs/y-websocket) | Yjs WebSocket 同步 Provider |
| Liveblocks | [liveblocks/liveblocks](https://github.com/liveblocks/liveblocks) | Presence、协作与多人状态服务 |
| PartyKit | [partykit/partykit](https://github.com/partykit/partykit) | 实时多用户服务器与房间模型 |
| ElectricSQL | [electric-sql/electric](https://github.com/electric-sql/electric) | Postgres 同步、local-first 数据 |

### 0.4 Worker、布局计算、虚拟化与观测

| 库 | GitHub | 定位 |
|---|---|---|
| Comlink | [GoogleChromeLabs/comlink](https://github.com/GoogleChromeLabs/comlink) | Worker RPC 桥接 |
| ELK.js | [kieler/elkjs](https://github.com/kieler/elkjs) | Worker 中的复杂图自动布局 |
| Dagre | [dagrejs/dagre](https://github.com/dagrejs/dagre) | 有向图层级布局 |
| D3-force | [d3/d3-force](https://github.com/d3/d3-force) | 力导向图模拟 |
| TanStack Virtual | [TanStack/virtual](https://github.com/TanStack/virtual) | Headless 虚拟列表/表格 |
| React Virtuoso | [petyosi/react-virtuoso](https://github.com/petyosi/react-virtuoso) | 高层虚拟列表、消息流 |
| Sentry JavaScript | [getsentry/sentry-javascript](https://github.com/getsentry/sentry-javascript) | 错误与性能监控 |
| OpenTelemetry JS | [open-telemetry/opentelemetry-js](https://github.com/open-telemetry/opentelemetry-js) | Trace、metrics、logs 标准 |

---

## 1. 基础 UI、空间、输入与渲染原语层

这一层拥有自己的局部交互状态；它们是引擎或原语，不是最终产品模块。

### 1.1 可访问 UI 原语与命令系统

| 库 | GitHub | 定位 |
|---|---|---|
| Radix Primitives | [radix-ui/primitives](https://github.com/radix-ui/primitives) | 无样式、可访问 UI 原语 |
| Base UI | [mui/base-ui](https://github.com/mui/base-ui) | MUI 团队的无样式 UI 原语 |
| Ark UI | [chakra-ui/ark](https://github.com/chakra-ui/ark) | 状态机驱动、跨框架 Headless UI |
| Headless UI | [tailwindlabs/headlessui](https://github.com/tailwindlabs/headlessui) | Tailwind 生态 Headless 组件 |
| React Aria | [adobe/react-spectrum](https://github.com/adobe/react-spectrum) | A11y、复杂输入、交互 hooks |
| shadcn/ui | [shadcn-ui/ui](https://github.com/shadcn-ui/ui) | 源码分发组件与设计基座 |
| cmdk | [pacocoursey/cmdk](https://github.com/pacocoursey/cmdk) | Command Menu 原语 |
| kbar | [timc1/kbar](https://github.com/timc1/kbar) | 命令面板与快捷操作 |
| react-hotkeys-hook | [JohannesKlauss/react-hotkeys-hook](https://github.com/JohannesKlauss/react-hotkeys-hook) | 全局/局部快捷键 |
| Lucide | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | 一致的开源图标系统 |
| Iconify | [iconify/iconify](https://github.com/iconify/iconify) | 多图标集统一接口 |

### 1.2 空间布局原语（四种几何模型）

| 空间模型 | 库 | GitHub | 定位 |
|---|---|---|---|
| Split Pane | react-resizable-panels | [bvaughn/react-resizable-panels](https://github.com/bvaughn/react-resizable-panels) | 轴向分栏、比例持久化 |
| Split Pane | Allotment | [jcampbell1/allotment](https://github.com/jcampbell1/allotment) | VS Code 风格可调整面板 |
| Docking Tree | Dockview | [mathuo/dockview](https://github.com/mathuo/dockview) | Tabs、Groups、Split、浮动窗格 |
| Docking Tree | FlexLayout-react | [caplin/FlexLayout](https://github.com/caplin/FlexLayout) | JSON 驱动 Dock Layout |
| Docking Tree | Golden Layout | [golden-layout/golden-layout](https://github.com/golden-layout/golden-layout) | 老牌 Docking Layout |
| Dashboard Grid | React Grid Layout | [react-grid-layout/react-grid-layout](https://github.com/react-grid-layout/react-grid-layout) | 网格坐标 Dashboard |
| Dashboard Grid | GridStack | [gridstack/gridstack.js](https://github.com/gridstack/gridstack.js) | 可拖拽仪表盘网格 |

### 1.3 输入、拖拽、手势与物理

| 输入模型 | 库 | GitHub | 定位 |
|---|---|---|---|
| Synthetic Pointer DnD | dnd-kit | [clauderic/dnd-kit](https://github.com/clauderic/dnd-kit) | 自定义 Overlay、传感器、排序、碰撞检测 |
| Native Drag Transport | Pragmatic DnD | [atlassian/pragmatic-drag-and-drop](https://github.com/atlassian/pragmatic-drag-and-drop) | 原生拖放、虚拟列表、跨区域传输 |
| React List DnD | hello-pangea/dnd | [hello-pangea/dnd](https://github.com/hello-pangea/dnd) | react-beautiful-dnd 社区延续 |
| Imperative DOM Sorting | SortableJS | [SortableJS/Sortable](https://github.com/SortableJS/Sortable) | 框架无关 DOM 排序 |
| Gesture | use-gesture | [pmndrs/use-gesture](https://github.com/pmndrs/use-gesture) | drag、pinch、wheel、touch 手势 |
| 2D Physics | Matter.js | [liabru/matter-js](https://github.com/liabru/matter-js) | 碰撞、刚体、游戏化交互 |
| 2D Physics | Planck.js | [piqnt/planck.js](https://github.com/piqnt/planck.js) | Box2D 风格物理引擎 |
| 3D Physics | Rapier | [dimforge/rapier](https://github.com/dimforge/rapier) | Rust/WASM 高性能物理 |

### 1.4 图编辑、画布、图谱与渲染引擎

| 渲染/交互路径 | 库 | GitHub | 定位 |
|---|---|---|---|
| DOM/SVG Node Graph | React Flow | [xyflow/xyflow](https://github.com/xyflow/xyflow) | React 节点图、流程图、DAG 编辑 |
| DOM/SVG Node Graph | Vue Flow | [bcakmakoglu/vue-flow](https://github.com/bcakmakoglu/vue-flow) | Vue 节点图 |
| Visual Programming | Rete.js | [retejs/rete](https://github.com/retejs/rete) | 节点编辑器、视觉编程 |
| Enterprise Graph Editor | AntV X6 | [antvis/X6](https://github.com/antvis/X6) | 图编辑、流程设计、企业图形 |
| Workflow Graph | LogicFlow | [didi/LogicFlow](https://github.com/didi/LogicFlow) | 流程图与可视化编排 |
| Freeform Canvas | tldraw | [tldraw/tldraw](https://github.com/tldraw/tldraw) | 无限画布 SDK、白板、空间应用 |
| Freeform Canvas | Excalidraw | [excalidraw/excalidraw](https://github.com/excalidraw/excalidraw) | 手绘风白板 |
| Canvas2D Scene | Konva | [konvajs/konva](https://github.com/konvajs/konva) | Canvas 场景图、选区、变换 |
| Canvas2D Scene | react-konva | [konvajs/react-konva](https://github.com/konvajs/react-konva) | Konva React 绑定 |
| Canvas2D Editor | Fabric.js | [fabricjs/fabric.js](https://github.com/fabricjs/fabric.js) | 图层、图片、绘制与编辑 |
| WebGL/WebGPU 2D | PixiJS | [pixijs/pixijs](https://github.com/pixijs/pixijs) | 高性能 2D、粒子、海量对象 |
| Network Graph | Cytoscape.js | [cytoscape/cytoscape.js](https://github.com/cytoscape/cytoscape.js) | 网络图、图算法、交互 |
| Network Graph | Sigma.js | [jacomyal/sigma.js](https://github.com/jacomyal/sigma.js) | WebGL 网络图渲染 |
| Graph Data Model | Graphology | [graphology/graphology](https://github.com/graphology/graphology) | 图数据结构与算法 |
| Graph Visualization | AntV G6 | [antvis/G6](https://github.com/antvis/G6) | 图可视化与关系网络 |
| SVG/Canvas Graphics | D3 | [d3/d3](https://github.com/d3/d3) | 数据驱动图形基础工具箱 |
| SVG Visualization | Visx | [airbnb/visx](https://github.com/airbnb/visx) | React + D3 低层可视化组件 |
| 3D Renderer | Three.js | [mrdoob/three.js](https://github.com/mrdoob/three.js) | WebGL/WebGPU 3D 引擎 |
| React 3D Renderer | React Three Fiber | [pmndrs/react-three-fiber](https://github.com/pmndrs/react-three-fiber) | Three.js React renderer |
| 3D Helpers | Drei | [pmndrs/drei](https://github.com/pmndrs/drei) | R3F 常用 helpers |
| Full 3D Engine | Babylon.js | [BabylonJS/Babylon.js](https://github.com/BabylonJS/Babylon.js) | 完整 3D/WebGPU 引擎 |

### 1.5 富文本、Markdown 与代码编辑内核

| 文本模型 | 库 | GitHub | 定位 |
|---|---|---|---|
| ProseMirror Core | ProseMirror | [ProseMirror/prosemirror](https://github.com/ProseMirror/prosemirror) | Transaction 驱动编辑器内核 |
| ProseMirror Framework | Tiptap | [ueberdosis/tiptap](https://github.com/ueberdosis/tiptap) | 可扩展富文本框架 |
| Markdown Editor | Milkdown | [Milkdown/milkdown](https://github.com/Milkdown/milkdown) | Markdown + ProseMirror |
| ProseMirror Framework | Remirror | [remirror/remirror](https://github.com/remirror/remirror) | React 优先 ProseMirror 框架 |
| Slate Framework | Slate | [ianstormtaylor/slate](https://github.com/ianstormtaylor/slate) | React 富文本框架 |
| Slate Framework | Plate | [udecode/plate](https://github.com/udecode/plate) | Slate + shadcn 风格组件系统 |
| Lexical Core | Lexical | [facebook/lexical](https://github.com/facebook/lexical) | 高性能编辑器内核 |
| Block Editor | BlockNote | [TypeCellOS/BlockNote](https://github.com/TypeCellOS/BlockNote) | Notion 式块编辑器 |
| Block Editor | Editor.js | [codex-team/editor.js](https://github.com/codex-team/editor.js) | Block JSON 编辑器 |
| MDX Editor | MDXEditor | [mdx-editor/editor](https://github.com/mdx-editor/editor) | Markdown/MDX 所见即所得 |
| Code Editor | Monaco Editor | [microsoft/monaco-editor](https://github.com/microsoft/monaco-editor) | VS Code 编辑器内核 |
| Code Editor | CodeMirror | [codemirror/dev](https://github.com/codemirror/dev) | 模块化代码编辑器 |
| Syntax Highlight | Shiki | [shikijs/shiki](https://github.com/shikijs/shiki) | VS Code TextMate 高亮 |

---

## 2. 领域复合能力层

这一层不是单一库的分类，而是把 Layer 1 原语组装为可复用的产品能力。以下列出最有价值的框架、组件与生态入口。

### 2.1 数据密集型界面、表格、图表与时间序列

| 领域能力 | 库 | GitHub | 定位 |
|---|---|---|---|
| Headless Table | TanStack Table | [TanStack/table](https://github.com/TanStack/table) | 列定义、排序、过滤、聚合 |
| Enterprise Data Grid | AG Grid | [ag-grid/ag-grid](https://github.com/ag-grid/ag-grid) | 高密度企业表格、编辑、分组 |
| Canvas Data Grid | Glide Data Grid | [glideapps/glide-data-grid](https://github.com/glideapps/glide-data-grid) | Canvas 高性能表格 |
| Charting | Apache ECharts | [apache/echarts](https://github.com/apache/echarts) | 丰富通用图表与地图 |
| React Charting | Nivo | [plouc/nivo](https://github.com/plouc/nivo) | React 声明式图表 |
| Financial Chart | Lightweight Charts | [tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts) | 时间序列、K线、金融图表 |
| Browser Analytics | DuckDB-Wasm | [duckdb/duckdb-wasm](https://github.com/duckdb/duckdb-wasm) | 浏览器列式分析与 SQL |
| Columnar Data | Apache Arrow JS | [apache/arrow](https://github.com/apache/arrow) | 列式数据交换与计算 |

### 2.2 文档、知识、文件、日历与时间线

| 领域能力 | 库 | GitHub | 定位 |
|---|---|---|---|
| Calendar | FullCalendar | [fullcalendar/fullcalendar](https://github.com/fullcalendar/fullcalendar) | 日历、资源排期、时间块 |
| Upload | Uppy | [transloadit/uppy](https://github.com/transloadit/uppy) | 多源上传、断点续传、插件体系 |
| Upload Protocol | tus-js-client | [tus/tus-js-client](https://github.com/tus/tus-js-client) | 可恢复上传协议客户端 |
| Upload Dropzone | react-dropzone | [react-dropzone/react-dropzone](https://github.com/react-dropzone/react-dropzone) | 拖放文件入口 |
| Timeline | vis-timeline | [visjs/vis-timeline](https://github.com/visjs/vis-timeline) | 交互时间线 |
| Search | Fuse.js | [krisk/Fuse](https://github.com/krisk/Fuse) | 客户端模糊搜索 |
| Search | Orama | [oramasearch/orama](https://github.com/oramasearch/orama) | 内存搜索引擎、向量/全文搜索 |

### 2.3 AI 前端视图、协议与服务端编排

| 执行层级 | 库 | GitHub | 定位 |
|---|---|---|---|
| Frontend View | assistant-ui | [assistant-ui/assistant-ui](https://github.com/assistant-ui/assistant-ui) | React AI Chat、Tool UI、流式消息 |
| Frontend View | AI Elements | [vercel/ai-elements](https://github.com/vercel/ai-elements) | AI UI 组件集合 |
| View + App Context | CopilotKit | [CopilotKit/CopilotKit](https://github.com/CopilotKit/CopilotKit) | Copilot UI、应用上下文交互 |
| Transport/Provider | Vercel AI SDK | [vercel/ai](https://github.com/vercel/ai) | 模型 Provider、stream、tool call |
| Transport/Typed Tools | TanStack AI | [TanStack/ai](https://github.com/TanStack/ai) | 类型化、多 Provider AI SDK |
| Prompt/Schema Contract | BAML | [BoundaryML/baml](https://github.com/BoundaryML/baml) | 结构化输出、Prompt DSL、类型生成 |
| Server Orchestration | LangGraph.js | [langchain-ai/langgraphjs](https://github.com/langchain-ai/langgraphjs) | 长链 Agent 图状态机、checkpoint |
| Server Orchestration | Mastra | [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | TypeScript Agent/workflow 框架 |
| Observability | Langfuse | [langfuse/langfuse](https://github.com/langfuse/langfuse) | LLM Trace、评测、Prompt 管理 |
| Observability | Arize Phoenix | [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) | LLM 可观测与评测 |

### 2.4 媒体、音频、视频与互动创作

| 领域能力 | 库 | GitHub | 定位 |
|---|---|---|---|
| Audio Waveform | Wavesurfer.js | [katspaugh/wavesurfer.js](https://github.com/katspaugh/wavesurfer.js) | 波形、标记、音频播放器 |
| Web Audio | Tone.js | [Tonejs/Tone.js](https://github.com/Tonejs/Tone.js) | 合成器、节拍、交互音乐 |
| Audio Player | Howler.js | [goldfire/howler.js](https://github.com/goldfire/howler.js) | 跨浏览器音频播放 |
| Video Generation | Remotion | [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | React 驱动视频生成 |
| Video Player | Video.js | [videojs/video.js](https://github.com/videojs/video.js) | 可扩展 Web 视频播放器 |
| Gallery / Lightbox | yet-another-react-lightbox | [igordanchenko/yet-another-react-lightbox](https://github.com/igordanchenko/yet-another-react-lightbox) | 图片/视频 Lightbox |
| 2D Game Engine | Phaser | [phaserjs/phaser](https://github.com/phaserjs/phaser) | 浏览器 2D 游戏引擎 |
| Creative Coding | p5.js | [processing/p5.js](https://github.com/processing/p5.js) | 生成艺术与创意编程 |
| Timeline Animation | Theatre.js | [theatre-js/theatre](https://github.com/theatre-js/theatre) | 可视化时间线、场景动画 |

---

## 3. 美学、主题、动效与渲染隔离层

这一层必须有性能预算：将微交互、叙事动画、GPU 特效和 Worker 渲染分开管理；复杂视觉不应与富文本、画布编辑、Docking 工作区长期争抢主线程。

### 3.1 Design Tokens、主题与视觉系统

| 库 | GitHub | 定位 |
|---|---|---|
| Tailwind CSS | [tailwindlabs/tailwindcss](https://github.com/tailwindlabs/tailwindcss) | 原子化样式与设计令牌承载 |
| Style Dictionary | [amzn/style-dictionary](https://github.com/amzn/style-dictionary) | 多平台设计 Token 构建 |
| next-themes | [pacocoursey/next-themes](https://github.com/pacocoursey/next-themes) | React/Next 主题切换 |
| class-variance-authority | [joe-bell/cva](https://github.com/joe-bell/cva) | 组件样式变体 |
| tailwind-variants | [heroui-inc/tailwind-variants](https://github.com/heroui-inc/tailwind-variants) | Tailwind 变体系统 |
| tailwind-merge | [dcastil/tailwind-merge](https://github.com/dcastil/tailwind-merge) | Tailwind class 冲突合并 |
| Mantine | [mantinedev/mantine](https://github.com/mantinedev/mantine) | 全量 React 设计系统 |
| Chakra UI | [chakra-ui/chakra-ui](https://github.com/chakra-ui/chakra-ui) | 可访问 React 设计系统 |
| Material UI | [mui/material-ui](https://github.com/mui/material-ui) | Material 风格企业 UI |
| Ant Design | [ant-design/ant-design](https://github.com/ant-design/ant-design) | 企业后台 UI 系统 |
| Semi Design | [DouyinFE/semi-design](https://github.com/DouyinFE/semi-design) | 企业设计系统与跨框架组件 |

### 3.2 UI Motion、叙事动画与可交互动画

| 动效类别 | 库 | GitHub | 定位 |
|---|---|---|---|
| React Motion | Motion | [motiondivision/motion](https://github.com/motiondivision/motion) | Layout、gesture、spring、presence |
| Physics Animation | React Spring | [pmndrs/react-spring](https://github.com/pmndrs/react-spring) | 弹簧物理动画 |
| Timeline / Scroll Story | GSAP | [greensock/GSAP](https://github.com/greensock/GSAP) | 高级时间线、ScrollTrigger |
| Automatic Layout Motion | AutoAnimate | [formkit/auto-animate](https://github.com/formkit/auto-animate) | 低侵入 DOM 自动过渡 |
| Vector Animation | Lottie Web | [airbnb/lottie-web](https://github.com/airbnb/lottie-web) | After Effects JSON 动画 |
| Interactive Vector State Machine | Rive Runtime | [rive-app/rive-wasm](https://github.com/rive-app/rive-wasm) | 互动矢量状态机动画 |
| Animated Components | Animata | [codse/animata](https://github.com/codse/animata) | Tailwind/React 动画组件 |
| Animated Components | SmoothUI | [serafimcloud/smoothui](https://github.com/serafimcloud/smoothui) | shadcn 风格动画组件 |

### 3.3 GPU 特效、粒子、滚动与 Worker 渲染

| 视觉类别 | 库 | GitHub | 定位 |
|---|---|---|---|
| Particle System | tsParticles | [tsparticles/tsparticles](https://github.com/tsparticles/tsparticles) | 粒子、交互背景、网络特效 |
| WebGL Micro Engine | OGL | [oframe/ogl](https://github.com/oframe/ogl) | 极简 WebGL 渲染与 shader |
| Shader Authoring | Shader Park | [shader-park/shader-park-core](https://github.com/shader-park/shader-park-core) | 声明式交互 Shader |
| Smooth Scroll | Lenis | [darkroomengineering/lenis](https://github.com/darkroomengineering/lenis) | 平滑滚动基础设施 |
| Worker Rendering | PixiJS WebWorker | [pixijs/pixi.js](https://github.com/pixijs/pixijs) | PixiJS + OffscreenCanvas/Worker 路径 |

---

## 4. 邻接的服务端执行层

这些不属于浏览器前端组件库，但会决定 Agent、协作、任务执行、权限和审计能否可靠工作。前端通过明确协议订阅它们，不在浏览器内承担它们的职责。

| 能力 | 库 | GitHub | 定位 |
|---|---|---|---|
| Durable Workflow | Temporal | [temporalio/sdk-typescript](https://github.com/temporalio/sdk-typescript) | 长任务、重试、补偿、可恢复执行 |
| Workflow / Job | Inngest | [inngest/inngest](https://github.com/inngest/inngest) | 事件驱动任务与工作流 |
| Queue | BullMQ | [taskforcesh/bullmq](https://github.com/taskforcesh/bullmq) | Redis 队列与后台任务 |
| Realtime Server | Socket.IO | [socketio/socket.io](https://github.com/socketio/socket.io) | WebSocket/回退实时通信 |
| API Contract | tRPC | [trpc/trpc](https://github.com/trpc/trpc) | TypeScript 端到端 RPC 类型 |
| API Contract | Connect | [connectrpc/connect-es](https://github.com/connectrpc/connect-es) | Connect/gRPC-Web TypeScript 协议 |
| Auth | Better Auth | [better-auth/better-auth](https://github.com/better-auth/better-auth) | TypeScript 认证框架 |
| Authorization | Casbin | [casbin/casbin](https://github.com/casbin/casbin) | RBAC/ABAC 权限策略 |

---

## 采用前的硬性检查项

1. **状态所有权**：库的实时内部状态是否被错误镜像进全局 Store？
2. **渲染管线**：DOM、SVG、Canvas2D、WebGL/WebGPU 的规模上限和 Overlay 策略是什么？
3. **输入模型**：拖拽是 Pointer 合成、Native Drag 还是命令式 DOM？是否兼容触屏、键盘、虚拟化与 iframe？
4. **空间模型**：Split Pane、Docking Tree、Dashboard Grid、Freeform Canvas 是否被错误混用？
5. **执行位置**：浏览器、Web Worker、Edge、Server、Durable Worker 中各自运行什么？
6. **线程预算**：高频动画、富文本解析、画布平移、图布局是否争抢主线程？能否降级或移至 Worker？
7. **授权边界**：MIT/Apache/MPL/GPL/商业 SDK、Pro/Cloud、生产 license key 是否满足你的使用方式？
8. **退出成本**：领域数据是否掌握在自己的 Schema、事件协议和持久化模型中，而非绑定在库的私有对象内？
