#!/usr/bin/env node
/**
 * Telegram MCP Server
 *
 * Provides tools for Claude Code to send files and messages to Telegram.
 *
 * Tools:
 * - send_file: Send a file to Telegram chat
 * - send_message: Send a text message to Telegram chat
 * - send_plan: Create a .md file with plan and send it to Telegram
 *
 * Environment variables:
 * - TELEGRAM_TOKEN: Bot token from @BotFather (required)
 * - TELEGRAM_CHAT_ID: Default chat ID (optional, can be overridden per-call)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import * as fs from "fs";
import * as path from "path";

const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN;
const DEFAULT_CHAT_ID = process.env.TELEGRAM_CHAT_ID;

// Validate environment - only token is required
if (!TELEGRAM_TOKEN) {
  console.error("Error: TELEGRAM_TOKEN environment variable is required");
  process.exit(1);
}

/**
 * Resolve chat_id from parameter or environment
 */
function resolveChatId(paramChatId?: string): string | null {
  return paramChatId || DEFAULT_CHAT_ID || null;
}

/**
 * Send a document to Telegram using multipart/form-data
 */
async function sendDocument(
  chatId: string,
  filePath: string,
  caption?: string
): Promise<{ ok: boolean; description?: string }> {
  const fileBuffer = fs.readFileSync(filePath);
  const fileName = path.basename(filePath);

  const formData = new FormData();
  formData.append("chat_id", chatId);
  formData.append("document", new Blob([fileBuffer]), fileName);
  if (caption) {
    formData.append("caption", caption);
  }

  const response = await fetch(
    `https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendDocument`,
    { method: "POST", body: formData }
  );

  return response.json();
}

/**
 * Send a text message to Telegram
 */
async function sendMessage(
  chatId: string,
  text: string,
  parseMode: string = "HTML"
): Promise<{ ok: boolean; description?: string }> {
  const response = await fetch(
    `https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: text,
        parse_mode: parseMode,
      }),
    }
  );

  return response.json();
}

// Create MCP server
const server = new Server(
  {
    name: "telegram",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "send_file",
        description:
          "Send a file to Telegram chat. Use this when the user asks you to send them a file, export something, or share a document.",
        inputSchema: {
          type: "object",
          properties: {
            file_path: {
              type: "string",
              description: "Absolute path to the file to send",
            },
            caption: {
              type: "string",
              description: "Optional caption for the file (supports HTML)",
            },
            chat_id: {
              type: "string",
              description:
                "Telegram chat ID to send to. If not specified, uses default from environment.",
            },
          },
          required: ["file_path"],
        },
      },
      {
        name: "send_message",
        description:
          "Send a text message to Telegram chat. Use this for notifications, summaries, or when the user asks to be notified about something.",
        inputSchema: {
          type: "object",
          properties: {
            text: {
              type: "string",
              description: "Message text (supports HTML formatting)",
            },
            parse_mode: {
              type: "string",
              enum: ["HTML", "Markdown", "MarkdownV2"],
              description: "Parse mode for formatting (default: HTML)",
            },
            chat_id: {
              type: "string",
              description:
                "Telegram chat ID to send to. If not specified, uses default from environment.",
            },
          },
          required: ["text"],
        },
      },
      {
        name: "send_plan",
        description:
          "Create a plan document and send it as a .md file to Telegram. Use this when the user asks you to create a plan, roadmap, or detailed specification and send it to them.",
        inputSchema: {
          type: "object",
          properties: {
            title: {
              type: "string",
              description: "Plan title (will be used as filename and heading)",
            },
            content: {
              type: "string",
              description: "Plan content in Markdown format",
            },
            chat_id: {
              type: "string",
              description:
                "Telegram chat ID to send to. If not specified, uses default from environment.",
            },
          },
          required: ["title", "content"],
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "send_file": {
        const filePath = args?.file_path as string;
        const caption = args?.caption as string | undefined;
        const chatId = resolveChatId(args?.chat_id as string | undefined);

        if (!filePath) {
          return {
            content: [{ type: "text", text: "Error: file_path is required" }],
            isError: true,
          };
        }

        if (!chatId) {
          return {
            content: [
              {
                type: "text",
                text: "Error: chat_id is required (not provided and no default set)",
              },
            ],
            isError: true,
          };
        }

        if (!fs.existsSync(filePath)) {
          return {
            content: [
              { type: "text", text: `Error: File not found: ${filePath}` },
            ],
            isError: true,
          };
        }

        const result = await sendDocument(chatId, filePath, caption);

        return {
          content: [
            {
              type: "text",
              text: result.ok
                ? `✅ File sent: ${path.basename(filePath)}`
                : `❌ Error: ${result.description}`,
            },
          ],
          isError: !result.ok,
        };
      }

      case "send_message": {
        const text = args?.text as string;
        const parseMode = (args?.parse_mode as string) || "HTML";
        const chatId = resolveChatId(args?.chat_id as string | undefined);

        if (!text) {
          return {
            content: [{ type: "text", text: "Error: text is required" }],
            isError: true,
          };
        }

        if (!chatId) {
          return {
            content: [
              {
                type: "text",
                text: "Error: chat_id is required (not provided and no default set)",
              },
            ],
            isError: true,
          };
        }

        const result = await sendMessage(chatId, text, parseMode);

        return {
          content: [
            {
              type: "text",
              text: result.ok
                ? "✅ Message sent"
                : `❌ Error: ${result.description}`,
            },
          ],
          isError: !result.ok,
        };
      }

      case "send_plan": {
        const title = args?.title as string;
        const content = args?.content as string;
        const chatId = resolveChatId(args?.chat_id as string | undefined);

        if (!title || !content) {
          return {
            content: [
              { type: "text", text: "Error: title and content are required" },
            ],
            isError: true,
          };
        }

        if (!chatId) {
          return {
            content: [
              {
                type: "text",
                text: "Error: chat_id is required (not provided and no default set)",
              },
            ],
            isError: true,
          };
        }

        // Create temp file with sanitized filename
        const safeTitle = title.replace(/[^a-zA-Z0-9_\-\u0400-\u04FF]/g, "_");
        const fileName = `plan_${safeTitle}_${Date.now()}.md`;
        const tempPath = `/tmp/${fileName}`;

        // Write plan content
        const fullContent = `# ${title}\n\n${content}`;
        fs.writeFileSync(tempPath, fullContent, "utf-8");

        try {
          // Send to Telegram
          const result = await sendDocument(
            chatId,
            tempPath,
            `📋 План: ${title}`
          );

          return {
            content: [
              {
                type: "text",
                text: result.ok
                  ? `✅ Plan sent: ${fileName}`
                  : `❌ Error: ${result.description}`,
              },
            ],
            isError: !result.ok,
          };
        } finally {
          // Cleanup temp file
          try {
            fs.unlinkSync(tempPath);
          } catch {
            // Ignore cleanup errors
          }
        }
      }

      default:
        return {
          content: [{ type: "text", text: `Unknown tool: ${name}` }],
          isError: true,
        };
    }
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : String(error);
    return {
      content: [{ type: "text", text: `Error: ${errorMessage}` }],
      isError: true,
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // Log to stderr to not interfere with JSON-RPC on stdout
  console.error(
    `Telegram MCP server started (default chat_id: ${DEFAULT_CHAT_ID || "not set"})`
  );
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
