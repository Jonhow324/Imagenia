const api = (path, options) => fetch(`/api/imagenia${path}`, options);
const health = document.querySelector('#health');
const message = document.querySelector('#message');

api('/health').then((response) => response.json()).then((data) => {
  health.textContent = data.status === 'ok' ? '后端已连接' : '后端异常';
}).catch(() => { health.textContent = '离线 mock'; });

document.querySelector('#generate-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const response = await api('/jobs/generate', {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify({prompt: form.get('prompt'), size: form.get('size'), quality: form.get('quality')}),
  });
  const data = await response.json();
  message.textContent = response.ok ? `任务已创建：${data.job_id}` : data.error?.message || '提交失败';
});
