// /api/share.js
// Receives anonymized governance metrics from CLI
// Stores them for research/aggregation

import { kv } from '@vercel/kv';

// Generate a random submission ID
function generateId() {
  return Math.random().toString(36).substring(2, 15);
}

// Validate the incoming data has required fields
function validatePayload(data) {
  const required = [
    'summary',
    'governance',
    'classification'
  ];

  for (const field of required) {
    if (!data[field]) {
      return { valid: false, error: `Missing required field: ${field}` };
    }
  }

  // Check governance has the key metric
  if (typeof data.governance.bash_acceptance_rate !== 'number') {
    return { valid: false, error: 'Missing bash_acceptance_rate' };
  }

  return { valid: true };
}

export default async function handler(req, res) {
  // Only accept POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  }

  try {
    const data = req.body;

    // Validate the payload
    const validation = validatePayload(data);
    if (!validation.valid) {
      return res.status(400).json({ error: validation.error });
    }

    // Generate a unique ID for this submission
    const submissionId = generateId();

    // Add metadata
    const record = {
      ...data,
      _meta: {
        submitted_at: new Date().toISOString(),
        version: data.version || 'unknown'
      }
    };

    // Store in Vercel KV
    // Key format: sub:{id}
    // TTL: none (keep forever for research)
    await kv.set(`sub:${submissionId}`, record);

    // Return success
    return res.status(200).json({
      success: true,
      message: 'Thanks for contributing to the research.',
      id: submissionId
    });

  } catch (error) {
    console.error('Share API error:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
