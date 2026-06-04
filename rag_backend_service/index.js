const express = require('express');
const cors    = require('cors');
const { spawn } = require('child_process');
const path    = require('path');

const app    = express();
const PYTHON = '/Users/prachi/anaconda3/envs/llms/bin/python';
const GEN_PY = path.join(__dirname, 'generation.py');

app.use(cors());
app.use(express.json());

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

  py.stdout.on('data', (data) => {
    buffer += data.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop(); // keep incomplete line

    for (const line of lines) {
      if (line.startsWith('TOKEN:')) {
        const token = line.slice(6);
        res.write(`data: ${JSON.stringify({ token })}\n\n`);
      } else if (line.startsWith('ERROR:')) {
        const msg = line.slice(6);
        res.write(`data: ${JSON.stringify({ error: msg })}\n\n`);
      }
    }
  });

  py.stderr.on('data', (data) => {
    // Python model-loading logs go to stderr — ignore unless debugging
    // console.error('[py stderr]', data.toString());
  });

  py.on('close', () => {
    res.write(`data: ${JSON.stringify({ done: true })}\n\n`);
    res.end();
  });

  req.on('close', () => py.kill());
});

const PORT = 5001;
app.listen(PORT, () => console.log(`Backend running on http://localhost:${PORT}`));
