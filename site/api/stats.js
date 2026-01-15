// /api/stats.js
// Returns aggregate statistics from all submissions
// No individual data exposed - only averages and counts

import { kv } from '@vercel/kv';

export default async function handler(req, res) {
  // Only accept GET requests
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed. Use GET.' });
  }

  try {
    // Get all submission keys
    const keys = await kv.keys('sub:*');
    const totalSubmissions = keys.length;

    if (totalSubmissions === 0) {
      return res.status(200).json({
        total_submissions: 0,
        message: 'No data yet. Be the first to contribute!'
      });
    }

    // Fetch all submissions
    const submissions = await Promise.all(
      keys.map(key => kv.get(key))
    );

    // Calculate aggregates
    let bashRates = [];
    let patterns = {};
    let archetypes = {};

    for (const sub of submissions) {
      if (!sub) continue;

      // Collect bash acceptance rates
      if (sub.governance?.bash_acceptance_rate) {
        bashRates.push(sub.governance.bash_acceptance_rate);
      }

      // Count patterns
      if (sub.classification?.pattern) {
        const p = sub.classification.pattern;
        patterns[p] = (patterns[p] || 0) + 1;
      }

      // Count archetypes
      if (sub.classification?.archetype) {
        const a = sub.classification.archetype;
        archetypes[a] = (archetypes[a] || 0) + 1;
      }
    }

    // Calculate stats
    const avgBashRate = bashRates.length > 0
      ? bashRates.reduce((a, b) => a + b, 0) / bashRates.length
      : null;

    const minBashRate = bashRates.length > 0 ? Math.min(...bashRates) : null;
    const maxBashRate = bashRates.length > 0 ? Math.max(...bashRates) : null;

    return res.status(200).json({
      total_submissions: totalSubmissions,
      bash_acceptance: {
        average: avgBashRate ? Math.round(avgBashRate * 100) / 100 : null,
        min: minBashRate ? Math.round(minBashRate * 100) / 100 : null,
        max: maxBashRate ? Math.round(maxBashRate * 100) / 100 : null
      },
      pattern_distribution: patterns,
      archetype_distribution: archetypes,
      updated_at: new Date().toISOString()
    });

  } catch (error) {
    console.error('Stats API error:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
