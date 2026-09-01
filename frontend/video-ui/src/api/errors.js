const DEFAULT_ERROR_MESSAGES = {
  NETWORK_ERROR: '网络连接失败，请检查网络后重试',
  TIMEOUT: '请求超时，请稍后重试',
  AUTHENTICATION_REQUIRED: '登录状态已失效，请重新登录',
  PERMISSION_DENIED: '没有权限执行此操作',
  NOT_FOUND: '请求的内容不存在',
  INTERNAL_SERVER_ERROR: '服务器暂时无法处理请求，请稍后重试'
};

const ERROR_CODES = {
  400: 'VALIDATION_ERROR',
  401: 'AUTHENTICATION_REQUIRED',
  403: 'PERMISSION_DENIED',
  404: 'NOT_FOUND',
  405: 'METHOD_NOT_ALLOWED',
  408: 'REQUEST_TIMEOUT',
  409: 'CONFLICT',
  429: 'RATE_LIMITED'
};

function errorCodeForStatus(status) {
  if (ERROR_CODES[status]) {
    return ERROR_CODES[status];
  }
  return status >= 500 ? 'INTERNAL_SERVER_ERROR' : 'REQUEST_FAILED';
}

/**
 * Convert API, legacy API, Axios and network failures into one client shape.
 * This function is deliberately free of Axios/browser dependencies so it can
 * be tested independently from the request client and Vue runtime.
 */
export function normalizeApiError(error) {
  const response = error?.response;
  const data = response?.data;
  const nested = data?.error;
  const status = response?.status;
  const code = nested?.code || data?.code || (status ? errorCodeForStatus(status) : null)
    || (error?.code === 'ECONNABORTED' ? 'TIMEOUT' : null)
    || (!response ? 'NETWORK_ERROR' : 'REQUEST_FAILED');
  const fields = nested?.fields || data?.fields || (data && typeof data === 'object' ? data : {});
  const meta = nested?.meta || data?.meta || {};
  const message = status >= 500
    ? DEFAULT_ERROR_MESSAGES.INTERNAL_SERVER_ERROR
    : nested?.message || data?.message || data?.detail || data?.error
      || DEFAULT_ERROR_MESSAGES[code] || error?.message || '请求失败';

  return {
    code,
    fields: fields && typeof fields === 'object' ? fields : {},
    meta: meta && typeof meta === 'object' ? meta : {},
    message,
    requestId: nested?.request_id || response?.headers?.['x-request-id'] || null,
    httpStatus: status || null,
    nested
  };
}

export { DEFAULT_ERROR_MESSAGES };
