export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).send('Method not allowed');
  }

  const body = req.body;

  // Step 1: Handle Smartsheet verification challenge
  const challenge = body?.challenge;
  if (challenge) {
    return res.status(200)
      .setHeader('Smartsheet-Hook-Challenge', challenge)
      .send('');
  }

  // Step 2: Handle real events — extract row ID
  const events = body?.events || [];
  const rowId = events[0]?.rowId?.toString() || '';

  // Step 3: Trigger GitHub Actions
  await fetch(
    'https://api.github.com/repos/Vruddhi192/recipe-finder-on2cook/.github/workflows/sync-recipes.yml/dispatches',
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.GITHUB_PAT}`,
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: { row_id: rowId }
      })
    }
  );

  return res.status(200).json({ ok: true, rowId });
}
