import { io } from 'socket.io-client';

import { socket, activeUserIds, USAGE_POOL } from '$lib/stores';
import { WEBUI_BASE_URL } from '$lib/constants';

/**
 * 设置WebSocket连接
 * 
 * 建立与后端服务器的Socket.IO连接，并设置各种事件监听器
 * 
 * @param enableWebsocket - 是否优先使用WebSocket传输，若为false则先尝试长轮询再回退到WebSocket
 */
export const setupSocket = async (enableWebsocket) => {
	// 创建Socket.IO客户端实例，连接到服务器
	const _socket = io(`${WEBUI_BASE_URL}` || undefined, {
		reconnection: true,                  // 启用自动重连
		reconnectionDelay: 1000,             // 重连延迟初始值(毫秒)
		reconnectionDelayMax: 5000,          // 重连延迟最大值(毫秒)
		randomizationFactor: 0.5,            // 重连延迟随机因子
		path: '/ws/socket.io',               // Socket.IO服务器路径
		transports: enableWebsocket ? ['websocket'] : ['polling', 'websocket'], // 传输方式
		auth: { token: localStorage.token }  // 认证信息
	});

	// 更新全局socket存储
	await socket.set(_socket);

	// 连接错误事件处理
	_socket.on('connect_error', (err) => {
		console.log('connect_error', err);
	});

	// 连接成功事件处理
	_socket.on('connect', () => {
		console.log('connected', _socket.id);
	});

	// 重连尝试事件处理
	_socket.on('reconnect_attempt', (attempt) => {
		console.log('reconnect_attempt', attempt);
	});

	// 重连失败事件处理
	_socket.on('reconnect_failed', () => {
		console.log('reconnect_failed');
	});

	// 断开连接事件处理
	_socket.on('disconnect', (reason, details) => {
		console.log(`Socket ${_socket.id} disconnected due to ${reason}`);
		if (details) {
			console.log('Additional details:', details);
		}
	});

	// 接收用户列表事件处理
	// 服务器发送在线用户列表更新时触发
	_socket.on('user-list', (data) => {
		console.log('user-list', data);
		activeUserIds.set(data.user_ids);
	});

	// 接收资源使用情况事件处理
	// 服务器发送模型使用情况统计更新时触发
	_socket.on('usage', (data) => {
		console.log('usage', data);
		USAGE_POOL.set(data['models']);
	});
};
