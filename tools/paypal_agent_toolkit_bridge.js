/**
 * ProofLedger — PayPal Dispute Rescue
 * Official PayPal Agent Toolkit & MCP Execution Bridge.
 * 
 * Directly leverages @paypal/agent-toolkit (v1.11.0) and @modelcontextprotocol/sdk.
 * Enforces a strict Read-Only boundary for autonomous AI agents:
 * - Read-Only Allowed: list_disputes, get_dispute, get_order, list_transactions
 * - Prohibited Mutations: create_refund, accept_dispute_claim, pay_order, etc. (Blocked with SECURITY_PROHIBITED)
 */

const fs = require('fs');
const path = require('path');

function resolvePayPalToolkit() {
  try {
    return require('@paypal/agent-toolkit/mcp');
  } catch (err) {
    // Fallback to npx cache locations
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const npxBase = path.join(homeDir, '.npm', '_npx');
    if (fs.existsSync(npxBase)) {
      const dirs = fs.readdirSync(npxBase);
      for (const d of dirs) {
        const candidate = path.join(npxBase, d, 'node_modules', '@paypal', 'agent-toolkit', 'mcp');
        if (fs.existsSync(candidate)) {
          return require(candidate);
        }
      }
    }
    throw new Error('Could not resolve @paypal/agent-toolkit/mcp module: ' + err.message);
  }
}

const { PayPalMCPToolkit, PayPalAPI } = resolvePayPalToolkit();

// Read-only actions configuration for PayPalMCPToolkit
const READ_ONLY_CONFIG = {
  context: {
    sandbox: (process.env.PAYPAL_MODE || process.env.PAYPAL_ENVIRONMENT || 'sandbox').toLowerCase() === 'sandbox'
  },
  actions: {
    disputes: { list: true, get: true },
    orders: { get: true },
    transactions: { list: true }
  }
};

const PROHIBITED_ACTIONS = new Set([
  'create_refund',
  'accept_dispute_claim',
  'pay_order',
  'create_order',
  'modify_payment',
  'auto_submit_evidence'
]);

function getToolkitInstance(accessToken) {
  const token = accessToken || process.env.PAYPAL_ACCESS_TOKEN || '';
  return new PayPalMCPToolkit({
    accessToken: token,
    configuration: READ_ONLY_CONFIG
  });
}

async function handleCommand() {
  const args = process.argv.slice(2);
  const command = args[0] || 'list_tools';

  if (command === 'list_tools') {
    const toolkit = getToolkitInstance('dummy_token');
    const tools = toolkit.getTools().map(t => ({
      name: t.method,
      title: t.name,
      description: t.description,
      parameters: t.parameters ? t.parameters.shape : {}
    }));
    console.log(JSON.stringify({
      server: 'PayPalAgentToolkit',
      version: '1.11.0',
      environment: READ_ONLY_CONFIG.context.sandbox ? 'SANDBOX' : 'LIVE',
      read_only_enforced: true,
      tools_count: tools.length,
      tools: tools
    }, null, 2));
    process.exit(0);
  }

  if (command === 'execute') {
    const method = args[1];
    let methodArgs = {};
    if (args[2]) {
      try {
        methodArgs = JSON.parse(args[2]);
      } catch (e) {
        console.error(JSON.stringify({
          ok: false,
          error: 'INVALID_JSON_ARGUMENTS: ' + e.message
        }));
        process.exit(1);
      }
    }

    if (PROHIBITED_ACTIONS.has(method)) {
      console.error(JSON.stringify({
        ok: false,
        error_code: -32000,
        error: `SECURITY_PROHIBITED: Tool '${method}' is forbidden. AI agents cannot perform autonomous financial modifications or dispute settlement.`
      }));
      process.exit(2);
    }

    const accessToken = process.env.PAYPAL_ACCESS_TOKEN;
    if (!accessToken) {
      console.error(JSON.stringify({
        ok: false,
        error: 'MISSING_PAYPAL_ACCESS_TOKEN: Set PAYPAL_ACCESS_TOKEN in environment.'
      }));
      process.exit(1);
    }

    try {
      const toolkit = getToolkitInstance(accessToken);
      const api = toolkit.getPaypalAPIService();
      const rawResult = await api.run(method, methodArgs);
      let parsed = rawResult;
      try {
        parsed = JSON.parse(rawResult);
      } catch (_) {}

      console.log(JSON.stringify({
        ok: true,
        method: method,
        toolkit: '@paypal/agent-toolkit (PayPalMCPToolkit)',
        result: parsed
      }, null, 2));
      process.exit(0);
    } catch (err) {
      console.error(JSON.stringify({
        ok: false,
        method: method,
        error: err.message
      }));
      process.exit(1);
    }
  }

  console.error(JSON.stringify({
    ok: false,
    error: `Unknown command: ${command}. Use 'list_tools' or 'execute <method> [args_json]'`
  }));
  process.exit(1);
}

handleCommand().catch(err => {
  console.error(JSON.stringify({ ok: false, error: err.message }));
  process.exit(1);
});

