"""配置模块：统一加载 .env 与 config.json，并构建全局 AppConfig。

学习导读：
    这个文件负责把“配置来源”变成程序内部统一使用的 AppConfig 对象。
    配置来源主要有三类：
    1. 环境变量，例如 DASHSCOPE_API_KEY；
    2. 项目根目录的 .env 文件；
    3. 项目根目录的 config.json 文件。

    读取优先级是：环境变量 > config.json > 代码默认值。
"""

# json：Python 标准库，用于读取 config.json 并把 JSON 字符串解析成 dict。
import json

# os：Python 标准库，用于读取环境变量，例如 os.getenv("DASHSCOPE_API_KEY")。
import os

# dataclass：把普通类变成“数据类”，自动生成 __init__ 等方法。
# replace：基于已有 dataclass 对象复制一个新对象，并替换部分字段。
from dataclasses import dataclass, replace

# Path：面向对象的路径处理工具，比手写字符串路径更可靠。
from pathlib import Path

# load_dotenv：从 .env 文件加载环境变量到当前进程。
from dotenv import load_dotenv


# 加载项目根目录的 .env 文件
# _PROJECT_ROOT：项目根目录路径。
# 当前文件是 app/mult_agents/config.py，parents[2] 会向上两级到项目根目录。
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# _ENV_PATH：项目根目录下的 .env 文件路径。
_ENV_PATH = _PROJECT_ROOT / ".env"

# 如果 .env 文件存在，就加载它。
# 加载后，里面的 KEY=VALUE 可以通过 os.getenv("KEY") 读取。
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


@dataclass(frozen=True)
class AppConfig:
    """多智能体系统的统一配置对象。

    @dataclass(frozen=True) 的意思：
        dataclass 会自动生成 __init__、__repr__ 等方法；
        frozen=True 表示对象创建后字段不允许直接修改，避免运行中配置被意外改坏。

    使用方式：
        config = AppConfig.from_file("config.json")
        print(config.model)
    """

    # api_key：调用大模型服务的 API Key。
    # 这个项目里主要对应 DASHSCOPE_API_KEY。
    api_key: str

    # model：大模型名称，例如 qwen-plus。
    model: str

    # thread_id：默认会话线程 ID，LangGraph checkpointer 会用它区分会话状态。
    thread_id: str

    # user_id：默认用户 ID，用于记忆系统和用户级数据隔离。
    user_id: str

    # tenant_id：默认租户 ID，用于多租户数据隔离。
    tenant_id: str

    # max_iterations：多智能体工作流最大迭代轮数。
    max_iterations: int

    # enable_memory：是否启用记忆能力。
    enable_memory: bool

    # short_term_ttl_seconds：短期记忆存活时间，单位是秒。
    short_term_ttl_seconds: int

    # short_term_max_messages：短期记忆最多保留多少条消息。
    short_term_max_messages: int

    # short_term_summary_threshold：短期记忆超过多少条后触发摘要压缩。
    short_term_summary_threshold: int

    # short_term_backend：短期记忆后端，例如 postgres、redis、memory。
    short_term_backend: str

    # long_term_backend：长期记忆后端，例如 postgres、sqlite、disabled。
    long_term_backend: str

    # long_term_scope：长期记忆作用范围，例如 user 表示按用户保存，thread 表示按会话保存。
    long_term_scope: str

    # save_conversation_task：是否把对话保存任务异步/后台化。
    save_conversation_task: bool

    # checkpointer_backend：LangGraph checkpointer 后端，例如 postgres、redis、memory、auto。
    checkpointer_backend: str

    # enable_milvus：是否启用 Milvus 向量库，用于本地知识库/RAG 检索。
    enable_milvus: bool

    # memory_top_k：从记忆系统中取回的相关记忆数量上限。
    memory_top_k: int

    # redis_url：Redis 连接地址。
    redis_url: str

    # postgres_dsn：PostgreSQL 连接字符串。
    postgres_dsn: str

    # milvus_host：Milvus 服务地址。
    milvus_host: str

    # milvus_port：Milvus 服务端口。
    milvus_port: int

    # milvus_collection：Milvus 集合名称，用来存放向量数据。
    milvus_collection: str

    def with_overrides(self, **kwargs) -> "AppConfig":
        """基于当前配置创建一个“覆盖部分字段”的新配置对象。

        参数：
            **kwargs：要覆盖的配置字段，例如 user_id="u1"、max_iterations=3。

        返回：
            AppConfig：一个新的配置对象。原对象不会被修改。
        """

        # cleaned：过滤掉值为 None 的覆盖项。
        # 这样调用方传 enable_memory=None 时，不会把原配置覆盖成 None。
        cleaned = {k: v for k, v in kwargs.items() if v is not None}

        # replace(self, **cleaned)：复制当前 dataclass，并替换 cleaned 中指定的字段。
        return replace(self, **cleaned)

    @staticmethod
    def _default_config_path() -> Path:
        """返回默认 config.json 路径。"""

        # 当前文件 app/mult_agents/config.py 向上两级是项目根目录，然后拼接 config.json。
        return Path(__file__).resolve().parents[2] / "config.json"

    @staticmethod
    def _resolve_str(data: dict, field: str, env_key: str, default: str = "") -> str:
        """按优先级解析字符串配置。

        参数：
            data：从 config.json 读取出的字典。
            field：config.json 中的字段名。
            env_key：环境变量名。
            default：环境变量和 config.json 都没有时使用的默认值。

        返回：
            str：解析后的字符串配置。
        """

        # 优先读取环境变量。
        env_value = os.getenv(env_key)
        if env_value is not None and str(env_value).strip() != "":
            return str(env_value).strip()

        # 环境变量没有时，再读取 config.json 中的字段。
        file_value = data.get(field)
        if file_value is not None and str(file_value).strip() != "":
            return str(file_value).strip()

        # 两边都没有，就使用代码里的默认值。
        return default

    @staticmethod
    def _resolve_int(data: dict, field: str, env_key: str, default: int) -> int:
        """按优先级解析整数配置。"""

        # 先按字符串规则取值，再转成 int。
        value = AppConfig._resolve_str(data, field, env_key, str(default))
        return int(value)

    @staticmethod
    def _resolve_bool(data: dict, field: str, env_key: str, default: bool) -> bool:
        """按优先级解析布尔配置。"""

        # 布尔值先转成字符串形式读取。
        # 默认 True 对应 "true"，默认 False 对应 "false"。
        value = AppConfig._resolve_str(data, field, env_key, "true" if default else "false")

        # 只有字符串等于 "true" 时返回 True，其它值都会返回 False。
        return value.lower() == "true"

    @staticmethod
    def from_file(path: str | Path | None = None) -> "AppConfig":
        """从 config.json 和环境变量构建 AppConfig。

        参数：
            path：config.json 的路径；如果不传，就使用项目根目录下的 config.json。

        返回：
            AppConfig：完整的运行配置对象。

        注意：
            即使从 config.json 读取，环境变量仍然拥有更高优先级。
        """

        # config_path：最终要读取的配置文件路径。
        config_path = Path(path) if path else AppConfig._default_config_path()

        # 如果配置文件不存在，直接报错，提醒调用方检查路径。
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        # 读取 config.json 文本，并解析成 Python 对象。
        data = json.loads(config_path.read_text(encoding="utf-8"))

        # config.json 顶层必须是对象，也就是 Python 里的 dict。
        if not isinstance(data, dict):
            raise ValueError("配置文件格式错误")

        # api_key 是必需配置。
        # 优先读取 DASHSCOPE_API_KEY 环境变量，其次读取 config.json 的 api_key。
        api_key = AppConfig._resolve_str(data, "api_key", "DASHSCOPE_API_KEY", "")
        if not api_key:
            raise ValueError(
                f"缺少 DASHSCOPE_API_KEY 配置，请在 {config_path} 中填写 api_key，或设置环境变量 DASHSCOPE_API_KEY"
            )

        # 以下字段都是按“环境变量 > config.json > 默认值”的优先级读取。
        model = AppConfig._resolve_str(data, "model", "MODEL", "qwen-plus")
        thread_id = AppConfig._resolve_str(data, "thread_id", "THREAD_ID", "default")
        user_id = AppConfig._resolve_str(data, "user_id", "USER_ID", "default_user")
        tenant_id = AppConfig._resolve_str(data, "tenant_id", "TENANT_ID", "default_tenant")
        max_iterations = AppConfig._resolve_int(data, "max_iterations", "MAX_ITERATIONS", 3)
        enable_memory = AppConfig._resolve_bool(data, "enable_memory", "ENABLE_MEMORY", True)
        short_term_ttl_seconds = AppConfig._resolve_int(data, "short_term_ttl_seconds", "SHORT_TERM_TTL_SECONDS", 604800)
        short_term_max_messages = AppConfig._resolve_int(data, "short_term_max_messages", "SHORT_TERM_MAX_MESSAGES", 30)
        short_term_summary_threshold = AppConfig._resolve_int(
            data, "short_term_summary_threshold", "SHORT_TERM_SUMMARY_THRESHOLD", 20
        )
        short_term_backend = AppConfig._resolve_str(data, "short_term_backend", "SHORT_TERM_BACKEND", "postgres").lower()
        long_term_backend = AppConfig._resolve_str(data, "long_term_backend", "LONG_TERM_BACKEND", "postgres").lower()
        long_term_scope = AppConfig._resolve_str(data, "long_term_scope", "LONG_TERM_SCOPE", "user").lower()
        save_conversation_task = AppConfig._resolve_bool(data, "save_conversation_task", "SAVE_CONVERSATION_TASK", False)
        checkpointer_backend = AppConfig._resolve_str(data, "checkpointer_backend", "CHECKPOINTER_BACKEND", "auto").lower()
        enable_milvus = AppConfig._resolve_bool(data, "enable_milvus", "ENABLE_MILVUS", True)
        memory_top_k = AppConfig._resolve_int(data, "memory_top_k", "MEMORY_TOP_K", 6)
        redis_url = AppConfig._resolve_str(data, "redis_url", "REDIS_URL", "redis://127.0.0.1:6379")
        postgres_dsn = AppConfig._resolve_str(
            data, "postgres_dsn", "POSTGRES_DSN", "postgresql://127.0.0.1:5432/postgres"
        )
        milvus_host = AppConfig._resolve_str(data, "milvus_host", "MILVUS_HOST", "127.0.0.1")
        milvus_port = AppConfig._resolve_int(data, "milvus_port", "MILVUS_PORT", 19530)
        milvus_collection = AppConfig._resolve_str(data, "milvus_collection", "MILVUS_COLLECTION", "mult_agent_memory")

        # 把解析好的各项配置组装成 AppConfig 实例。
        return AppConfig(
            api_key=api_key,
            model=model,
            thread_id=thread_id,
            user_id=user_id,
            tenant_id=tenant_id,
            max_iterations=max_iterations,
            enable_memory=enable_memory,
            short_term_ttl_seconds=short_term_ttl_seconds,
            short_term_max_messages=short_term_max_messages,
            short_term_summary_threshold=short_term_summary_threshold,
            short_term_backend=short_term_backend,
            long_term_backend=long_term_backend,
            long_term_scope=long_term_scope,
            save_conversation_task=save_conversation_task,
            checkpointer_backend=checkpointer_backend,
            enable_milvus=enable_milvus,
            memory_top_k=memory_top_k,
            redis_url=redis_url,
            postgres_dsn=postgres_dsn,
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            milvus_collection=milvus_collection,
        )

    @staticmethod
    def from_env() -> "AppConfig":
        """只从环境变量和代码默认值构建 AppConfig。

        返回：
            AppConfig：完整的运行配置对象。

        和 from_file() 的区别：
            from_file() 会读取 config.json；
            from_env() 不读取 config.json，只读取环境变量，不存在的字段使用代码默认值。
        """

        # data 为空字典，表示不提供 config.json 配置来源。
        data: dict = {}

        # api_key 仍然是必需项；这里必须来自环境变量。
        api_key = AppConfig._resolve_str(data, "api_key", "DASHSCOPE_API_KEY", "")
        if not api_key:
            raise ValueError("缺少 DASHSCOPE_API_KEY 环境变量")

        # 以下字段按“环境变量 > 默认值”的优先级读取。
        model = AppConfig._resolve_str(data, "model", "MODEL", "qwen-plus")
        thread_id = AppConfig._resolve_str(data, "thread_id", "THREAD_ID", "default")
        user_id = AppConfig._resolve_str(data, "user_id", "USER_ID", "default_user")
        tenant_id = AppConfig._resolve_str(data, "tenant_id", "TENANT_ID", "default_tenant")
        max_iterations = AppConfig._resolve_int(data, "max_iterations", "MAX_ITERATIONS", 3)
        enable_memory = AppConfig._resolve_bool(data, "enable_memory", "ENABLE_MEMORY", True)
        short_term_ttl_seconds = AppConfig._resolve_int(data, "short_term_ttl_seconds", "SHORT_TERM_TTL_SECONDS", 604800)
        short_term_max_messages = AppConfig._resolve_int(data, "short_term_max_messages", "SHORT_TERM_MAX_MESSAGES", 30)
        short_term_summary_threshold = AppConfig._resolve_int(
            data, "short_term_summary_threshold", "SHORT_TERM_SUMMARY_THRESHOLD", 20
        )
        short_term_backend = AppConfig._resolve_str(data, "short_term_backend", "SHORT_TERM_BACKEND", "postgres").lower()
        long_term_backend = AppConfig._resolve_str(data, "long_term_backend", "LONG_TERM_BACKEND", "postgres").lower()
        long_term_scope = AppConfig._resolve_str(data, "long_term_scope", "LONG_TERM_SCOPE", "user").lower()
        save_conversation_task = AppConfig._resolve_bool(data, "save_conversation_task", "SAVE_CONVERSATION_TASK", False)
        checkpointer_backend = AppConfig._resolve_str(data, "checkpointer_backend", "CHECKPOINTER_BACKEND", "auto").lower()
        enable_milvus = AppConfig._resolve_bool(data, "enable_milvus", "ENABLE_MILVUS", True)
        memory_top_k = AppConfig._resolve_int(data, "memory_top_k", "MEMORY_TOP_K", 6)
        redis_url = AppConfig._resolve_str(data, "redis_url", "REDIS_URL", "redis://127.0.0.1:6379")
        postgres_dsn = AppConfig._resolve_str(
            data, "postgres_dsn", "POSTGRES_DSN", "postgresql://127.0.0.1:5432/postgres"
        )
        milvus_host = AppConfig._resolve_str(data, "milvus_host", "MILVUS_HOST", "127.0.0.1")
        milvus_port = AppConfig._resolve_int(data, "milvus_port", "MILVUS_PORT", 19530)
        milvus_collection = AppConfig._resolve_str(data, "milvus_collection", "MILVUS_COLLECTION", "mult_agent_memory")

        # 返回只基于环境变量/默认值构建出的 AppConfig。
        return AppConfig(
            api_key=api_key,
            model=model,
            thread_id=thread_id,
            user_id=user_id,
            tenant_id=tenant_id,
            max_iterations=max_iterations,
            enable_memory=enable_memory,
            short_term_ttl_seconds=short_term_ttl_seconds,
            short_term_max_messages=short_term_max_messages,
            short_term_summary_threshold=short_term_summary_threshold,
            short_term_backend=short_term_backend,
            long_term_backend=long_term_backend,
            long_term_scope=long_term_scope,
            save_conversation_task=save_conversation_task,
            checkpointer_backend=checkpointer_backend,
            enable_milvus=enable_milvus,
            memory_top_k=memory_top_k,
            redis_url=redis_url,
            postgres_dsn=postgres_dsn,
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            milvus_collection=milvus_collection,
        )
