import { browser, dev } from '$app/environment';
// import { version } from '../../package.json';

/**
 * 应用名称常量
 * 定义了整个Web UI的应用名称
 */
export const APP_NAME = 'Open WebUI';

/**
 * WebUI主机名
 * 根据环境(开发/生产)和运行位置(浏览器/服务器)动态设置主机名
 */
export const WEBUI_HOSTNAME = browser ? (dev ? `${location.hostname}:8080` : ``) : '';
/**
 * WebUI基础URL
 * 用于构建完整的API路径，开发环境使用http协议
 */
export const WEBUI_BASE_URL = browser ? (dev ? `http://${WEBUI_HOSTNAME}` : ``) : ``;
/**
 * WebUI API基础URL
 * 所有自定义API的基础路径
 */
export const WEBUI_API_BASE_URL = `${WEBUI_BASE_URL}/api/v1`;

/**
 * Ollama API基础URL
 * 用于与Ollama服务通信的API路径
 */
export const OLLAMA_API_BASE_URL = `${WEBUI_BASE_URL}/ollama`;
/**
 * OpenAI兼容API基础URL
 * 提供OpenAI兼容接口的API路径
 */
export const OPENAI_API_BASE_URL = `${WEBUI_BASE_URL}/openai`;
/**
 * 音频处理API基础URL
 * 用于语音转文本、文本转语音等功能
 */
export const AUDIO_API_BASE_URL = `${WEBUI_BASE_URL}/api/v1/audio`;
/**
 * 图像生成和处理API基础URL
 * 用于图像生成、编辑等功能
 */
export const IMAGES_API_BASE_URL = `${WEBUI_BASE_URL}/api/v1/images`;
/**
 * 检索API基础URL
 * 用于知识库检索、RAG等功能
 */
export const RETRIEVAL_API_BASE_URL = `${WEBUI_BASE_URL}/api/v1/retrieval`;

/**
 * WebUI版本号
 * 从构建环境变量中获取
 */
export const WEBUI_VERSION = APP_VERSION;
/**
 * WebUI构建哈希值
 * 从构建环境变量中获取，用于标识具体构建版本
 */
export const WEBUI_BUILD_HASH = APP_BUILD_HASH;
/**
 * 所需的Ollama最低版本
 * 确保兼容性的Ollama版本要求
 */
export const REQUIRED_OLLAMA_VERSION = '0.1.16';

/**
 * 支持的文件MIME类型列表
 * 定义了系统可以处理的文件类型，用于上传验证和处理
 */
export const SUPPORTED_FILE_TYPE = [
	'application/epub+zip',
	'application/pdf',
	'text/plain',
	'text/csv',
	'text/xml',
	'text/html',
	'text/x-python',
	'text/css',
	'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
	'application/octet-stream',
	'application/x-javascript',
	'text/markdown',
	'audio/mpeg',
	'audio/wav',
	'audio/ogg',
	'audio/x-m4a'
];

/**
 * 支持的文件扩展名列表
 * 定义了系统可以处理的文件扩展名，用于上传验证和处理
 */
export const SUPPORTED_FILE_EXTENSIONS = [
	'md',
	'rst',
	'go',
	'py',
	'java',
	'sh',
	'bat',
	'ps1',
	'cmd',
	'js',
	'ts',
	'css',
	'cpp',
	'hpp',
	'h',
	'c',
	'cs',
	'htm',
	'html',
	'sql',
	'log',
	'ini',
	'pl',
	'pm',
	'r',
	'dart',
	'dockerfile',
	'env',
	'php',
	'hs',
	'hsc',
	'lua',
	'nginxconf',
	'conf',
	'm',
	'mm',
	'plsql',
	'perl',
	'rb',
	'rs',
	'db2',
	'scala',
	'bash',
	'swift',
	'vue',
	'svelte',
	'doc',
	'docx',
	'pdf',
	'csv',
	'txt',
	'xls',
	'xlsx',
	'pptx',
	'ppt',
	'msg'
];

/**
 * 粘贴文本的字符限制
 * 限制用户粘贴到聊天输入框的文本长度
 */
export const PASTED_TEXT_CHARACTER_LIMIT = 1000;

// Source: https://kit.svelte.dev/docs/modules#$env-static-public
// This feature, akin to $env/static/private, exclusively incorporates environment variables
// that are prefixed with config.kit.env.publicPrefix (usually set to PUBLIC_).
// Consequently, these variables can be securely exposed to client-side code.
