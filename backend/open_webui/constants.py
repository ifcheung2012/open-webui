from enum import Enum  # 导入枚举类型，用于创建常量集合


class MESSAGES(str, Enum):
    """
    成功消息常量枚举
    
    包含应用程序中使用的各种成功提示消息，这些消息会显示给用户。
    每个常量都是一个lambda函数，可以接受参数以生成格式化的消息字符串。
    """
    DEFAULT = lambda msg="": f"{msg if msg else ''}"  # 默认消息，可选地接受一个消息字符串
    MODEL_ADDED = lambda model="": f"The model '{model}' has been added successfully."  # 模型添加成功的消息
    MODEL_DELETED = (
        lambda model="": f"The model '{model}' has been deleted successfully."  # 模型删除成功的消息
    )


class WEBHOOK_MESSAGES(str, Enum):
    """
    Webhook消息常量枚举
    
    包含发送到webhook的各种通知消息，用于集成外部系统和通知。
    每个常量都是一个lambda函数，可以接受参数以生成格式化的消息字符串。
    """
    DEFAULT = lambda msg="": f"{msg if msg else ''}"  # 默认webhook消息
    USER_SIGNUP = lambda username="": (
        f"New user signed up: {username}" if username else "New user signed up"  # 用户注册通知消息
    )


class ERROR_MESSAGES(str, Enum):
    """
    错误消息常量枚举
    
    包含应用程序中使用的各种错误提示消息，这些消息会在发生错误时显示给用户。
    提供了友好且信息丰富的错误提示，帮助用户理解问题并采取适当的行动。
    """
    def __str__(self) -> str:
        """
        重写枚举的字符串表示方法
        
        Returns:
            str: 枚举值的字符串表示
        """
        return super().__str__()

    DEFAULT = (
        lambda err="": f'{"Something went wrong :/" if err == "" else "[ERROR: " + str(err) + "]"}'  # 默认错误消息
    )
    ENV_VAR_NOT_FOUND = "Required environment variable not found. Terminating now."  # 环境变量未找到错误
    CREATE_USER_ERROR = "Oops! Something went wrong while creating your account. Please try again later. If the issue persists, contact support for assistance."  # 创建用户错误
    DELETE_USER_ERROR = "Oops! Something went wrong. We encountered an issue while trying to delete the user. Please give it another shot."  # 删除用户错误
    EMAIL_MISMATCH = "Uh-oh! This email does not match the email your provider is registered with. Please check your email and try again."  # 邮箱不匹配错误
    EMAIL_TAKEN = "Uh-oh! This email is already registered. Sign in with your existing account or choose another email to start anew."  # 邮箱已被占用错误
    USERNAME_TAKEN = (
        "Uh-oh! This username is already registered. Please choose another username."  # 用户名已被占用错误
    )
    PASSWORD_TOO_LONG = "Uh-oh! The password you entered is too long. Please make sure your password is less than 72 bytes long."  # 密码过长错误
    COMMAND_TAKEN = "Uh-oh! This command is already registered. Please choose another command string."  # 命令已被占用错误
    FILE_EXISTS = "Uh-oh! This file is already registered. Please choose another file."  # 文件已存在错误

    ID_TAKEN = "Uh-oh! This id is already registered. Please choose another id string."  # ID已被占用错误
    MODEL_ID_TAKEN = "Uh-oh! This model id is already registered. Please choose another model id string."  # 模型ID已被占用错误
    NAME_TAG_TAKEN = "Uh-oh! This name tag is already registered. Please choose another name tag string."  # 名称标签已被占用错误

    INVALID_TOKEN = (
        "Your session has expired or the token is invalid. Please sign in again."  # 无效令牌错误
    )
    INVALID_CRED = "The email or password provided is incorrect. Please check for typos and try logging in again."  # 无效凭据错误
    INVALID_EMAIL_FORMAT = "The email format you entered is invalid. Please double-check and make sure you're using a valid email address (e.g., yourname@example.com)."  # 无效邮箱格式错误
    INVALID_PASSWORD = (
        "The password provided is incorrect. Please check for typos and try again."  # 无效密码错误
    )
    INVALID_TRUSTED_HEADER = "Your provider has not provided a trusted header. Please contact your administrator for assistance."  # 无效信任头错误

    EXISTING_USERS = "You can't turn off authentication because there are existing users. If you want to disable WEBUI_AUTH, make sure your web interface doesn't have any existing users and is a fresh installation."  # 已存在用户错误，无法关闭认证

    UNAUTHORIZED = "401 Unauthorized"  # 未授权错误
    ACCESS_PROHIBITED = "You do not have permission to access this resource. Please contact your administrator for assistance."  # 访问禁止错误
    ACTION_PROHIBITED = (
        "The requested action has been restricted as a security measure."  # 操作被禁止错误
    )

    FILE_NOT_SENT = "FILE_NOT_SENT"  # 文件未发送错误
    FILE_NOT_SUPPORTED = "Oops! It seems like the file format you're trying to upload is not supported. Please upload a file with a supported format and try again."  # 文件格式不支持错误

    NOT_FOUND = "We could not find what you're looking for :/"  # 资源未找到错误
    USER_NOT_FOUND = "We could not find what you're looking for :/"  # 用户未找到错误
    API_KEY_NOT_FOUND = "Oops! It looks like there's a hiccup. The API key is missing. Please make sure to provide a valid API key to access this feature."  # API密钥未找到错误
    API_KEY_NOT_ALLOWED = "Use of API key is not enabled in the environment."  # API密钥使用未启用错误

    MALICIOUS = "Unusual activities detected, please try again in a few minutes."  # 异常活动检测错误

    PANDOC_NOT_INSTALLED = "Pandoc is not installed on the server. Please contact your administrator for assistance."  # Pandoc未安装错误
    INCORRECT_FORMAT = (
        lambda err="": f"Invalid format. Please use the correct format{err}"  # 格式不正确错误
    )
    RATE_LIMIT_EXCEEDED = "API rate limit exceeded"  # API请求频率限制错误

    MODEL_NOT_FOUND = lambda name="": f"Model '{name}' was not found"  # 模型未找到错误
    OPENAI_NOT_FOUND = lambda name="": "OpenAI API was not found"  # OpenAI API未找到错误
    OLLAMA_NOT_FOUND = "WebUI could not connect to Ollama"  # Ollama连接失败错误
    CREATE_API_KEY_ERROR = "Oops! Something went wrong while creating your API key. Please try again later. If the issue persists, contact support for assistance."  # 创建API密钥错误
    API_KEY_CREATION_NOT_ALLOWED = "API key creation is not allowed in the environment."  # API密钥创建未允许错误

    EMPTY_CONTENT = "The content provided is empty. Please ensure that there is text or data present before proceeding."  # 内容为空错误

    DB_NOT_SQLITE = "This feature is only available when running with SQLite databases."  # 非SQLite数据库错误

    INVALID_URL = (
        "Oops! The URL you provided is invalid. Please double-check and try again."  # 无效URL错误
    )

    WEB_SEARCH_ERROR = (
        lambda err="": f"{err if err else 'Oops! Something went wrong while searching the web.'}"  # 网络搜索错误
    )

    OLLAMA_API_DISABLED = (
        "The Ollama API is disabled. Please enable it to use this feature."  # Ollama API已禁用错误
    )

    FILE_TOO_LARGE = (
        lambda size="": f"Oops! The file you're trying to upload is too large. Please upload a file that is less than {size}."  # 文件过大错误
    )

    DUPLICATE_CONTENT = (
        "Duplicate content detected. Please provide unique content to proceed."  # 重复内容错误
    )
    FILE_NOT_PROCESSED = "Extracted content is not available for this file. Please ensure that the file is processed before proceeding."  # 文件未处理错误


class TASKS(str, Enum):
    """
    任务类型常量枚举
    
    定义了应用程序中可用的各种AI生成任务类型。
    这些任务类型用于标识不同的生成功能，如标题生成、跟进生成等。
    """
    def __str__(self) -> str:
        """
        重写枚举的字符串表示方法
        
        Returns:
            str: 任务类型的字符串表示
        """
        return super().__str__()

    DEFAULT = lambda task="": f"{task if task else 'generation'}"  # 默认任务类型
    TITLE_GENERATION = "title_generation"  # 标题生成任务
    FOLLOW_UP_GENERATION = "follow_up_generation"  # 跟进问题生成任务
    TAGS_GENERATION = "tags_generation"  # 标签生成任务
    EMOJI_GENERATION = "emoji_generation"  # 表情符号生成任务
    QUERY_GENERATION = "query_generation"  # 查询生成任务
    IMAGE_PROMPT_GENERATION = "image_prompt_generation"  # 图像提示生成任务
    AUTOCOMPLETE_GENERATION = "autocomplete_generation"  # 自动完成生成任务
    FUNCTION_CALLING = "function_calling"  # 函数调用任务
    MOA_RESPONSE_GENERATION = "moa_response_generation"  # MOA响应生成任务
