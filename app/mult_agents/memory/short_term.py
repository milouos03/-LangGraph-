"""
短期记忆模块。

这个模块解决的是“同一次对话中，程序怎样暂时记住前文”的问题，包含两层：

1. ``ConversationBuffer``：保存一个对话线程中的消息，并在消息过多时压缩旧消息。
2. ``ShortTermMemory``：用 ``thread_id`` 管理多个 ``ConversationBuffer``，并负责过期清理。

这里的“线程”不是 Python 多线程，而是一次独立会话的标识。例如，两个用户可以分别使用
``conversation-001`` 和 ``conversation-002``，它们的消息不会混在一起。

快速示例::

    from langchain_core.messages import AIMessage, HumanMessage

    memory = ShortTermMemory(ttl_seconds=3600)
    memory.add_message("conversation-001", HumanMessage(content="你好"))
    memory.add_message("conversation-001", AIMessage(content="你好，有什么可以帮你？"))

    for message in memory.get_messages("conversation-001"):
        print(type(message).__name__, message.content)

注意：
    本类把数据存在当前 Python 进程的内存中。进程退出后数据会消失；如需持久化，应使用
    Redis、PostgreSQL 或 LangGraph 的 Checkpoint 存储。

阅读本文件前需要理解的 Python 语法：

``class ConversationBuffer:``
    使用 ``class`` 定义类。类可以理解为创建对象的“图纸”。

``class ShortTermMemory(BaseMemory):``
    括号里的 ``BaseMemory`` 是父类，表示 ``ShortTermMemory`` 继承父类的属性和接口。

``def add_message(self, message: BaseMessage) -> None:``
    ``def`` 定义函数；写在类中的函数称为方法。``self`` 代表调用该方法的当前对象；
    ``message: BaseMessage`` 是参数类型提示；``-> None`` 表示方法没有返回值。

``name: Optional[str] = None``
    ``Optional[str]`` 表示值可以是字符串，也可以是 ``None``；等号右侧是默认值。

``items: List[BaseMessage] = []``
    冒号后面是类型注解，等号后面才是真正赋给变量的值。

``mapping: Dict[str, Any]``
    表示字典的键是字符串，值可以是任意类型。类型注解主要帮助阅读和静态检查，
    Python 运行时通常不会自动阻止放入其他类型。

``**kwargs``
    两个星号收集调用时未明确列出的关键字参数，并把它们保存成字典。

``if value:``
    这是“真假值判断”。``None``、``False``、数字 ``0``、空字符串和空容器都视为假。

``a if condition else b``
    条件表达式：条件为真时得到 ``a``，否则得到 ``b``。

``items[-n:]``
    列表切片。从倒数第 n 项取到列表末尾，产生一个新列表。

``f"线程 {thread_id}"``
    f-string。花括号中的表达式会先求值，再插入字符串。

``for key, value in mapping.items():``
    遍历字典键值对，并使用“序列解包”一次赋值给两个变量。

``lambda item: item[1]``
    匿名函数，等价于一个只有一条返回表达式的小型 ``def`` 函数。

``[expression for item in items]``
    列表推导式：遍历 ``items``，计算表达式，并产生新列表。

``from .base import BaseMemory``
    开头的点表示相对导入：从当前包中的 ``base.py`` 导入名称。
"""

# ``logging`` 是 Python 标准库，用于输出可按级别控制的运行日志。
import logging
# 从 datetime 模块一次导入两个名称：
# datetime 表示具体时间点，timedelta 表示两个时间点之间的时长。
from datetime import datetime, timedelta
# typing 中的名称只用于描述类型，提高可读性和编辑器提示质量。
from typing import Any, Dict, List, Optional

# ``from 模块 import 名称`` 让下方代码可以直接写 HumanMessage，
# 而不必每次都写 langchain_core.messages.HumanMessage。
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

# ``.base`` 中的点表示 short_term.py 与 base.py 位于同一个 Python 包中。
from .base import BaseMemory, MemoryEntry, MemoryType

# 模块级 logger：调用方可统一配置日志级别和输出位置。
logger = logging.getLogger("mult_agents.memory")


# ``class`` 开始定义一个类；类名通常使用“大驼峰命名法”。
class ConversationBuffer:
    """管理单个对话线程的消息缓冲区。

    ``messages`` 保存仍需原样保留的近期消息；``summary`` 保存被压缩的旧消息。
    当消息数超过 ``max_messages`` 时，类会把较旧消息转成简单文本摘要，只保留最近
    ``summary_threshold`` 条原始消息。

    Args:
        max_messages: 触发压缩前允许保存的最大原始消息数。
        max_tokens: 预期的最大 token 数。目前仅保存该配置，尚未参与自动裁剪。
        summary_threshold: 压缩后保留的最近消息数量。

    Attributes:
        messages: 尚未被压缩的 LangChain 消息对象列表。
        summary: 历史消息的文本摘要；尚未压缩时为 ``None``。
        token_count: 最近一次加消息后按字符数粗略估算的 token 数，不是模型的精确计数。
            当前实现压缩后不会再次计算，因此发生压缩时该值可能暂时高于现存消息的估算值。

    Example:
        下面把上限设为 2，因此加入第 3 条消息时会触发压缩::

            buffer = ConversationBuffer(max_messages=2, summary_threshold=1)
            buffer.add_message(HumanMessage(content="我叫小明"))
            buffer.add_message(AIMessage(content="你好，小明"))
            buffer.add_message(HumanMessage(content="请记住我的名字"))

            print(buffer.summary)       # 前两条消息形成的简易摘要
            print(buffer.messages)      # 只保留最后 1 条原始消息
    """

    def __init__(
        self,
        max_messages: int = 20,
        max_tokens: int = 4000,
        summary_threshold: int = 10,
    ):
        # __init__ 是特殊方法：执行 ConversationBuffer(...) 时会自动调用。
        # self 是刚创建出来的实例，无需由调用方传入。
        # 参数后面的 ``: int`` 是类型提示，``= 20`` 等是默认值。
        # 因此 ConversationBuffer() 使用全部默认值，
        # ConversationBuffer(max_messages=5) 只覆盖其中一个默认值。

        # ``self.xxx`` 是实例属性：每个 ConversationBuffer 都有自己独立的配置和数据。
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.summary_threshold = summary_threshold

        # ``List[BaseMessage]`` 是类型注解，表示列表元素应是 LangChain 消息对象。
        self.messages: List[BaseMessage] = []
        # ``Optional[str]`` 等价于“str 或 None”。
        self.summary: Optional[str] = None
        self.token_count: int = 0

    def add_message(self, message: BaseMessage) -> None:
        """加入一条消息，并在超过数量上限时压缩历史。

        Args:
            message: ``HumanMessage``、``AIMessage``、``SystemMessage`` 等
                ``BaseMessage`` 的子类实例。

        Returns:
            ``None``。消息直接写入当前缓冲区（即修改实例状态）。

        Example::

            buffer = ConversationBuffer()
            buffer.add_message(HumanMessage(content="Python 的列表是什么？"))
        """
        # 点号 ``.`` 用于访问对象的属性或方法。
        # list.append(x) 会原地把一个元素 x 加到列表末尾，不会创建新列表。
        self.messages.append(message)
        # 方法名前虽然有下划线，但仍可调用；下划线只是“请当作内部实现使用”的约定。
        self._update_token_count()

        # 超过上限才压缩；等于上限时仍完整保留消息。
        # len(...) 返回容器元素数量；``>`` 是大于比较运算符。
        if len(self.messages) > self.max_messages:
            self._compress_messages()

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """按顺序批量加入消息。

        这里复用 :meth:`add_message`，因此每加入一条消息都会重新计数，并可能触发压缩。

        Example::

            buffer.add_messages([
                HumanMessage(content="问题"),
                AIMessage(content="回答"),
            ])
        """
        # for 循环依次把 messages 中的每个元素赋给局部变量 msg。
        for msg in messages:
            self.add_message(msg)

    def get_messages(
        self,
        include_summary: bool = True,
        last_n: Optional[int] = None,
    ) -> List[BaseMessage]:
        """读取消息，并可把历史摘要放在结果开头。

        Args:
            include_summary: 为 ``True`` 且存在摘要时，将摘要包装为
                ``SystemMessage`` 放到返回列表的第一项。
            last_n: 只取最近 N 条原始消息。``None`` 或 ``0`` 表示不限制。

        Returns:
            新的消息列表。修改返回列表本身不会改变 ``self.messages``。

        Example::

            recent = buffer.get_messages(include_summary=True, last_n=3)
            for message in recent:
                print(message.content)
        """
        # result 是局部变量，只在本次方法调用期间存在。
        # 空列表 [] 是可变对象，后面会通过 append/extend 修改它。
        result: List[BaseMessage] = []

        # 摘要使用 SystemMessage，告诉模型这是背景信息而非用户的新问题。
        # ``and`` 具有短路特性：include_summary 为假时，不再检查 self.summary。
        if include_summary and self.summary:
            # 先创建 SystemMessage 对象，再将它添加到 result。
            result.append(SystemMessage(content=f"历史对话摘要：{self.summary}"))

        # 此处先让两个变量指向同一列表。下方发生切片时，才会得到新列表。
        messages_to_return = self.messages
        # Python 中 None 和 0 都是假值；所以 last_n=0 与“不限制”行为相同。
        if last_n:
            # ``[-last_n:]`` 是切片语法，表示从倒数第 N 项一直取到末尾。
            messages_to_return = self.messages[-last_n:]

        # extend 会逐项加入；若使用 append，则会把整个列表当成一个元素。
        result.extend(messages_to_return)
        # return 立即结束函数，并把 result 交给调用方。
        return result

    def clear(self) -> None:
        """清空消息、摘要和 token 估算值。

        Example::

            buffer.clear()
            assert buffer.get_messages() == []
        """
        # 这里是“重新绑定”：让 self.messages 指向一个新的空列表。
        # 它不同于 self.messages.clear()；若外部保存了旧列表引用，旧列表不会被清空。
        self.messages = []
        self.summary = None
        self.token_count = 0

    def _update_token_count(self) -> None:
        """重新估算当前原始消息的 token 数。

        方法名前的单下划线表示“内部实现方法”，调用方通常不应直接使用。
        这里假定平均每两个字符约为一个 token，只适合控制大致规模；若需要精确计费或
        上下文限制，应改用目标模型对应的 tokenizer。
        """
        # 生成器表达式逐条计算内容长度，sum 再把长度相加，避免创建临时列表。
        # 从内向外阅读：
        # 1. msg.content 取得一条消息的内容；
        # 2. str(...) 确保内容可以按字符串处理；
        # 3. len(...) 取得字符数量；
        # 4. ``for msg in self.messages`` 依次产生每条消息的字符数；
        # 5. sum(...) 把所有字符数相加。
        # 括号内这种按需产生值的写法叫“生成器表达式”。
        total_chars = sum(len(str(msg.content)) for msg in self.messages)
        # ``//`` 是整除运算，例如 5 // 2 == 2。
        self.token_count = total_chars // 2

    def _compress_messages(self) -> None:
        """把旧消息转成简易摘要，保留最近的原始消息。

        当前实现并未调用 LLM 做语义总结，而是截取每条旧消息的前 100 个字符。
        其优点是快速、无额外费用；缺点是摘要可能不够自然，也可能遗漏重要信息。
        """
        # 防御性检查：如果消息还不够多，就不执行压缩。
        # <= 表示“小于或等于”。
        if len(self.messages) <= self.summary_threshold:
            # 单独的 return 不携带返回值，实际返回 None，并立刻停止执行本方法。
            return

        # 前半部分进入摘要，后 summary_threshold 条继续以原始消息形式保留。
        # ``[:-n]`` 表示从开头取到倒数第 n 项之前，不包含倒数第 n 项。
        messages_to_summarize = self.messages[:-self.summary_threshold]
        # ``[-n:]`` 表示最后 n 项。
        self.messages = self.messages[-self.summary_threshold:]

        summary_parts: List[str] = []
        for msg in messages_to_summarize:
            # isinstance 用于判断对象是否是指定类（或其子类）的实例。
            # isinstance(对象, 类型) 检查对象是否属于该类或其子类。
            # 下一行使用三元条件表达式，根据判断结果选择两个字符串之一。
            role = "用户" if isinstance(msg, HumanMessage) else "AI"
            content_preview = str(msg.content)[:100]
            # f-string 在运行时把 role 和 content_preview 的值插入花括号位置。
            summary_parts.append(f"{role}: {content_preview}...")

        # 用换行符拼接多个字符串片段。
        new_summary = "\n".join(summary_parts)

        # 空字符串和 None 都是假值；有实际文字的字符串是真值。
        if self.summary:
            # 保留上一次摘要，再追加本次新压缩的内容。
            self.summary = f"{self.summary}\n\n[更早的对话]\n{new_summary}"
        else:
            self.summary = new_summary

        logger.debug("消息历史已压缩，当前消息数: %s", len(self.messages))


# 括号中的 BaseMemory 表示继承。父类规定统一接口，子类提供短期记忆的具体实现。
class ShortTermMemory(BaseMemory):
    """用内存管理多个对话线程的短期记忆。

    每个 ``thread_id`` 对应一个独立的 :class:`ConversationBuffer`。读取或写入线程时会
    更新 ``last_access``；超过 ``ttl_seconds`` 未访问的线程，会在下一次清理时删除。

    Args:
        ttl_seconds: 一个线程自最后访问起可存活的秒数，默认 3600 秒。
        max_threads: 最多保留的线程数。超限时优先删除最久未访问的线程。

    Example::

        memory = ShortTermMemory(ttl_seconds=600, max_threads=100)
        memory.add_message(
            thread_id="user-42-chat-1",
            message=HumanMessage(content="我喜欢简洁的回答"),
            metadata={"language": "zh-CN"},
        )

        messages = memory.get_messages("user-42-chat-1")
        metadata = memory.get_thread_metadata("user-42-chat-1")
    """

    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_threads: int = 100,
    ):
        # super() 调用父类 BaseMemory 的初始化逻辑，声明该实现属于短期记忆。
        # super() 取得“当前类的父类代理”，然后调用父类的 __init__。
        # MemoryType.SHORT_TERM 是枚举成员，不是普通字符串。
        super().__init__(MemoryType.SHORT_TERM)
        self.ttl_seconds = ttl_seconds
        self.max_threads = max_threads

        # 嵌套字典结构：
        # {
        #     thread_id: {
        #         "buffer": ConversationBuffer,
        #         "metadata": dict,
        #         "created_at": datetime,
        #         "last_access": datetime,
        #     }
        # }
        # 外层 Dict 的键是 thread_id 字符串，值又是一个字典。
        # Any 表示内层值可能是 buffer、datetime、dict 等不同类型。
        self._storage: Dict[str, Dict[str, Any]] = {}
        # 变量可以保存 BaseCheckpointSaver 实例或 None；初始时尚未配置，所以为 None。
        self._checkpointer: Optional[BaseCheckpointSaver] = None

    def set_checkpointer(self, checkpointer: BaseCheckpointSaver) -> None:
        """保存 LangGraph Checkpoint 存储器的引用。

        当前类只负责保存引用，尚未直接调用 checkpointer。调用方可在后续集成 LangGraph
        StateGraph 时取用或扩展这里的逻辑。

        Example::

            from langgraph.checkpoint.memory import MemorySaver

            memory.set_checkpointer(MemorySaver())
        """
        # 赋值只保存对象引用，并不会复制 checkpointer 对象。
        self._checkpointer = checkpointer

    def get_or_create_buffer(self, thread_id: str) -> ConversationBuffer:
        """取得线程缓冲区；线程不存在时自动创建。

        这是“惰性创建”：只有某个线程第一次真正被使用时，才为它分配缓冲区。

        Example::

            buffer = memory.get_or_create_buffer("chat-001")
            buffer.add_message(HumanMessage(content="你好"))
        """
        # 每次创建/获取前顺便清理过期和超量线程。
        self._cleanup_expired()

        # ``x not in 字典`` 检查 x 是否不是该字典的键。
        if thread_id not in self._storage:
            # now 是局部变量；创建和最后访问使用同一个精确时间点。
            now = datetime.now()
            # 通过 ``字典[键] = 值`` 新建或覆盖一个键值对。
            self._storage[thread_id] = {
                "buffer": ConversationBuffer(),
                "metadata": {},
                "created_at": now,
                "last_access": now,
            }
            logger.debug("为新线程 %s 创建短期记忆缓冲区", thread_id)
        else:
            # else 只会在线程已经存在时执行。
            self._storage[thread_id]["last_access"] = datetime.now()

        # 连续两次方括号索引：先取得线程字典，再取得其中的 buffer。
        return self._storage[thread_id]["buffer"]

    def add_message(
        self,
        thread_id: str,
        message: BaseMessage,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """向指定线程加入一条 LangChain 消息。

        Args:
            thread_id: 对话线程的唯一标识。
            message: 要保存的 LangChain 消息对象。
            metadata: 可选的线程级元数据；会与已有字典合并，同名键会被新值覆盖。

        Example::

            memory.add_message(
                "chat-001",
                AIMessage(content="短期记忆用于保存当前会话上下文。"),
                metadata={"model": "example-model"},
            )
        """
        buffer = self.get_or_create_buffer(thread_id)
        buffer.add_message(message)

        # metadata 为 None 或空字典时不更新；非空字典时进入分支。
        if metadata:
            # dict.update 合并键值；例如 {"a": 1}.update({"a": 2}) 后 a 为 2。
            self._storage[thread_id]["metadata"].update(metadata)

        logger.debug("消息已添加到线程 %s 的短期记忆", thread_id)

    def get_messages(
        self,
        thread_id: str,
        include_summary: bool = True,
        last_n: Optional[int] = None,
    ) -> List[BaseMessage]:
        """读取指定线程的消息历史。

        不存在的线程返回空列表，而不是抛出异常。成功读取时会刷新该线程的最后访问时间。

        Example::

            latest_two = memory.get_messages("chat-001", last_n=2)
        """
        if thread_id not in self._storage:
            # 用空列表表示“没有消息”，调用方无需捕获 KeyError。
            return []

        self._storage[thread_id]["last_access"] = datetime.now()
        buffer = self._storage[thread_id]["buffer"]
        # 使用 ``参数名=值`` 传参叫关键字参数，含义比只按位置传参更清楚。
        return buffer.get_messages(include_summary=include_summary, last_n=last_n)

    def get_thread_metadata(self, thread_id: str) -> Dict[str, Any]:
        """返回线程元数据的浅拷贝。

        返回副本可防止调用方直接修改内部字典；若需修改，请使用
        :meth:`update_thread_metadata`。
        """
        if thread_id not in self._storage:
            return {}
        # dict.copy() 创建浅拷贝：最外层字典独立，但其中嵌套的可变对象仍然共享。
        return self._storage[thread_id]["metadata"].copy()

    def update_thread_metadata(
        self,
        thread_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        """创建线程（如有需要）并合并线程元数据。

        Example::

            memory.update_thread_metadata("chat-001", {"topic": "Python"})
        """
        # 调用该方法既确保线程存在，也刷新 last_access。
        self.get_or_create_buffer(thread_id)
        self._storage[thread_id]["metadata"].update(metadata)

    def clear_thread(self, thread_id: str) -> bool:
        """删除一个线程的缓冲区和元数据。

        Returns:
            找到并删除时返回 ``True``；线程原本不存在时返回 ``False``。
        """
        if thread_id in self._storage:
            # del 删除字典中的指定键以及它所关联的值。
            del self._storage[thread_id]
            logger.debug("线程 %s 的短期记忆已清空", thread_id)
            return True
        return False

    def list_active_threads(self) -> List[str]:
        """清理过期数据后，返回仍然活跃的所有线程 ID。

        Example::

            print(memory.list_active_threads())
        """
        self._cleanup_expired()
        # keys() 返回字典键视图；list(...) 将其转换成普通列表。
        return list(self._storage.keys())

    # 以下方法实现 BaseMemory 定义的统一接口，使短期记忆可以和其他记忆后端互换。

    def save(self, entry: MemoryEntry) -> str:
        """把通用 ``MemoryEntry`` 转成 LangChain 消息并保存。

        转换规则：

        - 字符串内容 -> ``HumanMessage``；
        - 字典且 ``role == "ai"`` -> ``AIMessage``；
        - 其他字典或其他类型 -> ``HumanMessage``。

        Example::

            entry = MemoryEntry(
                content={"role": "ai", "content": "你好"},
                memory_type=MemoryType.SHORT_TERM,
                thread_id="chat-001",
            )
            saved_id = memory.save(entry)
        """
        # ``or`` 提供默认值：thread_id 是 None 或空字符串时使用 "default"。
        # ``or`` 返回第一个真值。entry.thread_id 为 None 或空字符串时使用 default。
        thread_id = entry.thread_id or "default"
        buffer = self.get_or_create_buffer(thread_id)

        # if / elif / else 中只会执行第一个条件为真的分支。
        if isinstance(entry.content, str):
            message = HumanMessage(content=entry.content)
        elif isinstance(entry.content, dict):
            # dict.get(key, default) 在键不存在时返回默认值，不抛出 KeyError。
            content = entry.content.get("content", "")
            role = entry.content.get("role", "human")
            if role == "ai":
                message = AIMessage(content=content)
            else:
                message = HumanMessage(content=content)
        else:
            # 对其他类型使用 str 转换，确保消息 content 可被文本方式保存。
            message = HumanMessage(content=str(entry.content))

        buffer.add_message(message)

        if entry.metadata:
            self._storage[thread_id]["metadata"].update(entry.metadata)

        return entry.id

    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """按记忆 ID 获取数据；当前内存结构不支持此操作，固定返回 ``None``。

        ``memory_id`` 参数是为了满足 ``BaseMemory`` 的统一接口而保留的。
        """
        return None

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        namespace: Optional[str] = None,
        limit: int = 5,
        **kwargs: Any,
    ) -> List[MemoryEntry]:
        """把指定线程最近的消息包装成 ``MemoryEntry`` 列表。

        这是一个简化的“搜索”：当前实现不会比较 ``query`` 与消息文本，只返回最近
        ``limit`` 条。因此它更接近“读取最近记录”，而不是关键词或语义检索。

        Args:
            query: 为兼容统一搜索接口而保留，当前实现未使用。
            user_id: 写入返回条目的用户 ID。
            namespace: 用作线程 ID；未提供时读取 ``default`` 线程。
            limit: 最多返回多少条最近消息。
            **kwargs: 兼容未来扩展的额外关键字参数。

        Example::

            recent = memory.search(
                query="Python", namespace="chat-001", limit=3
            )
        """
        thread_id = namespace or "default"
        # 这里第二个参数使用位置传参，第三个使用关键字传参。
        messages = self.get_messages(thread_id, include_summary=False)

        entries: List[MemoryEntry] = []
        # 只遍历切片得到的最近 limit 条消息。
        for msg in messages[-limit:]:
            entry = MemoryEntry(
                content=msg.content,
                memory_type=MemoryType.SHORT_TERM,
                thread_id=thread_id,
                user_id=user_id,
                # 花括号构造字典；字典值由条件表达式决定。
                metadata={"role": "ai" if isinstance(msg, AIMessage) else "human"},
            )
            entries.append(entry)

        return entries

    def delete(self, memory_id: str) -> bool:
        """按记忆 ID 删除数据；当前实现不支持，固定返回 ``False``。"""
        return False

    def clear(
        self,
        user_id: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> int:
        """清除指定线程或全部短期记忆。

        Args:
            user_id: 为兼容统一接口而保留，当前内存实现未按用户过滤。
            namespace: 要清除的线程 ID；不提供时清除全部线程。

        Returns:
            删除的线程数量，而不是消息数量。

        Example::

            memory.clear(namespace="chat-001")  # 删除一个线程
            memory.clear()                      # 删除全部线程
        """
        if namespace:
            # 用布尔结果选择整数返回值：删除成功返回 1，否则返回 0。
            return 1 if self.clear_thread(namespace) else 0

        count = len(self._storage)
        self._storage.clear()
        logger.info("已清除所有短期记忆，共 %s 个线程", count)
        return count

    def list_namespaces(self, user_id: Optional[str] = None) -> List[str]:
        """返回所有活跃线程 ID。

        在这个实现中，“namespace（命名空间）”与 ``thread_id`` 表示同一概念。
        ``user_id`` 仅为兼容 ``BaseMemory`` 接口而保留。
        """
        return self.list_active_threads()

    def _cleanup_expired(self) -> None:
        """删除 TTL 已过期的线程，并把线程总数控制在上限内。

        清理分两步：

        1. 找出 ``now - last_access > ttl_seconds`` 的线程；
        2. 如果总数仍超过 ``max_threads``，再选择最久未访问的线程删除。

        这是“访问时清理”而非后台定时清理：只有调用相关公开方法时才会执行。
        """
        now = datetime.now()
        expired_threads: List[str] = []

        # items() 产生 (键, 值) 二元组；左侧两个变量会自动解包。
        for thread_id, data in self._storage.items():
            # 如果旧数据没有 last_access，就回退到 created_at；两者都没有则使用 now。
            last_access = data.get("last_access", data.get("created_at", now))
            # datetime 相减得到 timedelta，再与允许存活的 timedelta 比较。
            if now - last_access > timedelta(seconds=self.ttl_seconds):
                expired_threads.append(thread_id)

        if len(self._storage) > self.max_threads:
            # sorted 返回新列表，不会改变原字典。key 函数指定按最后访问时间升序排列。
            sorted_threads = sorted(
                self._storage.items(),
                # lambda 定义匿名函数。每个 item 是 (thread_id, data)：
                # item[1] 取得 data 字典，并从中读取用于排序的时间。
                key=lambda item: item[1].get(
                    "last_access", item[1].get("created_at", now)
                ),
            )
            threads_to_remove = len(self._storage) - self.max_threads
            # 这是生成器表达式：
            # sorted_threads 切片中的每项都是二元组；
            # ``thread_id, _`` 将其解包，下划线表示第二个值有意不用；
            # 表达式最终依次产生 thread_id。
            expired_threads.extend(
                thread_id
                for thread_id, _ in sorted_threads[:threads_to_remove]
            )

        # set 去重：某个线程可能既 TTL 过期，又属于超限清理对象。
        # set 是集合：元素不重复，所以能去掉列表中的重复 thread_id。
        unique_expired_threads = set(expired_threads)
        for thread_id in unique_expired_threads:
            del self._storage[thread_id]

        if unique_expired_threads:
            logger.debug("已清理 %s 个过期或超量线程", len(unique_expired_threads))
