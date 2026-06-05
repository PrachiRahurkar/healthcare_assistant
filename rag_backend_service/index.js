require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });

const express = require('express');
const cors    = require('cors');
const { spawn } = require('child_process');
const path    = require('path');

const app    = express();
const PYTHON = '/Users/prachi/anaconda3/envs/llms/bin/python';
const GEN_PY = path.join(__dirname, 'generation.py');

app.use(cors());
app.use(express.json());

app.use((err, req, res, next) => {
  if (err instanceof SyntaxError && 'body' in err) {
    return res.status(400).json({ error: 'Invalid JSON request body.' });
  }
  return next(err);
});

app.post('/ask', (req, res) => {
  const { plan_id, question } = req.body;

  if (!plan_id || !question) {
    return res.status(400).json({ error: 'plan_id and question are required.' });
  }

  // Server-Sent Events so the UI can stream tokens as they arrive
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  const py = spawn(PYTHON, [GEN_PY], {
    env: { ...process.env },
    cwd: __dirname,
  });

  py.stdin.write(JSON.stringify({ plan_id, question }));
  py.stdin.end();

  let buffer = '';
  let childClosed = false;
  let sentPayload = false;
  let stderr = '';

  const sendPayload = (payload) => {
    if (res.writableEnded) return;
    sentPayload = true;
    res.write(`data: ${JSON.stringify(payload)}\n\n`);
  };

  py.stdout.on('data', (data) => {
    buffer += data.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop(); // keep incomplete line

    for (const line of lines) {
      if (line.startsWith('TOKEN:')) {
        const token = line.slice(6);
        sendPayload({ token });
      } else if (line.startsWith('ERROR:')) {
        const msg = line.slice(6);
        sendPayload({ error: msg });
      }
    }
  });

  py.stderr.on('data', (data) => {
    stderr += data.toString();
  });

  py.on('error', (err) => {
    childClosed = true;
    sendPayload({ error: `Could not start Python pipeline: ${err.message}` });
    sendPayload({ done: true });
    res.end();
  });

  py.on('close', (code) => {
    childClosed = true;
    if (code !== 0 && !sentPayload) {
      const msg = stderr.trim() || `Python pipeline exited with code ${code}.`;
      sendPayload({ error: msg });
    }
    sendPayload({ done: true });
    res.end();
  });

  res.on('close', () => {
    if (!childClosed) py.kill();
  });
});

app.use((req, res) => {
  res.status(404).json({ error: `Route not found: ${req.method} ${req.originalUrl}` });
});

app.use((err, req, res, next) => {
  if (res.headersSent) {
    return next(err);
  }
  console.error(err);
  return res.status(500).json({ error: 'Internal server error.' });
});

const PORT = 5001;
app.listen(PORT, () => console.log(`Backend running on http://localhost:${PORT}`));
