# Path：pathlib 提供的路径处理类。
# 相比手写字符串路径，Path 更适合做“当前文件路径”“父目录”“拼接文件名”等操作。
from pathlib import Path

# BaseSettings：pydantic-settings 的配置基类。
# 继承它之后，类字段既可以使用代码里的默认值，也可以被环境变量或 .env 文件覆盖。
# SettingsConfigDict：用于声明 BaseSettings 的读取规则，例如 .env 文件位置、编码等。
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """应用配置类。

    这个类集中管理后端启动和运行时需要的配置。
    在 app_main.py 中实例化 AppSettings() 后，就能通过 settings.app_name、
    settings.host、settings.port 等属性读取配置值。
    """

    # app_name：应用名称。
    # FastAPI 会把它显示在自动生成的接口文档页面中，例如 /docs。
    app_name: str = "DeepResearch Multi-Agent Assistant"

    # app_env：应用运行环境。
    # 当前默认是 development，app_main.py 会根据它决定是否开启 uvicorn 的 reload 热重载。
    app_env: str = "development"

    # host：后端服务监听的 IP 地址。
    # 0.0.0.0 表示监听所有网卡，允许本机、局域网或容器外部访问。
    # 如果只想本机访问，通常可以改为 127.0.0.1。
    host: str = "0.0.0.0"

    # port：后端服务监听的端口号。
    # 启动后通常可以通过 http://localhost:8000 访问服务。
    port: int = 8000

    # cors_allow_origins：允许跨域访问后端的前端地址列表。
    # 这里用逗号分隔的字符串保存，是为了更方便从 .env 环境变量中读取。
    # 默认允许 Vite 开发服务器常用的两个地址。
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # config_path：项目主配置文件 config.json 的路径。
    # __file__ 是当前 settings.py 文件路径；
    # resolve() 转成绝对路径；
    # parents[3] 从 app/backend/config/settings.py 向上回到项目根目录；
    # 最后拼接 config.json。
    config_path: str = str(Path(__file__).resolve().parents[3] / "config.json")

    # model_config：pydantic-settings 的元配置，不是业务字段。
    # 它告诉 AppSettings 应该如何读取额外配置来源。
    model_config = SettingsConfigDict(
        # env_file：指定 .env 文件路径。
        # 这里同样从当前文件向上找到项目根目录，再拼接 .env。
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        # env_file_encoding：读取 .env 文件时使用 UTF-8 编码。
        env_file_encoding="utf-8",
        # extra="ignore"：如果 .env 里有 AppSettings 没定义的变量，就忽略它们。
        # 这样可以避免因为多余配置导致程序启动失败。
        extra="ignore",
    )

    def cors_origins(self) -> list[str]:
        """把逗号分隔的 CORS 字符串转换成 FastAPI 需要的列表格式。"""
        # split(",")：按逗号拆分字符串。
        # strip()：去掉每个地址前后的空格，避免配置里多写空格导致匹配失败。
        values = [item.strip() for item in self.cors_allow_origins.split(",")]

        # 过滤掉空字符串。
        # 例如配置成 "http://localhost:5173," 时，最后会多拆出一个空项，这里会移除它。
        return [item for item in values if item]
