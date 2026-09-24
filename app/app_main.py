"""
 * 灏忔淮璇惧爞,鎰挎櫙锛氳鎶€鏈笉鍐嶉毦瀛? * @Remark 鏈夐棶棰樿仈绯绘垜銆恱dclass68銆? * 婧愮爜-绗旇-鎶€鏈氦娴佺兢,瀹樼綉 https://xdclass.net
"""
# app_main.py 是后端服务的入口文件：
# 1. 配置日志；
# 2. 创建 FastAPI 应用对象；
# 3. 注册跨域中间件和接口路由；
# 4. 在直接运行本文件时启动 uvicorn Web 服务器。
import logging

# FastAPI：用于创建 Web API 应用的核心类。
from fastapi import FastAPI

# CORSMiddleware：FastAPI/Starlette 提供的跨域中间件。
# 前端和后端端口不同时，浏览器会触发 CORS 检查，需要它来允许前端访问后端接口。
from fastapi.middleware.cors import CORSMiddleware

# uvicorn：ASGI 服务器，用来真正监听端口并运行 FastAPI 应用。
import uvicorn

# AppSettings：项目自己的配置类，负责读取应用名称、运行环境、host、port、CORS 白名单等配置。
from backend.config import AppSettings

# health_router：健康检查接口路由，例如 GET /health。
# research_router：研究任务接口路由，例如 /api/v1/research/run 和 /api/v1/research/stream。
from backend.router import health_router, research_router


# 配置 Python 标准库 logging 的全局日志格式。
logging.basicConfig(
    # level：最低输出级别。INFO 表示输出 info、warning、error 等级别的日志。
    level=logging.INFO,
    # format：每行日志的展示格式。
    # asctime 是时间，levelname 是日志等级，message 是具体日志内容。
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# 单独设置 mult_agents 包的日志级别，方便观察多智能体流程中的关键信息。
logging.getLogger("mult_agents").setLevel(logging.INFO)

# 单独设置 backend 包的日志级别，方便观察后端接口、服务层等模块的信息。
logging.getLogger("backend").setLevel(logging.INFO)


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。

    这里采用“应用工厂函数”写法：把创建 app、注册中间件、注册路由这些步骤集中到一个函数里。
    好处是结构清晰，也方便测试或被 uvicorn 导入。
    """
    # settings：当前应用的配置对象。
    # AppSettings 会使用默认值，也会尝试从项目根目录的 .env 读取同名环境变量覆盖默认值。
    settings = AppSettings()

    # app：FastAPI 应用实例，是后端服务的核心对象。
    # title 会显示在自动生成的接口文档页面里，例如 /docs。
    app = FastAPI(title=settings.app_name)

    # 给 app 添加 CORS 跨域中间件。
    # 中间件会在请求进入接口前、响应返回浏览器前做额外处理。
    app.add_middleware(
        # CORSMiddleware 是要添加的中间件类。
        CORSMiddleware,
        # allow_origins：允许哪些前端源访问后端。
        # settings.cors_origins() 会把配置里的逗号分隔字符串转成 list[str]。
        allow_origins=settings.cors_origins(),
        # allow_credentials：是否允许浏览器携带 cookie、Authorization 等凭证信息。
        allow_credentials=True,
        # allow_methods：允许的 HTTP 方法。
        # ["*"] 表示 GET、POST、PUT、DELETE 等都允许。
        allow_methods=["*"],
        # allow_headers：允许的请求头。
        # ["*"] 表示允许前端发送任意请求头。
        allow_headers=["*"],
    )

    # 注册健康检查路由。
    # 注册后，health_router 中定义的接口才会成为这个应用的一部分。
    app.include_router(health_router)

    # 注册研究任务相关路由。
    # 例如同步运行接口和流式输出接口都通过这个 router 暴露。
    app.include_router(research_router)

    # 返回配置完成的 FastAPI 应用实例，供模块变量 app 和 uvicorn 使用。
    return app


# app：模块级 FastAPI 应用对象。
# 当执行 `uvicorn app_main:app` 时，uvicorn 会导入这个变量并运行它。
app = create_app()


# __name__ 是 Python 内置模块变量。
# 当这个文件被 `python app_main.py` 直接运行时，__name__ 等于 "__main__"；
# 当这个文件被 uvicorn 或其他模块导入时，__name__ 不等于 "__main__"。
if __name__ == "__main__":
    # runtime_settings：启动服务器时使用的配置对象。
    # 这里重新读取一次配置，用于确定 host、port、是否热重载等运行参数。
    runtime_settings = AppSettings()

    # 启动 uvicorn 服务器，让 FastAPI 应用开始监听 HTTP 请求。
    uvicorn.run(
        # "app_main:app" 表示：从 app_main 模块中找到名为 app 的 FastAPI 应用对象。
        "app_main:app",
        # host：服务监听的 IP 地址。
        # 默认 0.0.0.0 表示允许局域网或容器外部访问；如果是 127.0.0.1 则只允许本机访问。
        host=runtime_settings.host,
        # port：服务监听的端口号，默认是 8000。
        port=runtime_settings.port,
        # reload：是否开启代码变更自动重启。
        # 只有 app_env 等于 development 时开启，适合开发调试；生产环境通常关闭。
        reload=runtime_settings.app_env == "development",
    )
