import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { normalizeApiError } from '../src/api/errors.js';

test('normalizes the canonical API error envelope', () => {
  const result = normalizeApiError({
    response: {
      status: 422,
      data: {
        success: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: '参数校验失败',
          fields: { title: ['必填'] },
          request_id: 'req-422'
        }
      }
    }
  });

  assert.equal(result.code, 'VALIDATION_ERROR');
  assert.equal(result.message, '参数校验失败');
  assert.deepEqual(result.fields, { title: ['必填'] });
  assert.equal(result.requestId, 'req-422');
  assert.equal(result.httpStatus, 422);
});

test('keeps legacy field errors available to callers', () => {
  const result = normalizeApiError({
    response: {
      status: 400,
      data: { title: ['标题不能为空'] }
    }
  });

  assert.equal(result.code, 'VALIDATION_ERROR');
  assert.deepEqual(result.fields, { title: ['标题不能为空'] });
});

test('keeps authentication control metadata available to callers', () => {
  const result = normalizeApiError({
    response: {
      status: 400,
      data: {
        success: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: '请输入验证码',
          fields: {},
          meta: { show_captcha: true },
          request_id: 'req-captcha'
        }
      }
    }
  });

  assert.deepEqual(result.meta, { show_captcha: true });
});

test('hides server details and classifies transport failures', () => {
  const serverError = normalizeApiError({
    response: {
      status: 500,
      data: { detail: 'database password must not leak' }
    }
  });
  const timeout = normalizeApiError({ code: 'ECONNABORTED', message: 'timeout' });

  assert.equal(serverError.code, 'INTERNAL_SERVER_ERROR');
  assert.equal(serverError.message, '服务器暂时无法处理请求，请稍后重试');
  assert.doesNotMatch(serverError.message, /password/);
  assert.equal(timeout.code, 'TIMEOUT');
  assert.equal(timeout.httpStatus, null);
});

test('refresh requests use the shared service instead of a raw Axios call', async () => {
  const source = await readFile(new URL('../src/api/user.js', import.meta.url), 'utf8');

  assert.match(source, /service\.post\('\/token\/refresh\/'/);
  assert.doesNotMatch(source, /axios\.post\(/);
});
