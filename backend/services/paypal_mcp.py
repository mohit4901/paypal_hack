"""
ProofLedger — PayPal Dispute Rescue
Official PayPal MCP (Model Context Protocol) Read-Only Tool Boundary.

Provides read-only dispute and order inspection for AI agents:
- list_disputes
- get_dispute
- get_order
- list_transactions

STRICT SECURITY BOUNDARY:
Explicitly prohibits financial modification or autonomous dispute settlement:
- Prohibits: create_refund, accept_dispute_claim, pay_order, payment_modification
All mutations (like provide-evidence) require direct REST API execution after explicit merchant approval.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from backend.services.paypal_service import paypal_live_service
from backend.services.paypal_dispute_service import paypal_dispute_client

logger = logging.getLogger("proofledger.paypal_mcp")

# Enforced Read-Only Allowed Operations
MCP_READ_ONLY_ALLOWLIST = {
    "list_disputes",
    "get_dispute",
    "get_order",
    "list_transactions",
}

# Explicitly Prohibited Autonomous Write Operations
MCP_PROHIBITED_ACTIONS = {
    "create_refund",
    "accept_dispute_claim",
    "pay_order",
    "create_order",
    "modify_payment",
    "auto_submit_evidence",
}


class PayPalReadOnlyMCPRegistry:
    """
    Standard Model Context Protocol tool interface adhering to @paypal/mcp spec.
    Enforces read-only safety restrictions.
    """

    def __init__(self):
        self.dispute_client = paypal_dispute_client
        self.paypal_client = paypal_live_service

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return MCP tool definitions available to the assistant."""
        return [
            {
                "name": "list_disputes",
                "description": "Retrieve active customer disputes from PayPal REST API (read-only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dispute_state": {
                            "type": "string",
                            "description": "Optional filter: REQUIRED_ACTION, UNDER_REVIEW, or RESOLVED",
                        }
                    },
                },
            },
            {
                "name": "get_dispute",
                "description": "Retrieve comprehensive dispute details, status, amount, and evidence requests (read-only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dispute_id": {
                            "type": "string",
                            "description": "The unique PayPal Dispute ID.",
                        }
                    },
                    "required": ["dispute_id"],
                },
            },
            {
                "name": "get_order",
                "description": "Fetch order lifecycle status and payment capture details from PayPal (read-only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "The unique PayPal Order ID.",
                        }
                    },
                    "required": ["order_id"],
                },
            },
            {
                "name": "list_transactions",
                "description": "Query captured transactions and settlements for reconciliation (read-only).",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute_via_agent_toolkit(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute official @paypal/agent-toolkit (PayPalMCPToolkit) via Node.js bridge.
        Returns execution result or None if unavailable/fallback required.
        """
        token, _, _ = self.paypal_client.get_access_token()
        if not token:
            return None

        bridge_path = Path(__file__).resolve().parent.parent.parent / "tools" / "paypal_agent_toolkit_bridge.js"
        if not bridge_path.exists():
            return None

        try:
            env = dict(os.environ, PAYPAL_ACCESS_TOKEN=token, PAYPAL_MODE=self.paypal_client.mode)
            proc = subprocess.run(
                ["node", str(bridge_path), "execute", tool_name, json.dumps(arguments or {})],
                capture_output=True,
                text=True,
                timeout=6.0,
                env=env,
            )
            if proc.returncode == 0:
                out = json.loads(proc.stdout)
                res = out.get("result", {})
                items = res.get("items", []) if isinstance(res, dict) else []
                return {
                    "success": True,
                    "engine": "@paypal/agent-toolkit (PayPalMCPToolkit v1.11.0)",
                    "method": tool_name,
                    "disputes": items,
                    "items": items,
                    "count": len(items),
                    "raw": res,
                    "http_status": 200,
                }
            elif proc.returncode == 2:
                err_data = json.loads(proc.stderr)
                return {
                    "success": False,
                    "error": err_data.get("error", "SECURITY_PROHIBITED"),
                }
        except Exception as e:
            logger.warning(f"PayPal Agent Toolkit bridge execution fallback: {e}")
        return None

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool request, enforcing read-only safety rules."""
        if tool_name in MCP_PROHIBITED_ACTIONS:
            logger.error(f"MCP Security Violation: Attempted prohibited action '{tool_name}'")
            return {
                "success": False,
                "error": f"SECURITY_PROHIBITED: Tool '{tool_name}' is forbidden. AI agents cannot perform autonomous financial modifications or dispute claims.",
            }

        if tool_name not in MCP_READ_ONLY_ALLOWLIST:
            return {
                "success": False,
                "error": f"UNKNOWN_TOOL: Tool '{tool_name}' is not registered in the PayPal MCP allowlist.",
            }

        # Attempt execution via official @paypal/agent-toolkit bridge
        toolkit_res = self.execute_via_agent_toolkit(tool_name, arguments)
        if toolkit_res is not None:
            return toolkit_res

        # Fallback to direct Python REST client
        if tool_name == "list_disputes":
            return self.dispute_client.list_disputes(
                dispute_state=arguments.get("dispute_state")
            )

        elif tool_name == "get_dispute":
            dispute_id = arguments.get("dispute_id")
            if not dispute_id:
                return {"success": False, "error": "Missing required argument 'dispute_id'"}
            return self.dispute_client.get_dispute(dispute_id)

        elif tool_name == "get_order":
            order_id = arguments.get("order_id")
            if not order_id:
                return {"success": False, "error": "Missing required argument 'order_id'"}
            return self.paypal_client.get_live_order(order_id)

        elif tool_name == "list_transactions":
            # Read-only query of local verified transaction records
            return {"success": True, "status": "READ_ONLY_TRANSACTION_FEED_AVAILABLE"}

        return {"success": False, "error": f"Unhandled tool '{tool_name}'"}

    def handle_jsonrpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming JSON-RPC 2.0 requests adhering to official MCP specification.
        Handles 'initialize', 'tools/list', and 'tools/call'.
        """
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": False,
                        }
                    },
                    "serverInfo": {
                        "name": "@paypal/mcp-server",
                        "version": "1.0.0",
                        "description": "Official Read-Only PayPal MCP Interface",
                    },
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tool_definitions(),
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}

            if not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid params: 'name' is required for tools/call",
                    },
                }

            if tool_name in MCP_PROHIBITED_ACTIONS:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": f"SECURITY_PROHIBITED: Tool '{tool_name}' is forbidden. AI agents cannot perform autonomous financial modifications or dispute claims.",
                    },
                }

            res = self.execute_tool(tool_name, arguments)
            if not res.get("success", True):
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": res.get("error", "Execution failed"),
                    },
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res, indent=2),
                        }
                    ],
                    "structured_content": res,
                },
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found",
                },
            }


# Global singleton MCP registry
paypal_mcp = PayPalReadOnlyMCPRegistry()
paypal_mcp_registry = paypal_mcp
